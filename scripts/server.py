
import argparse
import tempfile
import threading
import time

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO

parser = argparse.ArgumentParser(description="Verify and save valid URLs from a file.")
parser.add_argument("-p", "--port", help="Desired port", required=False, default=8008)
parser.add_argument("-i", "--public-dir", help="Directory that contains our index.html", required=True)
parser.add_argument("-o", "--output-dir", help="Output directory for files we save", required=True)
parser.add_argument("-l", "--log-to-read", help="Log file we might want to monitor", required=False)
args = parser.parse_args()

app = Flask(__name__, template_folder=args.public_dir)
socketio = SocketIO(app)

def read_log():
    last_position = 0
    while True:
        with open(args.log_to_read, 'r') as log_file:
            log_file.seek(last_position)
            new_lines = [line.strip() for line in log_file.readlines() if line.strip()]

            if new_lines:
                socketio.emit('update_log', {'new_lines': new_lines})

            last_position = log_file.tell()  # Update the last position to the current position in the file

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

#@socketio.on('connect')
#def handle_connect():
    #socketio.emit('update_log', {'new_lines': log_data})

if __name__ == '__main__':
    print("Starting Flask Server")
    if args.log_to_read is not None and args.log_to_read != "":
        threading.Thread(target=read_log, daemon=True).start()
    app.run(host='0.0.0.0', port=args.port)

