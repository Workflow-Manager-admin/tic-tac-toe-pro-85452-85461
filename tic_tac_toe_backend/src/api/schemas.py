from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# PUBLIC_INTERFACE
class UserCreate(BaseModel):
    """Schema for registering a new user."""
    username: str = Field(..., max_length=32)
    password: str = Field(..., min_length=6)

# PUBLIC_INTERFACE
class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
class Token(BaseModel):
    """Schema for returned JWT tokens."""
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

# PUBLIC_INTERFACE
class GameCreate(BaseModel):
    type: str = Field(..., description="Type of game (single|multi)")

# PUBLIC_INTERFACE
class MoveCreate(BaseModel):
    x: int
    y: int

# PUBLIC_INTERFACE
class MoveResponse(BaseModel):
    x: int
    y: int
    symbol: str
    user_id: int
    turn_number: int
    timestamp: datetime

    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
class GameResponse(BaseModel):
    id: int
    type: str
    player_x: Optional[str]
    player_o: Optional[str]
    winner: Optional[str]
    is_active: bool
    moves: List[MoveResponse]

    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
class LeaderboardEntryResponse(BaseModel):
    username: str
    wins: int
    losses: int
    ties: int

    class Config:
        orm_mode = True

# PUBLIC_INTERFACE
class HistoryResponse(BaseModel):
    games: List[GameResponse]
