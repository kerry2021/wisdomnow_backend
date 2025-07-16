import json
import psycopg2
import os
import cgi
import uuid
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from api.utils.image_upload import upload_image_to_supabase
from supabase import create_client, Client

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']  # Needs delete permission
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

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
        ctype, pdict = cgi.parse_header(self.headers.get('Content-Type'))
        if ctype != 'multipart/form-data':
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Unsupported Content-Type')
            return

        pdict['boundary'] = bytes(pdict['boundary'], "utf-8")
        pdict['CONTENT-LENGTH'] = int(self.headers['Content-Length'])
        fields = cgi.parse_multipart(self.rfile, pdict)

        name = fields.get("name", [None])[0]
        email = fields.get("email", [None])[0]
        file_list = fields.get("image") 

        if not name or not email:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing name or email')
            return

        # Save image if present
        image_url = None
        if file_list:
            original_filename = fields.get("imageName", [None])[0]
            print(f"Original filename: {original_filename}")
            ext = os.path.splitext(original_filename)[-1].lower()
            if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
                ext = ".png"  # fallback default
            filename = f"{uuid.uuid4().hex}{ext}"
            file_data = file_list[0]            
            image_url = upload_image_to_supabase(file_data, filename, "user-images")
            print(f"Uploaded image URL: {image_url}")

        # Connect to Supabase (Postgres)
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        # Check if user exists and get its old pic_link
        cursor.execute("SELECT pic_link FROM users WHERE email = %s", (email,))        
        exists = cursor.fetchone()

        if exists:
            if image_url:
                old_pic_link = exists[0]
                old_filename = old_pic_link.split("/")[-1]
                if old_filename != filename:
                    try:
                        print("Deleting old file:", old_filename)
                        supabase.storage.from_("user-images").remove([old_filename])
                    except Exception as e:
                        print("Warning: failed to delete old file:", e)
                cursor.execute(
                    "UPDATE users SET name = %s, pic_link = %s WHERE email = %s",
                    (name, image_url, email)
                )
            else:
                cursor.execute(
                    "UPDATE users SET name = %s WHERE email = %s",
                    (name, email)
                )
        else:
            cursor.execute(
                "INSERT INTO users (name, email) VALUES (%s, %s)",
                (name, email)
            )

        conn.commit()
        cursor.close()
        conn.close()

        send_json(self, {"status": "ok"})

    def do_GET(self):
        parsed_path = urlparse(self.path)
        query_params = parse_qs(parsed_path.query)

        email = query_params.get("email", [None])[0]
        if not email:
            send_json(self, {"status": "error", "message": "Email parameter is required"}, status=400)
            return

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cursor = conn.cursor()

        # Fetch user profile
        cursor.execute("SELECT name, email, access_type, pic_link FROM users WHERE email = %s", (email,))
        user_profile = cursor.fetchone()
        cursor.close()
        conn.close()    

        if user_profile:
            response = {
                "status": "ok",
                "profile": {
                    "name": user_profile[0],
                    "email": user_profile[1],
                    "access_type": user_profile[2],
                    "pic_link": user_profile[3]
                }
            }
            send_json(self, response)
        else:
            send_json(self, {"status": "error", "message": "User not found"}, status=404)

