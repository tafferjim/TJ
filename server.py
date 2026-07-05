import os
from fastmcp import FastMCP

# Initialize FastMCP
mcp = FastMCP("AIPI-Extension")

# Create a sample tool your AIPI Lite can call
@mcp.tool()
def roll_dice(sides: int = 6) -> str:
    """Rolls a virtual dice with a custom number of sides."""
    import random
    result = random.randint(1, sides)
    return f"You rolled a {result} on a {sides}-sided dice!"

if __name__ == "__main__":
    # Render automatically injects a dynamic $PORT variable.
    # We fall back to 8000 for local testing.
    port = int(os.environ.get("PORT", 8000))
    
    # Run the server using the SSE transport protocol over the web
    mcp.run(transport="sse", host="0.0.0.0", port=port)