import json
import psycopg2
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import cgi
from api.utils.image_upload import upload_image_to_supabase

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
            image_url = upload_image_to_supabase(image_file, "uploaded.jpg")

        # Connect to DB
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        if course_id:
            if delete:
                # Delete course
                cursor.execute("DELETE FROM courses WHERE id = %s", (course_id,))
                conn.commit()
                cursor.close()
                conn.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "action": "deleted"}).encode())
                return
            
            # Try to update the course
            cursor.execute("SELECT id FROM courses WHERE id = %s", (course_id,))
            existing = cursor.fetchone()

            if existing:
                # Update
                if image_url:  # Only update image if a new one was uploaded
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
                # Insert
                cursor.execute(
                    "INSERT INTO courses (id, title, pic_link, description) VALUES (%s, %s, %s, %s)",
                    (course_id, title, image_url, description)
                )
                action = "inserted"
        else:
            # No ID given — insert new
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
        # Grab pagination parameters
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)
        page = int(query_params.get("page", [1])[0])
        limit = int(query_params.get("limit", [10])[0])
        offset = (page - 1) * limit
        print(f"Fetching courses: page={page}, limit={limit}, offset={offset}")

        # Connect to Supabase (Postgres)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM courses ORDER BY id LIMIT %s OFFSET %s", (limit, offset))
        courses = cursor.fetchall()

        #find total number of pages
        cursor.execute("SELECT COUNT(*) FROM courses")
        total_courses = cursor.fetchone()[0]   
        total_pages = (total_courses + limit - 1) // limit

        courses_list = []
        for course in courses:
            sessions_list = []
            cursor.execute("SELECT * FROM sessions WHERE course_id = %s", (course[0],))
            sessions = cursor.fetchall()
            for session in sessions:
                sessions_list.append({
                    "id": session[0],
                    "start_date": session[1],
                    "end_date": session[2],
                })
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
        