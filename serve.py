import http.server
import socketserver
import os

# Define the port the server will run on
PORT = 8000
# Define the directory to serve
DIRECTORY = "frontend"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # We change the directory before initializing the server
        super().__init__(*args, directory=DIRECTORY, **kwargs)

# Start the server
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving the '{DIRECTORY}' directory at http://localhost:{PORT}")
    # This will keep the server running until you stop it (e.g., with Ctrl+C)
    httpd.serve_forever()