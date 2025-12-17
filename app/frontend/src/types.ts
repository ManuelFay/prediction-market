export type MarketStatus = 'OPEN' | 'CLOSED' | 'PENDING' | 'RESOLVED' | 'INVALID';

export interface UserRead {
  id: number;
  name: string;
  balance: number;
}

export interface UserAuthRead extends UserRead {
  password: string;
}

export interface BetPreview {
  payout: number;
  probability: number;
}

export interface OddsPoint {
  timestamp: string;
  price_yes: number;
  price_no: number;
  side?: string | null;
  user_id?: number | null;
}

export interface MarketRead {
  id: number;
  question: string;
  description?: string | null;
  yes_meaning?: string | null;
  no_meaning?: string | null;
  resolution_source?: string | null;
  initial_prob_yes: number;
  liquidity_b: number;
  q_yes: number;
  q_no: number;
  status: MarketStatus;
  outcome?: string | null;
  created_at: string;
  event_time?: string | null;
  creator_id: number;
  creator_name?: string | null;
  price_yes: number;
  price_no: number;
  last_bet_at?: string | null;
  yes_preview: BetPreview;
  no_preview: BetPreview;
  total_pot: number;
  total_payout_yes: number;
  total_payout_no: number;
  creator_payout: number;
  is_deleted: boolean;
}

export interface BetRead {
  id: number;
  user_id: number;
  market_id: number;
  side: 'YES' | 'NO';
  shares: number;
  cost: number;
  placed_at: string;
  implied_odds: number;
}

export interface PayoutBreakdown {
  user_id: number;
  amount: number;
  entry_type: string;
  note?: string | null;
}

export interface MarketWithBets extends MarketRead {
  bets: BetRead[];
  odds_history: OddsPoint[];
  volume_yes: number;
  volume_no: number;
  payouts: PayoutBreakdown[];
}

export interface PositionRead {
  market_id: number;
  market_question: string;
  side: string;
  total_shares: number;
  total_stake: number;
  avg_odds: number;
  potential_payout: number;
  market_status: MarketStatus;
  market_outcome?: string | null;
}

export interface LedgerEntryRead {
  id: number;
  user_id: number;
  market_id?: number | null;
  amount: number;
  entry_type: string;
  created_at: string;
  note?: string | null;
}

export interface CommentRead {
  id: number;
  market_id: number;
  user_id: number;
  text: string;
  created_at: string;
  is_op: boolean;
}

export interface CommentPage {
  items: CommentRead[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface UserLoginPayload {
  name: string;
  password: string;
}

export interface MarketCreatePayload {
  question: string;
  description?: string;
  yes_meaning?: string;
  no_meaning?: string;
  resolution_source?: string;
  initial_prob_yes: number;
  event_time?: string;
}
