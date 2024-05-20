from pydantic import BaseModel

from enum import Enum

class MetaStatus(Enum):
    SUCCESS='success'

class MetaResource(BaseModel):
    code: int = 200
    status: MetaStatus|str = MetaStatus.SUCCESS
    message: str

class AccessTokenResource(BaseModel):
    credentials: str
    type: str
    expires_in: str

class UserResource(BaseModel):
    id: int
    username: str
    email: str

