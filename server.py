import os
import psycopg2
from fastmcp import FastMCP

mcp = FastMCP("AIPI-Memories-Extension")

DB_URL = os.environ.get("DATABASE_URL")

def initialize_database():
    """Automatically creates the memories table if it does not exist yet."""
    if not DB_URL:
        print("DATABASE_URL not found. Skipping initialization.")
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        # This automatically runs the table creation command for you
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
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {str(e)}")

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

if __name__ == "__main__":
    # Run the setup script right before the server launches
    initialize_database()
    
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)

