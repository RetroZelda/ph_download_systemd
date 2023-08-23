#!/bin/bash

if [ "$EUID" -ne 0 ]; then
    echo "This script requires superuser privileges (sudo)."
    exit 1
fi

script_dir=$(pwd)
log_dir=$script_dir/logs
service_name="ph_download.service"

# Remove the systemd service unit file
systemctl stop $service_name
systemctl disable $service_name
rm /etc/systemd/system/$service_name

# Remove things
rm -drf $log_dir

# Reload systemd daemon
systemctl daemon-reload

echo "Service uninstalled."
