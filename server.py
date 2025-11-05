import os
import json
import secrets
from typing import Optional

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

# ====== Konfiguration über Env-Variablen ======
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # z.B. sk-...
WORKFLOW_ID = os.getenv("WORKFLOW_ID")        # z.B. wf_...
OPENAI_BASE = os.getenv("OPENAI_BASE", "https://api.openai.com")

# erlaubte Origins (CORS), kommasepariert
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://www.team-rosenke.de,https://team-rosenke.de"
)

if not OPENAI_API_KEY or not WORKFLOW_ID:
    raise RuntimeError("Bitte OPENAI_API_KEY und WORKFLOW_ID in den Env-Variablen setzen.")

# ====== Flask-App & CORS ======
app = Flask(__name__)
CORS(
    app,
    resources={r"/api/*": {"origins": [o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()]}},
    supports_credentials=False,
)

# Gemeinsame HTTP-Header für ChatKit (Beta!)
OPENAI_HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "Content-Type": "application/json",
    "OpenAI-Beta": "chatkit_beta=v1",
}

# ====== Hilfsfunktionen für ChatKit Sessions ======
def create_session(user_id: Optional[str] = None) -> str:
    """
    Erstellt eine ChatKit-Session und gibt ein kurzlebiges client_secret zurück.
    Erforderliche Felder: user (string), workflow: { id: "wf_..." }
    """
    url = f"{OPENAI_BASE}/v1/chatkit/sessions"
    body = {
        "user": user_id or f"anon_{secrets.token_hex(8)}",
        "workflow": {"id": WORKFLOW_ID},
    }
    r = requests.post(url, headers=OPENAI_HEADERS, data=json.dumps(body), timeout=30)
    r.raise_for_status()
    data = r.json()
    secret = data.get("client_secret")
    if not secret:
        raise RuntimeError("client_secret fehlt in der OpenAI-Antwort")
    return secret


def refresh_session(client_secret: str) -> str:
    """
    Erneuert das kurzlebige client_secret.
    """
    url = f"{OPENAI_BASE}/v1/chatkit/sessions/refresh"
    body = {"client_secret": client_secret}
    r = requests.post(url, headers=OPENAI_HEADERS, data=json.dumps(body), timeout=30)
    r.raise_for_status()
    data = r.json()
    new_secret = data.get("client_secret")
    if not new_secret:
        raise RuntimeError("client_secret fehlt in der OpenAI-Refresh-Antwort")
    return new_secret


# ====== API-Routen ======

@app.route("/", methods=["GET"])
def health():
    return "OK", 200


@app.route("/api/chatkit/start", methods=["POST"])
def api_start():
    """
    Optionaler Body:
      { "user": "user_123" }
    Falls kein user übergeben wird, wird automatisch eine anonyme ID erzeugt.
    """
    try:
        payload = request.get_json(silent=True) or {}
        user_id = payload.get("user")
        secret = create_session(user_id=user_id)
        return jsonify({"client_secret": secret}), 200
    except requests.HTTPError as e:
        # OpenAI-Fehler möglichst transparent zurückgeben
        text = e.response.text if e.response is not None else str(e)
        return jsonify({"error": text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chatkit/refresh", methods=["POST"])
def api_refresh():
    """
    Erwartet Body:
      { "currentClientSecret": "..." }
    """
    try:
        payload = request.get_json(silent=True) or {}
        current = payload.get("currentClientSecret")
        if not current:
            return jsonify({"error": "Missing 'currentClientSecret'"}), 400
        new_secret = refresh_session(current)
        return jsonify({"client_secret": new_secret}), 200
    except requests.HTTPError as e:
        text = e.response.text if e.response is not None else str(e)
        return jsonify({"error": text}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ====== Lokaler Start (Render setzt PORT automatisch) ======
if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
