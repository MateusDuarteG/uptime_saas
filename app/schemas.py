from pydantic import BaseModel, EmailStr
import uuid

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    tenant_id: uuid.UUID
    is_active: bool = True

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    tenant_id: uuid.UUID
    is_active: bool

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: str | None = None