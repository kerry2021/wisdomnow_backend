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
        # We only update the markdown text here
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)

        session_period_id = data.get("sessionPeriodId")
        mkd_text = data.get("markdownText")
        total_pages = data.get("totalPages")

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        if session_period_id:
            cursor.execute(
                "UPDATE session_periods SET content_md = %s, total_pages = %s WHERE id = %s",
                (mkd_text, total_pages, session_period_id)
            )
            conn.commit()
            cursor.close()
            conn.close()
            send_json(self, {"status": "success", "message": "Markdown text updated successfully"})
    
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        session_period_id = params.get("sessionPeriodId", [None])[0]

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        if session_period_id:
            cursor.execute(
                "SELECT id, session_id, start_date, end_date, content_md FROM session_periods WHERE id = %s",
                (session_period_id,)
            )
            session_period = cursor.fetchone()
            if session_period:
                response = {
                    "id": session_period[0],
                    "sessionId": session_period[1],
                    "startDate": session_period[2].isoformat() if session_period[2] else None,
                    "endDate": session_period[3].isoformat() if session_period[3] else None,
                    "markdownText": session_period[4]
                }
                send_json(self, response)
            else:
                send_json(self, {"error": "Session period not found"}, status=404)
        else:
            send_json(self, {"error": "No session period ID provided"}, status=400)

        cursor.close()
        conn.close()