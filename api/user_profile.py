import json
import psycopg2
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

def CORS_helper(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

def send_json(handler, obj, status=200):    
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    CORS_helper(handler)
    handler.end_headers()
    handler.wfile.write(json.dumps(obj).encode("utf-8"))

class handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(204)
        CORS_helper(self)
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)

        name = data.get("name")
        email = data.get("email")
        print("Received data:", data)

        # Connect to Supabase (Postgres)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        exists = cursor.fetchone()

        if exists:
            cursor.execute(
                "Update users SET name = %s WHERE email = %s",
                (name, email)
            )
            conn.commit()

        cursor.close()
        conn.close()

        # Respond   
        send_json(self, {"status": "ok"}) 

    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        email = query_params.get("email", [None])[0]
        if not email:
            send_json(self, {"status": "error", "message": "Email parameter is required"}, status=400)
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        # Fetch user profile
        cursor.execute("SELECT name, email, access_type FROM users WHERE email = %s", (email,))
        user_profile = cursor.fetchone()
        cursor.close()
        conn.close()    

        if user_profile:
            response = {
                "status": "ok",
                "profile": {
                    "name": user_profile[0],
                    "email": user_profile[1],
                    "access_type": user_profile[2]
                }
            }
            send_json(self, response)
        else:
            send_json(self, {"status": "error", "message": "User not found"}, status=404)

