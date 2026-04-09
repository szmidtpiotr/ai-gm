from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

def now_utc():
    return datetime.now(timezone.utc)

class Game(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    system: str
    model: str
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: int = Field(index=True, foreign_key="game.id")
    role: str
    content: str
    created_at: datetime = Field(default_factory=now_utc)
