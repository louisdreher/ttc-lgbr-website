from pydantic import BaseModel


class UserCreate(BaseModel):
    email: str
    name: str
    password: str


class UserPublic(BaseModel):
    id: int
    email: str
    name: str
    is_active: bool
    roles: list[str]
