from flask import Flask, render_template, request
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lamp_state

app = Flask(__name__)
LAMPS = [1, 2, 3, 4, 5, 6]

def send_mqtt(lamp_id, payload):
    topic = f"zigbee2mqtt/lamp{lamp_id}/set"
    command = ["mosquitto_pub", "-t", topic, "-m", payload]
    subprocess.run(command)

@app.route('/')
def index():
    return render_template('index.html', saved=lamp_state.load(LAMPS))

@app.route('/state')
def state():
    return lamp_state.load(LAMPS)

@app.route('/control', methods=['POST'])
def control():
    data = request.json
    lamp_id = data.get('lamp_id')
    action = data.get('action')
    value = data.get('value')
    # Default to 0 if no transition is sent
    duration = data.get('transition', 0)

    if action == 'state':
        payload = f'{{"state": "{value}"}}'
    elif action == 'brightness':
        payload = f'{{"brightness": {value}, "transition": {duration}}}'
    elif action == 'color_temp':
        payload = f'{{"color_temp": {value}, "transition": {duration}}}'
    
    send_mqtt(lamp_id, payload)
    lamp_state.save(lamp_id, action, value)
    return {"status": "success"}

if __name__ == '__main__':
    lamp_state.start_listener(LAMPS)
    # host='0.0.0.0' makes it accessible to the local network
    app.run(host='0.0.0.0', port=5000)
