# Using the Friends Prediction Market

This guide walks through the basics of operating the demo prediction market as a user or market creator.

## Getting access
- Ask an admin for credentials to create users. Each new user starts with **50€** and a unique password.
- Logins for admin-only endpoints use HTTP Basic (`admin` / `admin` by default in local dev).

## Creating a market
1. Call `POST /markets?user_id=<yourId>` with a `MarketCreate` payload.
2. Set `initial_prob_yes` between **10% and 90%**; the system rejects anything outside that range.
3. A **10€ seed** is debited from your balance and locked into the AMM to fund early trades.
4. If your starting odds are far from 50%, the platform will automatically nudge `liquidity_b` higher to reduce volatility.

## Placing bets
- Bets are fixed at **1€** each and require your user password.
- **YES** bets are blocked once the live YES probability hits **90%** or above.
- **NO** bets are blocked once the live YES probability hits **10%** or below.
- The AMM enforces a loss cap: it will reject any bet that could make total winner payouts exceed the **10€ seed + all stakes so far**.

## Resolving markets
- Creators (or admins) resolve markets via `POST /markets/{id}/resolve` with outcomes `YES`, `NO`, or `INVALID`.
- Winners receive their stored shares as payouts; invalid markets refund all bets and return the seed to the creator.
- A payout ledger is available at `GET /users/{id}/ledger`.

## Frontend usage
- Serve the bundled UI with `uvicorn app.main:app --reload` and browse to `http://localhost:8000`.
- Market pages show current prices, odds history, volume per side, and any payouts once resolved.

## Tips
- For more stable prices, start markets near 50% or increase `liquidity_b` when creating the market.
- If a bet is rejected for exceeding the loss cap, wait for trades on the opposite side or increase liquidity before retrying.
