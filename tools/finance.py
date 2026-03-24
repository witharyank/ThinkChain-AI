def calculate_burn(expenses, revenue, cash):
    burn = expenses - revenue
    runway = cash / burn if burn > 0 else 0
    return {
        "monthly_burn": burn,
        "runway_months": runway
    }
