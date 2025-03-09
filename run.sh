#!/bin/bash

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python -m venv venv || python3 -m venv venv || echo "Failed to create virtual environment. Please check that Python is installed."
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate || echo "Failed to activate virtual environment."

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt || echo "Failed to install dependencies."

# Create necessary directories
echo "Creating directories..."
mkdir -p novel_temp
mkdir -p novel_output
mkdir -p templates
mkdir -p logs

# Check for .env file
if [ ! -f .env ]; then
  echo "Creating default .env file..."
  cp .env.example .env || echo "# Server configuration
SECRET_KEY=change_this_to_a_random_secret_key
PORT=8080

# Dropbox configuration
DROPBOX_ACCESS_TOKEN=your_dropbox_access_token" > .env
  echo "Please update the .env file with your configurations."
fi

# Create UptimeRobot config to keep the repl alive
echo "Setting up keep-alive configuration..."
if [ -n "$REPL_SLUG" ] && [ -n "$REPL_OWNER" ]; then
  export REPLIT_URL="https://${REPL_SLUG}.${REPL_OWNER}.repl.co"
  echo "REPLIT_URL=${REPLIT_URL}" >> .env
  echo "Detected Replit URL: ${REPLIT_URL}"
else
  echo "Could not detect Replit environment variables. Keep-alive may not work correctly."
fi

# Start the server
echo "Starting Novel Downloader API..."
python main.py || echo "Failed to start the server."