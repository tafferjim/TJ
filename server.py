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

# 1. Database Initialization
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

# 2. Establish Clean MCP Server Instantiation
server = Server("aipi-memory-backend")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="store_fact",
            description="Executes immediately to record memories, real-world data logs, and facts directly into the external database storage.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fact_to_save": {"type": "string", "description": "The exact factual text string context to register permanently."}
                },
                "required": ["fact_to_save"],
            },
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> types.CallToolResult:
    if name == "store_fact":
        if not arguments or "fact_to_save" not in arguments:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text="Error: Arguments empty.")],
                isError=True
            )
        
        db = SessionLocal()
        try:
            fact_payload = str(arguments.get("fact_to_save"))
            new_log = MemoryLog(memory_data=fact_payload)
            db.add(new_log)
            db.commit()
            
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Success: Stored into database table row (ID: {new_log.id})")],
                isError=False
            )
        except Exception as e:
            db.rollback()
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Database write crash: {str(e)}")],
                isError=True
            )
        finally:
            db.close()

    return types.CallToolResult(
        content=[types.TextContent(type="text", text="Error: Selected tool doesn't exist.")],
        isError=True
    )

# 3. Handle Clean SSE Protocol Connection Mappings
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
