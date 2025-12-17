from __future__ import annotations

from datetime import datetime
from pathlib import Path
import secrets
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, or_
from sqlmodel import Session, select, delete

from . import amm
from .database import get_session, init_db
from .models import Bet, Comment, Complaint, LedgerEntry, LedgerType, Market, MarketStatus, User
from .schemas import (
    BetCreate,
    BetRead,
    BetPreview,
    ComplaintCreate,
    CommentCreate,
    CommentDeleteRequest,
    CommentPage,
    CommentRead,
    DepositRequest,
    LedgerEntryRead,
    MarketCreate,
    MarketRead,
    MarketWithBets,
    OddsPoint,
    PositionRead,
    ResolutionRequest,
    UserCreate,
    UserAuthRead,
    UserLogin,
    UserRead,
    PayoutBreakdown,
)

MARKET_SEED = 10.0
DEFAULT_LIQUIDITY_B = 5.0
PRICE_CLIP_LOW = 0.1
PRICE_CLIP_HIGH = 0.9
PRICE_EPSILON = 1e-6
COMMENT_MAX_LENGTH = 280

app = FastAPI(title="Friends Prediction Market", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBasic()
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
if FRONTEND_DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# Helpers

def require_admin(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    username_ok = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    password_ok = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin credentials required",
            headers={"WWW-Authenticate": "Basic"},
        )


def add_ledger_entry(session: Session, user_id: int, market_id: int | None, amount: float, entry_type: LedgerType, note: str | None = None) -> None:
    entry = LedgerEntry(user_id=user_id, market_id=market_id, amount=amount, entry_type=entry_type, note=note)
    session.add(entry)


def market_exposure(session: Session, market_id: int) -> tuple[float, float, float]:
    bets = session.exec(select(Bet).where(Bet.market_id == market_id)).all()
    total_yes_shares = sum(bet.shares for bet in bets if bet.side.upper() == "YES")
    total_no_shares = sum(bet.shares for bet in bets if bet.side.upper() == "NO")
    total_staked = sum(bet.cost for bet in bets)
    return total_yes_shares, total_no_shares, total_staked


def comment_read(comment: Comment, market: Optional[Market] = None, session: Optional[Session] = None) -> CommentRead:
    market_obj = market
    if not market_obj and session:
        market_obj = session.get(Market, comment.market_id)
    creator_id = market_obj.creator_id if market_obj else None
    return CommentRead(
        id=comment.id,
        market_id=comment.market_id,
        user_id=comment.user_id,
        text=comment.text,
        created_at=comment.created_at,
        is_op=creator_id is not None and comment.user_id == creator_id,
    )


@app.get("/", response_class=HTMLResponse)
def serve_frontend() -> HTMLResponse:
    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail="Frontend not built. Run npm run build in app/frontend.")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


# User endpoints


@app.post("/auth/login", response_model=UserAuthRead)
def authenticate_user(payload: UserLogin, session: Session = Depends(get_session)) -> User:
    user = session.exec(select(User).where(func.lower(User.name) == payload.name.lower())).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.password != user.password:
        raise HTTPException(status_code=403, detail="Invalid credentials")
    return user


