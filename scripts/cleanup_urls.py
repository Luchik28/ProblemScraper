#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
URL Cleanup Script for Problem Finder

This script checks and fixes URLs in the database to ensure they are valid and properly formatted.
"""

import os
import re
import sys
import time
from typing import List, Dict, Tuple
from urllib.parse import urlparse, urlunparse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Try to load from script directory first, then from project root
    if os.path.exists(os.path.join(os.path.dirname(__file__), '.env')):
        load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
    else:
        load_dotenv()
    print("Loaded environment variables from .env file")
except Exception as e:
    print(f"Warning: Could not load .env file: {e}")

from supabase import create_client, Client

def get_supabase_client() -> Client:
    """Get a Supabase client using environment variables."""
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY environment variables must be set")
    
    print(f"Using Supabase URL: {supabase_url[:20]}...")
    return create_client(supabase_url, supabase_key)

def clean_url(url: str) -> str:
    """Clean and validate a URL."""
    if not url:
        return ""
    
    # Make sure URL starts with http:// or https://
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Parse URL and rebuild it to normalize components
    try:
        parsed = urlparse(url)
        
        # Remove any unwanted query params or fragments based on the site
        # (This is site-specific, add rules as needed)
        query = parsed.query
        
        # Rebuild the URL
        clean_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            query,
            ''  # Remove fragment (anchor) as it's not needed for the source
        ))
        
        return clean_url
    except Exception as e:
        print(f"Error cleaning URL {url}: {e}")
        return url

def clean_sources_in_database():
    """Clean all source URLs in the database."""
    try:
        supabase = get_supabase_client()
        print("Connected to Supabase")
        
        # Get all sources
        result = supabase.table("sources").select("*").execute()
        sources = result.data if result.data else []
        
        print(f"Found {len(sources)} sources in database")
        
        # Track changes
        updated_count = 0
        
        # Process all sources
        for source in sources:
            original_url = source.get("url", "")
            if not original_url:
                continue
                
            # Clean the URL
            cleaned_url = clean_url(original_url)
            
            # Skip if no change needed
            if cleaned_url == original_url:
                continue
                
            # Update the source
            supabase.table("sources").update({"url": cleaned_url}).eq("id", source["id"]).execute()
            updated_count += 1
            
            print(f"Updated URL: {original_url} -> {cleaned_url}")
        
        print(f"Finished cleaning URLs. Updated {updated_count} sources.")
        
    except Exception as e:
        print(f"Error cleaning sources: {e}")
        import traceback
        traceback.print_exc()

def clean_solution_urls_in_database():
    """Clean all solution URLs in the database."""
    try:
        supabase = get_supabase_client()
        print("Connected to Supabase")
        
        # Get all problems
        result = supabase.table("problems").select("*").execute()
        problems = result.data if result.data else []
        
        print(f"Found {len(problems)} problems in database")
        
        # Track changes
        updated_count = 0
        
        # Process all problems
        for problem in problems:
            original_url = problem.get("solution_url", "")
            if not original_url:
                # Extract URL from solution text if available
                solution_text = problem.get("solution", "")
                if solution_text:
                    url_match = re.search(r'https?://[^\s\)\]\'"]+(?:\.[^\s\)\]\'",]+)+[^\s\)\]\'".,]', solution_text)
                    if url_match:
                        original_url = url_match.group(0)
            
            if not original_url:
                continue
                
            # Clean the URL
            cleaned_url = clean_url(original_url)
            
            # Skip if no change needed
            if cleaned_url == original_url and problem.get("solution_url") == cleaned_url:
                continue
                
            # Update the problem
            supabase.table("problems").update({"solution_url": cleaned_url}).eq("id", problem["id"]).execute()
            updated_count += 1
            
            print(f"Updated solution URL for problem '{problem['statement'][:50]}...': {original_url} -> {cleaned_url}")
        
        print(f"Finished cleaning solution URLs. Updated {updated_count} problems.")
        
    except Exception as e:
        print(f"Error cleaning solution URLs: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n🧹 URL Cleanup Script for Problem Finder")
    print("--------------------------------------")
    
    # Clean source URLs
    print("\nCleaning source URLs...")
    clean_sources_in_database()
    
    # Clean solution URLs
    print("\nCleaning solution URLs...")
    clean_solution_urls_in_database()
    
    print("\nDone!")
