from flask import Flask, render_template, request
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lamp_state

app = Flask(__name__)
LAMPS = [3]

# This app only ever talks to lamp 3
TOPIC = "zigbee2mqtt/lamp3/set"

def send_mqtt(payload):
    command = ["mosquitto_pub", "-t", TOPIC, "-m", json.dumps(payload)]
    subprocess.run(command)

@app.route('/')
def index():
    return render_template('index.html', saved=lamp_state.load(LAMPS)[3])

@app.route('/state')
def state():
    return lamp_state.load(LAMPS)[3]

@app.route('/control', methods=['POST'])
def control():
    data = request.json or {}
    action = data.get('action')
    value = data.get('value')
    duration = data.get('transition', 0)

    try:
        if action == 'state' and value in ('ON', 'OFF'):
            payload = {"state": value}
        elif action == 'brightness':
            payload = {"brightness": max(0, min(254, int(value))), "transition": float(duration)}
        elif action == 'color_temp':
            payload = {"color_temp": max(150, min(500, int(value))), "transition": float(duration)}
        else:
            return {"status": "error", "message": "invalid action"}, 400
    except (TypeError, ValueError):
        return {"status": "error", "message": "invalid value"}, 400

    send_mqtt(payload)
    if action in payload:
        lamp_state.save(3, action, payload[action])
    return {"status": "success"}

if __name__ == '__main__':
    lamp_state.start_listener(LAMPS)
    # Port 5001 so it runs alongside the main Lumina app on 5000
    app.run(host='0.0.0.0', port=5001)
