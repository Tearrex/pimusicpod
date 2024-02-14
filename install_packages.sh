#!/bin/bash
if [ $(id -u) != 0 ]; then
echo 'Must run as sudo'
exit 1
fi

# directory of bash script
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

activate() {
    source "$SCRIPT_DIR/venv/bin/activate"
}

echo "Updating system..."
sudo apt update && sudo apt upgrade -y

echo "Installing system package dependencies..."
sudo apt install -y python3-pip python3-venv libopenjp2-7 pulseaudio pulseaudio-module-bluetooth omxplayer
clear

echo "Creating virtual environment for Python..."
python3 -m venv "$SCRIPT_DIR/venv"

echo "Installing Python packages in virtual env..."
activate
pip3 install -r requirements.txt
clear

echo "All dependencies installed successfully!"
