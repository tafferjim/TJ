import os
import psycopg2
import requests
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_me

app = FastAPI()

# --- DATABASE HELPERS ---
def get_memory_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

def get_recipe_db():
    return psycopg2.connect(os.environ.get("RECIPE_DATABASE_URL"))

# --- AUTOMATIC TABLE BUILDER ---
@app.on_event("startup")
def init_db():
    for db_func, table_query in [
        (get_memory_db, "CREATE TABLE IF NOT EXISTS memory_store (id SERIAL PRIMARY KEY, memory_key TEXT UNIQUE NOT NULL, memory_value TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"),
        (get_recipe_db, "CREATE TABLE IF NOT EXISTS recipe_store (id SERIAL PRIMARY KEY, recipe_name TEXT UNIQUE NOT NULL, ingredients TEXT NOT NULL, instructions TEXT NOT NULL, source_url TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);")
    ]:
        try:
            conn = db_func()
            cur = conn.cursor()
            cur.execute(table_query)
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Table init error: {e}")

# --- HARDWARE SSE GATEWAY CONNECTION HANDSHAKE ---
@app.get("/mcp/sse")
async def sse_endpoint(request: Request):
    """Establishes the exact legacy SSE live stream line your AIPI Lite demands."""
    async def event_generator():
        # Send initial MCP protocol handshake to tell the hardware the tools exist
        init_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "result": {
                "tools": [
                    {"name": "save_memory", "description": "Saves general memory facts.", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}},
                    {"name": "search_web_for_recipe", "description": "Searches the web for recipe links.", "inputSchema": {"type": "object", "properties": {"dish_name": {"type": "string"}}, "required": ["dish_name"]}},
                    {"name": "save_recipe_to_db", "description": "Saves structured recipes.", "inputSchema": {"type": "object", "properties": {"recipe_name": {"type": "string"}, "ingredients": {"type": "string"}, "instructions": {"type": "string"}}, "required": ["recipe_name", "ingredients", "instructions"]}}
                ]
            }
        }
        yield f"data: {json.dumps(init_payload)}\n\n"
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# --- CORE EXECUTION ROUTE FOR HANDSHAKE CONTROLS ---
@app.post("/mcp/sse")
async def handle_tool_call(request: Request):
    body = await request.json()
    method = body.get("method")
    params = body.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    # 1. Handle tool discovery request
    if method == "tools/list":
        return {
            "tools": [
                {"name": "save_memory", "description": "Saves personal facts.", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}},
                {"name": "search_web_for_recipe", "description": "Searches for cooking links.", "inputSchema": {"type": "object", "properties": {"dish_name": {"type": "string"}}, "required": ["dish_name"]}},
                {"name": "save_recipe_to_db", "description": "Saves recipes directly to database.", "inputSchema": {"type": "object", "properties": {"recipe_name": {"type": "string"}, "ingredients": {"type": "string"}, "instructions": {"type": "string"}}, "required": ["recipe_name", "ingredients", "instructions"]}}
            ]
        }

    # 2. Handle actual tool executions
    if method == "tools/call":
        if tool_name == "save_memory":
            try:
                conn = get_memory_db()
                cur = conn.cursor()
                cur.execute("INSERT INTO memory_store (memory_key, memory_value) VALUES (%s, %s) ON CONFLICT (memory_key) DO UPDATE SET memory_value = EXCLUDED.memory_value;", (arguments.get("key"), arguments.get("value")))
                conn.commit()
                cur.close()
                conn.close()
                return {"content": [{"type": "text", "text": f"SUCCESS: Saved key '{arguments.get('key')}' to database."}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Error: {e}"}]}

        elif tool_name == "search_web_for_recipe":
            try:
                url = f"https://duckduckgo.com{arguments.get('dish_name')}+recipe"
                res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                soup = BeautifulSoup(res.text, "html.parser")
                links = [a.get("href") for a in soup.find_all("a", class_="result__url") if a.get("href") and "http" in a.get("href")]
                return {"content": [{"type": "text", "text": f"Links: {', '.join(links[:2])}"}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Search failed: {e}"}]}

        elif tool_name == "save_recipe_to_db":
            try:
                conn = get_recipe_db()
                cur = conn.cursor()
                cur.execute("INSERT INTO recipe_store (recipe_name, ingredients, instructions) VALUES (%s, %s, %s) ON CONFLICT (recipe_name) DO UPDATE SET ingredients = EXCLUDED.ingredients, instructions = EXCLUDED.instructions;", (arguments.get("recipe_name"), arguments.get("ingredients"), arguments.get("instructions")))
                conn.commit()
                cur.close()
                conn.close()
                return {"content": [{"type": "text", "text": "SUCCESS: Recipe stored."}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"Error: {e}"}]}

    return {"error": "Unknown method or tool"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))






















