#!/bin/bash
if [ $(id -u) != 0 ]; then
echo 'Must run as sudo'
exit 1
fi

# directory of bash script
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
# directory of main python script
SCRIPT_PATH="$(dirname "$SCRIPT_DIR")"

sed -i "s|/path/to/script|$SCRIPT_PATH|g" $SCRIPT_DIR/pimusicpod.service
echo "Updated unit file script execution path"

cp $SCRIPT_DIR/pimusicpod.service /etc/systemd/system/.
echo "Copied unit file to /etc/systemd/system/"

echo "Enabling pimusicpod.service ..."
systemctl enable pimusicpod.service > /dev/null

echo "Reloading unit files..."
systemctl daemon-reload

echo "Service installed successfully!"
exit
