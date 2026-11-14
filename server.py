# -*- coding: utf-8 -*-
"""Server lokal untuk EPR Achievement Dashboard + Verifikasi Sell Out."""
import argparse
import datetime
import json
import mimetypes
import os
import shutil
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
ENGINE_DIR = os.path.join(ROOT, "engine")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")
INBOX_DIR = os.path.join(ROOT, "inbox")
PROCESSED_DIR = os.path.join(ROOT, "processed")
OUT_DIR = os.path.join(ROOT, "out")
for d in (INBOX_DIR, PROCESSED_DIR, OUT_DIR):
    os.makedirs(d, exist_ok=True)

sys.path.insert(0, ENGINE_DIR)
sys.path.insert(0, SCRIPTS_DIR)

import epr_build as B
import epr_db as D
import epr_tool as T
import export_from_db

LOCK = threading.Lock()
JOB = {
    "running": False,
    "done": False,
    "error": "",
    "logs": [],
    "files": [],
    "stats": None,
}


def _emit(msg):
    with LOCK:
        JOB["logs"].append(msg)


def _run_verify(file_path, build_excel):
    try:
        if not D.sku_all() and os.path.exists(T.SKU_FILE):
            n = D.sku_replace(T.import_sku(T.SKU_FILE))
            _emit(f"Database SKU diisi: {n} model")

        res = B.build([file_path], emit=_emit, out_dir=OUT_DIR, build_excel=build_excel)

        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        name = os.path.basename(file_path)
        dst = os.path.join(PROCESSED_DIR, name)
        if os.path.exists(dst):
            stem, ext = os.path.splitext(name)
            dst = os.path.join(PROCESSED_DIR, f"{stem}_{stamp}{ext}")
        shutil.move(file_path, dst)
        _emit(f"File input dipindahkan ke processed/{os.path.basename(dst)}")

        export_from_db.export_data(
            tool_dir=ROOT,
            out_path=os.path.join(ROOT, "data", "epr_data.json"),
        )
        _emit("Dashboard data (data/epr_data.json) berhasil diperbarui.")

        with LOCK:
            JOB["files"] = res.get("files", [])
            JOB["stats"] = res.get("stats")
            JOB["done"] = True
            JOB["running"] = False
    except Exception as exc:
        _emit(f"ERROR: {exc}")
        with LOCK:
            JOB["error"] = str(exc)
            JOB["done"] = True
            JOB["running"] = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            with LOCK:
                snap = dict(JOB)
                snap["logs"] = list(JOB["logs"])
            return self._send_json(snap)

        if path.startswith("/api/download/"):
            fname = os.path.basename(urllib.parse.unquote(path[len("/api/download/"):]))
            fpath = os.path.join(OUT_DIR, fname)
            if not fname or not os.path.isfile(fpath):
                self.send_error(404, "File tidak ditemukan")
                return
            with open(fpath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.send_header("Content-Disposition", f'attachment; filename="{fname}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        rel = "index.html" if path == "/" else path.lstrip("/")
        safe = os.path.normpath(os.path.join(ROOT, rel))
        if not safe.startswith(ROOT) or not os.path.isfile(safe):
            self.send_error(404, "Not found")
            return

        ctype, _ = mimetypes.guess_type(safe)
        with open(safe, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        if safe.endswith(".json"):
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/upload":
            self.send_error(404)
            return

        with LOCK:
            if JOB["running"]:
                return self._send_json({"ok": False, "error": "Proses verifikasi sedang berjalan."}, 409)

        raw_name = urllib.parse.unquote(self.headers.get("X-Filename", "upload.xlsx"))
        fname = os.path.basename(raw_name) or "upload.xlsx"
        build_excel = self.headers.get("X-Build-Excel", "0") == "1"

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return self._send_json({"ok": False, "error": "File kosong."}, 400)

        data = self.rfile.read(length)
        dst = os.path.join(INBOX_DIR, fname)
        with open(dst, "wb") as f:
            f.write(data)

        with LOCK:
            JOB["running"] = True
            JOB["done"] = False
            JOB["error"] = ""
            JOB["logs"] = [f"Menerima file: {fname} ({len(data)/1024/1024:.2f} MB)"]
            JOB["files"] = []
            JOB["stats"] = None

        t = threading.Thread(target=_run_verify, args=(dst, build_excel), daemon=True)
        t.start()
        return self._send_json({"ok": True})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"EPR Dashboard berjalan di {url}")
    print("Tekan Ctrl+C untuk berhenti.")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nDihentikan.")


if __name__ == "__main__":
    main()
