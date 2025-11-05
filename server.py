# server.py
import os, json
from flask import Flask, request, jsonify
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WORKFLOW_ID = os.getenv("WORKFLOW_ID")  # wf_... aus Agent Builder (Publish)

if not OPENAI_API_KEY or not WORKFLOW_ID:
    raise RuntimeError("Bitte OPENAI_API_KEY und WORKFLOW_ID als Env-Variablen setzen.")

app = Flask(__name__)

OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com")  # Standard: offizielles API

HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "chatkit_beta=v1",
}

def create_session():
    """
    Erstellt eine ChatKit-Session und liefert das client_secret zurück.
    Entspricht der Sessions-API aus der ChatKit-Doku.
    """
    url = f"{OPENAI_BASE}/v1/chatkit/sessions"
    body = {
        "workflow_id": WORKFLOW_ID,
        # optional: "user": {"id": "...", "name": "..."},
        # optional: "state_variables": {"plan": "pro"},
    }
    r = requests.post(url, headers=HEADERS, data=json.dumps(body), timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("client_secret")

def refresh_session(client_secret: str):
    """
    Erneuert das client_secret (Token-Refresh).
    """
    url = f"{OPENAI_BASE}/v1/chatkit/sessions/refresh"
    body = { "client_secret": client_secret }
    r = requests.post(url, headers=HEADERS, data=json.dumps(body), timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("client_secret")

@app.post("/api/chatkit/start")
def start():
    try:
        secret = create_session()
        return jsonify({"client_secret": secret}), 200
    except requests.HTTPError as e:
        return jsonify({"error": e.response.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.post("/api/chatkit/refresh")
def refresh():
    try:
        body = request.get_json(silent=True) or {}
        current = body.get("currentClientSecret")
        if not current:
            return jsonify({"error": "currentClientSecret fehlt"}), 400
        secret = refresh_session(current)
        return jsonify({"client_secret": secret}), 200
    except requests.HTTPError as e:
        return jsonify({"error": e.response.text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.get("/")
def health():
    return "OK", 200

if __name__ == "__main__":
    # Lokal starten (Render setzt später PORT automatisch)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
