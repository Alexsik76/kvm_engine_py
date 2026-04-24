import jwt
import structlog

log = structlog.get_logger()

def validate_access_token(token_string: str, secret: str) -> str | None:
    """Verifies the JWT token and returns the subject (user ID)."""
    try:
        decoded = jwt.decode(token_string, secret, algorithms=["HS256"])

        if decoded.get("type") != "access":
            log.warning("invalid_token_type", token_type=decoded.get("type"))
            return None

        sub = decoded.get("sub")
        if sub is None:
            log.warning("missing_sub_claim")
            return None

        return sub
    except jwt.PyJWTError as e:
        log.warning("jwt_validation_failed", error=str(e))
        return None
