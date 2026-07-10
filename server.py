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

def clean_hardware_text(text: str) -> str:
    """Safely converts special symbols to words to completely bypass slash and box display bugs."""
    if not text:
        return ""
    return text.replace("½", " 1-half ").replace("¼", " 1-fourth ").replace("¾", " 3-fourths ")

@mcp.tool()
def save_memory(content: str) -> str:
    """Saves a new long-term memory or recipe about the user to the external database."""
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
        return f"Successfully saved: '{content}'"
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
            return "Your memory bank is currently empty."
        memory_list = []
        for row in rows:
            text = clean_hardware_text(str(row[0]))
            memory_list.append(f"- {text}")
        return "Here are your saved logs:\n\n" + "\n".join(memory_list)
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
        cursor.execute("SELECT id, memory_text FROM memories ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return "There are no memories in the database to delete."
        mem_id = row[0]
        mem_text = clean_hardware_text(row[1])
        cursor.execute("DELETE FROM memories WHERE id = %s;", (mem_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Successfully erased the most recent entry: '{mem_text}'"
    except Exception as e:
        return f"Failed to delete the last memory. Error: {str(e)}"

@mcp.tool()
def get_local_time() -> str:
    """Returns the current local time."""
    now = datetime.datetime.now()
    return f"The current local time is {now.strftime('%I:%M %p on %B %d, %Y')}."

@mcp.tool()
def get_local_weather(city: str = "Austin") -> str:
    """Fetches the current weather for a specific city. Defaults to Austin."""
    api_key = "YOUR_OPENWEATHERMAP_API_KEY" # Replace with your real key if needed
    if api_key == "YOUR_OPENWEATHERMAP_API_KEY":
        return "Error: Weather API key has not been configured in the script yet."
    url = f"https://openweathermap.org{city}&appid={api_key}&units=imperial"
    try:
        response = requests.get(url).json()
        if response.get("cod") != 200:
            return f"Could not find weather data for: '{city}'."
        temp = response["main"]["temp"]
        desc = response["weather"]["description"]
        return f"The current weather in {city.title()} is {temp}°F with {desc}."
    except Exception as e:
        return f"Failed to fetch weather data. Error: {str(e)}"

@mcp.tool()
def read_recipe(keyword: str) -> str:
    """Retrieves a specific recipe text block from the database by matching a keyword."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        query = "SELECT memory_text FROM memories WHERE memory_text ILIKE %s ORDER BY id DESC LIMIT 1;"
        cursor.execute(query, (f"%{keyword}%",))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return f"I couldn't find any saved recipes matching '{keyword}'."
            
        recipe_text = clean_hardware_text(str(row[0]))
        return recipe_text
    except Exception as e:
        return f"Error reading recipe: {str(e)}"

@mcp.tool()
def list_recipes_paged(page: int = 1, limit: int = 3) -> str:
    """Lists saved recipes from the database in small, clean batches."""
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT memory_text FROM memories ORDER BY id DESC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return "Your database is currently empty."
            
        found_recipes = []
        for row in rows:
            text = clean_hardware_text(str(row[0]))
            
            # FIXED FILTER: Checks keywords explicitly, completely ignoring line breaks
            if any(k in text.lower() for k in ["recipe", "ingredients", "cook", "bake", "cornbread", "flour"]):
                first_line = text.split("\n")[0].strip("- *#")
                title = first_line[:45] + "..." if len(first_line) > 45 else first_line
                found_recipes.append(title)
                
        if not found_recipes:
            return "No entries match your recipe keywords."
            
        total_recipes = len(found_recipes)
        total_pages = (total_recipes + limit - 1) // limit
        
        if page > total_pages or page < 1:
            return f"Page {page} does not exist. Total pages: {total_pages}."
            
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_items = found_recipes[start_idx:end_idx]
        
        output = [f"--- RECIPE MENU (Page {page} of {total_pages}) ---"]
        for i, item in enumerate(page_items, start=start_idx + 1):
            output.append(f"{i}. {item}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Failed to list recipes. Error: {str(e)}"

if __name__ == "__main__":
    initialize_database()
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)


