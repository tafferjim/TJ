import os
import psycopg2
import requests
import re
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

port_env = int(os.environ.get("PORT", 8000))

# Initialize FastMCP Server
mcp = FastMCP(
    "AIPI_Lite_Dual_DB_Server",
    host="0.0.0.0",
    port=port_env
)

# --- DATABASE CONNECTION HELPERS ---
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


# --- AUTOMATIC DATABASE INITIALIZATION ---
def initialize_databases():
    try:
        # Initialize Memory Database
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
        
        # Initialize Separate Recipe Database
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
        print("Both independent databases initialized successfully.")
    except Exception as e:
        print(f"Error during dual database initialization: {e}")

initialize_databases()


# --- DATABASE 1 TOOLS (MEMORIES) ---
@mcp.tool()
def save_memory(key: str, value: str) -> str:
    """Saves a general personal memory fact to your personal memory database."""
    try:
        conn = get_memory_db()
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
        return f"SUCCESS: Saved personal fact under key '{key}'."
    except Exception as e:
        return f"Memory DB Error: {str(e)}"

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
        return f"No personal memory found for key: '{key}'"
    except Exception as e:
        return f"Memory DB Error: {str(e)}"


# --- FRACTION CLEANING HELPER ---
def clean_recipe_fractions(text: str) -> str:
    """Converts tricky fractions and slash notations into readable text for speech."""
    # 1. Convert unicode symbols to words
    unicode_map = {
        '½': ' one-half ', '⅓': ' one-third ', '⅔': ' two-thirds ',
        '¼': ' one-fourth ', '¾': ' three-fourths ', '⅛': ' one-eighth ',
        '⅜': ' three-eighths ', '⅝': ' five-eighths ', '⅞': ' seven-eighths '
    }
    for char, word in unicode_map.items():
        text = text.replace(char, word)
        
    # 2. Convert text fractions like 1/2 or 1/4 into words using text regex
    text = re.sub(r'\b1/2\b', ' one-half ', text)
    text = re.sub(r'\b1/3\b', ' one-third ', text)
    text = re.sub(r'\b2/3\b', ' two-thirds ', text)
    text = re.sub(r'\b1/4\b', ' one-fourth ', text)
    text = re.sub(r'\b3/4\b', ' three-fourths ', text)
    text = re.sub(r'\b1/8\b', ' one-eighth ', text)
    
    # 3. Clean up any accidental double spaces created by the swap
    text = re.sub(r' +', ' ', text)
    return text


# --- DATABASE 2 TOOLS (RECIPES & AUTOMATED WEB SEARCHING) ---
@mcp.tool()
def search_web_for_recipe(dish_name: str) -> str:
    """Searches the internet for recipe links based on a food or dish name query."""
    try:
        search_url = f"https://duckduckgo.com{dish_name}+recipe"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(search_url, headers=headers, timeout=10)
        
        soup = BeautifulSoup(response.text, "html.parser")
        links = []
        
        for a in soup.find_all("a", class_="result__url"):
            href = a.get("href")
            if href and "http" in href:
                links.append(href)
                
        if not links:
            return "No recipe links found on the web for that dish."
            
        return f"Top recipe links found:\n" + "\n".join(links[:3])
    except Exception as e:
        return f"Web search failed: {str(e)}"

@mcp.tool()
def search_and_scrape_recipe(url: str) -> str:
    """Extracts raw text data from a specific cooking webpage link to read ingredients and instructions."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return f"Failed to open link. Status code: {response.status_code}"
            
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
            
        raw_text = soup.get_text(separator=' \n ', strip=True)[:5000]
        
        # FIX: Filter all scraped text through the fraction cleaning filter
        clean_text = clean_recipe_fractions(raw_text)
        return clean_text
    except Exception as e:
        return f"Web scraper error: {str(e)}"

@mcp.tool()
def save_recipe_to_db(recipe_name: str, ingredients: str, instructions: str, source_url: str = "") -> str:
    """Saves a structured food recipe exclusively into your private recipe database."""
    try:
        conn = get_recipe_db()
        cur = conn.cursor()
        
        # Run clean rules on items being saved to the database as well
        safe_ingredients = clean_recipe_fractions(ingredients)
        safe_instructions = clean_recipe_fractions(instructions)
        
        cur.execute("""
            INSERT INTO recipe_store (recipe_name, ingredients, instructions, source_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (recipe_name) 
            DO UPDATE SET ingredients = EXCLUDED.ingredients, instructions = EXCLUDED.instructions;
        """, (recipe_name, safe_ingredients, safe_instructions, source_url))
        conn.commit()
        cur.close()
        conn.close()
        return f"SUCCESS: Saved '{recipe_name}' into your separate recipe database."
    except Exception as e:
        return f"Recipe DB Error: {str(e)}"

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
            return f"RECIPE: {recipe_name}\n\nINGREDIENTS:\n{row[0]}\n\nINSTRUCTIONS:\n{row[1]}"
        return f"No recipe found for '{recipe_name}' in your cooking database."
    except Exception as e:
        return f"Recipe DB Error: {str(e)}"


if __name__ == "__main__":
    mcp.run(transport="sse")













