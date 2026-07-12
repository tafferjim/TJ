import os
import sys
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import psycopg2

def get_memory_db():
    url = os.environ.get("DATABASE_URL", "")
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgres://", 1)
    return psycopg2.connect(url, sslmode="require")

try:
    conn = get_memory_db()
    with conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_store (
                    id SERIAL PRIMARY KEY,
                    memory_key TEXT UNIQUE NOT NULL,
                    memory_value TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
    print("DATABASE SYSTEM SYNCHRONIZED SUCCESSFULLY.")
except Exception as e:
    print(f"CRITICAL DATABASE INITIALIZATION ERROR: {e}")

TOOL_MANIFEST = [
    {
        "name": "save_memory",
        "description": "Saves personal facts and codes to the database.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "string"}
            },
            "required": ["key", "value"]
        }
    }
]

class MasterMCPHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        """Universal handshake stream that catches any device GET handshake."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        init_payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "result": {"tools": TOOL_MANIFEST}
        }
        
        try:
            # Send explicit event line format headers
            self.wfile.write(b"event: endpoint\n")
            self.wfile.write(f"data: /mcp/sse\n\n".encode("utf-8"))
            self.wfile.flush()

            self.wfile.write(b"event: message\n")
            self.wfile.write(f"data: {json.dumps(init_payload)}\n\n".encode("utf-8"))
            self.wfile.flush()
            
            while True:
                time.sleep(4)
                self.wfile.write(b"event: ping\ndata: {}\n\n")
                self.wfile.flush()
        except (ConnectionResetError, BrokenPipeError):
            pass

    def do_POST(self):
        """Universal database capture tool: Intercepts all inputs and writes to Postgres rows."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        
        try:
            body = json.loads(post_data)
        except Exception:
            body = {"raw_payload": post_data}

        params = body.get("params", {})
        method = body.get("method", "")
        request_id = body.get("id", 1)

        if method in ["initialize", "mcp.initialize"]:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "MasterMemoryServer", "version": "1.0.0"}
                }
            }
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
            return

        # UNIVERSAL INTERCEPTOR: Catch any text string keys passed from the device firmware
        arguments = params.get("arguments") or body.get("arguments") or params or body
        
        # Flatten dictionary elements cleanly to map directly into text cells
        key_val = arguments.get("key") or arguments.get("memory_key") or arguments.get("text") or "test_pin"
        value_val = arguments.get("value") or arguments.get("memory_value") or str(arguments)

        # Force key normalization to preserve "test pin" variations explicitly
        if "pin" in str(value_val).lower() and key_val == "test_pin":
            key_val = "test pin"

        db_conn = None
        try:
            db_conn = get_memory_db()
            with db_conn:
                with db_conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO memory_store (memory_key, memory_value) 
                        VALUES (%s, %s) 
                        ON CONFLICT (memory_key) 
                        DO UPDATE SET memory_value = EXCLUDED.memory_value;
                    """, (str(key_val), str(value_val)))
            
            # Formulate the explicit successful layout string the AIPI engine is listening for
            reply_text = f"SUCCESS: Stored your {key_val} memory entry."
        except Exception as database_error:
            reply_text = f"Database tracking configuration fault: {database_error}"
        finally:
            if db_conn:
                db_conn.close()

        # Build clean JSON-RPC frame layout blocks
        reply_payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": reply_text}],
                "isError": False
            }
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(reply_payload).encode("utf-8"))

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), MasterMCPHandler)
    print(f"MASTER APPLICATION RUNNING ON PORT {port}...")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
