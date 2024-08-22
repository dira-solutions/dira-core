from .form import *
from app.entity.user import User
from app.entity.personal_access_token import PersonalAccessToken

from fastapi import HTTPException
from diracore.support.http.auth.middleware import JWTAuthentication
from diracore.support.http.auth.resource import *
from diracore.main import app
from tortoise.expressions import Q

import random
import bcrypt

class AuthenticationController:
    async def login(request_form: UserLoginRequestForm):
        jwt: JWTAuthentication = app.make(JWTAuthentication)

        user: User = await jwt.authenticate_user(request_form)

        personal_token: PersonalAccessToken = await jwt.create_access_token(user.id, data={"sub": user.username, "id": user.id})

        return {
            'meta': MetaResource(
                code=200, 
                status=MetaStatus.SUCCESS, 
                message='Quote fetched successfully.'
            ),
            'data': {
                'user': UserResource(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                ),
                'access_token': AccessTokenResource(
                    credentials=personal_token.credentials,
                    type=personal_token.name,
                    expires_in=personal_token.expires_at.strftime("%d/%m/%Y, %H:%M:%S")
                )
            }
        }

    async def register(request_form: UserRegisterRequestForm):
        user_exists = await User.filter(Q(username=request_form.username) | Q(email=request_form.email)).exists()
        if user_exists:
            raise HTTPException(status_code=400, detail="Username or Email already exists")

        user = await User.create(
            username=request_form.username or f"User-{random.randint(1, 99999):04d}",
            email=request_form.email,
            password=request_form.password
        )

        jwt: JWTAuthentication = app.make(JWTAuthentication)
        personal_token = await jwt.create_access_token(user.id, data={
            "sub": user.username, 
            "id": user.id
        })

        return {
            'meta': MetaResource(
                code=200, 
                status=MetaStatus.SUCCESS, 
                message='User created successfully!'
            ),
            'data': {
                'user': UserResource(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                ),
                'access_token': AccessTokenResource(
                    credentials=personal_token.credentials,
                    type=personal_token.name,
                    expires_in=personal_token.expires_at.strftime("%d/%m/%Y, %H:%M:%S")
                )
            }
        }

    async def logout(request_form: UserLoginRequestForm):
        jwt: JWTAuthentication = app.make(JWTAuthentication)
        user: User = await jwt.authenticate_user(request_form)
        tokens = await PersonalAccessToken.filter(user_id=user.id).delete()

        return {
            'meta': MetaResource(
                message='User created successfully!'
            ),
            'data': {
                'user': UserResource(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                ),
                'deleted_tokens': tokens
            }
        }