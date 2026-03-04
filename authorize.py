"""
One-time Google Sheets authorization.
Starts a tiny local web server to catch the OAuth redirect automatically.
"""

import os
import json
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
import urllib.request
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
SHEET_ID      = os.environ.get("GOOGLE_SHEET_ID", "")
SCOPES        = "https://www.googleapis.com/auth/spreadsheets"
REDIRECT_URI  = "http://localhost:8080"

auth_code = None

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        params = parse_qs(urlparse(self.path).query)
        auth_code = params.get("code", [None])[0]

        if auth_code:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html><body style="font-family:sans-serif;text-align:center;padding:60px">
                <h2>&#x2705; Authorization successful!</h2>
                <p>You can close this tab and go back to the terminal.</p>
                </body></html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Error: no code received")

    def log_message(self, format, *args):
        pass  # silence server logs


def exchange_code(code):
    data = urlencode({
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }).encode()

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def verify_sheet(token_response):
    if not SHEET_ID or SHEET_ID == "PASTE_YOUR_SHEET_ID_HERE":
        print("⚠️  Set GOOGLE_SHEET_ID in .env then run: python bot.py")
        return

    try:
        access_token = token_response["access_token"]
        req = urllib.request.Request(
            f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            title = data.get("properties", {}).get("title", "Unknown")
            print(f"✅ Sheet connected: '{title}'")
            print("\n🚀 All done! Run:  python bot.py")
    except Exception as e:
        print(f"⚠️  Sheet check failed: {e}")
        print("   token.json was saved — try running python bot.py anyway.")


if __name__ == "__main__":
    # Build auth URL
    auth_url = "https://accounts.google.com/o/oauth2/auth?" + urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent"
    })

    # Start local server in background
    server = HTTPServer(("localhost", 8080), OAuthHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    print("🌐 Opening browser for Google authorization...")
    print("   (if browser doesn't open, copy the URL below manually)\n")
    print(auth_url)
    webbrowser.open(auth_url)

    print("\n⏳ Waiting for you to approve in the browser...")
    thread.join(timeout=120)

    if not auth_code:
        print("❌ Timed out waiting for authorization. Try again.")
        exit(1)

    print("🔄 Exchanging code for token...")
    token_response = exchange_code(auth_code)

    token_json = {
        "token": token_response.get("access_token"),
        "refresh_token": token_response.get("refresh_token"),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": [SCOPES]
    }

    with open("token.json", "w") as f:
        json.dump(token_json, f, indent=2)

    print("✅ token.json saved!")
    verify_sheet(token_response)