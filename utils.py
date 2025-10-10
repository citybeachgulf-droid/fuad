from typing import Optional
import os
from random import randint
from datetime import datetime, timedelta
from flask import current_app
try:
    from twilio.rest import Client  # type: ignore
except Exception:  # pragma: no cover - optional dependency during local dev
    Client = None  # type: ignore


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


def generate_otp_code(length: int = 6) -> str:
    """Generate a numeric OTP of the requested length."""
    length = max(4, min(8, int(length)))
    start = 10 ** (length - 1)
    end = (10 ** length) - 1
    return str(randint(start, end))


def format_phone_e164(phone: str) -> Optional[str]:
    """Very light normalization to E.164 if user includes leading zeros/spaces.
    NOTE: In production prefer `phonenumbers` lib for robust parsing.
    """
    if not phone:
        return None
    digits = ''.join(ch for ch in phone if ch.isdigit() or ch == '+')
    if digits.startswith('00'):
        digits = '+' + digits[2:]
    if not digits.startswith('+'):
        # Assume Oman default country code +968 if none provided
        digits = '+968' + digits.lstrip('0')
    return digits


def send_sms_via_twilio(to_phone: str, message: str) -> bool:
    """Send SMS using Twilio credentials from config. Returns True on success."""
    app = current_app
    account_sid = app.config.get('TWILIO_ACCOUNT_SID')
    auth_token = app.config.get('TWILIO_AUTH_TOKEN')
    from_number = app.config.get('TWILIO_FROM_NUMBER')
    if not (account_sid and auth_token and from_number and Client):
        # Consider logging a warning in real setup
        return False
    try:
        client = Client(account_sid, auth_token)
        client.messages.create(
            body=message,
            from_=from_number,
            to=to_phone,
        )
        return True
    except Exception:
        return False

