from pydantic import BaseModel, EmailStr, Field, validator, model_validator

class UserLoginRequestForm(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str

    @model_validator(mode='after')
    def check_username_or_email(cls, values):
        if not values.username and not values.email:
            raise ValueError('You must fill in at least one of the fields: username or email')
        return values

    class Config:
        from_attributes = True
        # orm_mode = True

class UserRegisterRequestForm(BaseModel):
    username: str = Field(default=None, nullable=True, min_length=8)
    email: EmailStr
    password: str

    @validator('password')
    def password_requirements(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(char.isdigit() for char in v):
            raise ValueError('Password must contain at least one digit')
        if not any(char.isalpha() for char in v):
            raise ValueError('Password must contain at least one letter')
        return v