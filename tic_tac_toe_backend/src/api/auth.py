import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer
from src.api import models, database

# Configuration via env
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'supersecretkey')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# PUBLIC_INTERFACE
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# PUBLIC_INTERFACE
def get_password_hash(password):
    return pwd_context.hash(password)

# PUBLIC_INTERFACE
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# PUBLIC_INTERFACE
def get_user_from_db(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

# PUBLIC_INTERFACE
def authenticate_user(db: Session, username: str, password: str):
    user = get_user_from_db(db, username)
    if user and verify_password(password, user.hashed_password):
        return user
    return None

# PUBLIC_INTERFACE
def get_current_user(db: Session = Depends(database.get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user_from_db(db, username=username)
    if user is None:
        raise credentials_exception
    return user
