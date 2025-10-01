def calculate_max_loan(income, annual_rate, years, max_ratio):
    """
    Calculate the maximum principal (loan amount) a client can take given
    a maximum affordable monthly payment derived from income and max_ratio.

    Args:
        income (float): Monthly income
        annual_rate (float): Annual interest rate in percent, e.g., 6.0
        years (int): Loan term in years
        max_ratio (float): Maximum payment to income ratio (e.g., 0.4)

    Returns:
        tuple[float, float]: (P, max_payment) where P is maximum principal and
        max_payment is the allowed monthly payment.
    """
    # Provided formula with a guard for zero interest
    r = (annual_rate / 100.0) / 12.0
    n = int(years) * 12
    max_payment = float(income) * float(max_ratio)

    if n <= 0:
        return 0.0, max_payment

    if r == 0:
        P = max_payment * n
    else:
        numerator = (1 + r) ** n - 1
        denominator = r * (1 + r) ** n
        if denominator == 0:
            P = 0.0
        else:
            P = max_payment * (numerator / denominator)

    return P, max_payment

