from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)  # bcrypt's own 72-byte ceiling


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True  # allows UserOut.model_validate(user_orm_object)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
