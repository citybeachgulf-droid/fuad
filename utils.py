from typing import Optional
import os
from urllib.parse import urlparse
from random import randint
from datetime import datetime, timedelta
from flask import current_app
try:
    from twilio.rest import Client  # type: ignore
except Exception:  # pragma: no cover - optional dependency during local dev
    Client = None  # type: ignore

# Optional: B2 via S3 API (boto3)
try:
    import boto3  # type: ignore
    from botocore.client import Config as BotoConfig  # type: ignore
    _HAS_BOTO3 = True
except Exception:  # pragma: no cover - optional dependency
    boto3 = None  # type: ignore
    BotoConfig = None  # type: ignore
    _HAS_BOTO3 = False


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


# -------------------------------
# Storage helpers (Backblaze B2 via S3, with local fallback)
# -------------------------------

def _is_external_url(value: Optional[str]) -> bool:
    if not value:
        return False
    v = str(value).strip().lower()
    return v.startswith('http://') or v.startswith('https://')


def _b2_is_configured(app) -> bool:
    return bool(
        getattr(app.config, 'get', None) and
        app.config.get('B2_S3_ENDPOINT') and
        app.config.get('B2_S3_ACCESS_KEY_ID') and
        app.config.get('B2_S3_SECRET_ACCESS_KEY') and
        app.config.get('B2_S3_BUCKET') and
        _HAS_BOTO3
    )


def _get_b2_s3_client(app):
    if not _b2_is_configured(app):
        return None
    try:
        session = boto3.session.Session()
        client = session.client(
            's3',
            endpoint_url=app.config.get('B2_S3_ENDPOINT'),
            aws_access_key_id=app.config.get('B2_S3_ACCESS_KEY_ID'),
            aws_secret_access_key=app.config.get('B2_S3_SECRET_ACCESS_KEY'),
            config=BotoConfig(signature_version='s3v4'),
        )
        return client
    except Exception:
        return None


def _build_b2_public_url(app, key: str) -> Optional[str]:
    key = key.lstrip('/')
    base = app.config.get('B2_PUBLIC_URL_BASE')
    if base:
        return f"{base.rstrip('/')}/{key}"
    # Fallback to path-style on the S3 endpoint (works on many setups for public buckets)
    endpoint = app.config.get('B2_S3_ENDPOINT')
    bucket = app.config.get('B2_S3_BUCKET')
    if endpoint and bucket:
        return f"{endpoint.rstrip('/')}/{bucket}/{key}"
    return None


def store_file_and_get_url(file_storage, *, key: str, local_abs_dir: str, filename: str) -> str:
    """Try uploading the given FileStorage to Backblaze B2 (S3 API). On success,
    returns a public URL. If B2 is not configured or upload fails, saves locally
    under the provided absolute directory and returns the relative path within
    the Flask static directory (e.g., 'uploads/...').

    Args:
        file_storage: Werkzeug FileStorage
        key: desired object key in the bucket, e.g., 'requests/req_123/file.pdf'
        local_abs_dir: absolute directory path under app.static_folder to save fallback
        filename: target filename to use for local save

    Returns:
        str: URL (https://...) if uploaded to B2, else relative path inside 'static/'
    """
    from flask import current_app
    app = current_app

    # Attempt B2 upload first if configured
    client = _get_b2_s3_client(app)
    if client is not None:
        try:
            content_type = getattr(file_storage, 'mimetype', None) or 'application/octet-stream'
            fileobj = file_storage.stream if hasattr(file_storage, 'stream') else file_storage
            client.upload_fileobj(
                Fileobj=fileobj,
                Bucket=app.config.get('B2_S3_BUCKET'),
                Key=key,
                ExtraArgs={'ACL': 'public-read', 'ContentType': content_type}
            )
            url = _build_b2_public_url(app, key)
            if url:
                return url
        except Exception:
            # Fallback to local save on any error
            pass

    # Local fallback
    try:
        os.makedirs(local_abs_dir, exist_ok=True)
        abs_path = os.path.join(local_abs_dir, filename)
        file_storage.save(abs_path)
        # derive relative path inside static folder
        static_root = os.path.join(app.root_path, 'static')
        rel_path = os.path.relpath(abs_path, static_root).replace('\\', '/')
        return rel_path
    except Exception:
        # As a last resort, return an empty string so callers can handle error messages
        return ''

