from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from src.api import models, schemas, database, auth

# --- FastAPI app config ---
tags_metadata = [
    {"name": "Authentication", "description": "Register and login endpoints"},
    {"name": "Game", "description": "Game logic, moves, matchmaking"},
    {"name": "Leaderboard", "description": "Leaderboard scores"},
    {"name": "History", "description": "Game history for users"},
]

app = FastAPI(
    title="Tic Tac Toe Backend API",
    version="1.0.0",
    openapi_tags=tags_metadata,
    description="REST API backend for fullstack Tic Tac Toe game."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter(prefix="/api")

# --- CREATE DB TABLES IF NOT EXISTS (for demo use only, real prod uses Alembic) ---
from sqlalchemy_utils import create_database, database_exists
from sqlalchemy.exc import ProgrammingError

try:
    if not database_exists(database.engine.url):
        create_database(database.engine.url)
    models.Base.metadata.create_all(bind=database.engine)
except ProgrammingError:
    pass

# --- PUBLIC ENDPOINTS ---

@app.get("/", tags=["Root"])
def health_check():
    """Health check endpoint."""
    return {"message": "Healthy"}

# ---------- AUTHENTICATION ----------
# PUBLIC_INTERFACE
@router.post("/auth/register", response_model=schemas.UserResponse, summary="Register", tags=["Authentication"])
def register(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    """Registers a new user. Username must be unique."""
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_pw = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # create leaderboard entry
    lb = models.LeaderboardEntry(user_id=new_user.id)
    db.add(lb)
    db.commit()
    return new_user

# PUBLIC_INTERFACE
@router.post("/auth/login", response_model=schemas.Token, summary="Login", tags=["Authentication"])
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    """Logs a user in and returns JWT access token."""
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# ---------- GAME LOGIC -----------
def get_symbol_for_user(game: models.Game, user_id) -> str:
    if game.player_x_id == user_id:
        return "X"
    elif game.player_o_id == user_id:
        return "O"
    return "?"

def board_from_moves(moves):
    """Return a 3x3 board from moves."""
    board = [["" for _ in range(3)] for _ in range(3)]
    for move in moves:
        board[move.x][move.y] = move.symbol
    return board

def check_winner(board):
    # Lines to check: rows, cols, diags
    for i in range(3):
        if board[i][0] and all(board[i][j] == board[i][0] for j in range(3)):
            return board[i][0]
        if board[0][i] and all(board[j][i] == board[0][i] for j in range(3)):
            return board[0][i]
    # Diagonals
    if board[0][0] and all(board[i][i] == board[0][0] for i in range(3)):
        return board[0][0]
    if board[0][2] and all(board[i][2-i] == board[0][2] for i in range(3)):
        return board[0][2]
    return None

def is_full(board):
    return all(cell for row in board for cell in row)

# PUBLIC_INTERFACE
@router.post("/game/new", response_model=schemas.GameResponse, summary="Create New Game", tags=["Game"])
def new_game(game_req: schemas.GameCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Start a new game; single or multiplayer (places in matchmaking if multiplayer)."""
    if game_req.type == "single":
        new_game = models.Game(
            player_x_id=current_user.id,
            type=models.GameType.SINGLE,
            is_active=True
        )
        db.add(new_game)
        db.commit()
        db.refresh(new_game)
        return _game_to_response(new_game)
    elif game_req.type == "multi":
        # Assign as X, wait for O
        existing_pending = db.query(models.Game).filter(
            models.Game.type==models.GameType.MULTI,
            models.Game.player_o_id==None,
            models.Game.is_active==True
        ).first()
        if existing_pending and existing_pending.player_x_id != current_user.id:
            existing_pending.player_o_id = current_user.id
            db.commit()
            db.refresh(existing_pending)
            return _game_to_response(existing_pending)
        else:
            # Create the game and enter matchmaking
            new_game = models.Game(
                player_x_id=current_user.id,
                type=models.GameType.MULTI,
                is_active=True
            )
            db.add(new_game)
            db.commit()
            db.refresh(new_game)
            return _game_to_response(new_game)
    else:
        raise HTTPException(status_code=400, detail="type must be single or multi")

def _game_to_response(game: models.Game):
    moves = sorted(game.moves, key=lambda m: m.turn_number)
    return schemas.GameResponse(
        id=game.id,
        type=game.type.value,
        player_x=game.player_x.username if game.player_x else None,
        player_o=game.player_o.username if game.player_o else None,
        winner=game.winner.username if game.winner else None,
        is_active=game.is_active,
        moves=[
            schemas.MoveResponse(
                x=m.x, y=m.y, symbol=m.symbol,
                user_id=m.user_id, turn_number=m.turn_number, timestamp=m.timestamp
            ) for m in moves
        ]
    )

# PUBLIC_INTERFACE
@router.post("/game/{game_id}/move", response_model=schemas.GameResponse, summary="Make Move", tags=["Game"])
def make_move(game_id: int, move: schemas.MoveCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Make a move. If it's computer's turn in single-player, auto-respond."""
    game = db.query(models.Game).filter(models.Game.id==game_id).first()
    if not game or not game.is_active:
        raise HTTPException(status_code=404, detail="Game not found or inactive")
    moves = sorted(game.moves, key=lambda m: m.turn_number)
    symbol = get_symbol_for_user(game, current_user.id)
    if len(moves) == 0:
        # Must be X’s turn and must match
        if symbol != "X":
            raise HTTPException(status_code=403, detail="You are not X; cannot move first")
    else:
        # Strict turn-taking: next symbol
        last_symbol = moves[-1].symbol
        if (last_symbol == symbol):
            raise HTTPException(status_code=403, detail="It's not your turn")

    # Check move validity
    board = board_from_moves(moves)
    if not (0 <= move.x <= 2 and 0 <= move.y <=2):
        raise HTTPException(status_code=400, detail="Invalid board coordinates")
    if board[move.x][move.y]:
        raise HTTPException(status_code=400, detail="Cell is already taken")
    tn = len(moves) + 1
    m = models.Move(
        game_id=game.id,
        user_id=current_user.id,
        x=move.x,
        y=move.y,
        symbol=symbol,
        turn_number=tn
    )
    db.add(m)
    db.commit()
    db.refresh(game)
    moves = sorted(game.moves, key=lambda m: m.turn_number)
    board = board_from_moves(moves)
    win = check_winner(board)
    full = is_full(board)
    if win or full:
        game.is_active = False
        if win:
            if win == "X":
                winner_id = game.player_x_id
                loser_id = game.player_o_id if game.player_o_id else None
            else:
                winner_id = game.player_o_id
                loser_id = game.player_x_id
            if winner_id:
                game.winner_id = winner_id
                # Leaderboard update
                lbw = db.query(models.LeaderboardEntry).filter_by(user_id=winner_id).first()
                if lbw:
                    lbw.wins += 1
                if loser_id:
                    lbl = db.query(models.LeaderboardEntry).filter_by(user_id=loser_id).first()
                    if lbl:
                        lbl.losses += 1
            else:
                pass
        else:
            # Tie
            if game.player_x_id:
                lbe = db.query(models.LeaderboardEntry).filter_by(user_id=game.player_x_id).first()
                if lbe:
                    lbe.ties += 1
            if game.player_o_id:
                lbe = db.query(models.LeaderboardEntry).filter_by(user_id=game.player_o_id).first()
                if lbe:
                    lbe.ties += 1
        game.completed_at = database.datetime.datetime.utcnow()
        db.commit()
    game = db.query(models.Game).filter(models.Game.id == game.id).first()
    # AI move if single-player, only if not ended
    if game.type == models.GameType.SINGLE and game.is_active and get_symbol_for_user(game, current_user.id) == "X":
        # AI is 'O', do a random valid move
        from random import choice
        board = board_from_moves(sorted(game.moves, key=lambda m: m.turn_number))
        empty = [(ix, iy) for ix in range(3) for iy in range(3) if not board[ix][iy]]
        if empty:
            ai_x, ai_y = choice(empty)
            ai_move = models.Move(
                game_id=game.id,
                user_id=None,  # No user for AI
                x=ai_x,
                y=ai_y,
                symbol="O",
                turn_number=len(game.moves) + 1
            )
            db.add(ai_move)
            db.commit()
            db.refresh(game)
            # Update result
            moves = sorted(game.moves, key=lambda m: m.turn_number)
            board = board_from_moves(moves)
            win = check_winner(board)
            full = is_full(board)
            if win or full:
                game.is_active = False
                if win:
                    game.winner_id = game.player_x_id if win == "X" else None
                    # User can only win or tie versus AI
                    if win == "X":
                        lbw = db.query(models.LeaderboardEntry).filter_by(user_id=game.player_x_id).first()
                        if lbw:
                            lbw.wins += 1
                    if win == "O":
                        lbe = db.query(models.LeaderboardEntry).filter_by(user_id=game.player_x_id).first()
                        if lbe:
                            lbe.losses += 1
                else:
                    lbe = db.query(models.LeaderboardEntry).filter_by(user_id=game.player_x_id).first()
                    if lbe:
                        lbe.ties += 1
                game.completed_at = database.datetime.datetime.utcnow()
                db.commit()
            db.refresh(game)
    return _game_to_response(game)

# ---------- LEADERBOARD ----------

# PUBLIC_INTERFACE
@router.get("/leaderboard", response_model=List[schemas.LeaderboardEntryResponse], summary="Get Leaderboard", tags=["Leaderboard"])
def get_leaderboard(db: Session = Depends(database.get_db)):
    """Returns leaderboard sorted by win count."""
    entries = db.query(models.LeaderboardEntry).join(models.User).order_by(models.LeaderboardEntry.wins.desc()).all()
    return [
        schemas.LeaderboardEntryResponse(
            username=e.user.username,
            wins=e.wins,
            losses=e.losses,
            ties=e.ties
        ) for e in entries
    ]

# ---------- GAME HISTORY ----------

# PUBLIC_INTERFACE
@router.get("/history", response_model=schemas.HistoryResponse, summary="Get user game history", tags=["History"])
def get_history(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    """Returns games played by the current user."""
    games = db.query(models.Game).filter(
        ((models.Game.player_x_id == current_user.id) | (models.Game.player_o_id == current_user.id))
    ).all()
    return schemas.HistoryResponse(games=[_game_to_response(g) for g in games])

app.include_router(router)

