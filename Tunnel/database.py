from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Async PostgreSQL configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:pmgJEqXiDwOeMaHOuehkcqYXCAevXlfJ@postgres.railway.internal:5432/wind_tunnel_db")

# Make sure to use asyncpg for async operations
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create async engine
engine = create_async_engine(DATABASE_URL)

# Create async session
AsyncSessionLocal = sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

Base = declarative_base()

# Async dependency
async def get_db():
    async_session = AsyncSessionLocal()
    try:
        yield async_session
    finally:
        await async_session.close()

