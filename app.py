import os
import random
import secrets
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)

# Allow the existing Netlify website to call this API. You can add more
# comma-separated origins in Render's ALLOWED_ORIGINS environment variable.
allowed_origins = [
    item.strip()
    for item in os.environ.get(
        "ALLOWED_ORIGINS", "https://chakkagamecuj.netlify.app"
    ).split(",")
    if item.strip()
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

rooms = {}
room_lock = threading.RLock()
WORDS = ["Mango", "Pizza", "Cricket", "Moon", "Coffee", "Tiger", "Rain", "Biryani"]


def now():
    return time.time()


def alive_players(room_data):
    return [p for p in room_data["players"].values() if p["alive"]]


def get_player(room_code, player_id):
    room_data = rooms.get(room_code)
    if not room_data or player_id not in room_data["players"]:
        return None, None
    return room_data, room_data["players"][player_id]


def finish(room_data, winner, message):
    room_data["phase"] = "result"
    room_data["winner"] = winner
    room_data["message"] = message
    for person in room_data["players"].values():
        person["role"] = "Chakka" if person["pid"] == room_data["chakka"] else "Chee Chakka"
    room_data["round_end"] = 0


def resolve_vote(room_data):
    tally = {}
    for voter, target in room_data["votes"].items():
        if (
            voter in room_data["players"]
            and room_data["players"][voter]["alive"]
            and target in room_data["players"]
            and room_data["players"][target]["alive"]
        ):
            tally[target] = tally.get(target, 0) + 1

    if not tally:
        room_data["phase"] = "discussion"
        room_data["message"] = "No votes. Discuss and vote again."
        room_data["votes"] = {}
        return

    high_score = max(tally.values())
    top_players = [person_id for person_id, count in tally.items() if count == high_score]
    if len(top_players) != 1:
        room_data["phase"] = "discussion"
        room_data["message"] = "Vote tied! Nobody eliminated."
        room_data["votes"] = {}
        return

    eliminated_id = top_players[0]
    room_data["players"][eliminated_id]["alive"] = False

    if eliminated_id == room_data["chakka"]:
        finish(room_data, "chee", "CHAKKA NO. 1! The Chakka was eliminated. Chee Chakkas win!")
        return

    remaining = alive_players(room_data)
    if len(remaining) <= 2:
        finish(room_data, "chakka", "CHAKKA SURVIVED! Chakka wins. Everyone else is a Chee Chakka!")
        return

    eliminated_name = room_data["players"][eliminated_id]["name"]
    room_data["phase"] = "discussion"
    room_data["message"] = eliminated_name + " was eliminated and was a Chee Chakka. Discuss again."
    room_data["votes"] = {}


@app.get("/")
def home():
    # This also lets you test the full game directly on its Render URL.
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/health")
def health():
    return jsonify(status="ok", service="chakka-kon")


@app.post("/api/create")
def create():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()[:20]
    if not name:
        return jsonify(error="Enter a nickname"), 400

    with room_lock:
        code = secrets.token_hex(3).upper()
        while code in rooms:
            code = secrets.token_hex(3).upper()
        player_id = secrets.token_hex(8)
        rooms[code] = {
            "players": {
                player_id: {
                    "pid": player_id,
                    "name": name,
                    "alive": True,
                    "host": True,
                    "role": None,
                }
            },
            "host": player_id,
            "phase": "lobby",
            "chakka": None,
            "word": None,
            "votes": {},
            "chat": [],
            "message": "Waiting for 5 players.",
            "round_end": 0,
        }
    return jsonify(room=code, pid=player_id)


@app.post("/api/join")
def join():
    data = request.get_json(silent=True) or {}
    code = str(data.get("room", "")).strip().upper()
    name = str(data.get("name", "")).strip()[:20]

    with room_lock:
        room_data = rooms.get(code)
        if not room_data:
            return jsonify(error="Room not found"), 404
        if not name:
            return jsonify(error="Enter a nickname"), 400
        if room_data["phase"] != "lobby":
            return jsonify(error="Game already started"), 400
        if len(room_data["players"]) >= 5:
            return jsonify(error="Room is full (5 players)"), 400
        player_id = secrets.token_hex(8)
        room_data["players"][player_id] = {
            "pid": player_id,
            "name": name,
            "alive": True,
            "host": False,
            "role": None,
        }
    return jsonify(room=code, pid=player_id)


@app.post("/api/start")
def start():
    data = request.get_json(silent=True) or {}
    code = str(data.get("room", "")).strip().upper()
    player_id = data.get("pid", "")
    with room_lock:
        room_data, person = get_player(code, player_id)
        if not room_data:
            return jsonify(error="Room/player not found"), 404
        if person["pid"] != room_data["host"]:
            return jsonify(error="Only host can start"), 403
        if room_data["phase"] != "lobby":
            return jsonify(error="Game has already started"), 400
        if len(room_data["players"]) != 5:
            return jsonify(error="Need exactly 5 players"), 400
        room_data["chakka"] = random.choice(list(room_data["players"]))
        room_data["word"] = random.choice(WORDS)
        for current_id, current_person in room_data["players"].items():
            current_person["role"] = "Chakka" if current_id == room_data["chakka"] else "Chee Chakka"
        room_data["phase"] = "discussion"
        room_data["message"] = "Game started! Discuss who the Chakka is."
        room_data["votes"] = {}
    return jsonify(ok=True)


@app.post("/api/open-voting")
def open_voting():
    data = request.get_json(silent=True) or {}
    code = str(data.get("room", "")).strip().upper()
    player_id = data.get("pid", "")
    with room_lock:
        room_data, person = get_player(code, player_id)
        if not room_data:
            return jsonify(error="Room/player not found"), 404
        if person["pid"] != room_data["host"]:
            return jsonify(error="Only host can start voting"), 403
        if room_data["phase"] != "discussion":
            return jsonify(error="Not in discussion phase"), 400
        room_data["phase"] = "voting"
        room_data["votes"] = {}
        room_data["round_end"] = now() + 10
        room_data["message"] = "Vote now! 10 seconds."
    return jsonify(ok=True)


@app.post("/api/vote")
def vote():
    data = request.get_json(silent=True) or {}
    code = str(data.get("room", "")).strip().upper()
    player_id = data.get("pid", "")
    target = data.get("target")
    with room_lock:
        room_data, person = get_player(code, player_id)
        if not room_data:
            return jsonify(error="Room/player not found"), 404
        if room_data["phase"] != "voting":
            return jsonify(error="Voting is closed"), 400
        if not person["alive"]:
            return jsonify(error="Eliminated players cannot vote"), 400
        if player_id in room_data["votes"]:
            return jsonify(error="You already voted"), 400
        if target not in room_data["players"] or not room_data["players"][target]["alive"]:
            return jsonify(error="Invalid target"), 400
        if target == player_id:
            return jsonify(error="You cannot vote for yourself"), 400
        room_data["votes"][player_id] = target
        if len(room_data["votes"]) >= len(alive_players(room_data)):
            resolve_vote(room_data)
    return jsonify(ok=True)


@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    code = str(data.get("room", "")).strip().upper()
    player_id = data.get("pid", "")
    message = str(data.get("text", "")).strip()[:300]
    with room_lock:
        room_data, person = get_player(code, player_id)
        if not room_data:
            return jsonify(error="Room/player not found"), 404
        if not message:
            return jsonify(error="Message empty"), 400
        room_data["chat"].append({"name": person["name"], "text": message, "time": now()})
        room_data["chat"] = room_data["chat"][-100:]
    return jsonify(ok=True)


@app.post("/api/state")
def state():
    data = request.get_json(silent=True) or {}
    code = str(data.get("room", "")).strip().upper()
    player_id = data.get("pid", "")
    with room_lock:
        room_data, person = get_player(code, player_id)
        if not room_data:
            return jsonify(error="Room/player not found"), 404
        # The 10-second vote is finalized when a player polls after the deadline.
        if room_data["phase"] == "voting" and now() >= room_data["round_end"]:
            resolve_vote(room_data)
        remaining = max(0, int(room_data["round_end"] - now())) if room_data["phase"] == "voting" else 0
        result = {
            "phase": room_data["phase"],
            "message": room_data["message"],
            "remaining": remaining,
            "host": person["pid"] == room_data["host"],
            # Only each player receives their own role and (for Chakka) secret word.
            "role": person.get("role") if room_data["phase"] != "lobby" else None,
            "word": room_data["word"] if person["pid"] == room_data["chakka"] and room_data["phase"] != "lobby" else None,
            "players": [
                {"pid": item["pid"], "name": item["name"], "alive": item["alive"], "host": item["host"]}
                for item in room_data["players"].values()
            ],
            "chat": room_data["chat"][-50:],
            "votes": len(room_data["votes"]),
            "winner": room_data.get("winner"),
        }
    return jsonify(result)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
