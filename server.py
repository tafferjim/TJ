import os
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
    device_id = Column(String(50), index=True)
    memory_data = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 2. Create the official MCP Server
server = Server("aipi-memory-backend")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="save_device_memory",
            description="Saves custom device logs and memories into the external database.",
            inputSchema={
                "type": "object",
                "properties": {
                    "device_id": {"type": "string"},
                    "memory_data": {"type": "string"},
                },
                "required": ["device_id", "memory_data"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "save_device_memory":
        if not arguments:
            return [types.TextContent(type="text", text="Error: Missing arguments")]

        db = SessionLocal()
        try:
            new_log = MemoryLog(
                device_id=str(arguments.get("device_id")),
                memory_data=str(arguments.get("memory_data"))
            )
            db.add(new_log)
            db.commit()
            return [types.TextContent(type="text", text=f"Success: Saved memory with ID {new_log.id}")]
        except Exception as e:
            db.rollback()
            return [types.TextContent(type="text", text=f"Error saving memory: {str(e)}")]
        finally:
            db.close()
    return [types.TextContent(type="text", text="Error: Unknown tool")]

# 3. Handle official SSE protocol transportation
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