@app.post("/users", response_model=UserAuthRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> User:
    user = User(name=payload.name)
    session.add(user)
    session.flush()
    add_ledger_entry(session, user.id, None, 50.0, LedgerType.STARTING_BALANCE, "Initial allocation")
    session.commit()
    session.refresh(user)
    return user


@app.get("/users", response_model=List[UserRead])
def list_users(session: Session = Depends(get_session)) -> List[User]:
    return session.exec(select(User)).all()


@app.get("/admin/users", response_model=List[UserAuthRead])
def list_users_with_passwords(
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> List[UserAuthRead]:
    return session.exec(select(User)).all()


@app.post("/reset", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def reset_state(session: Session = Depends(get_session), _: None = Depends(require_admin)) -> Response:
    session.exec(delete(LedgerEntry))
    session.exec(delete(Bet))
    session.exec(delete(Complaint))
    session.exec(delete(Comment))
    session.exec(delete(Market))
    session.exec(delete(User))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/users/{user_id}", response_model=UserRead)
def get_user(user_id: int, session: Session = Depends(get_session)) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.get("/users/{user_id}/ledger", response_model=List[LedgerEntryRead])
def user_ledger(user_id: int, session: Session = Depends(get_session)) -> List[LedgerEntry]:
    return session.exec(select(LedgerEntry).where(LedgerEntry.user_id == user_id).order_by(LedgerEntry.created_at)).all()


@app.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_user(user_id: int, session: Session = Depends(get_session), _: None = Depends(require_admin)) -> Response:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    created_markets = session.exec(select(Market).where(Market.creator_id == user_id)).all()
    if created_markets:
        raise HTTPException(status_code=400, detail="Delete or reassign the user's markets first")

    existing_bets = session.exec(select(Bet).where(Bet.user_id == user_id)).all()
    if existing_bets:
        raise HTTPException(status_code=400, detail="Cannot delete a user with existing bets")

    ledger_entries = session.exec(select(LedgerEntry).where(LedgerEntry.user_id == user_id)).all()
    for entry in ledger_entries:
        session.delete(entry)

    complaints = session.exec(select(Complaint).where(Complaint.user_id == user_id)).all()
    for complaint in complaints:
        session.delete(complaint)

    session.delete(user)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/users/{user_id}/deposit", response_model=UserRead)
def deposit(
    user_id: int,
    payload: DepositRequest,
    session: Session = Depends(get_session),
    _: None = Depends(require_admin),
) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.balance += payload.amount
    add_ledger_entry(session, user.id, None, payload.amount, LedgerType.STARTING_BALANCE, note="Manual top-up")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@app.get("/users/{user_id}/positions", response_model=List[PositionRead])
def user_positions(user_id: int, session: Session = Depends(get_session)) -> List[PositionRead]:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    bets = session.exec(select(Bet).where(Bet.user_id == user_id)).all()
    positions: dict[tuple[int, str], PositionRead] = {}
    for bet in bets:
        market = session.get(Market, bet.market_id)
        if not market:
            continue
        key = (bet.market_id, bet.side)
        if key not in positions:
            positions[key] = PositionRead(
                market_id=bet.market_id,
                market_question=market.question,
                side=bet.side,
                total_shares=0.0,
                total_stake=0.0,
                avg_odds=0.0,
                potential_payout=0.0,
                market_status=market.status,
                market_outcome=market.outcome,
            )
        pos = positions[key]
        pos.total_shares += bet.shares
        pos.total_stake += bet.cost
        pos.market_status = market.status
        pos.market_outcome = market.outcome
        pos.avg_odds = pos.total_shares / pos.total_stake if pos.total_stake else 0
        pos.potential_payout = pos.total_shares if market.status in {MarketStatus.OPEN, MarketStatus.PENDING, MarketStatus.CLOSED} else (
            pos.total_shares if market.outcome == bet.side else 0
        )

    return list(positions.values())


# Market endpoints


@app.post("/markets", response_model=MarketRead, status_code=status.HTTP_201_CREATED)
def create_market(payload: MarketCreate, user_id: int, session: Session = Depends(get_session)) -> Market:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < 10:
        raise HTTPException(status_code=400, detail="Insufficient balance for seed")

    if not 0.1 <= payload.initial_prob_yes <= 0.9:
        raise HTTPException(status_code=400, detail="Initial probability must be between 10% and 90%")

    liquidity_b = DEFAULT_LIQUIDITY_B

    q_yes, q_no = amm.initial_q_values(payload.initial_prob_yes, subsidy=MARKET_SEED, b=liquidity_b)

    market = Market(
        question=payload.question,
        description=payload.description,
        yes_meaning=payload.yes_meaning,
        no_meaning=payload.no_meaning,
        resolution_source=payload.resolution_source,
        initial_prob_yes=payload.initial_prob_yes,
        liquidity_b=liquidity_b,
        q_yes=q_yes,
        q_no=q_no,
        creator_id=user.id,
        event_time=payload.event_time,
        total_pot=MARKET_SEED,
    )
    user.balance -= MARKET_SEED
    session.add(market)
    session.flush()
    add_ledger_entry(
        session,
        user.id,
        market_id=market.id,
        amount=-MARKET_SEED,
        entry_type=LedgerType.DEPOSIT_SEED,
        note="Market seed",
    )
    session.commit()
    session.refresh(market)
    return market_read(market, session)


@app.get("/markets", response_model=List[MarketRead])
def list_markets(session: Session = Depends(get_session)) -> List[MarketRead]:
    visibility_filter = or_(Market.is_deleted.is_(False), Market.is_deleted.is_(None))
    markets = session.exec(select(Market).where(visibility_filter)).all()
    return [market_read(m, session) for m in markets]


@app.get("/markets/{market_id}", response_model=MarketWithBets)
def get_market(market_id: int, session: Session = Depends(get_session)) -> MarketWithBets:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    market_data = market_read(market, session)
    bets = session.exec(select(Bet).where(Bet.market_id == market_id)).all()
    odds_history = compute_odds_history(market, bets)
    volume_yes = sum(b.cost for b in bets if b.side.upper() == "YES")
    volume_no = sum(b.cost for b in bets if b.side.upper() == "NO")
    return MarketWithBets(
        **market_data.dict(),
        bets=bets,
        odds_history=odds_history,
        volume_yes=volume_yes,
        volume_no=volume_no,
        payouts=payout_breakdown(session, market),
    )


@app.post("/markets/{market_id}/bet", response_model=BetRead, status_code=status.HTTP_201_CREATED)
def place_bet(market_id: int, payload: BetCreate, user_id: int, session: Session = Depends(get_session)) -> Bet:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.is_deleted:
        raise HTTPException(status_code=400, detail="Market has been deleted")
    if market.status != MarketStatus.OPEN:
        raise HTTPException(status_code=400, detail="Market not open")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.password != user.password:
        raise HTTPException(status_code=403, detail="Invalid password")
    if user.balance < 1:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    side = payload.side.upper()
    if side not in {"YES", "NO"}:
        raise HTTPException(status_code=400, detail="Side must be YES or NO")

    price_yes = amm.price_yes(market.q_yes, market.q_no, market.liquidity_b)
    if side == "YES" and price_yes >= PRICE_CLIP_HIGH - PRICE_EPSILON:
        raise HTTPException(status_code=400, detail="YES betting disabled at or above 90% probability")
    if side == "NO" and price_yes <= PRICE_CLIP_LOW + PRICE_EPSILON:
        raise HTTPException(status_code=400, detail="NO betting disabled at or below 10% probability")

    new_q_yes, new_q_no = amm.shares_for_cost(1.0, side, market.q_yes, market.q_no, market.liquidity_b)
    delta_yes = new_q_yes - market.q_yes
    delta_no = new_q_no - market.q_no

    yes_shares, no_shares, total_staked = market_exposure(session, market.id)
    projected_yes = yes_shares + (delta_yes if side == "YES" else 0)
    projected_no = no_shares + (delta_no if side == "NO" else 0)
    pot_with_new_bet = MARKET_SEED + total_staked + 1.0
    if max(projected_yes, projected_no) > pot_with_new_bet:
        raise HTTPException(
            status_code=400,
            detail="Bet would exceed the creator's capped loss; try again later or increase liquidity.",
        )

    market.q_yes, market.q_no = new_q_yes, new_q_no
    market.last_bet_at = datetime.utcnow()

    user.balance -= 1
    add_ledger_entry(session, user.id, market_id=market.id, amount=-1, entry_type=LedgerType.BET_DEBIT, note=f"Bet on {side}")

    shares = delta_yes if side == "YES" else delta_no
    price_yes = amm.price_yes(new_q_yes, new_q_no, market.liquidity_b)
    probability = price_yes if side == "YES" else 1 - price_yes
    bet = Bet(user_id=user.id, market_id=market.id, side=side, shares=shares, cost=1.0, implied_odds=probability)
    session.add(bet)
    session.add(market)
    session.add(user)
    session.commit()
    session.refresh(bet)
    return bet


@app.post("/markets/{market_id}/complain", status_code=status.HTTP_201_CREATED)
def add_complaint(market_id: int, payload: ComplaintCreate, user_id: int, session: Session = Depends(get_session)) -> Complaint:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.status not in {MarketStatus.PENDING}:
        raise HTTPException(status_code=400, detail="Complaints allowed only during pending resolution")
    complaint = Complaint(user_id=user_id, market_id=market_id, reason=payload.reason)
    session.add(complaint)
    session.commit()
    session.refresh(complaint)
    return complaint


@app.get("/markets/{market_id}/comments", response_model=CommentPage)
def list_comments(
    market_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    session: Session = Depends(get_session),
) -> CommentPage:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    stmt = (
        select(Comment)
        .where(Comment.market_id == market_id, Comment.is_deleted.is_(False))
        .order_by(Comment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size + 1)
    )
    comments = session.exec(stmt).all()
    has_more = len(comments) > page_size
    items = comments[:page_size]

    return CommentPage(
        items=[comment_read(c, market=market) for c in items],
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@app.post("/markets/{market_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(
    market_id: int,
    payload: CommentCreate,
    user_id: int,
    session: Session = Depends(get_session),
) -> CommentRead:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.is_deleted:
        raise HTTPException(status_code=400, detail="Market has been deleted")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.password != user.password:
        raise HTTPException(status_code=403, detail="Invalid password")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment cannot be empty")
    if len(text) > COMMENT_MAX_LENGTH:
        raise HTTPException(status_code=400, detail=f"Comment exceeds {COMMENT_MAX_LENGTH} characters")

    comment = Comment(user_id=user.id, market_id=market.id, text=text)
    session.add(comment)
    session.commit()
    session.refresh(comment)
    return comment_read(comment, market=market)


@app.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_comment(
    comment_id: int,
    user_id: int,
    payload: CommentDeleteRequest,
    session: Session = Depends(get_session),
) -> Response:
    comment = session.get(Comment, comment_id)
    if not comment or comment.is_deleted:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != user_id:
        raise HTTPException(status_code=403, detail="Only the author can delete this comment")

    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.password != user.password:
        raise HTTPException(status_code=403, detail="Invalid password")

    comment.is_deleted = True
    comment.deleted_at = datetime.utcnow()
    session.add(comment)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/markets/{market_id}/resolve", response_model=MarketRead)
def resolve_market(market_id: int, payload: ResolutionRequest, session: Session = Depends(get_session)) -> MarketRead:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.status in {MarketStatus.RESOLVED, MarketStatus.INVALID}:
        raise HTTPException(status_code=400, detail="Market already resolved")
    outcome = payload.outcome.upper()
    if outcome not in {"YES", "NO", "INVALID"}:
        raise HTTPException(status_code=400, detail="Invalid outcome")

    if outcome == "INVALID":
        refund_invalid_market(session, market)
        market.total_payout_yes = 0.0
        market.total_payout_no = 0.0
        market.creator_payout = 0.0
        market.total_pot = 0.0
    else:
        pay_winners(session, market, outcome)
    market.status = MarketStatus.RESOLVED if outcome != "INVALID" else MarketStatus.INVALID
    market.outcome = outcome
    session.add(market)
    session.commit()
    session.refresh(market)
    return market_read(market, session)


@app.delete("/markets/{market_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_market(market_id: int, user_id: int, session: Session = Depends(get_session)) -> Response:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this market")

    market.status = MarketStatus.CLOSED
    market.is_deleted = True
    session.add(market)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Business logic helpers


def market_read(market: Market, session: Optional[Session] = None) -> MarketRead:
    price = amm.price_yes(market.q_yes, market.q_no, market.liquidity_b)
    yes_payout, yes_probability = compute_bet_preview(market, "YES")
    no_payout, no_probability = compute_bet_preview(market, "NO")
    creator_name = None
    if session:
        creator = session.get(User, market.creator_id)
        creator_name = creator.name if creator else None
    elif market.creator:
        creator_name = market.creator.name

    return MarketRead(
        id=market.id,
        question=market.question,
        description=market.description,
        yes_meaning=market.yes_meaning,
        no_meaning=market.no_meaning,
        resolution_source=market.resolution_source,
        initial_prob_yes=market.initial_prob_yes,
        liquidity_b=market.liquidity_b,
        q_yes=market.q_yes,
        q_no=market.q_no,
        status=market.status,
        outcome=market.outcome,
        created_at=market.created_at,
        event_time=market.event_time,
        creator_id=market.creator_id,
        price_yes=price,
        price_no=1 - price,
        last_bet_at=market.last_bet_at,
        yes_preview=BetPreview(payout=yes_payout, probability=yes_probability),
        no_preview=BetPreview(payout=no_payout, probability=no_probability),
        total_pot=market.total_pot,
        total_payout_yes=market.total_payout_yes,
        total_payout_no=market.total_payout_no,
        creator_payout=market.creator_payout,
        creator_name=creator_name,
        is_deleted=market.is_deleted,
    )


def compute_odds_history(market: Market, bets: list[Bet]) -> list[OddsPoint]:
    q_yes, q_no = amm.initial_q_values(market.initial_prob_yes, subsidy=MARKET_SEED, b=market.liquidity_b)
    history: list[OddsPoint] = []

    initial_price = amm.price_yes(q_yes, q_no, market.liquidity_b)
    history.append(
        OddsPoint(timestamp=market.created_at, price_yes=initial_price, price_no=1 - initial_price, side=None, user_id=None)
    )

    for bet in sorted(bets, key=lambda b: b.placed_at):
        q_yes, q_no = amm.shares_for_cost(bet.cost, bet.side, q_yes, q_no, market.liquidity_b)
        price = amm.price_yes(q_yes, q_no, market.liquidity_b)
        history.append(OddsPoint(timestamp=bet.placed_at, price_yes=price, price_no=1 - price, side=bet.side, user_id=bet.user_id))

    return history


def compute_bet_preview(market: Market, side: str) -> tuple[float, float]:
    new_q_yes, new_q_no = amm.shares_for_cost(1.0, side, market.q_yes, market.q_no, market.liquidity_b)
    delta_yes = new_q_yes - market.q_yes
    delta_no = new_q_no - market.q_no
    price_yes = amm.price_yes(new_q_yes, new_q_no, market.liquidity_b)
    if side == "YES":
        return delta_yes, price_yes
    return delta_no, 1 - price_yes


def pay_winners(session: Session, market: Market, outcome: str) -> None:
    bets = session.exec(select(Bet).where(Bet.market_id == market.id)).all()
    total_bets = sum(bet.cost for bet in bets)
    market.total_pot = MARKET_SEED + total_bets

    total_winner_payout = 0.0
    for bet in bets:
        if bet.side == outcome:
            payout = bet.shares
            total_winner_payout += payout
            user = session.get(User, bet.user_id)
            if user:
                user.balance += payout
                add_ledger_entry(session, user.id, market.id, payout, LedgerType.PAYOUT, note="Winner payout")
                session.add(user)

    market.total_payout_yes = total_winner_payout if outcome == "YES" else 0.0
    market.total_payout_no = total_winner_payout if outcome == "NO" else 0.0

    creator = session.get(User, market.creator_id)
    creator_payout = market.total_pot - total_winner_payout
    market.creator_payout = creator_payout
    if creator:
        creator.balance += creator_payout
        add_ledger_entry(
            session,
            creator.id,
            market.id,
            creator_payout,
            LedgerType.CREATOR_PAYOUT,
            note="Creator settlement",
        )
        session.add(creator)


def refund_invalid_market(session: Session, market: Market) -> None:
    bets = session.exec(select(Bet).where(Bet.market_id == market.id)).all()
    for bet in bets:
        user = session.get(User, bet.user_id)
        if user:
            user.balance += bet.cost
            add_ledger_entry(session, user.id, market.id, bet.cost, LedgerType.REFUND, note="Invalid market refund")
            session.add(user)
    # Return the seed to the creator when possible
    creator = session.get(User, market.creator_id)
    if creator:
        creator.balance += MARKET_SEED
        add_ledger_entry(session, creator.id, market.id, MARKET_SEED, LedgerType.REFUND, note="Seed returned")
        session.add(creator)


def payout_breakdown(session: Session, market: Market) -> list[PayoutBreakdown]:
    entries = session.exec(
        select(LedgerEntry).where(
            LedgerEntry.market_id == market.id,
            LedgerEntry.entry_type.in_([LedgerType.PAYOUT, LedgerType.CREATOR_PAYOUT, LedgerType.REFUND]),
        )
    ).all()
    return [
        PayoutBreakdown(user_id=entry.user_id, amount=entry.amount, entry_type=entry.entry_type, note=entry.note)
        for entry in entries
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
