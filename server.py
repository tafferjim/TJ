import os
from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. Database Setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class MemoryLog(Base):
    __tablename__ = "memory_logs"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True)
    memory_data = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 2. Create the official MCP Server with SSE
mcp = FastMCP("AIPI Memory Backend")

# This creates a tool that your AIPI Lite can see and call automatically
@mcp.tool()
def save_device_memory(device_id: str, memory_data: str) -> str:
    """Saves custom device logs and memories into the external database."""
    db = SessionLocal()
    try:
        new_log = MemoryLog(device_id=device_id, memory_data=memory_data)
        db.add(new_log)
        db.commit()
        return f"Success: Memory saved into database with ID {new_log.id}"
    except Exception as e:
        db.rollback()
        return f"Error saving memory: {str(e)}"
    finally:
        db.close()
