import os
import sys
import json
import mimetypes
import shutil
import subprocess
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
CATALOG_PATH = os.path.join(BASE_DIR, "design_catalog.json")
WEB_DIR = os.path.join(BASE_DIR, "web")
PORT = 8080

class DesignRefHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet standard logs
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/ensure_local":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
            
            folder = body.get("folder", "general")
            fname = body.get("filename", "ref.jpg")
            img_url = body.get("image_url", "")
            thumb_url = body.get("thumbnail_url", "")
            
            target_dir = os.path.join(DOWNLOADS_DIR, folder)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, fname)
            
            if not (os.path.exists(target_path) and os.path.getsize(target_path) > 1024):
                tmp_path = target_path + ".tmp"
                try:
                    subprocess.run(["curl.exe", "-s", "--max-time", "15", img_url, "-o", tmp_path], timeout=18)
                    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
                        with open(tmp_path, "rb") as f:
                            head = f.read(200)
                        if b"<!DOCTYPE" in head or b"<html" in head:
                            if thumb_url:
                                subprocess.run(["curl.exe", "-s", "--max-time", "15", thumb_url, "-o", tmp_path], timeout=18)
                        if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
                            os.replace(tmp_path, target_path)
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    if os.path.exists(tmp_path):
                        try: os.remove(tmp_path)
                        except: pass

            exists = os.path.exists(target_path) and os.path.getsize(target_path) > 1024
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "ok": exists,
                "local_url": f"/downloads/{folder}/{urllib.parse.quote(fname)}" if exists else None,
                "local_file_path": target_path,
                "file_uri": "file:///" + target_path.replace("\\", "/")
            }).encode("utf-8"))
            return

        self.send_error(404, "Endpoint not found")

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            local_count = 0
            total_bytes = 0
            breakdown = {}
            if os.path.exists(DOWNLOADS_DIR):
                for root, dirs, files in os.walk(DOWNLOADS_DIR):
                    rel = os.path.relpath(root, DOWNLOADS_DIR)
                    valid_files = [f for f in files if not f.endswith(".tmp")]
                    if valid_files and rel != ".":
                        breakdown[rel] = len(valid_files)
                    for f in valid_files:
                        p = os.path.join(root, f)
                        local_count += 1
                        total_bytes += os.path.getsize(p)
                        
            catalog_count = 0
            if os.path.exists(CATALOG_PATH):
                try:
                    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                        catalog_count = len(json.load(f))
                except: pass
                
            drive = os.path.splitdrive(BASE_DIR)[0] or "C:"
            _, _, free = shutil.disk_usage(drive)
            
            resp = {
                "local_images": local_count,
                "local_size_mb": round(total_bytes / (1024 * 1024), 2),
                "catalog_total": catalog_count,
                "free_disk_gb": round(free / (1024 ** 3), 2),
                "breakdown": breakdown,
                "downloads_path": DOWNLOADS_DIR
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        elif path == "/api/catalog":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            if os.path.exists(CATALOG_PATH):
                with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                    catalog = json.load(f)
                for it in catalog:
                    folder = it.get("folder", "")
                    fname = it.get("filename", "")
                    loc = os.path.join(DOWNLOADS_DIR, folder, fname)
                    if os.path.exists(loc) and os.path.getsize(loc) > 1024:
                        it["is_local"] = True
                        it["local_url"] = f"/downloads/{folder}/{urllib.parse.quote(fname)}"
                    else:
                        it["is_local"] = False
                        it["local_url"] = None
                    it["local_file_path"] = loc
                    it["file_uri"] = "file:///" + loc.replace("\\", "/")
                self.wfile.write(json.dumps(catalog).encode("utf-8"))
            else:
                self.wfile.write(json.dumps([]).encode("utf-8"))
            return

        elif path.startswith("/downloads/"):
            rel_path = urllib.parse.unquote(path[len("/downloads/"):])
            full_path = os.path.join(DOWNLOADS_DIR, rel_path)
            if os.path.exists(full_path) and os.path.isfile(full_path):
                mime, _ = mimetypes.guess_type(full_path)
                if not mime:
                    if full_path.endswith(".webp"):
                        mime = "image/webp"
                    else:
                        mime = "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(os.path.getsize(full_path)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                with open(full_path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
                return
            else:
                self.send_error(404, "File not found")
                return

        if path == "/" or path == "/index.html":
            target_file = os.path.join(WEB_DIR, "index.html")
        else:
            clean_path = path.lstrip("/")
            target_file = os.path.join(WEB_DIR, clean_path)

        if os.path.exists(target_file) and os.path.isfile(target_file):
            mime, _ = mimetypes.guess_type(target_file)
            self.send_response(200)
            self.send_header("Content-Type", mime or "text/html")
            self.send_header("Content-Length", str(os.path.getsize(target_file)))
            self.end_headers()
            with open(target_file, "rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return

        self.send_error(404, "Not Found")

def run():
    os.makedirs(WEB_DIR, exist_ok=True)
    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingHTTPServer(server_address, DesignRefHandler)
    print("=" * 60, flush=True)
    print(f"DESIGN REFERENCE WEB SERVER READY", flush=True)
    print(f"URL: http://localhost:{PORT}", flush=True)
    print(f"Web Root: {WEB_DIR}", flush=True)
    print(f"Downloads: {DOWNLOADS_DIR}", flush=True)
    print("=" * 60, flush=True)
    httpd.serve_forever()

if __name__ == "__main__":
    run()
