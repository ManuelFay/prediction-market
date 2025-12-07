from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import MarketStatus


class OddsPoint(BaseModel):
    timestamp: datetime
    price_yes: float
    price_no: float
    side: Optional[str] = None
    user_id: Optional[int] = None


class UserCreate(BaseModel):
    name: str


class UserRead(BaseModel):
    id: int
    name: str
    balance: float

    class Config:
        from_attributes = True


class UserAuthRead(UserRead):
    password: str


class DepositRequest(BaseModel):
    amount: float = Field(..., gt=0)


class BetPreview(BaseModel):
    payout: float
    probability: float


class MarketCreate(BaseModel):
    question: str
    description: Optional[str] = None
    yes_meaning: Optional[str] = None
    no_meaning: Optional[str] = None
    resolution_source: Optional[str] = None
    initial_prob_yes: float = Field(..., gt=0, lt=1)
    liquidity_b: float = Field(5.0, gt=0)
    event_time: Optional[datetime] = None


class MarketRead(BaseModel):
    id: int
    question: str
    description: Optional[str]
    yes_meaning: Optional[str]
    no_meaning: Optional[str]
    resolution_source: Optional[str]
    initial_prob_yes: float
    liquidity_b: float
    q_yes: float
    q_no: float
    status: MarketStatus
    outcome: Optional[str]
    created_at: datetime
    event_time: Optional[datetime]
    creator_id: int
    creator_name: Optional[str]
    price_yes: float
    price_no: float
    last_bet_at: Optional[datetime]
    yes_preview: BetPreview
    no_preview: BetPreview
    total_pot: float
    total_payout_yes: float
    total_payout_no: float
    creator_payout: float

    class Config:
        from_attributes = True


class BetCreate(BaseModel):
    side: str
    password: str


class BetRead(BaseModel):
    id: int
    user_id: int
    market_id: int
    side: str
    shares: float
    cost: float
    placed_at: datetime
    implied_odds: float

    class Config:
        from_attributes = True


class ComplaintCreate(BaseModel):
    reason: str


class ResolutionRequest(BaseModel):
    outcome: str  # YES, NO, INVALID


class MarketWithBets(MarketRead):
    bets: list[BetRead]
    odds_history: list[OddsPoint]
    volume_yes: float
    volume_no: float
    payouts: list["PayoutBreakdown"]


class PositionRead(BaseModel):
    market_id: int
    market_question: str
    side: str
    total_shares: float
    total_stake: float
    avg_odds: float
    potential_payout: float
    market_status: MarketStatus
    market_outcome: Optional[str]


class LedgerEntryRead(BaseModel):
    id: int
    user_id: int
    market_id: Optional[int]
    amount: float
    entry_type: str
    created_at: datetime
    note: Optional[str]

    class Config:
        from_attributes = True


class PayoutBreakdown(BaseModel):
    user_id: int
    amount: float
    entry_type: str
    note: Optional[str]
