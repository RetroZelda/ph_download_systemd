#!/bin/bash

# Check if inotifywait is installed
command -v inotifywait >/dev/null 2>&1 || { echo >&2 "Please install inotify-tools package. Aborting."; exit 1; }

folder_to_monitor=$(readlink -f "$(pwd)/../input")
folder_config=$(readlink -f "$(pwd)/../config")
folder_done=$(readlink -f "$(pwd)/../done")

# Create the folder if it doesn't exist
if [ ! -d "$folder_to_monitor" ]; then
    echo "Creating folder: $folder_to_monitor"
    mkdir -p "$folder_to_monitor"
fi
if [ ! -d "$folder_done" ]; then
    echo "Creating folder: $folder_done"
    mkdir -p "$folder_done"
fi

echo "Add a file with a unique URL per line inside of: $folder_to_monitor"

inotifywait -m -e create "$folder_to_monitor" |
    while read path action file; do
        echo "Processing $file"
        for existing_file in "$folder_to_monitor"/*; do
            if [[ -f "$existing_file" ]]; then

                python3 ./download.py -i "$existing_file" -c "$folder_config"
                echo "$existing_file has finished processing"
                mv "$existing_file" "$folder_done"
            fi
        done
    done
