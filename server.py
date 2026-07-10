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
def get_local_weather(city: str = "Austin") -> str:
    """Fetches the current weather for a specific city. Defaults to Austin, Texas."""

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

@mcp.tool()
def scrape_and_save_recipe(url: str) -> str:
    """Fetches a recipe webpage from an online link, extracts the core text, and automatically saves it to the database."""
    import requests
    from bs4 import BeautifulSoup

    try:
        # 1. Fetch the webpage content with a standard user-agent header
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return f"Failed to reach the website. Status code: {response.status_code}"

        # 2. Parse the HTML and extract text from the core recipe layout elements
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strip out unwanted website clutter like navigation bars, ads, and footers
        for element in soup(["script", "style", "nav", "footer", "header", "form"]):
            element.decompose()

        # Extract remaining text lines cleanly
        raw_text = soup.get_text(separator="\n")
        cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        page_content = "\n".join(cleaned_lines[:300]) # Cap it to the first 300 lines to fit database lengths

        # 3. Connect to your database and push the scraped recipe straight in
        if not DB_URL:
            return "Error: DATABASE_URL environment variable is not set."
            
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        query = "INSERT INTO memories (memory_text) VALUES (%s);"
        
        # Format the entry title cleanly with the source URL
        database_entry = f"Scraped Recipe Link ({url}):\n\n{page_content}"
        
        cursor.execute(query, (database_entry,))
        conn.commit()
        cursor.close()
        conn.close()

        return f"Successfully scraped the link and imported the recipe data straight to your database!"

    except Exception as e:
        return f"Failed to pull recipe from link. Error: {str(e)}"

@mcp.tool()
def read_recipe(keyword: str, section: str = "all") -> str:
    """Retrieves a specific recipe from the database and breaks it down by section or step.
    
    Args:
        keyword: The name of the dish (e.g., 'cornbread', 'lasagna').
        section: Options are 'all', 'ingredients', 'instructions', or a step number like 'step 1'.
    """
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
        
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Search the database for any entry containing your keyword
        query = "SELECT memory_text FROM memories WHERE memory_text ILIKE %s ORDER BY id DESC LIMIT 1;"
        cursor.execute(query, (f"%{keyword}%",))
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not row:
            return f"I couldn't find any saved recipes matching '{keyword}' in your database."
            
        recipe_text = row[0]
        
        # If you ask for the whole thing
        if section.lower() == "all":
            return f"Found your recipe for {keyword}:\n\n{recipe_text}"
            
        # Let the AI filter the text block dynamically based on your request
        return (
            f"Here is the requested section ({section}) for your {keyword} recipe:\n\n"
            f"{recipe_text}\n\n"
            f"[AI Action: Please locate and read ONLY the requested '{section}' from the text above.]"
        )
        
    except Exception as e:
        return f"Failed to retrieve the recipe. Error: {str(e)}"

if __name__ == "__main__":
    initialize_database()
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)




