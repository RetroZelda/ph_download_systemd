#!/bin/bash

# Set the name for the virtual environment
venv_name="../.venv"

# Set the path to the Python interpreter (change if needed)
python_executable="python3"

# Create and activate the virtual environment
echo "Creating virtual environment..."
"$python_executable" -m venv "$venv_name"

echo "Activating virtual environment..."
source "$venv_name/bin/activate" 

pip3 install --upgrade git+https://github.com/EchterAlsFake/PHUB
pip install ffmpeg_progress_yield
pip3 install BeautifulSoup4
pip3 install validators
pip3 install flask
pip3 install flask-socketio
pip3 install tqdm
pip3 install pytube
pip3 install pytubefix

./monitor.sh >> ../logs/general.log 2>&1 &
./run_web.sh >> ../logs/general.log 2>&1 &

