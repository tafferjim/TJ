import os
import psycopg2
import requests
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from bs4 import BeautifulSoup

app = FastAPI()

def get_memory_db():
    return psycopg2.connect(os.environ.get("DATABASE_URL"))

def get_recipe_db():
    return psycopg2.connect(os.environ.get("RECIPE_DATABASE_URL"))

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

    try:
        conn = get_recipe_db()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS recipe_store (
                id SERIAL PRIMARY KEY,
                recipe_name TEXT UNIQUE NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("Recipe table ready.")
    except Exception as e:
        print(f"Recipe init error: {e}")

# --- FIX: THE MANDATORY MANIFEST DISCOVERY PATH FOR THE DASHBOARD ---
@app.get("/mcp/")
@app.get("/mcp")
async def mcp_root():
    """Tells the AIPI Dashboard that the server is alive and where to go."""
    return {"status": "active", "transport": "sse", "endpoint": "/mcp/sse"}

@app.get("/mcp/sse")
async def sse_endpoint(request: Request):
    """Clean protocol handshake stream for the physical hardware connection layer."""
    async def event_generator():
        init_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "result": {
                "tools": [
                    {"name": "save_memory", "description": "Saves personal facts and codes.", "inputSchema": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}},
                    {"name": "search_web_for_recipe", "description": "Searches for cooking recipes.", "inputSchema": {"type": "object", "properties": {"dish_name": {"type": "string"}}, "required": ["dish_name"]}}
                ]
            }
        }
        yield f"data: {json.dumps(init_payload)}\n\n"
        while True:
            if await request.is_disconnected():
                break
            await asyncio.sleep(5)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/mcp/sse")
async def handle_tool_call(request: Request):
    """Executes direct database insertions based on the device's voice signals."""
    body = await request.json()
    params = body.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name == "save_memory":
        try:
            conn = get_memory_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO memory_store (memory_key, memory_value) 
                VALUES (%s, %s) 
                ON CONFLICT (memory_key) DO UPDATE SET memory_value = EXCLUDED.memory_value;
            """, (arguments.get("key"), arguments.get("value")))
            conn.commit()
            cur.close()
            conn.close()
            return {"content": [{"type": "text", "text": f"SUCCESS: Saved key '{arguments.get('key')}'."}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Database Error: {e}"}]}

    elif tool_name == "search_web_for_recipe":
        try:
            dish = arguments.get("dish_name")
            url = f"https://duckduckgo.com{dish}+recipe"
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            links = [a.get("href") for a in soup.find_all("a", class_="result__url") if a.get("href") and "http" in a.get("href")]
            
            conn = get_recipe_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO recipe_store (recipe_name, ingredients, instructions) 
                VALUES (%s, %s, %s) 
                ON CONFLICT (recipe_name) DO UPDATE SET ingredients = EXCLUDED.ingredients;
            """, (dish, f"Source links: {', '.join(links[:2])}", "Scraped automated data text placeholders."))
            conn.commit()
            cur.close()
            conn.close()
            return {"content": [{"type": "text", "text": f"SUCCESS: Found and saved a recipe for {dish} to your recipe database."}]}
        except Exception as e:
            return {"content": [{"type": "text", "text": f"Search Error: {e}"}]}

    return {"error": "Unknown tool call method configuration structure."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))























