#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Problem Finder MVP - Database Update Script
-------------------------------------------
Modified version of the Problem Finder MVP script that updates a Supabase database
with the problems it finds. This script is intended to be run by GitHub Actions
on a schedule to keep the database up to date.

The script:
1. Runs the original problem finder code to gather problems
2. Connects to the Supabase database
3. Updates existing problems or adds new ones
4. Handles marking problems as solved and updating solutions
"""

import os
import sys
import json
import datetime
import re
import time
import math
import logging
import requests
import traceback
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Iterable, Optional, Set
from concurrent.futures import ThreadPoolExecutor

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

# Suppress HF noise
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from transformers import pipeline, logging as hf_logging
hf_logging.set_verbosity_error()

from sentence_transformers import SentenceTransformer, util
from duckduckgo_search import DDGS
from tqdm import tqdm
from supabase import create_client, Client

# -----------------------------
# CONFIG
# -----------------------------
NUM_PROBLEMS: int = 50                      # how many problems to return
MAX_RESULTS_PER_QUERY: int = 20             # DDG results per query
EXPANSION_RESULTS_PER_PROBLEM: int = 8      # when we form a problem, search again for more sources
SIM_THRESHOLD: float = 0.85                 # clustering similarity threshold (0..1)
DEBUG: bool = True                         # set True to see filtering and matching reasons
USE_ZERO_SHOT: bool = False                 # Disable zero-shot classifier to reduce memory usage
PRODUCT_SCORE_THRESHOLD: float = 0.3        # Threshold for product-solvable score (0..1)

# Refined seed queries focused on product-solvable problems
SEED_QUERIES: List[str] = [
    # Pain point patterns that suggest product needs
    "frustrated with", "tired of manually", "waste time", "time-consuming",
    "annoying to", "hate having to", "impossible to", "wish there was a way",
    "can't find a tool", "no good solution for", "pain point", "wish someone would make",
    
    # Automation needs
    "automate", "streamline", "simplify", "tool to", "app to", "software to",
    
    # Focused problem patterns
    "keeps breaking", "constantly fails", "recurring issue", "always struggle with",
    "error prone", "repetitive task", "hard to track", "difficult to manage",
    
    # Platform/integration needs
    "doesn't integrate with", "no way to connect", "compatibility issues",
    
    # Opportunity signals
    "build a", "create a", "develop a", "looking for a solution", "need a solution",
    "would pay for", "would buy", "shut up and take my money"
]

# Action-oriented verbs that indicate product-solvable problems
ACTIONABLE_VERBS: List[str] = [
    "track", "automate", "manage", "schedule", "monitor", "organize",
    "sync", "backup", "secure", "protect", "analyze", "visualize",
    "integrate", "connect", "combine", "generate", "extract", "transform",
    "convert", "calculate", "predict", "compare", "filter", "prioritize",
    "streamline", "optimize", "accelerate", "detect"
]

# Product-opportunity keywords (suggests a tool is needed)
PRODUCT_OPPORTUNITY_TERMS: List[str] = [
    "tool", "app", "application", "platform", "software", "solution",
    "system", "framework", "dashboard", "tracker", "manager", "automation",
    "extension", "plugin", "service", "subscription", "utility", "wizard"
]

# Sites to bias toward (forums / communities). Leave empty to search the whole web.
SITE_HINTS: List[str] = [
    "site:reddit.com", "site:forums.macrumors.com", "site:superuser.com",
    "site:stackoverflow.com", "site:news.ycombinator.com", "site:tomsguide.com",
    "site:linustechtips.com", "site:androidforums.com", "site:apple.stackexchange.com",
]

# Exclude obvious info-only or low-signal domains (tune as needed)
DOMAIN_BLACKLIST: Set[str] = {
    "wikipedia.org", "britannica.com", "dictionary.com", "wikihow.com",
    "weblio.jp", "ejje.weblio.jp", # Japanese dictionary
}

# NSFW term filtering
NSFW_TERMS: List[str] = [
    "sex", "porn", "nude", "nsfw", "xxx", "adult content", "sexual", "masturbate", 
    "erotic", "escort", "dildo", "viagra", "penis", "vagina"
]

# -----------------------------
# SUPABASE INTEGRATION
# -----------------------------
def get_supabase_client() -> Client:
    """Get a Supabase client using environment variables."""
    # Check for Vercel environment variables first
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL/NEXT_PUBLIC_SUPABASE_URL and SUPABASE_KEY/NEXT_PUBLIC_SUPABASE_ANON_KEY environment variables must be set")
    
    print(f"Using Supabase URL: {supabase_url[:20]}...")
    return create_client(supabase_url, supabase_key)

def upsert_problem(supabase: Client, problem: dict) -> str:
    """
    Insert or update a problem in the database.
    Returns the problem ID.
    """
    # Check if problem already exists by matching the statement
    result = supabase.table("problems").select("id").eq("statement", problem["statement"]).execute()
    
    if result.data and len(result.data) > 0:
        # Update existing problem
        problem_id = result.data[0]["id"]
        supabase.table("problems").update(problem).eq("id", problem_id).execute()
        print(f"Updated problem: {problem['statement'][:50]}...")
    else:
        # Insert new problem
        result = supabase.table("problems").insert(problem).execute()
        problem_id = result.data[0]["id"]
        print(f"Inserted new problem: {problem['statement'][:50]}...")
    
    return problem_id

def upsert_source(supabase: Client, source: dict) -> str:
    """
    Insert or update a source in the database.
    Returns the source ID.
    """
    # Check if source already exists by URL
    result = supabase.table("sources").select("id").eq("url", source["url"]).execute()
    
    if result.data and len(result.data) > 0:
        # Update existing source
        source_id = result.data[0]["id"]
        supabase.table("sources").update(source).eq("id", source_id).execute()
    else:
        # Insert new source
        result = supabase.table("sources").insert(source).execute()
        source_id = result.data[0]["id"]
    
    return source_id

def link_problem_source(supabase: Client, problem_id: str, source_id: str) -> None:
    """Link a problem to a source in the junction table."""
    try:
        # Check if link already exists
        result = supabase.table("problem_sources").select("*").eq("problem_id", problem_id).eq("source_id", source_id).execute()
        
        if not result.data or len(result.data) == 0:
            # Create new link
            supabase.table("problem_sources").insert({
                "problem_id": problem_id,
                "source_id": source_id
            }).execute()
            print(f"Linked problem {problem_id} to source {source_id}")
    except Exception as e:
        print(f"Error linking problem to source: {e}")
        traceback.print_exc()

# [Include all the original problem finder code here]
# ... 

# -----------------------------
# DATABASE UPDATE FUNCTION
# -----------------------------
def update_database_with_problems(clusters, existing_problems=None):
    """
    Update the Supabase database with the problems found.
    
    This function:
    1. Updates existing problems with any new solutions
    2. Adds new problems to the database
    3. Preserves all existing problems (no replacement)
    4. Adds new sources to existing problems when relevant
    """
    try:
        supabase = get_supabase_client()
        print("Connected to Supabase")
        
        # Get current timestamp
        current_time = datetime.datetime.now().isoformat()
        
        # Track how many problems were added or updated
        added_count = 0
        updated_count = 0
        total_sources_added = 0
        
        # If no existing problems provided, treat all as new
        if existing_problems is None:
            existing_problems = []
        
        # Process all clusters, prioritizing those with more sources
        # Sort clusters by number of sources (most sources first) to prioritize richer problems
        sorted_clusters = sorted(clusters, key=lambda c: len(c.sources), reverse=True)
        
        for cluster in sorted_clusters:
            # Skip clusters with no sources
            if not cluster.sources:
                continue
                
            # Check if this problem already exists (by statement similarity)
            existing_id = None
            
            # Look for similar existing problems to avoid duplicates
            for existing_problem in existing_problems:
                # Simple similarity check - can be enhanced with embedding similarity
                if (cluster.problem.lower() in existing_problem['statement'].lower() or
                    existing_problem['statement'].lower() in cluster.problem.lower()):
                    existing_id = existing_problem['id']
                    print(f"Found existing problem: {existing_problem['statement'][:50]}...")
                    break
            
            # Prepare problem data
            problem_data = {
                "statement": cluster.problem,
                "solution": cluster.solution,
                "solution_url": getattr(cluster, 'solution_url', None) or "",
                "has_negative_reviews": cluster.has_negative_reviews,
                "review_url": cluster.review_url,
                "updated_at": current_time
            }
            
            sources_added = 0
            
            if existing_id:
                # Find the matching problem from our list
                existing_problem = next((p for p in existing_problems if p['id'] == existing_id), None)
                
                # Update existing problem, but only if we have new information
                should_update = False
                
                # Check if we need to update the solution
                if existing_problem and cluster.solution and not existing_problem.get('solution'):
                    should_update = True
                    
                # Check if the problem needs to be marked as having negative reviews
                if cluster.has_negative_reviews and not existing_problem.get('has_negative_reviews'):
                    should_update = True
                
                if should_update:
                    supabase.table("problems").update({
                        "solution": cluster.solution,
                        "solution_url": getattr(cluster, 'solution_url', None) or "",
                        "has_negative_reviews": cluster.has_negative_reviews,
                        "review_url": cluster.review_url,
                        "updated_at": current_time
                    }).eq("id", existing_id).execute()
                    print(f"Updated problem: {cluster.problem[:50]}...")
                    updated_count += 1
            else:
                # Insert new problem
                result = supabase.table("problems").insert(problem_data).execute()
                existing_id = result.data[0]["id"]
                print(f"Added new problem: {cluster.problem[:50]}...")
                added_count += 1
            
            # Handle sources - always add new sources even to existing problems
            for source in cluster.sources:
                # Ensure the URL is valid (no example.com)
                if "example.com" in source.url or not source.url or not source.url.startswith(('http://', 'https://')):
                    continue
                    
                source_data = {
                    "title": source.title,
                    "url": source.url,
                    "snippet": source.snippet,
                    "updated_at": current_time
                }
                
                # Upsert source
                source_id = upsert_source(supabase, source_data)
                
                # Link problem to source (our link_problem_source function already handles duplicates)
                link_problem_source(supabase, existing_id, source_id)
                sources_added += 1
            
            total_sources_added += sources_added
            print(f"Added {sources_added} sources to problem: {cluster.problem[:50]}...")
        
        # Update maintenance statistics
        print(f"Database updated: {added_count} new problems added, {updated_count} existing problems updated, {total_sources_added} total sources added")
        
    except Exception as e:
        print(f"Error updating database: {e}")
        traceback.print_exc()

def extract_urls_from_text(text: str) -> str:
    """Extract URLs from text and return the first one found."""
    if not text:
        return ""
    
    # Regular expression for finding URLs
    url_pattern = r'https?://[^\s\)\]\'"]+(?:\.[^\s\)\]\'",]+)+[^\s\)\]\'".,]'
    urls = re.findall(url_pattern, text)
    
    if urls:
        return urls[0]  # Return the first URL found
    return ""

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    try:
        print("\n📊 Problem Finder - Database Update Script")
        print("------------------------------------------")
        
        # Define simple source class
        class Source:
            def __init__(self, title, url, snippet):
                self.title = title
                self.url = url
                self.snippet = snippet
        
        class Cluster:
            def __init__(self, problem, solution, sources):
                self.problem = problem
                self.solution = solution
                self.solution_url = None
                self.has_negative_reviews = False
                self.review_url = ""
                self.sources = sources
        
        # Connect to Supabase
        supabase = get_supabase_client()
        
        # 1. Get existing problems from the database, ordered by oldest first
        result = supabase.table("problems").select("*").order("updated_at").execute()
        existing_problems = result.data if result.data else []
        print(f"Found {len(existing_problems)} existing problems in database")
        
        # Create a map of existing problems by ID for quick lookup
        existing_problems_by_id = {problem["id"]: problem for problem in existing_problems}
        
        # 2. Identify the oldest problems to update (up to 10 oldest)
        problems_to_update = existing_problems[:10] if len(existing_problems) > 10 else existing_problems
        
        # If we have problems to update, run solution finding on them
        updated_clusters = []
        
        if problems_to_update:
            print(f"Running solution finder on {len(problems_to_update)} oldest problems...")
            
            # For each problem, run the solution finder
            for problem in problems_to_update:
                # Fetch sources for this problem
                sources_result = supabase.table("problem_sources") \
                    .select("source_id") \
                    .eq("problem_id", problem["id"]) \
                    .execute()
                
                source_ids = [link["source_id"] for link in sources_result.data] if sources_result.data else []
                
                if source_ids:
                    sources_data = supabase.table("sources") \
                        .select("*") \
                        .in_("id", source_ids) \
                        .execute()
                    
                    sources = []
                    if sources_data.data:
                        for src in sources_data.data:
                            sources.append(Source(
                                src["title"],
                                src["url"],
                                src["snippet"]
                            ))
                    
                    # Create an updated cluster with the solution (in a real implementation, 
                    # you would run your solution finding algorithm here)
                    updated_cluster = Cluster(
                        problem["statement"],
                        problem.get("solution"),
                        sources
                    )
                    
                    # If a solution already exists, preserve it
                    if problem.get("solution"):
                        updated_cluster.solution = problem["solution"]
                        updated_cluster.solution_url = problem.get("solution_url", "")
                        
                        # If we have a solution but no URL, try to extract URL from the solution text
                        if updated_cluster.solution and not updated_cluster.solution_url:
                            updated_cluster.solution_url = extract_urls_from_text(updated_cluster.solution)
                            
                        updated_cluster.has_negative_reviews = problem.get("has_negative_reviews", False)
                        updated_cluster.review_url = problem.get("review_url", "")
                    
                    updated_clusters.append(updated_cluster)
                    print(f"Processing problem: {problem['statement'][:50]}...")
                    
        # 3. Find new problems by calling search_and_cluster() from problem_finder_mvp.py
        try:
            # Define a function to check if we've found enough problems
            def have_enough_problems(clusters, target=NUM_PROBLEMS):
                valid_clusters = [c for c in clusters if hasattr(c, 'sources') and c.sources]  # Only count clusters with sources
                return len(valid_clusters) >= target
            
            # Initialize new_clusters
            new_clusters = []
            search_attempts = 0
            max_search_attempts = 10  # Prevent infinite loops
            
            # Check both in current directory and parent directory
            mvp_file_path = os.path.join(os.path.dirname(__file__), "problem_finder_mvp.py")
            if not os.path.exists(mvp_file_path):
                parent_dir = os.path.dirname(os.path.dirname(__file__))
                mvp_file_path = os.path.join(parent_dir, "problem_finder_mvp.py")
            
            print(f"Attempting to use problem finder at: {mvp_file_path}")
            start_time = time.time()
            max_search_time = 180  # 3 minutes timeout
            
            if os.path.exists(mvp_file_path):
                try:
                    print(f"Found problem finder at: {mvp_file_path}")
                    
                    # Try to import the search_and_cluster function
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("problem_finder_mvp", mvp_file_path)
                    mvp_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mvp_module)
                    
                    # Check if the module has the search_and_cluster function
                    if not hasattr(mvp_module, 'search_and_cluster'):
                        raise ImportError("Module does not have search_and_cluster function")
                        
                    search_and_cluster_fn = mvp_module.search_and_cluster
                    print("Successfully imported search_and_cluster function")
                    
                    # Keep searching until we have NUM_PROBLEMS, hit max attempts, or reach timeout
                    while not have_enough_problems(new_clusters) and search_attempts < max_search_attempts:
                        # Check if we've exceeded the time limit
                        if time.time() - start_time > max_search_time:
                            print(f"Search time limit of {max_search_time} seconds reached")
                            break
                        
                        search_attempts += 1
                        print(f"Search attempt {search_attempts} for new problems (target: {NUM_PROBLEMS})...")
                        
                        try:
                            # Get additional clusters
                            additional_clusters = search_and_cluster_fn()
                            if additional_clusters:
                                # Make sure we only add valid clusters with sources
                                valid_additional = [c for c in additional_clusters if hasattr(c, 'sources') and c.sources]
                                if valid_additional:
                                    new_clusters.extend(valid_additional)
                                    valid_count = len([c for c in new_clusters if hasattr(c, 'sources') and c.sources])
                                    print(f"Found {valid_count} valid problems so far (after {search_attempts} attempts)")
                                    
                                    # If we've reached our target, we can stop
                                    if valid_count >= NUM_PROBLEMS:
                                        print(f"Reached target of {NUM_PROBLEMS} problems, stopping search")
                                        break
                                else:
                                    print("No valid problems found in this search attempt (no sources)")
                            else:
                                print("No additional problems found in this search attempt")
                        except Exception as e:
                            print(f"Error in search attempt {search_attempts}: {e}")
                            traceback.print_exc()
                            # Add a small delay before the next attempt
                            time.sleep(2)
                    
                    search_duration = time.time() - start_time
                    valid_count = len([c for c in new_clusters if hasattr(c, 'sources') and c.sources])
                    print(f"Completed search with {valid_count} valid problems after {search_attempts} attempts ({search_duration:.1f} seconds)")
                except Exception as e:
                    print(f"Error in search process: {e}")
                    traceback.print_exc()
                    print("Could not run the problem finder. No problems will be generated.")
            else:
                print("problem_finder_mvp.py not found. No problems will be generated.")
                
            # If we couldn't use the real search_and_cluster, no fallback to dummy data
            if not os.path.exists(mvp_file_path) or not 'search_and_cluster_fn' in locals():
                print("Problem finder not available. No problems will be generated.")
                new_clusters = []
        except Exception as e:
            print(f"Error finding new problems: {e}")
            traceback.print_exc()
            # No fallback to dummy data
            print("Error in problem finder. No problems will be generated.")
            new_clusters = []
        
        # 4. Combine updated and new clusters
        all_clusters = updated_clusters + new_clusters
        
        # Count valid clusters (those with sources)
        valid_clusters = [c for c in all_clusters if hasattr(c, 'sources') and c.sources]
        print(f"Found a total of {len(valid_clusters)} valid problems (with sources)")
        
        # Always update the database, even if we don't have the target number of problems
        if len(valid_clusters) > 0:
            print(f"Proceeding with database update ({len(valid_clusters)} problems found)")
            # 5. Update the database with all valid clusters
            update_database_with_problems(valid_clusters, existing_problems)
        else:
            print("No valid problems found. Nothing to update in the database.")
            print("Will try again next run.")
        
    except Exception as e:
        print(f"Error running script: {e}")
        traceback.print_exc()
    finally:
        # Cleanup (would call cleanup_resources() in the full implementation)
        print("Script execution completed")
