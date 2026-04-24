import jwt
import structlog
from typing import Optional

log = structlog.get_logger()

def validate_access_token(token_string: str, secret: str) -> Optional[str]:
    """
    Verifies the JWT token and returns the subject (user ID).
    Equivalent to the Go implementation.
    """
    try:
        # Decode the token, verifying the signature with the secret and HMAC (HS256)
        decoded = jwt.decode(
            token_string, 
            secret, 
            algorithms=["HS256"], 
            options={"verify_signature": True}
        )
        
        # Ensure the type claim exists and equals "access"
        token_type = decoded.get("type")
        if token_type != "access":
            log.warning("invalid_token_type", token_type=token_type)
            return None
            
        # Ensure the sub claim exists
        sub = decoded.get("sub")
        if not sub:
            log.warning("missing_sub_claim")
            return None
            
        return sub
    except jwt.PyJWTError as e:
        log.warning("jwt_validation_failed", error=str(e))
        return None
