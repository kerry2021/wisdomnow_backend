import json
import psycopg2
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import timedelta, datetime

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

        sessionID = data.get("sessionId")
        courseID = data.get("courseId")
        startDate = data.get("startDate")
        endDate = data.get("endDate")
        instructorIds = data.get("instructorIds", [])
        periodDays = data.get("periodDays", 7)
        periodLabel = data.get("periodLabel", "Week")
        print("Received data:", data)     
        
        
        # Connect to Supabase (Postgres)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        # Insert new session and get the session ID

        if sessionID:
            # Delete existing instructors for this session
            cursor.execute("DELETE FROM session_instructors WHERE session_id = %s", (sessionID,))            
        else:
            cursor.execute(
                "INSERT INTO sessions (course_id, start_date, end_date, period_label) VALUES (%s, %s, %s, %s) RETURNING id",
                (courseID, startDate, endDate, periodLabel)
            )            
            sessionID = cursor.fetchone()[0]

            #if period days is provided, create periods based on the start and end dates
            if periodDays:
                period_start = datetime.fromisoformat(startDate)
                period_end = period_start + timedelta(days=periodDays)
                while period_end < datetime.fromisoformat(endDate):
                    cursor.execute(
                        "INSERT INTO session_periods (session_id, start_date, end_date) VALUES (%s, %s, %s)",
                        (sessionID, period_start.strftime('%Y-%m-%d'), period_end.strftime('%Y-%m-%d'))                      
                    )
                    period_start = period_end
                    period_end += timedelta(days=periodDays)

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
        session_id = params.get("sessionId", [None])[0]
        print(f"Fetching session with ID: {session_id}")

        #grab the session matching the session ID and all instructors for that session
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        
        if session_id:
            cursor.execute(
                "SELECT id, course_id, start_date, end_date, period_label FROM sessions WHERE id = %s",
                (session_id,)
            )
            session = cursor.fetchone()
            if not session:
                send_json(self, {"error": "Session not found"}, status=404)
                return
            
            # Grab session periods
            cursor.execute(
                "SELECT id, start_date, end_date FROM session_periods WHERE session_id = %s",
                (session_id,)
            )
            periods = cursor.fetchall()
            periods_list = [{"id": period[0], "start_date": period[1].isoformat() if period[1] else None, "end_date": period[2].isoformat() if period[2] else None} for period in periods]

            session_data = {
                "id": session[0],
                "course_id": session[1],
                "start_date": session[2].isoformat() if session[2] else None,
                "end_date": session[3].isoformat() if session[3] else None,
                "period_label": session[4],
                "instructors": [],
                "periods": periods_list
            }

            cursor.execute(
                "SELECT users.id, users.email, users.name, users.pic_link FROM session_instructors join users ON instructor_id = users.user_id WHERE session_id = %s",
                (session_id,)
            )
            instructors = cursor.fetchall()
            for instructor in instructors:
                session_data["instructors"].append({
                    "id": instructor[0],
                    "email": instructor[1],
                    "name": instructor[2],
                    "pic_link": instructor[3]
                })
            print(f"Session data: {session_data}")
            send_json(self, session_data)
        
 
    def do_DELETE(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        session_id = params.get("sessionId", [None])[0]
        print(f"Deleting session with ID: {session_id}")

        if not session_id:
            send_json(self, {"error": "Session ID is required"}, status=400)
            return

        # Connect to Supabase (Postgres)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        # Delete the session and its related data
        cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        send_json(self, {"status": "ok", "action": "deleted"})




