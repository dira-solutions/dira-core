from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from fastapi import Depends
from jose import JWTError, jwt
from typing import Any
from datetime import datetime, timedelta
from tortoise.models import Model
from app.entity.user import PersonalAccessToken, User
from .form import UserLoginRequestForm

import bcrypt
from diracore.contracts.foundation.application import Application

class JWTAuthentication():
    def __init__(self, secret_key: str, algorithm: str, token_expire_minutes: int, user_model: Model):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expire_minutes = int(token_expire_minutes)
        self.user_model = user_model

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self
    
    def handle(self):  
        async def get_current_user(token = Depends(HTTPBearer())):
            try:
                payload = self.decode(token.credentials)
                user_id: str = payload.get("id")
                if user_id is None:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Could not validate credentials",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            except JWTError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user = await self.user_model.where_actual_token(token.credentials).get_or_none(id=user_id)
            if user is None:
                raise HTTPException(status_code=404, detail="User not found")
            return user      
        return get_current_user

    async def authenticate_user(self, form: UserLoginRequestForm) -> User:
        if form.username:
            user: User = await User.get_or_none(username=form.username)
        elif form.email:
            user: User = await User.get_or_none(email=form.email)
        is_password = bcrypt.checkpw(form.password.encode(), user.password.encode())
        if not user and not is_password:
            raise HTTPException(status_code=404, detail="Account not found. Please check your credentials and try again.")
        return user

    async def create_access_token(self, user_id, data: dict, name=None, type='bearer') -> PersonalAccessToken:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.token_expire_minutes)
        to_encode.update({"exp": expire})

        token_count = await PersonalAccessToken.filter(user_id=user_id).active().count()
        name = name if name else f"Token-{token_count}"

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        now = datetime.utcnow()
        token = await PersonalAccessToken.create(
            user_id=user_id,
            name=name,
            type=type,
            credentials=encoded_jwt,
            last_used_at=now,
            expires_at=now+timedelta(minutes=self.token_expire_minutes)
        )
        return token
    
    def decode(self, token: str):
        payload = jwt.decode(
            token=token, 
            key=self.secret_key, 
            algorithms=[self.algorithm]
        )
        return payload
