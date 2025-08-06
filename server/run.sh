#!/bin/bash

# Navigate to the server directory
cd ~/BotibotWeb/server/

# Activate the virtual environment
source venv/bin/activate

# Check if the server is already running on port 5000
if ! lsof -i :5000 > /dev/null; then
    # Start the server in the background
    python main.py &
    # Wait a moment to ensure the server starts
    sleep 2
else
    echo "Server is already running on port 5000"
fi

# Launch Firefox in kiosk mode
export DISPLAY=:0
firefox --kiosk http://127.0.0.1:5000
