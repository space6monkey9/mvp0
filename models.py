from sqlmodel import Field, SQLModel, Relationship, JSON, Column
import datetime
from typing import List, Optional
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
    evidence_urls: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    bribe_id: str | None = None
    user_id: int = Field(foreign_key="user.id")


