import pytest
from jwt import InvalidTokenError

from app.security.tokens import TokenType, create_token, decode_jwt_token


def test_decode_returns_payload_for_valid_token():
    assert decode_jwt_token(create_token(42, "hash"), TokenType.ACCESS)["sub"] == "42"


def test_decode_raises_jwt_error_not_http_exception_for_invalid_token():
    with pytest.raises(InvalidTokenError):
        decode_jwt_token("garbage", TokenType.ACCESS)
