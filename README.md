# Prediction Market Specs
---

## 1. Concept

* A **friends-only prediction / betting app**.
* Everyone gets an **account with virtual 50€** (or points) to play with.
* Anyone can **create markets** and **bet 1€ at a time**.
* **Live betting is allowed** (during the event), and you *want* people to arbitrage information they have.
* **Odds are dynamic** (set by an AMM), but **each bet’s payoff is fixed at the time it’s placed**.
* The **market creator seeds liquidity** (10€) and implicitly acts as the “book”.

---

## 2. Users & Balances

* Each user:

  * Has an account balance (start at 50€).
  * Can:

    * Create markets (risking a 10€ seed each).
    * Place 1€ bets on open markets (max 1€ per 5 seconds per market).

* Balances are tracked via a **ledger/transactions** table:

  * `DEPOSIT_SEED`, `BET_DEBIT`, `PAYOUT`, `REFUND`, etc.

---

## 3. Market Lifecycle

Each **binary market** (YES/NO):

1. **CREATE**

   * Creator specifies:

     * Question, YES/NO meaning.
     * Event info (e.g. “PSG vs OM, full-time result YES = PSG wins”).
     * **Initial probability p₀** (their subjective odds).
     * Optional event start time (for info; you allow live betting anyway).
     * Resolution rules + source (“Use official score from X”).
   * System:

     * Debits **10€** from creator as **liquidity seed**.
     * Initializes an **AMM state** with:

       * Liquidity parameter **b**.
       * Initial share quantities `q_yes`, `q_no` such that:

         * AMM’s implied price p_yes = p₀.
         * The market has effectively a 10€ subsidy (implementation detail).

2. **OPEN**

   * Market is live.
   * Users can place **1€ bets** on YES or NO.
   * **At most one bet per market every 5 seconds** (rate-limiting in backend).

3. **CLOSED FOR NEW BETS**

   * Optional: you *can* decide to stop accepting bets at some time (e.g. after full-time whistle), but by design you’re okay with **live betting**.

4. **PENDING RESOLUTION**

   * Event outcome known; creator picks YES/NO/INVALID.
   * Short dispute window where bettors can **complain**.

5. **RESOLVED / INVALID**

   * If no complaints (or dispute resolved): finalize and pay out.
   * If market is INVALID: refund all stakes + seed proportionally.

---

## 4. Pricing: AMM (Cost-Function Market Maker)

Use a **cost-function AMM** (LMSR-style) for each binary market.

### 4.1 State

For each market:

* `q_yes`, `q_no`: total “YES shares” and “NO shares” sold by the AMM.
* `b`: liquidity parameter (controls how much prices move per 1€).
* Cost function:

[
C(q_\text{yes}, q_\text{no}) = b \cdot \ln\left(e^{q_\text{yes}/b} + e^{q_\text{no}/b}\right)
]

* **Instantaneous prices** (implied probabilities):

[
p_\text{yes} = \frac{e^{q_\text{yes}/b}}{e^{q_\text{yes}/b} + e^{q_\text{no}/b}} \quad,\quad
p_\text{no} = 1 - p_\text{yes}
]

These `p_yes`, `p_no` are what you convert into odds and show to users.

### 4.2 Initial seeding (creator’s 10€)

When a market is created:

* Creator provides 10€.
* System chooses `q_yes`, `q_no` and maybe `b` such that:

  * `p_yes = p₀` (creator’s chosen probability).
  * The AMM’s internal **“subsidy”** (the cost difference between current `C` and a neutral starting point) = 10€.

Implementation detail: solve one or two simple equations for `q_yes`, `q_no` (or fix `b` globally and solve for `q`s).

Intuition: their 10€ is used to **pre-load** liquidity so the first bets don’t swing price insanely.

---

## 5. Betting Mechanics (Fixed Stake, AMM Under the Hood)

### 5.1 User view

* Bet size is always **1€**.

* For each open market, the app shows:

  * Current implied probability: `p_yes`, `p_no`.
  * Decimal odds:

    * `odds_yes = 1 / p_yes`
    * `odds_no = 1 / p_no`

