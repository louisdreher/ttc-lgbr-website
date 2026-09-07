from sqlmodel import SQLModel

class UserCredentials(SQLModel):
    email: str
    password: str

class Token(SQLModel):
    access_token: str
    token_type: str