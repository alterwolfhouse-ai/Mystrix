from __future__ import annotations

from pydantic import BaseModel


class SignupReq(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginReq(BaseModel):
    email: str
    password: str


class FavReq(BaseModel):
    symbol: str


class SuggestReq(BaseModel):
    text: str
