import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app import amm
from app.main import MARKET_SEED, app, get_session


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    app.state.test_engine = engine

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_session, None)
    app.state.test_engine = None


def create_user(client: TestClient, name: str = "Alice") -> dict:
    response = client.post("/users", json={"name": name}, auth=("admin", "admin"))
    assert response.status_code == 201
    return response.json()


def test_auth_login_requires_correct_password(client: TestClient) -> None:
    user = create_user(client)

    bad_login = client.post(
        "/auth/login", json={"name": user["name"], "password": "wrong"}
    )
    assert bad_login.status_code == 403

    good_login = client.post(
        "/auth/login", json={"name": user["name"], "password": user["password"]}
    )
    assert good_login.status_code == 200
    assert good_login.json()["id"] == user["id"]


def test_create_user_requires_admin(client: TestClient) -> None:
    response = client.post("/users", json={"name": "NoAdmin"})
    assert response.status_code == 401


def create_market(client: TestClient, creator_id: int) -> dict:
    payload = {
        "question": "Will it rain tomorrow?",
        "description": "Test market",
        "yes_meaning": "Yes",
        "no_meaning": "No",
        "resolution_source": "Weather API",
        "initial_prob_yes": 0.5,
        "liquidity_b": 5.0,
    }
    response = client.post(f"/markets?user_id={creator_id}", json=payload)
    assert response.status_code == 201
    return response.json()


def create_market_with_prob(client: TestClient, creator_id: int, prob_yes: float) -> dict:
    payload = {
        "question": "Probability guard test?",
        "description": "",
        "yes_meaning": "Yes",
        "no_meaning": "No",
        "resolution_source": "",
        "initial_prob_yes": prob_yes,
        "liquidity_b": 5.0,
    }
    response = client.post(f"/markets?user_id={creator_id}", json=payload)
    assert response.status_code == 201
    return response.json()


def test_market_detail_includes_odds_history_and_volume(client: TestClient) -> None:
    user = create_user(client)
    market = create_market(client, user["id"])

    bet_resp = client.post(
        f"/markets/{market['id']}/bet?user_id={user['id']}",
        json={"side": "YES", "password": user["password"]},
    )
    assert bet_resp.status_code == 201

    detail_resp = client.get(f"/markets/{market['id']}")
    assert detail_resp.status_code == 200
    market_detail = detail_resp.json()

    assert market_detail["volume_yes"] == pytest.approx(1.0)
    assert market_detail["volume_no"] == pytest.approx(0.0)
    assert len(market_detail["odds_history"]) == 2
    assert market_detail["odds_history"][-1]["side"] == "YES"
    assert market_detail["odds_history"][-1]["user_id"] == user["id"]


def test_multiple_bets_allowed_without_delay(client: TestClient) -> None:
    user = create_user(client)
    market = create_market(client, user["id"])

    first_bet = client.post(
        f"/markets/{market['id']}/bet?user_id={user['id']}",
        json={"side": "YES", "password": user["password"]},
    )
    assert first_bet.status_code == 201

    second_bet = client.post(
        f"/markets/{market['id']}/bet?user_id={user['id']}",
        json={"side": "NO", "password": user["password"]},
    )
    assert second_bet.status_code == 201


def test_probability_guards_block_extreme_sides(client: TestClient) -> None:
    user = create_user(client)
    high_prob_market = create_market_with_prob(client, user["id"], 0.9)
    low_prob_market = create_market_with_prob(client, user["id"], 0.1)

    yes_blocked = client.post(
        f"/markets/{high_prob_market['id']}/bet?user_id={user['id']}",
        json={"side": "YES", "password": user["password"]},
    )
    assert yes_blocked.status_code == 400

    no_allowed = client.post(
        f"/markets/{high_prob_market['id']}/bet?user_id={user['id']}",
        json={"side": "NO", "password": user["password"]},
    )
    assert no_allowed.status_code == 201

    no_blocked = client.post(
        f"/markets/{low_prob_market['id']}/bet?user_id={user['id']}",
        json={"side": "NO", "password": user["password"]},
    )
    assert no_blocked.status_code == 400

    yes_allowed = client.post(
        f"/markets/{low_prob_market['id']}/bet?user_id={user['id']}",
        json={"side": "YES", "password": user["password"]},
    )
    assert yes_allowed.status_code == 201


def test_market_creation_rejects_out_of_range_probabilities(client: TestClient) -> None:
    user = create_user(client)

    too_high = client.post(
        f"/markets?user_id={user['id']}",
        json={
            "question": "Out of range?",
            "initial_prob_yes": 0.95,
            "liquidity_b": 5.0,
        },
    )
    assert too_high.status_code == 422

    too_low = client.post(
        f"/markets?user_id={user['id']}",
        json={
            "question": "Out of range?",
            "initial_prob_yes": 0.05,
            "liquidity_b": 5.0,
        },
    )
    assert too_low.status_code == 422


