import json
import psycopg2
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import cgi
from api.utils.image_upload import upload_image_to_supabase
from datetime import datetime

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
        print("OPTIONS request received")
        self.send_response(204)
        CORS_helper(self)
        self.end_headers()

    def do_DELETE(self):
        print("DELETE request received")
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        data = json.loads(body)
        course_id = data.get("courseId")

        if not course_id:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing courseId')
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
        conn.commit()
        cursor.close()
        conn.close()

        self.send_response(200)
        CORS_helper(self)
        self.end_headers()
        self.wfile.write(b'Course deleted successfully')

    def do_POST(self):
        ctype, pdict = cgi.parse_header(self.headers.get('Content-Type'))
        if ctype != 'multipart/form-data':
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Unsupported Content-Type')
            return

        pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
        pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
        fields = cgi.parse_multipart(self.rfile, pdict)

        course_id = fields.get("courseId", [None])[0]
        title = fields.get("courseName", [""])[0]
        description = fields.get("description", [""])[0]
        image_file = fields.get("image", [None])[0]
        delete = fields.get("delete", [None])[0]

        image_url = ""
        if image_file:
            image_url = upload_image_to_supabase(image_file, "uploaded.jpg", "course-images")

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        if course_id:
            cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
            existing = cursor.fetchone()

            if existing:
                if image_url:
                    cursor.execute(
                        "UPDATE courses SET title = %s, description = %s, pic_link = %s WHERE id = %s",
                        (title, description, image_url, course_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE courses SET title = %s, description = %s WHERE id = %s",
                        (title, description, course_id)
                    )
                action = "updated"
            else:
                cursor.execute(
                    "INSERT INTO courses (id, title, pic_link, description) VALUES (%s, %s, %s, %s)",
                    (course_id, title, image_url, description)
                )
                action = "inserted"
        else:
            cursor.execute(
                "INSERT INTO courses (title, pic_link, description) VALUES (%s, %s, %s)",
                (title, image_url, description)
            )
            action = "inserted"

        conn.commit()
        cursor.close()
        conn.close()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok", "action": action}).encode())

    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        page = int(query_params.get("page", [1])[0])
        limit = int(query_params.get("limit", [10])[0])
        offset = (page - 1) * limit
        language_filter = query_params.get("language", [None])[0]
        instructor_id = query_params.get("instructorId", [None])[0]
        student_id = query_params.get("studentId", [None])[0]
        start_date = query_params.get("startDate", [None])[0]
        end_date = query_params.get("endDate", [None])[0]

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM courses ORDER BY id LIMIT %s OFFSET %s", (limit, offset))
        courses = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM courses")
        total_courses = cursor.fetchone()[0]
        total_pages = (total_courses + limit - 1) // limit

        courses_list = []
        for course in courses:
            sessions_list = []
            session_query = "SELECT id, start_date, end_date, language FROM sessions WHERE course_id = %s"
            session_params = [course[0]]

            if start_date:
                session_query += " AND start_date >= %s"
                session_params.append(start_date)
            if end_date:
                session_query += " AND end_date <= %s"
                session_params.append(end_date)
            if language_filter:
                session_query += " AND language = %s"
                session_params.append(language_filter)

            print("query:", session_query, "params:", session_params)
            cursor.execute(session_query, session_params)
            sessions = cursor.fetchall()

            for session in sessions:
                if instructor_id:
                    cursor.execute("SELECT 1 FROM session_instructors WHERE session_id = %s AND instructor_id = %s", (session[0], instructor_id))
                    if cursor.fetchone() is None:
                        continue

                if student_id:
                    cursor.execute("SELECT 1 FROM session_students WHERE session_id = %s AND student_id = %s", (session[0], student_id))
                    if cursor.fetchone() is None:
                        continue

                cursor.execute("SELECT name FROM session_instructors JOIN users on instructor_id = users.user_id WHERE session_id = %s", (session[0],))
                instructors = cursor.fetchall()
                instructors_list = [instructor[0] for instructor in instructors]
                sessions_list.append({
                    "id": session[0],
                    "start_date": session[1].isoformat() if session[1] else None,
                    "end_date": session[2].isoformat() if session[2] else None,
                    "language": session[3],
                    "instructors": instructors_list
                })

            if sessions_list:
                courses_list.append({
                    "id": course[0],
                    "course_title": course[1],
                    "pic_link": course[2],
                    "description": course[3],
                    "sessions": sessions_list,
                    "pages_count": total_pages,
                })

        cursor.close()
        conn.close()
        print(f"Returning {len(courses_list)} courses")
        send_json(self, {"courses": courses_list, "page": page, "limit": limit})
        CORS_helper(self)
        