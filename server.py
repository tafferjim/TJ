import os
import psycopg2
from fastmcp import FastMCP

mcp = FastMCP("AIPI-Memories-Extension")

DB_URL = os.environ.get("DATABASE_URL")

def initialize_database():
    """Automatically creates the memories table if it does not exist yet."""
    if not DB_URL:
        print("DATABASE_URL not found. Skipping initialization.", flush=True)
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                memory_text TEXT NOT NULL
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Database initialized successfully.", flush=True)
    except Exception as e:
        print(f"Database initialization failed: {str(e)}", flush=True)

@mcp.tool()
def save_memory(content: str) -> str:
    """Saves a new long-term memory or fact about the user to the external database."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
        
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        query = "INSERT INTO memories (memory_text) VALUES (%s);"
        cursor.execute(query, (content,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return f"Successfully saved to your Render database: '{content}'"
    except Exception as e:
        return f"Failed to save memory. Error: {str(e)}"

@mcp.tool()
def get_memories() -> str:
    """Retrieves all saved long-term memories and facts from the database with clear ID numbers."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
        
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, memory_text, created_at FROM memories ORDER BY created_at DESC;")
        rows = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not rows:
            return "The memories table exists, but it is currently empty! Try saving a memory first."
            
        memory_list = []
        # Cleanly separate the ID, text, and timestamp variables from the database tuple
        for row in rows:
            mem_id = row[0]
            mem_text = row[1]
            mem_date = row[2]
            memory_list.append(f"ID {mem_id}: '{mem_text}' (Saved on {mem_date})")
            
        return "Here are the saved memories:\n" + "\n".join(memory_list)
    except Exception as e:
        return f"Failed to retrieve memories. Error: {str(e)}"

@mcp.tool()
def delete_memory(memory_id: int) -> str:
    """Deletes a specific memory from the database using its numerical ID."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
        
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Check if the memory exists first
        cursor.execute("SELECT memory_text FROM memories WHERE id = %s;", (memory_id,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return f"Could not find any memory with ID {memory_id}."
            
        memory_text = row[0]
        
        # Delete the row
        cursor.execute("DELETE FROM memories WHERE id = %s;", (memory_id,))
        conn.commit()
        
        cursor.close()
        conn.close()
        return f"Successfully deleted memory ID {memory_id}: '{memory_text}'"
    except Exception as e:
        return f"Failed to delete memory. Error: {str(e)}"

if __name__ == "__main__":
    initialize_database()
    
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)

