import os
import psycopg2
from fastmcp import FastMCP

# We add instructions directly to the server so the AI knows it MUST use it for memories
mcp = FastMCP(
    "AIPI_Lite_Memory_Server",
    instructions="You are a memory assistant. Every time the user asks you to remember, save, store, or recall information, you MUST use the save_memory or retrieve_memory tools. Do not just keep it in mind; always write it to the external database."
)

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("CRITICAL: DATABASE_URL environment variable is missing!")
    return psycopg2.connect(db_url)

def initialize_database():
    try:
        conn = get_db_connection()
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
        print("Database initialized.")
    except Exception as e:
        print(f"Error initializing database: {e}")

initialize_database()

@mcp.tool()
def save_memory(key: str, value: str) -> str:
    """Saves or updates a memory string associated with a specific key."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO memory_store (memory_key, memory_value)
            VALUES (%s, %s)
            ON CONFLICT (memory_key) 
            DO UPDATE SET memory_value = EXCLUDED.memory_value;
        """, (key, value))
        conn.commit()
        cur.close()
        conn.close()
        return f"SUCCESS: Memory saved under key '{key}'."
    except Exception as e:
        return f"Database Error while saving: {str(e)}"

@mcp.tool()
def retrieve_memory(key: str) -> str:
    """Retrieves a saved memory string using its key."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT memory_value FROM memory_store WHERE memory_key = %s;", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return f"Found memory: {row[0]}"
        return f"No memory found for key: '{key}'"
    except Exception as e:
        return f"Database Error while retrieving: {str(e)}"

# The modern, official way to export the app for Uvicorn
app = mcp.streamable_http_app()








