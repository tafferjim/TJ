import os
import psycopg2
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

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
    """Builds database structures instantly upon container boot."""
    try:
        conn = get_memory_db()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory_store (
                        id SERIAL PRIMARY KEY,
                        memory_key TEXT UNIQUE NOT NULL,
                        memory_value TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)
        print("Database successfully synchronized.")
    except Exception as e:
        print(f"Database setup error: {e}")

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

# CAPTURE EVERY GET REQUEST ROUTE TRAFFIC TYPE ANYWHERE ON THE SERVER
@app.get("/")
@app.get("/mcp")
@app.get("/mcp/")
@app.get("/mcp/sse")
@app.get("/mcp/sse/")
async def universal_sse_endpoint(request: Request):
    """Maintains active streaming network sessions for hardware handshake tracking loops."""
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

# CAPTURE EVERY POST ACTION TRAFFIC TYPE ANYWHERE ON THE SERVER
@app.post("/")
@app.post("/mcp")
@app.post("/mcp/")
@app.post("/mcp/sse")
@app.post("/mcp/sse/")
async def universal_handle_tool_call(request: Request):
    """Processes any hardware write actions directly into your active table records rows."""
    try:
        body = await request.json()
    except Exception:
        return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
        
    method = body.get("method")
    params = body.get("params", {})
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

    tool_name = params.get("name") or body.get("name") or body.get("method")
    arguments = params.get("arguments") or body.get("arguments") or params
    
    key_val = arguments.get("key") or arguments.get("memory_key") or "voice_memo"
    value_val = arguments.get("value") or arguments.get("memory_value") or str(body)

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
            "result": {"content": [{"type": "text", "text": "SUCCESS"}]}
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

