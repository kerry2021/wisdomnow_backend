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
        session_period_id = data.get("sessionPeriodId")
        progress = data.get("progress")

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()    

        #check if the same user_id and session_period_id already exists
        cursor.execute(
            """ 
            SELECT id, progress FROM student_session_period 
            WHERE user_id = %s AND session_period_id = %s
            """,
            (user_id, session_period_id)
        )

        pass_progress = cursor.fetchone()

        if pass_progress:
            if progress <= pass_progress[1]:
                #no need to update, return success
                send_json(self, {"status": "success", "message": "No update needed, existing progress is higher or equal"})
                return
            
            cursor.execute(
                """ 
                UPDATE student_session_period 
                SET progress = %s 
                WHERE user_id = %s AND session_period_id = %s
                """,
                (progress, user_id, session_period_id)
            )
        else:                
            cursor.execute(
                """ 
                INSERT INTO student_session_period (user_id, session_period_id, progress)
                VALUES (%s, %s, %s)
                """,
                (user_id, session_period_id, progress)
            )
        conn.commit()
        cursor.close()
        conn.close()
        print("User session period updated successfully")
        send_json(self, {"status": "success", "message": "User session period updated successfully"})
        