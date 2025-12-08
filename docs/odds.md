# Odds calculation and evolution

This system uses a **Logarithmic Market Scoring Rule (LMSR)** automated market maker. Prices are derived from the outstanding share inventory (``q_yes`` and ``q_no``) and a liquidity parameter ``b``.

## Initialisation

When a market is created, the initial share quantities are seeded so that the starting probability matches the requested ``initial_prob_yes`` while embedding the creator's subsidy ``S`` (``MARKET_SEED``). The liquidity parameter is fixed at ``b = 5`` for every market; it is not adjusted for skewed probabilities or user input.

- Base inventories: ``q_yes = b * ln(p)`` and ``q_no = b * ln(1 - p)`` where ``p`` is the initial yes probability.
- The subsidy is injected by shifting both inventories equally: ``q_yes' = q_yes + S`` and ``q_no' = q_no + S``. This keeps the initial price unchanged while increasing the cost function by ``S``.

## Price formula

At any point the instantaneous yes-price is given by the LMSR closed form:

``price_yes = exp(q_yes / b) / (exp(q_yes / b) + exp(q_no / b))``
price_no is simply ``1 - price_yes``.

## Buying shares

A unit bet of size ``c`` increases the LMSR cost from ``C(q_yes, q_no)`` to ``C(q_yes + Δ_yes, q_no + Δ_no)`` where ``C(q_yes, q_no) = b * ln(exp(q_yes / b) + exp(q_no / b))``.

- For a YES bet we solve for ``Δ_yes`` so that ``C(q_yes + Δ_yes, q_no) - C(q_yes, q_no) = c``.
- For a NO bet we solve for ``Δ_no`` in ``C(q_yes, q_no + Δ_no) - C(q_yes, q_no) = c``.
- The bet mints ``Δ_yes`` (or ``Δ_no``) shares; implied odds for the bettor are taken from the post-trade price of their side.

The implementation performs a bounded binary search to find ``Δ`` that matches the target cost increase.

## Clipping and safety guards

Several guardrails prevent impossible or loss-heavy states:

- **Probability clip on creation:** ``initial_prob_yes`` must be within ``[0.1, 0.9]``.
- **Trade-side clip:** betting YES is blocked once ``price_yes >= 0.9``; betting NO is blocked once ``price_yes <= 0.1``. This keeps trades away from near-certain outcomes.
- **Creator loss cap:** before accepting a bet we ensure the larger of total YES/NO shares would not exceed the funded pot (seed + prior stake + new stake). If it would, the trade is rejected to cap creator downside at the subsidy amount.

## State updates

After a valid bet, balances and ledgers record the 1-credit stake, inventories ``q_yes``/``q_no`` are updated with the computed deltas, and ``last_bet_at`` tracks recent activity. The resulting prices feed into previews for subsequent traders.
