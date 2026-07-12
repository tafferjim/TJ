import os
import psycopg2
import requests
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_memory_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

@app.on_event("startup")
def init_db():
    """Builds clean, empty tables instantly upon startup."""
    try:
        conn = get_memory_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS memory_store (
                id SERIAL PRIMARY KEY,
                memory_key TEXT UNIQUE NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Memory table ready.")
    except Exception as e:
        print(f"Memory init error: {e}")

TOOL_MANIFEST = [
    {
        "name": "save_memory",
        "description": "Saves personal facts and codes to the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"}
            },
            "required": ["key", "value"]
        }
    }
]

@app.get("/mcp")
@app.get("/mcp/")
async def mcp_root():
    return {"status": "active", "transport": "sse", "endpoint": "/mcp/sse"}

@app.get("/mcp/sse")
@app.get("/mcp/sse/")
async def sse_endpoint(request: Request):
    """Establishes the persistent SSE handshake stream that the AIPI Lite dashboard requires."""
    async def event_generator():
        init_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "result": {"tools": TOOL_MANIFEST}
        }
        yield f"data: {json.dumps(init_payload)}\n\n"
        while True:
            if await request.is_disconnected():
                break
            yield "data: {}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/mcp/sse")
@app.post("/mcp/sse/")
@app.post("/mcp")
async def handle_tool_call(request: Request):
    """Processes incoming data updates from the active hardware channel."""
    try:
        body = await request.json()
    except Exception:
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
        
    method = body.get("method")
    params = body.get("params", {})
    
    # Catch every possible name placement the hardware uses
    tool_name = params.get("name") or body.get("name") or body.get("method")
    arguments = params.get("arguments") or body.get("arguments") or params
    
    # Fallback to map raw text properties to key/value pairs
    key_val = arguments.get("key") or arguments.get("memory_key") or arguments.get("text") or "voice_memo"
    value_val = arguments.get("value") or arguments.get("memory_value") or arguments.get("dish_name") or str(arguments)
    
    request_id = body.get("id")

    if method in ["initialize", "mcp.initialize"]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "RenderMemoryServer", "version": "1.0.0"}
            }
        }

    if method in ["tools/list", "mcp.tools/list"]:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": TOOL_MANIFEST}
        }

    # Intercept any tool names matching memory or custom database calls
    if tool_name in ["save_memory", "tools/call", "mcp.tools/call", "memory", "custom"] or "memory" in str(tool_name):
        conn = None
        try:
            conn = get_memory_db()
            with conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO memory_store (memory_key, memory_value) 
                        VALUES (%s, %s) 
                        ON CONFLICT (memory_key) 
                        DO UPDATE SET memory_value = EXCLUDED.memory_value;
                    """, (str(key_val), str(value_val)))
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"SUCCESS: Saved key '{key_val}'."}]}
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"Database Error: {e}"}]}
            }
        finally:
            if conn:
                conn.close()

    # Generic catch-all write fallback to ensure the operation always succeeds
    try:
        conn = get_memory_db()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO memory_store (memory_key, memory_value) 
                    VALUES (%s, %s) 
                    ON CONFLICT (memory_key) 
                    DO UPDATE SET memory_value = EXCLUDED.memory_value;
                """, (f"auto_{tool_name}", str(arguments)))
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": "SUCCESS: Logged fallback entry data."}]}
        }
    except Exception:
        if conn:
            conn.close()

    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
