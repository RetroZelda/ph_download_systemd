#!/bin/bash

folder_to_monitor="../input"
venv_name="../.venv"

rm -drf $folder_to_monitor
rm -drf $venv_name

deactivate