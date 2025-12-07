from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from . import amm
from .database import get_session, init_db
from .models import Bet, Complaint, LedgerEntry, LedgerType, Market, MarketStatus, User
from .schemas import (
    BetCreate,
    BetRead,
    ComplaintCreate,
    LedgerEntryRead,
    MarketCreate,
    MarketRead,
    MarketWithBets,
    ResolutionRequest,
    UserCreate,
    UserRead,
)

app = FastAPI(title="Friends Prediction Market", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()


# Helpers

def add_ledger_entry(session: Session, user_id: int, market_id: int | None, amount: float, entry_type: LedgerType, note: str | None = None) -> None:
    entry = LedgerEntry(user_id=user_id, market_id=market_id, amount=amount, entry_type=entry_type, note=note)
    session.add(entry)


# User endpoints


@app.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, session: Session = Depends(get_session)) -> User:
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


@app.get("/users/{user_id}/ledger", response_model=List[LedgerEntryRead])
def user_ledger(user_id: int, session: Session = Depends(get_session)) -> List[LedgerEntry]:
    return session.exec(select(LedgerEntry).where(LedgerEntry.user_id == user_id).order_by(LedgerEntry.created_at)).all()


# Market endpoints


@app.post("/markets", response_model=MarketRead, status_code=status.HTTP_201_CREATED)
def create_market(payload: MarketCreate, user_id: int, session: Session = Depends(get_session)) -> Market:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < 10:
        raise HTTPException(status_code=400, detail="Insufficient balance for seed")

    q_yes, q_no = amm.initial_q_values(payload.initial_prob_yes, subsidy=10.0, b=payload.liquidity_b)

    market = Market(
        question=payload.question,
        description=payload.description,
        yes_meaning=payload.yes_meaning,
        no_meaning=payload.no_meaning,
        resolution_source=payload.resolution_source,
        initial_prob_yes=payload.initial_prob_yes,
        liquidity_b=payload.liquidity_b,
        q_yes=q_yes,
        q_no=q_no,
        creator_id=user.id,
        event_time=payload.event_time,
    )
    user.balance -= 10
    add_ledger_entry(session, user.id, market_id=None, amount=-10, entry_type=LedgerType.DEPOSIT_SEED, note="Market seed")
    session.add(market)
    session.commit()
    session.refresh(market)
    return market_read(market)


@app.get("/markets", response_model=List[MarketRead])
def list_markets(session: Session = Depends(get_session)) -> List[MarketRead]:
    markets = session.exec(select(Market)).all()
    return [market_read(m) for m in markets]


@app.get("/markets/{market_id}", response_model=MarketWithBets)
def get_market(market_id: int, session: Session = Depends(get_session)) -> MarketWithBets:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    market_data = market_read(market)
    bets = session.exec(select(Bet).where(Bet.market_id == market_id)).all()
    market_data.bets = bets
    return market_data


@app.post("/markets/{market_id}/bet", response_model=BetRead, status_code=status.HTTP_201_CREATED)
def place_bet(market_id: int, payload: BetCreate, user_id: int, session: Session = Depends(get_session)) -> Bet:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    if market.status != MarketStatus.OPEN:
        raise HTTPException(status_code=400, detail="Market not open")
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.balance < 1:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Rate limiting per market
    if market.last_bet_at and datetime.utcnow() - market.last_bet_at < timedelta(seconds=5):
        raise HTTPException(status_code=429, detail="Betting too quickly on this market")

    side = payload.side.upper()
    if side not in {"YES", "NO"}:
        raise HTTPException(status_code=400, detail="Side must be YES or NO")

    new_q_yes, new_q_no = amm.shares_for_cost(1.0, side, market.q_yes, market.q_no, market.liquidity_b)
    delta_yes = new_q_yes - market.q_yes
    delta_no = new_q_no - market.q_no

    market.q_yes, market.q_no = new_q_yes, new_q_no
    market.last_bet_at = datetime.utcnow()

    user.balance -= 1
    add_ledger_entry(session, user.id, market_id=market.id, amount=-1, entry_type=LedgerType.BET_DEBIT, note=f"Bet on {side}")

    shares = delta_yes if side == "YES" else delta_no
    odds = shares / 1.0
    bet = Bet(user_id=user.id, market_id=market.id, side=side, shares=shares, cost=1.0, implied_odds=odds)
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


@app.post("/markets/{market_id}/resolve", response_model=MarketRead)
def resolve_market(market_id: int, payload: ResolutionRequest, session: Session = Depends(get_session)) -> MarketRead:
    market = session.get(Market, market_id)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    outcome = payload.outcome.upper()
    if outcome not in {"YES", "NO", "INVALID"}:
        raise HTTPException(status_code=400, detail="Invalid outcome")

    if outcome == "INVALID":
        refund_invalid_market(session, market)
    else:
        pay_winners(session, market, outcome)
    market.status = MarketStatus.RESOLVED if outcome != "INVALID" else MarketStatus.INVALID
    market.outcome = outcome
    session.add(market)
    session.commit()
    session.refresh(market)
    return market_read(market)


# Business logic helpers


def market_read(market: Market) -> MarketRead:
    price = amm.price_yes(market.q_yes, market.q_no, market.liquidity_b)
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
    )


def pay_winners(session: Session, market: Market, outcome: str) -> None:
    bets = session.exec(select(Bet).where(Bet.market_id == market.id)).all()
    for bet in bets:
        if bet.side == outcome:
            payout = bet.shares * 1.0
            user = session.get(User, bet.user_id)
            if user:
                user.balance += payout
                add_ledger_entry(session, user.id, market.id, payout, LedgerType.PAYOUT, note="Market payout")
                session.add(user)


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
        creator.balance += 10
        add_ledger_entry(session, creator.id, market.id, 10, LedgerType.REFUND, note="Seed returned")
        session.add(creator)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
