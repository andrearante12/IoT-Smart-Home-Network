"""Last known brightness / color_temp / on-off for each lamp, shared by the web apps.

Values are saved when a page sends a command, and kept in sync with the real
lamps by a background listener on the zigbee2mqtt state topics.
"""
import fcntl
import json
import os
import subprocess
import threading
import time

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lamp_state.json")
LOCK_FILE = STATE_FILE + ".lock"
DEFAULTS = {"brightness": 254, "color_temp": 500, "state": None}
REFRESH_SECONDS = 60


def _read():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load(lamp_ids):
    """Return {lamp_id: {"brightness": .., "color_temp": .., "state": ..}} with defaults filled in."""
    saved = _read()
    return {i: {**DEFAULTS, **saved.get(str(i), {})} for i in lamp_ids}


def _clean(key, value):
    if key == "state":
        return value if value in ("ON", "OFF") else None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def update(lamp_id, values):
    values = {k: _clean(k, v) for k, v in values.items() if k in DEFAULTS}
    values = {k: v for k, v in values.items() if v is not None}
    if not values:
        return
    # Lock so both apps can write without clobbering each other
    with open(LOCK_FILE, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = _read()
        state.setdefault(str(lamp_id), {}).update(values)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)


def save(lamp_id, key, value):
    update(lamp_id, {key: value})


def _request_state(lamp_ids):
    for i in lamp_ids:
        subprocess.run(["mosquitto_pub", "-t", f"zigbee2mqtt/lamp{i}/get",
                        "-m", '{"state": "", "brightness": "", "color_temp": ""}'])


def _listen(lamp_ids):
    topics = {f"zigbee2mqtt/lamp{i}": i for i in lamp_ids}
    command = ["mosquitto_sub", "-v"]
    for t in topics:
        command += ["-t", t]
    while True:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, text=True)
        time.sleep(1)
        _request_state(lamp_ids)
        for line in proc.stdout:
            topic, _, payload = line.partition(" ")
            if topic not in topics:
                continue
            try:
                update(topics[topic], json.loads(payload))
            except (json.JSONDecodeError, AttributeError):
                continue
        # mosquitto_sub exited (e.g. broker restart); retry shortly
        proc.wait()
        time.sleep(5)


def _poll(lamp_ids):
    # Not every bulb reports changes on its own, so ask periodically
    while True:
        time.sleep(REFRESH_SECONDS)
        _request_state(lamp_ids)


def start_listener(lamp_ids):
    threading.Thread(target=_listen, args=(lamp_ids,), daemon=True).start()
    threading.Thread(target=_poll, args=(lamp_ids,), daemon=True).start()
