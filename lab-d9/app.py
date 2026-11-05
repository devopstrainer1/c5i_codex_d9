"""Loopback only offline classroom app. Not a production authenticated service."""
import html
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from core import Store, VoiceController, ExtractionPipeline, ScreenPolicy

ROOT = Path(__file__).parent
store = Store()
voice = VoiceController(store)
pipeline = ExtractionPipeline(store)
csrf = secrets.token_urlsafe(24)
lock = threading.RLock()


def fixture(name):
    return json.loads((ROOT / "fixtures" / (name + ".json")).read_text())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def page(self, message=""):
        status = html.escape(json.dumps(store.claims, indent=2))
        audit = html.escape(json.dumps(store.audit[-8:], indent=2))
        hidden = '<input type="hidden" name="csrf" value="' + csrf + '">'
        def form(action, content):
            return '<form method="post" action="' + action + '">' + hidden + content + '</form>'
        if self.path == "/legacy":
            body = '<h1>Legacy claims screen</h1><p>Synthetic data. No supported JSON integration.</p><pre>' + status + '</pre>'
            body += form('/legacy', '<label>New stage <select name="stage"><option>Review</option><option>Underwriting</option><option>Approved</option></select></label><label><input type="checkbox" name="approve" value="yes"> I approve this synthetic stage change</label><button>Save stage</button>')
            body += '<p>This form writes through the classroom backend. A browser adapter is a learner extension.</p><a href="/">Back</a>'
        else:
            body = '<h1>Day 9 claims operations lab</h1><p><strong>OFFLINE REPLAY</strong> No microphone, model call or automated browser is running.</p><pre>' + status + '</pre><h2>Voice controller</h2>'
            body += form('/voice', '<label>Replay event <select name="text"><option>status</option><option>move Underwriting</option><option>confirm</option><option>yes but wait</option><option>cancel</option></select></label><button>Send event</button>')
            body += '<p>Pending proposal: ' + html.escape(str(voice.pending)) + '</p><h2>Document review</h2>'
            body += '<p>Compare the original fixtures first. Replay candidates are already extracted; no OCR is performed.</p>'
            body += form('/extract', '<label>Candidate <select name="candidate"><option>clean</option><option>bad</option></select></label><label><input type="checkbox" name="review" value="yes"> I checked the original critical fields and approve this exact candidate</label><button>Validate and process</button>')
            body += '<p>Accepted documents: ' + str(len(store.accepted)) + '; quarantined: ' + str(len(store.quarantine)) + '</p><h2>Screen policy</h2>'
            body += form('/screen', '<button>Show policy dry run</button>')
            body += '<p><a href="/legacy">Open local legacy screen</a></p><h2>Recent audit</h2><pre>' + audit + '</pre>'
            body += '<p>Single process in memory. Restart to reset. Authentication, durable storage and live adapters are exercises.</p>'
        markup = '<!doctype html><html><head><meta charset="utf-8"><title>Day 9 lab</title><style>body{font:17px system-ui;max-width:960px;margin:35px auto;padding:0 24px;color:#172331}h1,h2{color:#182632}pre{background:#eef2f6;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere}label{display:block;margin:12px 0}button,select{font:inherit;padding:9px}form{margin:16px 0} .message{border-left:4px solid #445c7c;padding:14px}</style></head><body>'
        if message:
            markup += '<pre class="message">' + html.escape(message) + '</pre>'
        return (markup + body + '</body></html>').encode()

    def respond(self, code, data, content_type="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path not in {"/", "/legacy"}:
            return self.respond(404, b"Not found", "text/plain")
        with lock:
            self.respond(200, self.page())

    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        if size > 8192:
            return self.respond(413, b"Too large", "text/plain")
        data = parse_qs(self.rfile.read(size).decode())
        if data.get("csrf", [""])[0] != csrf:
            return self.respond(403, b"Invalid form token", "text/plain")
        with lock:
            if self.path == "/voice":
                result = voice.handle(data.get("text", [""])[0])
            elif self.path == "/extract":
                name = data.get("candidate", ["clean"])[0]
                if name not in {"clean", "bad"}:
                    return self.respond(400, b"Invalid fixture", "text/plain")
                c = fixture(name)
                source = (ROOT / "fixtures" / "source.txt").read_text()
                token = pipeline.review(c, source, "classroom-reviewer") if data.get("review") == ["yes"] else None
                result = pipeline.process(c, source, token)
            elif self.path == "/screen":
                result = ScreenPolicy().run(fixture("screen_plan"), dry_run=True)
            elif self.path == "/legacy":
                if data.get("approve") != ["yes"]:
                    result = "DENIED: approval required"
                else:
                    try:
                        store.move("CLM-000101", data.get("stage", [""])[0], store.claims["CLM-000101"]["version"])
                        result = "SAVED synthetic stage"
                    except ValueError as error:
                        result = str(error)
            else:
                return self.respond(404, b"Not found", "text/plain")
            self.respond(200, self.page(json.dumps(result, indent=2)))


if __name__ == "__main__":
    print("Offline lab: http://127.0.0.1:5050 ; Ctrl+C stops. Restart resets state.", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 5050), Handler).serve_forever()
