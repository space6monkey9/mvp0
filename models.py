from sqlmodel import Field, SQLModel, Relationship
import datetime
from typing import List
import uuid

print("models.py file is being executed!")

class User(SQLModel, table=True):
    bribes: List["Bribe"] = Relationship(back_populates="user")
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, max_length=20, unique=True)

class Bribe(SQLModel, table=True):
    user: User = Relationship(back_populates="bribes")
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ofcl_name: str | None = None
    dept: str
    bribe_amt: int
    pin_code: str | None = None
    state_ut: str
    district: str
    descr: str = Field(max_length= 3000)
    doi: datetime.date | None = None
    evidence: bytes | None = None
    bribe_id: str | None = None 
    user_id: int = Field(foreign_key="user.id")


