#!/usr/bin/env python3
"""
Database connection and initialization for AudioMoth Spectrogram Viewer
Using SQLAlchemy 2.x with modern patterns
"""

import sqlite3
from typing import Optional
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models"""
    pass


# Global variables for database connection
engine = None
SessionLocal = None
metadata = MetaData()


def init_database(db_path: str) -> None:
    """Initialize database connection with SQLAlchemy"""
    global engine, SessionLocal
    
    # Create SQLAlchemy engine with connection pooling
    database_url = f"sqlite:///{db_path}"
    print(f"Database URL: {database_url}")
    
    engine = create_engine(
        database_url,
        poolclass=StaticPool,
        pool_pre_ping=True,
        echo=False  # Set to True for SQL debugging
    )
    
    # Create session factory
    SessionLocal = sessionmaker(bind=engine)
    
    # Test the connection
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM audio_files"))
            count = result.scalar()
            print(f"Database connection successful. Audio files: {count}")
    except Exception as e:
        print(f"Database connection failed: {e}")
        raise
    
    # Create tables if they don't exist (but don't override existing ones)
    # Base.metadata.create_all(bind=engine)


def get_db_session():
    """Get a database session - use as context manager"""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    return SessionLocal()


def get_raw_connection():
    """Get raw SQLite connection for legacy compatibility"""
    if engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    # Get raw connection with Row factory for named column access
    raw_conn = engine.raw_connection()
    raw_conn.row_factory = sqlite3.Row
    return raw_conn


def execute_raw_query(query: str, params: tuple = ()) -> list:
    """Execute raw SQL query and return results"""
    conn = get_raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()