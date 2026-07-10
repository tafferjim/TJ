import os
import datetime
import requests
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
    """Retrieves all memories as a simple text list."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT memory_text FROM memories ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        if not rows:
            return "The memories table exists, but it is currently empty! Try saving a memory first."
        memory_list = []
        for row in rows:
            memory_list.append(f"- {str(row[0])}")
        return "Here are the saved memories extracted directly from the database:\n\n" + "\n".join(memory_list)
    except Exception as e:
        return f"Failed to retrieve memories. Error: {str(e)}"

@mcp.tool()
def delete_last_memory() -> str:
    """Deletes the single most recently saved memory from the database. No ID required."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        # Find the newest entry
        cursor.execute("SELECT id, memory_text FROM memories ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return "There are no memories in the database to delete."
        mem_id = row[0]
        mem_text = row[1]
        # Wipe it out
        cursor.execute("DELETE FROM memories WHERE id = %s;", (mem_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Successfully erased the most recent memory: '{mem_text}'"
    except Exception as e:
        return f"Failed to delete the last memory. Error: {str(e)}"

@mcp.tool()
def get_local_time() -> str:
    """Returns the current local time by directly pulling from a live time API to bypass all server clock caching."""
    import requests
    try:
        # Request live Austin time directly from the World Time API
        response = requests.get("https://worldtimeapi.org", timeout=5).json()
        datetime_str = response["datetime"] # Example: "2026-07-10T14:11:22..."
        
        # Parse the web timestamp into a clean format
        from datetime import datetime
        clean_time = datetime.fromisoformat(datetime_str[0:19])
        return f"The current local time is {clean_time.strftime('%I:%M %p on %B %d, %Y')}."
    except Exception as e:
        # Fallback to local server time calculation if the web API fails
        import datetime as dt
        utc_now = dt.datetime.utcnow()
        local_now = utc_now - dt.timedelta(hours=5) # Hard force CDT offset
        return f"The current local time is {local_now.strftime('%I:%M %p on %B %d, %Y')}."

@mcp.tool()
def get_local_weather(city: str) -> str:
    """Fetches the current weather for a specific city."""
    # Replace the string below with your actual OpenWeatherMap API key
    api_key = "d7434761f3661acda639776b3ab2a235"
    
    if api_key == "YOUR_OPENWEATHERMAP_API_KEY":
        return "Error: Weather API key has not been configured in the script yet."
        
    url = f"https://openweathermap.org{city}&appid={api_key}&units=imperial"
    
    try:
        response = requests.get(url).json()
        if response.get("cod") != 200:
            return f"Could not find weather data for the city: '{city}'."
            
        temp = response["main"]["temp"]
        desc = response["weather"][0]["description"]
        humidity = response["main"]["humidity"]
        
        return f"The current weather in {city.title()} is {temp}°F with {desc}. Humidity is at {humidity}%."
    except Exception as e:
        return f"Failed to fetch weather data. Error: {str(e)}"

if __name__ == "__main__":
    initialize_database()
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)




