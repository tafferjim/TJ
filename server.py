import os
from fastmcp import FastMCP

mcp = FastMCP("AIPI-Extension")

# Tool 1: The Dice Roller (Already working!)
@mcp.tool()
def roll_dice(sides: int = 6) -> str:
    """Rolls a virtual dice with a custom number of sides."""
    import random
    result = random.randint(1, sides)
    return f"You rolled a {result} on a {sides}-sided dice!"

# Tool 2: New Coin Flipper
@mcp.tool()
def flip_coin() -> str:
    """Flips a coin to return heads or tails."""
    import random
    return f"The coin landed on {random.choice(['Heads', 'Tails'])}!"

# Tool 3: New Personalized dynamic greeting
@mcp.tool()
def get_motivational_quote(name: str) -> str:
    """Generates a quick custom motivational boost for the user."""
    import random
    quotes = [
        "You are doing great things today!",
        "Every small step leads to big progress.",
        "Keep pushing forward, you've got this!"
    ]
    return f"Hey {name}, here is your boost: {random.choice(quotes)}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
