
import argparse
import tempfile
from flask import Flask, request, jsonify, render_template

parser = argparse.ArgumentParser(description="Verify and save valid URLs from a file.")
parser.add_argument("-p", "--port", help="Desired port", required=False, default=8008)
parser.add_argument("-i", "--public-dir", help="Directory that contains our index.html", required=True)
parser.add_argument("-o", "--output-dir", help="Output directory for files we save", required=True)
args = parser.parse_args()

app = Flask(__name__,
            template_folder=args.public_dir)

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

if __name__ == '__main__':
    print("Starting Flask Server")
    app.run(host='0.0.0.0', port=args.port)
