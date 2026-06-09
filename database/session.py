import os
import sys
from pathlib import Path

# Add parent directory to path to allow imports when running directly
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv

# Load .env from project root
env_path = parent_dir / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Annotated, Generator
from sqlalchemy import create_engine, MetaData
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker, declarative_base
from Core.config import DB_URL, settings
from loguru import logger

# Configure logger to write to file if enabled
if settings.LOG_TO_FILE:
    log_file_path = parent_dir / settings.LOG_FILE_PATH
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_file_path),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
        level=settings.LOG_LEVEL,
        rotation="10 MB",
        retention="10 days",
        compression="zip"
    )

Base = declarative_base()

engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

metadata = MetaData()
metadata.reflect(bind=engine)

try:
    with engine.connect() as conn:
        logger.info("Database connected successfully")
except SQLAlchemyError as e:
    logger.error(f"Database connection failed: {e}")
    raise e