import os
import psycopg2
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("AIPI_Lite_Memory_Server")

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("CRITICAL: DATABASE_URL environment variable is missing!")
    return psycopg2.connect(db_url)

def initialize_database():
    """Automatically creates the memory table if it does not exist."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Create a simple key-value memory table
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
        print("Database initialization successful or already exists.")
    except Exception as e:
        print(f"Error initializing database: {e}")

# Run database setup immediately when the server starts
initialize_database()

@mcp.tool()
def save_memory(key: str, value: str) -> str:
    """Saves or updates a memory string associated with a specific key."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Upsert: Insert new memory, or update if the key already exists
        cur.execute("""
            INSERT INTO memory_store (memory_key, memory_value)
            VALUES (%s, %s)
            ON CONFLICT (memory_key) 
            DO UPDATE SET memory_value = EXCLUDED.memory_value;
        """, (key, value))
        
        conn.commit()
        cur.close()
        conn.close()
        return f"Successfully saved memory for key: '{key}'"
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
            return f"Memory found: {row[0]}"
        return f"No memory found for key: '{key}'"
    except Exception as e:
        return f"Database Error while retrieving: {str(e)}"

# Create the ASGI application for Uvicorn using the modern FastMCP method
app = mcp.streamable_http_app()







