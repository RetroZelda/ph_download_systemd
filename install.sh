#!/bin/bash

if [ "$EUID" -ne 0 ]; then
    echo "This script requires superuser privileges (sudo)."
    exit 1
fi

# Get the directory of the install.sh script
script_dir=$(pwd)/scripts
log_dir=$(pwd)/logs
service_name="ph_download.service"
target_user=$SUDO_USER

if [ ! -d "$log_dir" ]; then
    echo "Creating folder: $log_dir"
    sudo -u $target_user mkdir -p "$log_dir"
fi

# Create the systemd service unit file
cat <<EOF | sudo tee /etc/systemd/system/$service_name > /dev/null
[Unit]
Description=Download videos from Youtube, PornHub, and VRPorn
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$target_user
RemainAfterExit=true
ExecStartPre=/bin/sleep 30
WorkingDirectory=$script_dir
ExecStart=$script_dir/activate.sh
ExecStop=$script_dir/deactivate.sh
StandardOutput=file:$log_dir/general.log
StandardError=inherit

[Install]
WantedBy=default.target
EOF

# ensure we have the log file
sudo -u $target_user touch $log_dir/general.log

# ensure we have all the needed packages
apt install inotify-tools

# Reload systemd daemon
systemctl daemon-reload
echo "Enabling service: $service_name"
systemctl enable $service_name
echo "Starting service: $service_name"
systemctl start $service_name

echo "Service installed: $service_name"
