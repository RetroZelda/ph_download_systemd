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

pip3 install --upgrade git+https://github.com/Egsagon/PHUB.git
pip3 install validators
pip3 install Flask

./monitor.sh & ./run_web.sh & 

