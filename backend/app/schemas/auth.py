"""Authentication request and response schemas."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class AuthUser(BaseModel):
    id: int
    username: str
    role: str
    status: str
    scenario_id: int | None = None
    scenario_code: str | None = None
    created_at: str
    updated_at: str


class AuthResponse(BaseModel):
    user: AuthUser
    expires_in: int
    csrf_token: str
