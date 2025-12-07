from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app import amm
from app.main import app, get_session
from app.models import Market


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
    response = client.post("/users", json={"name": name})
    assert response.status_code == 201
    return response.json()


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


def test_market_detail_includes_odds_history_and_volume(client: TestClient) -> None:
    user = create_user(client)
    market = create_market(client, user["id"])

    bet_resp = client.post(
        f"/markets/{market['id']}/bet?user_id={user['id']}", json={"side": "YES"}
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


def test_bet_rate_limit_enforced(client: TestClient) -> None:
    user = create_user(client)
    market = create_market(client, user["id"])

    first_bet = client.post(
        f"/markets/{market['id']}/bet?user_id={user['id']}", json={"side": "YES"}
    )
    assert first_bet.status_code == 201

    second_bet = client.post(
        f"/markets/{market['id']}/bet?user_id={user['id']}", json={"side": "NO"}
    )
    assert second_bet.status_code == 429


def test_resolve_market_pays_winners(client: TestClient) -> None:
    creator = create_user(client, "Creator")
    yes_bettor = create_user(client, "Yes Bettor")
    no_bettor = create_user(client, "No Bettor")
    market = create_market(client, creator["id"])

    bet_yes_resp = client.post(
        f"/markets/{market['id']}/bet?user_id={yes_bettor['id']}", json={"side": "YES"}
    )
    assert bet_yes_resp.status_code == 201
    bet_yes = bet_yes_resp.json()

    bet_no_resp = client.post(
        f"/markets/{market['id']}/bet?user_id={no_bettor['id']}", json={"side": "NO"}
    )
    if bet_no_resp.status_code == 429:
        with Session(client.app.state.test_engine) as session:
            market_row = session.get(Market, market["id"])
            market_row.last_bet_at = market_row.last_bet_at - timedelta(seconds=10)
            session.add(market_row)
            session.commit()
        bet_no_resp = client.post(
            f"/markets/{market['id']}/bet?user_id={no_bettor['id']}", json={"side": "NO"}
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
