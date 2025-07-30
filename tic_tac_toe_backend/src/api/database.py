import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Get DB connection info from environment
DB_USER = os.getenv("POSTGRES_USER", "tic_tac_toe_user")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DB_NAME = os.getenv("POSTGRES_DB", "tic_tac_toe_db")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

SQLALCHEMY_DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# PUBLIC_INTERFACE
def get_db():
    """Dependency injection for DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
