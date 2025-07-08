# cors_helper.py

def add_cors_headers(handler, origin='https://your-frontend-project.vercel.app'):
    handler.send_header('Access-Control-Allow-Origin', origin)
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
