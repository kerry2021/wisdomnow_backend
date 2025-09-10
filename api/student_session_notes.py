import json
import psycopg2
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

def CORS_helper(handler):
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")

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
        print(data)

        user_id = data.get("userId")
        session_id = data.get("sessionId")
        notes = data.get("notes")

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        #update if the same user_id and session_id already exists
        cursor.execute(
            """ 
            UPDATE session_students
            SET notes = %s 
            WHERE user_id = %s AND session_id = %s
            """,
            (notes, user_id, session_id)
        )

        if cursor.rowcount == 0:
            send_json(self, {"error": "No matching record found to update"}, status=404)
        
        else:
            conn.commit()
            send_json(self, {"status": "success", "message": "Notes updated successfully"})
        
        cursor.close()
        conn.close()
    
    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        user_id = query_params.get("userId", [None])[0]
        session_id = query_params.get("sessionId", [None])[0]

        if not user_id or not session_id:
            send_json(self, {"error": "Missing userId or sessionId parameter"}, status=400)
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        cursor.execute(
            """ 
            SELECT notes FROM session_students 
            WHERE user_id = %s AND session_id = %s
            """,
            (user_id, session_id)
        )

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result:
            send_json(self, {"notes": result[0]})
        else:
            send_json(self, {"error": "No notes found for the given userId and sessionId"}, status=404)
    


