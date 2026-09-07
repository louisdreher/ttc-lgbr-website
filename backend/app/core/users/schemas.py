from sqlmodel import SQLModel

class UserCreate(SQLModel):
    email: str
    name: str
    password: str

class UserPublic(SQLModel):
    id: int
    email: str
    name: str
    is_active: bool
    roles: list[str]