import json
import psycopg2
import os
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):

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
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write("User registered.".encode("utf-8"))

    def do_GET(self):
        self.send_response(405)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write("Method Not Allowed".encode("utf-8"))
