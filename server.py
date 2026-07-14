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
    device_id = Column(String(50), index=True, default="aipi_lite")
    memory_data = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 2. Create the official MCP Server
server = Server("aipi-memory-backend")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="store_fact",
            description="Run this tool immediately when the user commands you to store a fact externally.",
            inputSchema={
                "type": "object",
                "properties": {
                    "fact_to_save": {"type": "string", "description": "The text or memory entry to save."}
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
                content=[types.TextContent(type="text", text="Error: Missing data")],
                isError=True
            )
        
        db = SessionLocal()
        try:
            fact_text = str(arguments.get("fact_to_save"))
            new_log = MemoryLog(memory_data=fact_text)
            db.add(new_log)
            db.commit()
            
            # This returns the official CallToolResult layout the AIPI platform requires
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Saved to external database (ID: {new_log.id})")],
                isError=False
            )
        except Exception as e:
            db.rollback()
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=f"Database error: {str(e)}")],
                isError=True
            )
        finally:
            db.close()
            
    return types.CallToolResult(
        content=[types.TextContent(type="text", text="Error: Unknown tool")],
        isError=True
    )

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
