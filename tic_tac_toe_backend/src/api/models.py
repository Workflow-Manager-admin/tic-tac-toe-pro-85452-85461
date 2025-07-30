from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship, declarative_base
import enum

Base = declarative_base()

class GameType(enum.Enum):
    SINGLE = "single"
    MULTI = "multi"

# PUBLIC_INTERFACE
class User(Base):
    """User model representing players of the game."""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(32), unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    games = relationship("Game", back_populates="player_x", foreign_keys='Game.player_x_id')
    moves = relationship("Move", back_populates="user")

# PUBLIC_INTERFACE
class Game(Base):
    """Game model storing game metadata."""
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, index=True)
    player_x_id = Column(Integer, ForeignKey("users.id"))
    player_o_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    type = Column(Enum(GameType), default=GameType.SINGLE)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    player_x = relationship("User", foreign_keys=[player_x_id], back_populates="games")
    player_o = relationship("User", foreign_keys=[player_o_id])
    winner = relationship("User", foreign_keys=[winner_id])
    moves = relationship("Move", back_populates="game")

# PUBLIC_INTERFACE
class Move(Base):
    """Move model records each tic-tac-toe action."""
    __tablename__ = "moves"
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    x = Column(Integer)
    y = Column(Integer)
    symbol = Column(String(1))  # 'X' or 'O'
    turn_number = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

    game = relationship("Game", back_populates="moves")
    user = relationship("User", back_populates="moves")

# PUBLIC_INTERFACE
class LeaderboardEntry(Base):
    """Leaderboard entry for high score tracking."""
    __tablename__ = "leaderboard"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    ties = Column(Integer, default=0)
    user = relationship("User")
