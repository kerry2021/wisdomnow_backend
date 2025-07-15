from supabase import create_client
import os
import uuid

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # use service role key on backend
supabase = create_client(url, key)

def upload_image_to_supabase(image_bytes, filename):
    path = f"{uuid.uuid4().hex}_{filename}"
    supabase.storage.from_("course-images").upload(path, image_bytes)
    return f"{url}/storage/v1/object/public/course-images/{path}"