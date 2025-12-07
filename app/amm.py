from __future__ import annotations

import math
from typing import Literal


def cost(q_yes: float, q_no: float, b: float) -> float:
    return b * math.log(math.exp(q_yes / b) + math.exp(q_no / b))


def price_yes(q_yes: float, q_no: float, b: float) -> float:
    exp_yes = math.exp(q_yes / b)
    exp_no = math.exp(q_no / b)
    return exp_yes / (exp_yes + exp_no)


def initial_q_values(p_yes: float, subsidy: float, b: float) -> tuple[float, float]:
    if not 0 < p_yes < 1:
        raise ValueError("Initial probability must be between 0 and 1")

    base_q_yes = b * math.log(p_yes)
    base_q_no = b * math.log(1 - p_yes)
    # Shift both quantities by the subsidy; this keeps prices unchanged while
    # increasing the AMM cost by the subsidy amount.
    return base_q_yes + subsidy, base_q_no + subsidy


def shares_for_cost(
    amount: float,
    side: Literal["YES", "NO"],
    q_yes: float,
    q_no: float,
    b: float,
    *,
    tolerance: float = 1e-9,
    max_iter: int = 200,
) -> tuple[float, float]:
    if amount <= 0:
        raise ValueError("Trade amount must be positive")

    target = cost(q_yes, q_no, b) + amount

    def new_cost(delta: float) -> float:
        if side == "YES":
            return cost(q_yes + delta, q_no, b)
        return cost(q_yes, q_no + delta, b)

    low, high = 0.0, b * 50
    while new_cost(high) < target:
        high *= 2
        if high > 1e9:
            raise RuntimeError("Failed to bracket the root for trade computation")

    for _ in range(max_iter):
        mid = (low + high) / 2
        current = new_cost(mid)
        if abs(current - target) < tolerance:
            return (
                (q_yes + mid if side == "YES" else q_yes),
                (q_no if side == "YES" else q_no + mid),
            )
        if current < target:
            low = mid
        else:
            high = mid
    raise RuntimeError("Trade computation did not converge")
