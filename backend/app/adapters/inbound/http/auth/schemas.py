from pydantic import BaseModel


class UserCredentials(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