* When user presses “Bet 1€ on YES”:

  * They see:

    * “You’re betting 1€ on YES at odds X.xx. If YES wins, your maximum payoff is X.xx€.”

* Once confirmed:

  * Their **payout is fixed** (via the number of shares they get; see below).
  * Later price changes don’t affect this bet.

### 5.2 Under the hood: buying shares from the AMM

When user bets 1€ on YES:

1. Current state: `(q_yes, q_no)`.
2. You need to find **new state** `(q_yes', q_no)` such that:

[
C(q_\text{yes}', q_\text{no}) - C(q_\text{yes}, q_\text{no}) = 1 \text{€}
]

3. The user receives **Δq_yes = q_yes' - q_yes** YES-shares.

   * Each YES-share pays **1€** if YES happens, **0€** if NO.
4. Backend:

   * Debits 1€ from user balance.
   * Updates `q_yes = q_yes'`.
   * Stores bet:

     * `market_id`, `user_id`, `side=YES`, `shares=Δq_yes`, `cost=1€`, plus **display odds** at the time (for UI/history).

So:

* The **financial contract is fixed**: they own `Δq_yes` shares that pay out if YES.
* The **“odds” you show** is just:

[
\text{effective_odds} = \frac{\text{payout if YES}}{\text{stake}} = \frac{\Delta q_\text{yes} \cdot 1€}{1€}
]

For small b and small trades, this is roughly `1 / p_yes`. You can store and show that as the effective odds.

Same story for NO bets.

---

## 6. Resolution & Complaints

### 6.1 Resolution rules (per market)

On creation, the creator must define:

* Clear **YES/NO condition** ("YES if PSG wins after 90 minutes, excluding ET/penalties").
* **Source of truth** (e.g. official league website, specific app).
* Expected time when result is available.

### 6.2 Flow

1. After event is over, creator picks outcome: YES / NO / INVALID.
2. Market moves to **PENDING** for X hours (e.g. 12 or 24h).
3. Any bettor on that market can press **“Complain”** and provide a reason.
4. If **no complaints** by deadline:

   * Market becomes **RESOLVED** → payouts triggered.
5. If complaints exist:

   * Either:

     * Majority vote of involved bettors (excluding creator), or
     * A designated “referee” friend decides YES/NO/INVALID.
   * If outcome can’t be agreed on → mark **INVALID** and refund stakes.

---

## 7. Payouts & Risk

### 7.1 Payouts

When market is RESOLVED:

* If outcome is YES:

  * For each bet, the user gets: `shares_yes * 1€`.
  * NO-shares pay 0.
* If outcome is NO:

  * For each bet, the user gets: `shares_no * 1€`.
  * YES-shares pay 0.
* If INVALID:

  * Pro-rata or full refunds:

    * Simplest: just refund each bet’s original stake and return as much as possible of the seed.

### 7.2 Who bears risk?

* The **AMM (subsidized by the 10€ seed)** is the counterparty.
* The **market creator** is effectively funding that subsidy:

  * In bad scenarios (everyone well-informed, creator miscalibrated), their 10€ gets drained.
  * In other scenarios, they might profit if friends make bad bets.

You can add:

* **Max liability per market**: cap the total net loss the AMM can suffer (beyond the 10€ seed).
* Optionally show to the creator: “Max possible loss/gain right now”.

---

## 8. Operational Rules & Constraints

* **Max bet size**: 1€ per bet (hard cap).
* **Rate limiting**: one bet per market every **5 seconds** (global, not per user), to:

  * Avoid race conditions,
  * Reduce flash-exploitation of stale odds.
* **Live betting allowed**:

  * Users can keep betting as long as market is OPEN.
  * Odds will adapt via AMM every time a bet is placed.
* **Transparency**:

  * Show current probabilities, odds, and market depth (maybe graph of price over time).
  * Show to each user their:

    * Active positions (shares held),
    * Implied average odds,
    * PnL after markets resolve.
