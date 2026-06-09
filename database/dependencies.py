from typing import Annotated, Generator
from sqlalchemy.orm import Session
from fastapi import Depends
from .session import SessionLocal

async def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DB_DEPENDENCY = Annotated[Session, Depends(get_db)]