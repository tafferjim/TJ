import os
import datetime
import requests
import psycopg2
from fastmcp import FastMCP

mcp = FastMCP("AIPI-Memories-Extension")
DB_URL = os.environ.get("DATABASE_URL")

def initialize_database():
    """Automatically sets up both separate tables on launch inside your paid database."""
    if not DB_URL:
        print("DATABASE_URL environment variable is missing. Skipping table check.", flush=True)
        return
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Table 1: Isolated space for standard personal text logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                memory_text TEXT NOT NULL
            );
        """)
        
        # Table 2: Isolated space for structured recipes 
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recipe_name TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL
            );
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Database tables initialized successfully side-by-side!", flush=True)
    except Exception as e:
        print(f"Database table setup failed: {str(e)}", flush=True)

def clean_hardware_text(text: str) -> str:
    """Safely converts complex symbols to words to eliminate box characters on the screen."""
    if not text:
        return ""
    return text.replace("½", " 1-half ").replace("¼", " 1-fourth ").replace("¾", " 3-fourths ")

# ==================== PERSONAL MEMORY TOOLS ====================

@mcp.tool()
def save_memory(content: str) -> str:
    """Saves a standard personal memory or fact. Does NOT save recipes here."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memories (memory_text) VALUES (%s);", (content,))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Saved to memories index: '{content}'"
    except Exception as e:
        return f"Error saving memory: {str(e)}"

@mcp.tool()
def delete_last_memory() -> str:
    """Deletes the most recent general memory entry from the memories table."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE id = (SELECT id FROM memories ORDER BY id DESC LIMIT 1);")
        conn.commit()
        cursor.close()
        conn.close()
        return "Successfully deleted your last general memory entry."
    except Exception as e:
        return f"Error: {str(e)}"

# ==================== TIME & WEATHER TOOLS ====================

@mcp.tool()
def get_local_time() -> str:
    """Returns the current local time."""
    now = datetime.datetime.now()
    return f"The current local time is {now.strftime('%I:%M %p on %B %d, %Y')}."

@mcp.tool()
def get_local_weather(city: str = "Austin") -> str:
    """Fetches weather for a city. Defaults to Austin."""
    api_key = "YOUR_OPENWEATHERMAP_API_KEY" # Replace with your real key if needed
    if api_key == "YOUR_OPENWEATHERMAP_API_KEY":
        return "Error: Weather API key not configured."
    url = f"https://openweathermap.org{city}&appid={api_key}&units=imperial"
    try:
        response = requests.get(url).json()
        temp = response["main"]["temp"]
        desc = response["weather"]["description"]
        return f"The current weather in {city.title()} is {temp}°F with {desc}."
    except Exception as e:
        return f"Error fetching weather: {str(e)}"

# ==================== SEPARATED RECIPE TOOLS ====================

@mcp.tool()
def save_recipe(recipe_name: str, ingredients: str, instructions: str) -> str:
    """Saves a structured recipe safely into the dedicated recipe book database table."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        query = "INSERT INTO recipes (recipe_name, ingredients, instructions) VALUES (%s, %s, %s);"
        cursor.execute(query, (recipe_name, ingredients, instructions))
        conn.commit()
        cursor.close()
        conn.close()
        return f"Successfully logged the recipe for '{recipe_name}' into your cookbook database!"
    except Exception as e:
        return f"Failed to save recipe. Error: {str(e)}"

@mcp.tool()
def read_recipe(dish_name: str) -> str:
    """Looks up a recipe from the cookbook table and formats fractions clearly for the screen."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        query = "SELECT recipe_name, ingredients, instructions FROM recipes WHERE recipe_name ILIKE %s ORDER BY id DESC LIMIT 1;"
        cursor.execute(query, (f"%{dish_name}%",))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not row:
            return f"I couldn't find any recipes for '{dish_name}' in your cookbook."
            
        name = clean_hardware_text(row[0])
        ing = clean_hardware_text(row[1])
        ins = clean_hardware_text(row[2])
        
        return f"RECIPE FOR {name.upper()}:\n\n[INGREDIENTS]\n{ing}\n\n[INSTRUCTIONS]\n{ins}"
    except Exception as e:
        return f"Error opening cookbook: {str(e)}"

@mcp.tool()
def list_recipes() -> str:
    """Lists every single dish saved inside the dedicated cookbook table."""
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT recipe_name FROM recipes ORDER BY recipe_name ASC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return "Your cookbook is currently empty. Tell me a recipe to save!"
            
        titles = [f"- {clean_hardware_text(row[0])}" for row in rows]
        return "Here are the recipes saved in your database cookbook:\n\n" + "\n".join(titles)
    except Exception as e:
        return f"Error viewing cookbook index: {str(e)}"

if __name__ == "__main__":
    initialize_database()
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)



