import os
from fastapi import FastAPI, Request
from fastapi.responses import EventSourceResponse
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import asyncio

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
    memory_data = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 2. FastAPI Application
app = FastAPI()

# This is the pure SSE connection endpoint the AIPI hooks into
@app.get("/sse")
async def sse_endpoint(request: Request):
    async def event_generator():
        # Keeps a direct, simple SSE network line open to the AIPI console
        while True:
            if await request.is_disconnected():
                break
            yield {"event": "ping", "data": "keep-alive"}
            await asyncio.sleep(20)

    return EventSourceResponse(event_generator())

# This is the direct endpoint that intercepts memories and saves them to the DB
@app.post("/sse")
async def receive_memory(request: Request):
    body = await request.json()
    
    # Extract the text memory regardless of how the AIPI structures the payload
    memory_text = body.get("text") or body.get("memory_data") or body.get("arguments", {}).get("text") or str(body)
    
    db = SessionLocal()
    try:
        new_log = MemoryLog(memory_data=str(memory_text))
        db.add(new_log)
        db.commit()
        return {"status": "success", "id": new_log.id}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
