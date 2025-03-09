#!/usr/bin/env python3
"""
Setup script for Novel Downloader API
Creates necessary directories and default files
"""

import os
import shutil
import sys

def create_directory(path):
    """Create directory if it doesn't exist"""
    if not os.path.exists(path):
        print(f"Creating directory: {path}")
        os.makedirs(path)
    else:
        print(f"Directory already exists: {path}")

def main():
    """Main setup function"""
    print("Setting up Novel Downloader API...")

    # Create directories
    create_directory('novel_temp')
    create_directory('novel_output')
    create_directory('templates')
    create_directory('logs')

    # Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            print("Creating .env file from .env.example")
            shutil.copy('.env.example', '.env')
        else:
            print("Creating default .env file")
            with open('.env', 'w') as f:
                f.write("""# Server configuration
SECRET_KEY=change_this_to_a_random_secret_key
PORT=8080

# Dropbox configuration
DROPBOX_ACCESS_TOKEN=your_dropbox_access_token
""")
    else:
        print(".env file already exists")

    # Create log file
    log_file = os.path.join('logs', 'novel_downloader.log')
    if not os.path.exists(log_file):
        print(f"Creating log file: {log_file}")
        with open(log_file, 'w') as f:
            f.write("")
    else:
        print(f"Log file already exists: {log_file}")

    print("\nSetup completed successfully!")
    print("\nTo start the server, run:")
    print("  python main.py")

    return 0

if __name__ == "__main__":
    sys.exit(main())