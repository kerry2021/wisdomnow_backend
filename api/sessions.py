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

        sessionID = data.get("sessionId, None")
        courseID = data.get("courseId")
        startDate = data.get("startDate")
        endDate = data.get("endDate")
        instructorIds = data.get("instructorIds", [])
        print("Received data:", data)     
        
        
        # Connect to Supabase (Postgres)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        # Insert new session and get the session ID

        if sessionID:
            # Update existing session
            cursor.execute(
                "UPDATE sessions SET course_id = %s, start_date = %s, end_date = %s WHERE id = %s",
                (courseID, startDate, endDate, sessionID)
            )            

            # Delete existing instructors for this session
            cursor.execute("DELETE FROM session_instructors WHERE session_id = %s", (sessionID,))            
        else:
            cursor.execute(
                "INSERT INTO sessions (course_id, start_date, end_date) VALUES (%s, %s, %s) RETURNING id",
                (courseID, startDate, endDate)
            )            
            sessionID = cursor.fetchone()[0]

        # Insert instructors into session_instructors
        for instructorID in instructorIds:
            cursor.execute(
                "INSERT INTO session_instructors (session_id, instructor_id) VALUES (%s, %s)",
                (sessionID, instructorID)
            )
        conn.commit()
        cursor.close()
        conn.close()

        # Respond   
        send_json(self, {"status": "ok", "session_id": sessionID})

    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        session_id = params.get("id", [None])[0]

        #grab the session matching the session ID and all instructors for that session
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        if session_id:
            cursor.execute(
                "SELECT id, course_id, start_date, end_date FROM sessions WHERE id = %s",
                (session_id,)
            )
            session = cursor.fetchone()
            if not session:
                send_json(self, {"error": "Session not found"}, status=404)
                return

            session_data = {
                "id": session[0],
                "course_id": session[1],
                "start_date": session[2].isoformat() if session[2] else None,
                "end_date": session[3].isoformat() if session[3] else None,
                "instructors": []
            }

            cursor.execute(
                "SELECT users.id, users.name, users.pic_link FROM session_instructors join users ON instructor_id = users.id WHERE session_id = %s",
                (session_id,)
            )
            instructors = cursor.fetchall()
            for instructor in instructors:
                session_data["instructors"].append({
                    "id": instructor[0],
                    "name": instructor[1],
                    "pic_link": instructor[2]
                })
            send_json(self, session_data)
        
 





