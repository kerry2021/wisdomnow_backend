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

    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        session_id = query_params.get("session_id", [None])[0]
        role = query_params.get("role", [None])[0]  # either "applicant" or "student"

        if not session_id or not role:
            send_json(self, {"error": "Missing session_id or role parameter"}, status=400)
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        if role == "applicant":
            cursor.execute("""
                SELECT u.user_id, u.name, u.pic_link 
                FROM session_applicants sa
                JOIN users u ON sa.user_id = u.user_id
                WHERE sa.session_id = %s
            """, (session_id,))
        elif role == "student":
            cursor.execute("""
                SELECT u.user_id, u.name, u.pic_link 
                FROM session_students ss
                JOIN users u ON ss.user_id = u.user_id
                WHERE ss.session_id = %s
            """, (session_id,))
        else:
            send_json(self, {"error": "Invalid role parameter, must be 'applicant' or 'student'"}, status=400)
            return

        users = cursor.fetchall()
        cursor.close()
        conn.close()

        user_list = [{"user_id": u[0], "name": u[1], "pic_link": u[2]} for u in users]
        send_json(self, user_list)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)

        session_id = data.get("session_id")
        user_id = data.get("user_id")
        role = data.get("role")  # either "applicant" or "student"

        print(f"Received POST data: session_id={session_id}, user_id={user_id}, role={role}")

        if not session_id or not user_id or not role:
            send_json(self, {"error": "Missing session_id, user_id, or role"}, status=400)
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        try:
            if role == "applicant":
                cursor.execute("""
                    INSERT INTO session_applicants (session_id, user_id, application_date)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT DO NOTHING
                """, (session_id, user_id))

            elif role == "student":
                cursor.execute("""
                    INSERT INTO session_students (session_id, user_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (session_id, user_id))

                cursor.execute("""
                    DELETE FROM session_applicants
                    WHERE session_id = %s AND user_id = %s
                """, (session_id, user_id))
            else:
                send_json(self, {"error": "Invalid role, must be 'applicant' or 'student'"}, status=400)
                return

            conn.commit()
            send_json(self, {"status": "success"})

        except Exception as e:
            conn.rollback()
            send_json(self, {"error": str(e)}, status=500)
        finally:
            cursor.close()
            conn.close()

    def do_DELETE(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)

        session_id = data.get("session_id")
        user_id = data.get("user_id")
        role = data.get("role")  # either "applicant" or "student"

        print(f"Received DELETE request: session_id={session_id}, user_id={user_id}, role={role}")

        if not session_id or not user_id or not role:
            send_json(self, {"error": "Missing session_id, user_id, or role parameter"}, status=400)
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        try:
            if role == "applicant":
                cursor.execute("""
                    DELETE FROM session_applicants
                    WHERE session_id = %s AND user_id = %s
                """, (session_id, user_id))
            elif role == "student":
                cursor.execute("""
                    DELETE FROM session_students
                    WHERE session_id = %s AND user_id = %s
                """, (session_id, user_id))
            else:
                send_json(self, {"error": "Invalid role, must be 'applicant' or 'student'"}, status=400)
                return

            conn.commit()
            send_json(self, {"status": "deleted"})

        except Exception as e:
            conn.rollback()
            send_json(self, {"error": str(e)}, status=500)
        finally:
            cursor.close()
            conn.close()

