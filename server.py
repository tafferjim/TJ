import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_backend, create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# 1. Database Setup
# Render provides the DATABASE_URL environment variable automatically
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Database Model (What the database stores)
class MemoryLog(Base):
    __tablename__ = "memory_logs"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(50), index=True)
    memory_data = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 3. FastAPI Setup
app = FastAPI()

# Pydantic Model (What your AIPI Lite sends)
class MemoryPayload(BaseModel):
    device_id: str
    memory_data: str

@app.post("/save-memory")
def save_memory(payload: MemoryPayload):
    db = SessionLocal()
    try:
        new_log = MemoryLog(
            device_id=payload.device_id,
            memory_data=payload.memory_data
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        return {"status": "success", "id": new_log.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
