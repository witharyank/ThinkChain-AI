def calculate_burn(expenses=None, revenue=None, cash=0):
    """
    Burn-rate logic:
    - If explicit burn/expenses is provided, use it directly (do not subtract revenue).
    - If expenses is missing, derive a conservative fallback from expenses-revenue.
    """
    if expenses is not None:
        monthly_burn = float(expenses)
    else:
        exp_val = float(expenses or 0)
        rev_val = float(revenue or 0)
        monthly_burn = max(exp_val - rev_val, 0)

    runway = float(cash or 0) / monthly_burn if monthly_burn > 0 else 0
    return {
        "monthly_burn": monthly_burn,
        "runway_months": runway,
    }
