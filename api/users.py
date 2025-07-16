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

        if not exists:
            cursor.execute(
                "INSERT INTO users (name, email, access_type) VALUES (%s, %s, %s)",
                (name, email, "student")
            )
            conn.commit()

        cursor.close()
        conn.close()

        # Respond   
        send_json(self, {"status": "ok"}) 

    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        access_type = query_params.get("access_type", [None])[0]
        #get all users and filter by access_type
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        if access_type == "all":
            cursor.execute("SELECT user_id, name, pic_link FROM users")
        elif access_type:
            cursor.execute("SELECT user_id, name, pic_link FROM users WHERE access_type = %s", (access_type,))
        else:
            print("Error: access_type not provided")
            self.send_response(400)


        users = cursor.fetchall()
        cursor.close()
        conn.close()
        user_list = [{"user_id": user[0], "name": user[1], "pic_link": user[2]} for user in users]
        send_json(self, user_list)
        
