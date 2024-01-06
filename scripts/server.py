
import argparse
import tempfile
import threading
import time
import os

from threading import Thread
from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

parser = argparse.ArgumentParser(description="Verify and save valid URLs from a file.")
parser.add_argument("-p", "--port", help="Desired port", required=False, default=8008)
parser.add_argument("-i", "--public-dir", help="Directory that contains our index.html", required=True)
parser.add_argument("-o", "--output-dir", help="Output directory for files we save", required=True)
parser.add_argument("-l", "--log-to-read", help="Log file we might want to monitor", required=False)
args = parser.parse_args()

class SharedResource:
    def __init__(self):
        self.num_connected = 0
        self.thread_running = False
        self.lock = threading.Lock()

    def thread_on(self):
        with self.lock:
            self.thread_running = True
        
    def thread_off(self):
        with self.lock:
            self.thread_running = False

    def is_thread_on(self):
        value = False
        with self.lock:
            value = self.thread_running
        return value
        
    def add_num_connected(self, value):
        new_value = 0
        with self.lock:
            self.num_connected += value
            new_value = self.num_connected
        return new_value

    def set_num_connected(self, value):
        with self.lock:
            self.num_connected = value

    def get_num_connected(self):
        value = 0
        with self.lock:
            value = self.num_connected 
        return value
            

def read_log(data):
    data.thread_on()
    print("Opening read_log thread")
    print(f"Monitoring Log: {args.log_to_read}")
    last_position = 0
    while data.get_num_connected() > 0:
        try:
            with open(args.log_to_read, 'r') as log_file:
                log_file.seek(last_position)
                new_lines = [line.strip() for line in log_file.readlines() if line.strip()]

                if new_lines:
                    socketio.emit('update_log', {'new_lines': new_lines})
                else:
                    time.sleep(1)

                last_position = log_file.tell()  # Update the last position to the current position in the file
        except FileNotFoundError:
            new_lines = f"Log File {args.log_to_read} not found."
            print(new_lines)
            socketio.emit('update_log', {'new_lines': new_lines})
            break
    print("closing read_log thread")
    data.thread_off()

app = Flask(__name__, template_folder=args.public_dir)
socketio = SocketIO(app)
num_connected = SharedResource()
log_thread = Thread(target=read_log, daemon=True, args=(num_connected,))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/save', methods=['POST'])
def save_text():
    try:
        data = request.get_json()
        text = data['text']
        with tempfile.NamedTemporaryFile(dir=args.output_dir, delete=False, mode='w') as temp_file:
            temp_file.write(text)
        return jsonify({'message': 'Submitted successfully.'})
    except Exception as e:
        return jsonify({'error': str(e)})

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    if num_connected.add_num_connected(1) == 1 and not num_connected.is_thread_on():
        if args.log_to_read is not None and args.log_to_read != "":
            log_thread.start()   

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    if num_connected.add_num_connected(-1) == 0 and num_connected.is_thread_on():
        if args.log_to_read is not None and args.log_to_read != "":
            log_thread.join()

if __name__ == '__main__':
    print("Starting Flask Server")
    app.run(host='0.0.0.0', port=args.port, debug=False)

    if num_connected.is_thread_on():
        num_connected.set_num_connected(0)
        log_thread.join()

