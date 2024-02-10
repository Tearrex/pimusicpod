#!/bin/bash
if [ $(id -u) != 0 ]; then
echo 'Must run as sudo'
exit 1
fi

echo "Stopping pimusicpod.service ..."
systemctl stop pimusicpod.service

echo "Disabling pimusicpod.service ..."
systemctl disable pimusicpod.service

echo "Deleting service unit files..."
rm /etc/systemd/system/pimusicpod.service

echo "Reloading unit files..."
systemctl daemon-reload

echo "Service removed successfully!"