def test_creator_loss_is_capped_by_seed(client: TestClient) -> None:
    user = create_user(client)

    market_resp = client.post(
        f"/markets?user_id={user['id']}",
        json={
            "question": "Will the cap trigger?",
            "initial_prob_yes": 0.1,
            "liquidity_b": 0.5,
        },
    )
    assert market_resp.status_code == 201
    market = market_resp.json()

    failure_resp = None
    for _ in range(20):
        bet_resp = client.post(
            f"/markets/{market['id']}/bet?user_id={user['id']}",
            json={"side": "YES", "password": user["password"]},
        )
        if bet_resp.status_code != 201:
            failure_resp = bet_resp
            break

    assert failure_resp is not None
    assert failure_resp.status_code == 400

    market_detail = client.get(f"/markets/{market['id']}").json()
    yes_shares = sum(bet["shares"] for bet in market_detail["bets"] if bet["side"] == "YES")
    pot_with_bets = MARKET_SEED + len(market_detail["bets"])
    assert yes_shares <= pot_with_bets + 1e-6


def test_resolve_market_pays_winners(client: TestClient) -> None:
    creator = create_user(client, "Creator")
    yes_bettor = create_user(client, "Yes Bettor")
    no_bettor = create_user(client, "No Bettor")
    market = create_market(client, creator["id"])

    bet_yes_resp = client.post(
        f"/markets/{market['id']}/bet?user_id={yes_bettor['id']}",
        json={"side": "YES", "password": yes_bettor["password"]},
    )
    assert bet_yes_resp.status_code == 201
    bet_yes = bet_yes_resp.json()

    bet_no_resp = client.post(
        f"/markets/{market['id']}/bet?user_id={no_bettor['id']}",
        json={"side": "NO", "password": no_bettor["password"]},
    )
    assert bet_no_resp.status_code == 201

    resolve_resp = client.post(
        f"/markets/{market['id']}/resolve", json={"outcome": "YES"}
    )
    assert resolve_resp.status_code == 200

    yes_user_resp = client.get(f"/users/{yes_bettor['id']}")
    assert yes_user_resp.status_code == 200
    yes_user = yes_user_resp.json()

    expected_balance = 50.0 - bet_yes["cost"] + bet_yes["shares"]
    assert yes_user["balance"] == pytest.approx(expected_balance)

    no_user_resp = client.get(f"/users/{no_bettor['id']}")
    assert no_user_resp.status_code == 200
    no_user = no_user_resp.json()
    assert no_user["balance"] == pytest.approx(50.0 - bet_no_resp.json()["cost"])

    market_detail = client.get(f"/markets/{market['id']}").json()
    assert market_detail["status"] == "RESOLVED"
    assert market_detail["outcome"] == "YES"

    # Verify the payout helper returns the expected share amount for a YES bet
    init_q_yes, init_q_no = amm.initial_q_values(0.5, subsidy=10.0, b=5.0)
    new_q_yes, _ = amm.shares_for_cost(1.0, "YES", init_q_yes, init_q_no, 5.0)
    expected_shares = new_q_yes - init_q_yes
    assert bet_yes["shares"] == pytest.approx(expected_shares)


def test_random_bets_zero_sum_and_payout_breakdown(client: TestClient) -> None:
    random.seed(1234)
    users = [create_user(client, f"User {idx}") for idx in range(4)]
    creator = users[0]
    market = create_market(client, creator["id"])
    password_map = {u["id"]: u["password"] for u in users}

    def place_or_wait(user_id: int, side: str) -> None:
        client.post(
            f"/markets/{market['id']}/bet?user_id={user_id}",
            json={"side": side, "password": password_map[user_id]},
        )

    bettors = [u["id"] for u in users]
    for _ in range(20):
        place_or_wait(random.choice(bettors), random.choice(["YES", "NO"]))

    outcome = random.choice(["YES", "NO"])
    resolve_resp = client.post(f"/markets/{market['id']}/resolve", json={"outcome": outcome})
    assert resolve_resp.status_code == 200

    resolved_market = client.get(f"/markets/{market['id']}").json()
    pot = resolved_market["total_pot"]
    total_payout = resolved_market["total_payout_yes"] + resolved_market["total_payout_no"]
    creator_payout = resolved_market["creator_payout"]
    assert pot == pytest.approx(total_payout + creator_payout)
    assert resolved_market["payouts"], "Payout breakdown should be populated"

    all_users = client.get("/users").json()
    total_balance = sum(u["balance"] for u in all_users)
    assert total_balance == pytest.approx(50.0 * len(all_users))


def test_reset_endpoint_clears_state(client: TestClient) -> None:
    user = create_user(client, "Temp")
    market = create_market(client, user["id"])
    assert market["id"]

    reset_resp = client.post("/reset", auth=("admin", "admin"))
    assert reset_resp.status_code == 204

    users_after = client.get("/users")
    assert users_after.status_code == 200
    assert users_after.json() == []


def test_admin_can_delete_user_without_activity(client: TestClient) -> None:
    user = create_user(client, "ToRemove")

    blocked = client.delete(f"/users/{user['id']}")
    assert blocked.status_code == 401

    allowed = client.delete(f"/users/{user['id']}", auth=("admin", "admin"))
    assert allowed.status_code == 204

    missing = client.get(f"/users/{user['id']}")
    assert missing.status_code == 404
