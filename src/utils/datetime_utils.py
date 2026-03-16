from datetime import datetime, timezone


def utcnow() -> datetime:
    """Retorna datetime atual com timezone UTC."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """Retorna datetime UTC sem timezone — usar só onde o banco exige naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)