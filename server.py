import os
import psycopg2
import requests
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

port_env = int(os.environ.get("PORT", 8000))

# FIX: We add explicit time-range handling rules to the FastMCP initialization instructions
mcp = FastMCP(
    "AIPI_Lite_Dual_DB_Server",
    host="0.0.0.0",
    port=port_env,
    instructions="""
    You are an expert culinary assistant with access to a recipe database.
    
    CRITICAL SPEECH RULES FOR RECIPES:
    1. TIME RANGES: Cooking sites often write time ranges like '20-25 minutes' or '10-15 minutes'. If you see a massive four-digit time number like '2025 minutes' or '1015 minutes', you MUST recognize that this is a typo. Break it back up and speak it out loud as a time range (e.g., say 'twenty to twenty-five minutes' or 'ten to fifteen minutes'). Never tell the user to cook something for thousands of minutes.
    
    2. INGREDIENT AMOUNTS: Always speak and save the exact numeric amounts. Never say 'some' or 'a few' if numbers are present. Speak fractions out loud as full words (e.g., read '1/2' as 'one-half' and '1/4' as 'one-fourth').
    """
)

def get_memory_db():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("CRITICAL: DATABASE_URL variable is missing!")
    return psycopg2.connect(db_url)

def get_recipe_db():
    db_url = os.environ.get("RECIPE_DATABASE_URL")
    if not db_url:
        raise ValueError("CRITICAL: RECIPE_DATABASE_URL variable is missing!")
    return psycopg2.connect(db_url)

def initialize_databases():
    try:
        conn1 = get_memory_db()
        cur1 = conn1.cursor()
        cur1.execute("""
            CREATE TABLE IF NOT EXISTS memory_store (
                id SERIAL PRIMARY KEY,
                memory_key TEXT UNIQUE NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn1.commit()
        cur1.close()
        conn1.close()
        
        conn2 = get_recipe_db()
        cur2 = conn2.cursor()
        cur2.execute("""
            CREATE TABLE IF NOT EXISTS recipe_store (
                id SERIAL PRIMARY KEY,
                recipe_name TEXT UNIQUE NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                source_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn2.commit()
        cur2.close()
        conn2.close()
        print("Databases initialized.")
    except Exception as e:
        print(f"Init Error: {e}")

initialize_databases()

@mcp.tool()
def save_memory(key: str, value: str) -> str:
    """Saves a general personal memory fact to your personal memory database."""
    try:
        conn = get_memory_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO memory_store (memory_key, memory_value)
            VALUES (%s, %s)
            ON CONFLICT (memory_key) DO UPDATE SET memory_value = EXCLUDED.memory_value;
        """, (key, value))
        conn.commit()
        cur.close()
        conn.close()
        return f"SUCCESS: Saved key '{key}'."
    except Exception as e:
        return f"Memory Error: {str(e)}"

@mcp.tool()
def retrieve_memory(key: str) -> str:
    """Retrieves a general personal memory fact from your personal memory database."""
    try:
        conn = get_memory_db()
        cur = conn.cursor()
        cur.execute("SELECT memory_value FROM memory_store WHERE memory_key = %s;", (key,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return f"Found memory: {row}"
        return f"No memory found for key: '{key}'"
    except Exception as e:
        return f"Memory Error: {str(e)}"

@mcp.tool()
def search_web_for_recipe(dish_name: str) -> str:
    """Searches the internet for recipe links based on a food or dish name query."""
    try:
        search_url = f"https://duckduckgo.com{dish_name}+recipe"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        links = []
        for a in soup.find_all("a", class_="result__url"):
            href = a.get("href")
            if href and "http" in href:
                links.append(href)
        if not links:
            return "No recipe links found on the web."
        return f"Top recipe links found:\n" + "\n".join(links[:3])
    except Exception as e:
        return f"Search failed: {str(e)}"

@mcp.tool()
def search_and_scrape_recipe(url: str) -> str:
    """Extracts raw text data from a specific cooking webpage link to read ingredients and instructions."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Error code: {response.status_code}"
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text(separator=' \n ', strip=True)[:5000]
    except Exception as e:
        return f"Scraper error: {str(e)}"

@mcp.tool()
def save_recipe_to_db(recipe_name: str, ingredients: str, instructions: str, source_url: str = "") -> str:
    """Saves a structured food recipe exclusively into your private recipe database."""
    try:
        conn = get_recipe_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO recipe_store (recipe_name, ingredients, instructions, source_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (recipe_name) 
            DO UPDATE SET ingredients = EXCLUDED.ingredients, instructions = EXCLUDED.instructions;
        """, (recipe_name, ingredients, instructions, source_url))
        conn.commit()
        cur.close()
        conn.close()
        return f"SUCCESS: Saved '{recipe_name}' into recipe database."
    except Exception as e:
        return f"Recipe Save Error: {str(e)}"

@mcp.tool()
def retrieve_recipe_from_db(recipe_name: str) -> str:
    """Searches your isolated recipe database for a saved dish."""
    try:
        conn = get_recipe_db()
        cur = conn.cursor()
        cur.execute("SELECT ingredients, instructions FROM recipe_store WHERE recipe_name ILIKE %s;", (f"%{recipe_name}%",))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return f"RECIPE: {recipe_name}\n\nINGREDIENTS:\n{row}\n\nINSTRUCTIONS:\n{row}"
        return f"No recipe found for '{recipe_name}'."
    except Exception as e:
        return f"Recipe Retrieve Error: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="sse")















