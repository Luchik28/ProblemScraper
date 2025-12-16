#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Problem Finder - Test Script
----------------------------
This script verifies that your environment is set up correctly and can connect
to Supabase. It's a quick check before running the full problem finder.
"""

import os
import sys
import traceback
from dotenv import load_dotenv

# Try to load environment variables
try:
    # Try to load from script directory first, then from project root
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
        load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
    else:
        load_dotenv()
    print("✅ Loaded environment variables from .env file")
except Exception as e:
    print(f"⚠️ Warning: Could not load .env file: {e}")

# Check for Supabase environment variables
supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    print("❌ Error: SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY environment variables must be set")
    sys.exit(1)
else:
    print(f"✅ Found Supabase URL: {supabase_url[:20]}...")

# Try importing required packages
print("Checking for required packages...")
missing_packages = []

try:
    from supabase import create_client
    print("✅ supabase-py is installed")
except ImportError:
    print("❌ supabase-py is missing")
    missing_packages.append("supabase")

try:
    from duckduckgo_search import DDGS
    print("✅ duckduckgo_search is installed")
except ImportError:
    print("❌ duckduckgo_search is missing")
    missing_packages.append("duckduckgo_search")

try:
    from transformers import pipeline
    print("✅ transformers is installed")
except ImportError:
    print("❌ transformers is missing")
    missing_packages.append("transformers")

try:
    from sentence_transformers import SentenceTransformer
    print("✅ sentence-transformers is installed")
except ImportError:
    print("❌ sentence-transformers is missing")
    missing_packages.append("sentence-transformers")

try:
    import torch
    print(f"✅ torch is installed (version {torch.__version__})")
except ImportError:
    print("❌ torch is missing")
    missing_packages.append("torch")

if missing_packages:
    print("\n❌ Some packages are missing. Install them with:")
    print(f"pip install {' '.join(missing_packages)}")
    sys.exit(1)

# Try connecting to Supabase
print("\nTrying to connect to Supabase...")
try:
    from supabase import create_client
    supabase = create_client(supabase_url, supabase_key)
    
    # Try a simple query to verify connection
    result = supabase.table("problems").select("count").execute()
    count = len(result.data)
    print(f"✅ Successfully connected to Supabase. Found {count} problems.")
    
except Exception as e:
    print(f"❌ Error connecting to Supabase: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All checks passed! Your environment is set up correctly.")
print("You can now run the full problem finder script:")
print("python problem_finder_update.py")
