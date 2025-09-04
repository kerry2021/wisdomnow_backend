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
    
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)        
        session_id = query_components.get("sessionId", [None])[0]
        user_id = query_components.get("userId", [None])[0]
        
        #access user's profile, get their name, email and profile picture
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        cursor.execute("SELECT name, email, pic_link FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        profile_info = {"name": user[0], "email": user[1], "pic_link": user[2]} if user else None        
        #find all session periods for the given session_id, and get the user's progress for each period
        cursor.execute(
            """ 
            SELECT sp.id, sp.start_date, sp.end_date, COALESCE(ssp.progress, 0) as progress, sp.total_pages 
            FROM session_periods sp 
            LEFT JOIN student_session_period ssp 
            ON sp.id = ssp.session_period_id AND ssp.user_id = %s 
            WHERE sp.session_id = %s
            """,
            (user_id, session_id)
        )
        periods = cursor.fetchall()        
        periods_list = [{"id": period[0], "start_date": period[1].isoformat() if period[1] else None, "end_date": period[2].isoformat() if period[2] else None, "progress": period[3], "total_pages": period[4]} for period in periods]
        #sort periods by start_date
        periods_list.sort(key=lambda x: x["start_date"] or "")

        cursor.close()
        conn.close()        
        send_json(self, {"status": "ok", "profile": profile_info, "periods": periods_list})
