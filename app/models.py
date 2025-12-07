from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship


class MarketStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    INVALID = "INVALID"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    balance: float = 50.0

    markets: list["Market"] = Relationship(back_populates="creator")
    bets: list["Bet"] = Relationship(back_populates="user")
    transactions: list["LedgerEntry"] = Relationship(back_populates="user")


class Market(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    question: str
    description: Optional[str] = None
    yes_meaning: Optional[str] = None
    no_meaning: Optional[str] = None
    resolution_source: Optional[str] = None
    initial_prob_yes: float
    liquidity_b: float
    q_yes: float
    q_no: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: MarketStatus = MarketStatus.OPEN
    outcome: Optional[str] = None
    event_time: Optional[datetime] = None
    creator_id: int = Field(foreign_key="user.id")
    last_bet_at: Optional[datetime] = None

    creator: User = Relationship(back_populates="markets")
    bets: list["Bet"] = Relationship(back_populates="market")
    complaints: list["Complaint"] = Relationship(back_populates="market")


class Bet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    market_id: int = Field(foreign_key="market.id")
    side: str  # YES or NO
    shares: float
    cost: float
    placed_at: datetime = Field(default_factory=datetime.utcnow)
    implied_odds: float

    user: User = Relationship(back_populates="bets")
    market: Market = Relationship(back_populates="bets")


class LedgerType(str, enum.Enum):
    DEPOSIT_SEED = "DEPOSIT_SEED"
    BET_DEBIT = "BET_DEBIT"
    PAYOUT = "PAYOUT"
    REFUND = "REFUND"
    STARTING_BALANCE = "STARTING_BALANCE"


class LedgerEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    market_id: Optional[int] = Field(default=None, foreign_key="market.id")
    amount: float
    entry_type: LedgerType
    created_at: datetime = Field(default_factory=datetime.utcnow)
    note: Optional[str] = None

    user: User = Relationship(back_populates="transactions")


class Complaint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    market_id: int = Field(foreign_key="market.id")
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    market: Market = Relationship(back_populates="complaints")
