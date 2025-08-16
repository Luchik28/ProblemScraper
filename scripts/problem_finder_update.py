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

# Suppress HF noise
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from transformers import pipeline, logging as hf_logging
hf_logging.set_verbosity_error()

from sentence_transformers import SentenceTransformer, util
from ddgs import DDGS
from tqdm import tqdm
from supabase import create_client, Client

# Import all the original problem finder code here
# This is the same code from problem_finder_mvp.py with a few modifications
# to update the database instead of writing to a file TEST

# -----------------------------
# CONFIG
# -----------------------------
NUM_PROBLEMS: int = 15                      # how many problems to return
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
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
    
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
    # Check if link already exists
    result = supabase.table("problem_sources").select("*").eq("problem_id", problem_id).eq("source_id", source_id).execute()
    
    if not result.data or len(result.data) == 0:
        # Create new link
        supabase.table("problem_sources").insert({
            "problem_id": problem_id,
            "source_id": source_id
        }).execute()

# [Include all the original problem finder code here]
# ... 

# -----------------------------
# DATABASE UPDATE FUNCTION
# -----------------------------
def update_database_with_problems(clusters):
    """Update the Supabase database with the problems found."""
    try:
        supabase = get_supabase_client()
        print("Connected to Supabase")
        
        # Get current timestamp
        current_time = datetime.datetime.now().isoformat()
        
        for cluster in clusters:
            # Prepare problem data
            problem_data = {
                "statement": cluster.problem,
                "solution": cluster.solution,
                "has_negative_reviews": cluster.has_negative_reviews,
                "review_url": cluster.review_url,
                "updated_at": current_time
            }
            
            # Upsert problem
            problem_id = upsert_problem(supabase, problem_data)
            
            # Handle sources
            for source in cluster.sources:
                source_data = {
                    "title": source.title,
                    "url": source.url,
                    "snippet": source.snippet,
                    "updated_at": current_time
                }
                
                # Upsert source
                source_id = upsert_source(supabase, source_data)
                
                # Link problem to source
                link_problem_source(supabase, problem_id, source_id)
        
        # Clean up old problems that haven't been updated in a long time (90 days)
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=90)).isoformat()
        supabase.table("problems").delete().lt("updated_at", cutoff_date).execute()
        
        print(f"Database updated with {len(clusters)} problems")
    except Exception as e:
        print(f"Error updating database: {e}")
        traceback.print_exc()

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    try:
        print("\n📊 Problem Finder - Database Update Script")
        print("------------------------------------------")
        
        # Run the problem finder and get the clusters
        clusters = search_and_cluster()
        
        # Update the database with the problems
        update_database_with_problems(clusters)
        
    finally:
        # Make sure we clean up resources even if there's an error
        cleanup_resources()
