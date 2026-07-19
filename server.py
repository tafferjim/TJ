import os
import psycopg2
import requests
from bs4 import BeautifulSoup
from fastmcp import FastMCP

mcp = FastMCP("AIPI-Memories-Extension")

DB_URL = os.environ.get("DATABASE_URL")
RECIPE_DB_URL = os.environ.get("RECIPE_DATABASE_URL")
MAILBOX_DB_URL = os.environ.get("MAILBOX_DATABASE_URL")


# ---------------------------------------------------------------------------
# Database initialization
# ---------------------------------------------------------------------------

def initialize_database():
    """Creates the memories table if it does not exist yet."""
    print(f"DB_URL is set: {bool(DB_URL)}", flush=True)
    if not DB_URL:
        print("DATABASE_URL not found. Skipping memory DB initialization.", flush=True)
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
        print("Memory database initialized successfully.", flush=True)
    except Exception as e:
        print(f"Memory database initialization failed: {str(e)}", flush=True)


def initialize_recipe_database():
    """Creates the recipe_store table (in the separate recipes database) if it does not exist yet."""
    print(f"RECIPE_DB_URL is set: {bool(RECIPE_DB_URL)}", flush=True)
    if not RECIPE_DB_URL:
        print("RECIPE_DATABASE_URL not found. Skipping recipe DB initialization.", flush=True)
        return
    try:
        conn = psycopg2.connect(RECIPE_DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recipe_store (
                id SERIAL PRIMARY KEY,
                recipe_name TEXT UNIQUE NOT NULL,
                ingredients TEXT NOT NULL,
                instructions TEXT NOT NULL,
                source_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Recipe database initialized successfully.", flush=True)
    except Exception as e:
        print(f"Recipe database initialization failed: {str(e)}", flush=True)

def initialize_mailbox_database():
    """Creates the mailbox table (in the separate mailbox database) if it does not exist yet."""
    print(f"MAILBOX_DB_URL is set: {bool(MAILBOX_DB_URL)}", flush=True)
    if not MAILBOX_DB_URL:
        print("MAILBOX_DATABASE_URL not found. Skipping mailbox DB initialization.", flush=True)
        return
    try:
        conn = psycopg2.connect(MAILBOX_DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mailbox (
                id SERIAL PRIMARY KEY,
                from_device TEXT NOT NULL,
                to_device TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                read_at TIMESTAMP
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Mailbox database initialized successfully.", flush=True)
    except Exception as e:
        print(f"Mailbox database initialization failed: {str(e)}", flush=True)


# ---------------------------------------------------------------------------
# Existing memory tools (unchanged from the working version)
# ---------------------------------------------------------------------------

@mcp.tool()
def save_memory(content: str) -> str:
    """Saves a new long-term memory or fact about the user to the external database."""
    print(f"save_memory CALLED with content: {content!r}", flush=True)
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO memories (memory_text) VALUES (%s);", (content,))
        conn.commit()
        cursor.close()
        conn.close()
        print("save_memory: insert committed successfully", flush=True)
        return f"Successfully saved to your Render database: '{content}'"
    except Exception as e:
        print(f"save_memory FAILED: {str(e)}", flush=True)
        return f"Failed to save memory. Error: {str(e)}"


@mcp.tool()
def get_memories() -> str:
    """Retrieves all memories as a simple text list."""
    print("get_memories CALLED", flush=True)
    if not DB_URL:
        return "Error: DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT memory_text FROM memories ORDER BY id ASC;")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        print(f"get_memories: retrieved {len(rows)} rows", flush=True)
        if not rows:
            return "The memories table exists, but it is currently empty! Try saving a memory first."
        memory_list = [f"- {str(row[0])}" for row in rows]
        return "Here are the saved memories extracted directly from the database:\n\n" + "\n".join(memory_list)
    except Exception as e:
        print(f"get_memories FAILED: {str(e)}", flush=True)
        return f"Failed to retrieve memories. Error: {str(e)}"


@mcp.tool()
def delete_last_memory() -> str:
    """Deletes the single most recently saved memory from the database. No ID required."""
    print("delete_last_memory CALLED", flush=True)
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
        mem_id, mem_text = row
        cursor.execute("DELETE FROM memories WHERE id = %s;", (mem_id,))
        conn.commit()
        cursor.close()
        conn.close()
        print(f"delete_last_memory: deleted id={mem_id}", flush=True)
        return f"Successfully erased the most recent memory: '{mem_text}'"
    except Exception as e:
        print(f"delete_last_memory FAILED: {str(e)}", flush=True)
        return f"Failed to delete the last memory. Error: {str(e)}"


# ---------------------------------------------------------------------------
# New recipe tools (merged from the old script, bug fixed, separate database)
# ---------------------------------------------------------------------------

@mcp.tool()
def search_and_scrape_recipe(url: str) -> str:
    """Extracts raw text data from a recipe webpage URL to help find ingredients and instructions."""
    print(f"search_and_scrape_recipe CALLED with url: {url!r}", flush=True)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            print(f"search_and_scrape_recipe: bad status {response.status_code}", flush=True)
            return f"Failed to fetch webpage. Status code: {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator=" \n ", strip=True)
        print("search_and_scrape_recipe: scrape succeeded", flush=True)
        # Return the first 5000 characters so the AI doesn't overload on data
        return text[:5000]
    except Exception as e:
        print(f"search_and_scrape_recipe FAILED: {str(e)}", flush=True)
        return f"Web scraping error: {str(e)}"


@mcp.tool()
def save_recipe_to_db(recipe_name: str, ingredients: str, instructions: str, source_url: str = "") -> str:
    """Saves a fully formatted recipe directly into the recipe database."""
    print(f"save_recipe_to_db CALLED with recipe_name: {recipe_name!r}", flush=True)
    if not RECIPE_DB_URL:
        return "Error: RECIPE_DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(RECIPE_DB_URL)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO recipe_store (recipe_name, ingredients, instructions, source_url)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (recipe_name)
            DO UPDATE SET ingredients = EXCLUDED.ingredients,
                          instructions = EXCLUDED.instructions,
                          source_url = EXCLUDED.source_url;
        """, (recipe_name, ingredients, instructions, source_url))
        conn.commit()
        cursor.close()
        conn.close()
        print("save_recipe_to_db: insert/update committed successfully", flush=True)
        return f"SUCCESS: '{recipe_name}' has been safely stored in your recipe database."
    except Exception as e:
        print(f"save_recipe_to_db FAILED: {str(e)}", flush=True)
        return f"Database Error while saving recipe: {str(e)}"


@mcp.tool()
def retrieve_recipe_from_db(recipe_name: str) -> str:
    """Searches the recipe database for a previously saved recipe."""
    print(f"retrieve_recipe_from_db CALLED with recipe_name: {recipe_name!r}", flush=True)
    if not RECIPE_DB_URL:
        return "Error: RECIPE_DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(RECIPE_DB_URL)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ingredients, instructions FROM recipe_store WHERE recipe_name ILIKE %s;",
            (f"%{recipe_name}%",),
        )
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            print("retrieve_recipe_from_db: found match", flush=True)
            return f"RECIPE: {recipe_name}\n\nINGREDIENTS:\n{row[0]}\n\nINSTRUCTIONS:\n{row[1]}"
        print("retrieve_recipe_from_db: no match found", flush=True)
        return f"No recipe found in your database named '{recipe_name}'."
    except Exception as e:
        print(f"retrieve_recipe_from_db FAILED: {str(e)}", flush=True)
        return f"Database Error while retrieving recipe: {str(e)}"

# ---------------------------------------------------------------------------
# New inter-device mailbox tools
# ---------------------------------------------------------------------------

@mcp.tool()
def leave_note(from_device: str, message: str, to_device: str = "") -> str:
    """Leaves a note for another AIPI device to find, or broadcasts to all devices if to_device is blank."""
    print(f"leave_note CALLED from {from_device!r} to {to_device!r}", flush=True)
    if not MAILBOX_DB_URL:
        return "Error: MAILBOX_DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(MAILBOX_DB_URL)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO mailbox (from_device, to_device, message) VALUES (%s, %s, %s);",
            (from_device, to_device or None, message),
        )
        conn.commit()
        cursor.close()
        conn.close()
        return f"Note left for {to_device or 'anyone'}."
    except Exception as e:
        print(f"leave_note FAILED: {str(e)}", flush=True)
        return f"Failed to leave note. Error: {str(e)}"


@mcp.tool()
def check_notes(device_name: str) -> str:
    """Checks for unread notes addressed to this device or broadcast to all devices."""
    print(f"check_notes CALLED for {device_name!r}", flush=True)
    if not MAILBOX_DB_URL:
        return "Error: MAILBOX_DATABASE_URL environment variable is not set."
    try:
        conn = psycopg2.connect(MAILBOX_DB_URL)
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, from_device, message FROM mailbox
               WHERE (to_device = %s OR to_device IS NULL) AND read_at IS NULL
               ORDER BY created_at;""",
            (device_name,),
        )
        rows = cursor.fetchall()
        if rows:
            ids = [r[0] for r in rows]
            cursor.execute("UPDATE mailbox SET read_at = CURRENT_TIMESTAMP WHERE id = ANY(%s);", (ids,))
            conn.commit()
        cursor.close()
        conn.close()
        if not rows:
            return "No new notes."
        return "; ".join(f"{r[1]} says: {r[2]}" for r in rows)
    except Exception as e:
        print(f"check_notes FAILED: {str(e)}", flush=True)
        return f"Failed to check notes. Error: {str(e)}"


if __name__ == "__main__":
    initialize_database()
    initialize_recipe_database()
    initialize_mailbox_database()
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on port {port}", flush=True)
    mcp.run(transport="sse", host="0.0.0.0", port=port)
