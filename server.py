import os
import psycopg2
import requests
import re
from bs4 import BeautifulSoup
from recipe_scrapers import scrape_me
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("AIPI_Lite_Dual_DB_Server")

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
        print("Independent databases initialized.")
    except Exception as e:
        print(f"Initialization Error: {e}")

initialize_databases()


# --- SPEECH AND FORMAT REPAIR FILTER ---
def fix_fractions_and_times(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\b1\s*/\s*2\b', ' one-half ', text)
    text = re.sub(r'\b1\s*/\s*3\b', ' one-third ', text)
    text = re.sub(r'\b2\s*/\s*3\b', ' two-thirds ', text)
    text = re.sub(r'\b1\s*/\s*4\b', ' one-fourth ', text)
    text = re.sub(r'\b3\s*/\s*4\b', ' three-fourths ', text)
    text = re.sub(r'\b1\s*/\s*8\b', ' one-eighth ', text)
    
    unicode_map = {
        '½': ' one-half ', '⅓': ' one-third ', '⅔': ' two-thirds ',
        '¼': ' one-fourth ', '¾': ' three-fourths ', '⅛': ' one-eighth '
    }
    for char, word in unicode_map.items():
        text = text.replace(char, word)

    def split_match(match):
        num_str = match.group(1)
        half = len(num_str) // 2
        return f" {num_str[:half]} to {num_str[half:]} "
    text = re.sub(r'\b(\d{4})\s*(minutes|mins|hours|hrs)\b', split_match, text, flags=re.IGNORECASE)
    return re.sub(r' +', ' ', text).strip()


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
            ON CONFLICT (memory_key) DO UPDATE SET memory_value = EXCLUDED.memory_value;
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


# --- DATABASE 2 TOOLS (RECIPES & AUTOMATED WEB SEARCHING) ---
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
    """Extracts purely isolated ingredients and instructions from a URL, ignoring blogger fluff."""
    try:
        scraper = scrape_me(url, wild_mode=True)
        ingredients_list = scraper.ingredients()
        clean_ingredients = "\n".join([fix_fractions_and_times(i) for i in ingredients_list])
        instructions_text = scraper.instructions()
        clean_instructions = fix_fractions_and_times(instructions_text)
        return f"INGREDIENTS:\n{clean_ingredients}\n\nINSTRUCTIONS:\n{clean_instructions}"
    except Exception as e:
        return f"Could not isolate structured data: {str(e)}"

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

# CRITICAL FIX: Expose the ASGI gateway mapping layer natively for Uvicorn
app = mcp.asgi()



















