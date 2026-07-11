import os
import datetime
import psycopg2
from fastmcp import FastMCP

mcp = FastMCP("AIPI-Core-Memories")
DB_URL = os.environ.get("DATABASE_URL")

def initialize_database():
    """Wipes out any mixed data and forces a 100% blank table for personal memories."""
    if not DB_URL:
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS recipes;")
        cursor.execute("DROP TABLE IF EXISTS memories;")
        cursor.execute("""
            CREATE TABLE memories (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                memory_text TEXT NOT NULL
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Personal memories database table wiped and ready!", flush=True)
    except Exception as e:
        print(f"Setup failed: {str(e)}", flush=True)

@mcp.tool()
def save_memory(content: str) -> str:
    """Saves a standard long-term personal memory or fact about the user."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memories (memory_text) VALUES (%s);", (content,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Successfully saved to your long-term memory: '{content}'"
    except Exception as e:
        return f"Failed to save memory: {str(e)}"

@mcp.tool()
def get_memories() -> str:
    """Retrieves all saved memories as a simple text list."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT memory_text FROM memories ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            return "Your memory bank is currently empty."
        memory_list = [f"- {str(row[0])}" for row in rows]
        return "Here are your saved memories:\n\n" + "\n".join(memory_list)
    except Exception as e:
        return f"Failed to retrieve memories: {str(e)}"

@mcp.tool()
def delete_last_memory() -> str:
    """Deletes the single most recently saved memory entry."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = (SELECT id FROM memories ORDER BY id DESC LIMIT 1);")
        conn.commit()
        cursor.close()
        conn.close()
        return "Successfully deleted your last memory entry."
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    initialize_database()
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)





