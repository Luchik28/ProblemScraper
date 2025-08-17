#!/usr/bin/env bash

# This script runs the URL cleanup process to fix any URLs in the database

echo "Starting URL cleanup process..."

# Change to the script directory
cd "$(dirname "$0")"

# Run the Python script
python cleanup_urls.py

echo "URL cleanup process complete!"
