import hashlib
import hmac

from passlib.context import CryptContext

from app.core.config import settings

bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def password_fingerprint(password_hash: str) -> str:
    """HMAC do hash da senha: muda quando a senha muda e não revela o hash."""
    return hmac.new(
        settings.SECRET_KEY.encode(), password_hash.encode(), hashlib.sha256
    ).hexdigest()[:32]
