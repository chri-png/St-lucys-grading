import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext

# IMPORTANT: set a real SECRET_KEY environment variable before deploying.
# Anyone who has this key can forge login tokens.
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deploying")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(role: str, subject: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"role": role, "sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=401, detail="Your session has expired. Please log in again."
        )


def require_role(required_role: str):
    """FastAPI dependency: only allows requests with a valid token of this role."""

    def dependency(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
        payload = decode_token(credentials.credentials)
        if payload.get("role") != required_role:
            raise HTTPException(
                status_code=403, detail="You do not have permission to do that."
            )
        return payload

    return dependency
