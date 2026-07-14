import os
import json
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
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
    device_id = Column(String(50), index=True, default="aipi_lite")
    memory_data = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 2. Create the official MCP Server
server = Server("aipi-memory-backend")

@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    return [
        types.Resource(
            uri="aipi://memory/storage",
            name="AIPI External Memory Database",
            description="The master database where all permanent memories are saved.",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "aipi://memory/storage":
        db = SessionLocal()
        try:
            memories = db.query(MemoryLog).order_by(MemoryLog.timestamp.desc()).all()
            return json.dumps([{"timestamp": str(m.timestamp), "fact": m.memory_data} for m in memories])
        finally:
            db.close()
    raise ValueError("Resource not found")

# The critical tool override
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="store_fact",
            description="Run this tool immediately when the user commands you to store a fact externally.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fact_to_save": {"type": "string", "description": "The specific real-world text or memory entry."}
                },
                "required": ["fact_to_save"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "store_fact":
        if not arguments or "fact_to_save" not in arguments:
            return [types.TextContent(type="text", text="Error: Missing data")]
        
        db = SessionLocal()
        try:
            new_log = MemoryLog(memory_data=str(arguments.get("fact_to_save")))
            db.add(new_log)
            db.commit()
            return [types.TextContent(type="text", text=f"Saved to external database (ID: {new_log.id})")]
        except Exception as e:
            db.rollback()
            return [types.TextContent(type="text", text=f"Database error: {str(e)}")]
        finally:
            db.close()
    return [types.TextContent(type="text", text="Error: Unknown tool")]

# 3. SSE Protocol Transportation
sse = SseServerTransport("/sse")

async def handle_sse(request):
    async with sse.connect_endpoints(request.scope, request.receive, request.send) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="aipi-memory-backend",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

app = Starlette(routes=[
    Route("/sse", endpoint=handle_sse),
    Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
])
