import datetime
import jwt
from typing import Optional

def create_access_token(sub: str, secret: str, expires_delta: int) -> str:
    iat = datetime.datetime.now(datetime.timezone.utc)
    exp = iat + datetime.timedelta(minutes=expires_delta)
    payload = {
        "sub": sub,
        "type": "access",
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp())
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def create_refresh_token(sub: str, secret: str, expires_delta: int) -> str:
    iat = datetime.datetime.now(datetime.timezone.utc)
    exp = iat + datetime.timedelta(minutes=expires_delta)
    payload = {
        "sub": sub,
        "type": "refresh",
        "iat": int(iat.timestamp()),
        "exp": int(exp.timestamp())
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def verify_refresh_token(token_string: str, secret: str) -> Optional[str]:
    try:
        decoded = jwt.decode(token_string, secret, algorithms=["HS256"])
        if decoded.get("type") != "refresh":
            return None
        return decoded.get("sub")
    except jwt.PyJWTError:
        return None
