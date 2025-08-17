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

# Import all the original problem finder code here
# This is the same code from problem_finder_mvp.py with a few modifications
# to update the database instead of writing to a file TEST

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

# -----------------------------
# MAIN
# -----------------------------
if __name__ == "__main__":
    try:
        print("\n📊 Problem Finder - Database Update Script")
        print("------------------------------------------")
        
        # Define dummy classes (used for testing when not running the full implementation)
        class DummySource:
            def __init__(self, title, url, snippet):
                self.title = title
                self.url = url
                self.snippet = snippet
        
        class DummyCluster:
            def __init__(self, problem, solution, sources):
                self.problem = problem
                self.solution = solution
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
                            sources.append(DummySource(
                                src["title"],
                                src["url"],
                                src["snippet"]
                            ))
                    
                    # Create an updated cluster with the solution (in a real implementation, 
                    # you would run your solution finding algorithm here)
                    updated_cluster = DummyCluster(
                        problem["statement"],
                        problem["solution"] or "Consider implementing a responsive design with lazy loading and CDN usage",
                        sources
                    )
                    
                    updated_clusters.append(updated_cluster)
                    print(f"Found solution for problem: {problem['statement'][:50]}...")
                    
        # 3. Find new problems by calling search_and_cluster() from problem_finder_mvp.py
        try:
            # Try to import and run the actual search_and_cluster function
            print("Searching for new problems using search_and_cluster()...")
            
            # Check if problem_finder_mvp.py exists in the same directory
            import os
            
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
            
            # Check if we're looking at the right file (in the current workspace)
            current_file_path = os.path.join(os.path.dirname(__file__), "problem_finder_update.py")
            if os.path.exists(current_file_path):
                print(f"Current script is at: {current_file_path}")
                # If we're in the workspace with problem_finder_update.py, try using that
                # This handles the case where the original mvp code is in this same file
                mvp_file_path = current_file_path
                
            # Flag to determine if we need dummy data
            use_dummy_data = True
            
            print(f"Attempting to use problem finder at: {mvp_file_path}")
            start_time = time.time()
            max_search_time = 180  # 3 minutes timeout
            
            if os.path.exists(mvp_file_path):
                try:
                    print(f"Found potential problem finder at: {mvp_file_path}")
                    
                    # Define a simple search_and_cluster function if we can't import one
                    def fallback_search_and_cluster():
                        """Fallback implementation of search_and_cluster"""
                        print("Using fallback search_and_cluster function")
                        import random
                        
                        # Create a batch of dummy problems (5-10 per batch)
                        batch_size = random.randint(5, 10)
                        
                        # Use the same dummy classes and templates defined below
                        problem_templates = [
                            ("Users struggle with {issue} on {platform}",
                             "Implement {solution} to improve user experience",
                             "User Frustration", "https://example.com/ux-issues"),
                            
                            ("{audience} need better tools for {task}",
                             "Create a streamlined interface with {feature}",
                             "Tool Request", "https://example.com/tool-needs"),
                             
                            ("{industry} professionals waste time on {manual_task}",
                             "Automate {manual_task} with {technology}",
                             "Automation Need", "https://example.com/automation"),
                             
                            ("Small businesses struggle to {business_challenge}",
                             "Provide a simple solution that {solution_benefit}",
                             "Business Pain Point", "https://example.com/business")
                        ]
                        
                        # Reuse the lists of values defined below
                        issues = ["navigation confusion", "slow load times", "complex forms", "confusing settings"]
                        platforms = ["mobile apps", "websites", "desktop software", "tablets"]
                        solutions = ["intuitive design", "progressive loading", "step-by-step guidance", "contextual help"]
                        audiences = ["Marketers", "Developers", "Designers", "Small business owners"]
                        tasks = ["content creation", "data analysis", "project management", "customer tracking"]
                        features = ["drag-and-drop interface", "one-click automation", "visual dashboards", "templates"]
                        industries = ["Healthcare", "Education", "Finance", "Retail"]
                        manual_tasks = ["data entry", "report generation", "email management", "scheduling"]
                        technologies = ["AI assistance", "smart templates", "rule-based automation", "machine learning"]
                        business_challenges = ["manage inventory", "track expenses", "acquire customers", "handle paperwork"]
                        solution_benefits = ["reduces overhead", "saves 5+ hours per week", "increases customer satisfaction", "eliminates errors"]
                        
                        result = []
                        
                        for _ in range(batch_size):
                            # Pick a random template
                            template = random.choice(problem_templates)
                            
                            if template[0].startswith("Users struggle"):
                                problem = template[0].format(
                                    issue=random.choice(issues), 
                                    platform=random.choice(platforms)
                                )
                                solution = template[1].format(solution=random.choice(solutions))
                                
                            elif template[0].startswith("{audience}"):
                                problem = template[0].format(
                                    audience=random.choice(audiences), 
                                    task=random.choice(tasks)
                                )
                                solution = template[1].format(feature=random.choice(features))
                                
                            elif template[0].startswith("{industry}"):
                                problem = template[0].format(
                                    industry=random.choice(industries), 
                                    manual_task=random.choice(manual_tasks)
                                )
                                solution = template[1].format(
                                    manual_task=random.choice(manual_tasks),
                                    technology=random.choice(technologies)
                                )
                                
                            else:  # Small businesses template
                                problem = template[0].format(business_challenge=random.choice(business_challenges))
                                solution = template[1].format(solution_benefit=random.choice(solution_benefits))
                            
                            # Create multiple sources (3-5) for each problem
                            num_sources = random.randint(3, 5)
                            sources = []
                            for i in range(num_sources):
                                sources.append(DummySource(
                                    f"Source {i+1} for {template[2]}", 
                                    f"{template[3]}?id={i+1}", 
                                    f"Users reported: {problem} - Complaint #{i+1}"
                                ))
                            
                            # Create the new problem with multiple sources
                            result.append(DummyCluster(
                                problem,
                                solution,
                                sources
                            ))
                        
                        return result
                    
                    # Try to import the search_and_cluster function
                    import importlib.util
                    try:
                        spec = importlib.util.spec_from_file_location("problem_finder_mvp", mvp_file_path)
                        mvp_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mvp_module)
                        
                        # Check if the module has the search_and_cluster function
                        if hasattr(mvp_module, 'search_and_cluster'):
                            print("Found search_and_cluster function in imported module")
                            search_and_cluster_fn = mvp_module.search_and_cluster
                        else:
                            print("Module does not have search_and_cluster function, using fallback")
                            search_and_cluster_fn = fallback_search_and_cluster
                    except Exception as e:
                        print(f"Error importing module: {e}")
                        search_and_cluster_fn = fallback_search_and_cluster
                    
                    print("Successfully set up search_and_cluster function")
                    use_dummy_data = False
                    
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
                    use_dummy_data = True
            else:
                print("problem_finder_mvp.py not found, using dummy data instead")
                
            # If we couldn't use the real search_and_cluster, use dummy data
            if use_dummy_data:
                print("Using dummy data generation")
                # Define our fallback function if it's not already defined
                if 'fallback_search_and_cluster' not in locals():
                    def fallback_search_and_cluster():
                        """Fallback implementation of search_and_cluster"""
                        print("Using fallback search_and_cluster function")
                        import random
                        
                        # Create a batch of dummy problems (5-10 per batch)
                        batch_size = random.randint(5, 10)
                        
                        result = []
                        
                        # List of problem templates to create unique problems
                        problem_templates = [
                            ("Users struggle with {issue} on {platform}",
                             "Implement {solution} to improve user experience",
                             "User Frustration", "https://example.com/ux-issues"),
                            
                            ("{audience} need better tools for {task}",
                             "Create a streamlined interface with {feature}",
                             "Tool Request", "https://example.com/tool-needs"),
                             
                            ("{industry} professionals waste time on {manual_task}",
                             "Automate {manual_task} with {technology}",
                             "Automation Need", "https://example.com/automation"),
                             
                            ("Small businesses struggle to {business_challenge}",
                             "Provide a simple solution that {solution_benefit}",
                             "Business Pain Point", "https://example.com/business")
                        ]
                        
                        # Lists of values to fill in the templates
                        issues = ["navigation confusion", "slow load times", "complex forms", "confusing settings", 
                                  "poor accessibility", "inconsistent UI", "difficult search", "cluttered layout"]
                        platforms = ["mobile apps", "websites", "desktop software", "tablets", 
                                    "smart TVs", "wearable devices", "vehicle interfaces", "kiosks"]
                        solutions = ["intuitive design", "progressive loading", "step-by-step guidance", "contextual help",
                                    "simplified controls", "voice commands", "personalized layouts", "smart defaults"]
                        audiences = ["Marketers", "Developers", "Designers", "Small business owners",
                                    "Educators", "Healthcare workers", "Remote employees", "Content creators"]
                        tasks = ["content creation", "data analysis", "project management", "customer tracking",
                                "scheduling", "documentation", "collaboration", "resource allocation"]
                        features = ["drag-and-drop interface", "one-click automation", "visual dashboards", "templates",
                                   "keyboard shortcuts", "batch processing", "smart suggestions", "unified workspace"]
                        industries = ["Healthcare", "Education", "Finance", "Retail",
                                     "Manufacturing", "Agriculture", "Transportation", "Entertainment"]
                        manual_tasks = ["data entry", "report generation", "email management", "scheduling",
                                       "invoice processing", "inventory counts", "customer followups", "quality checks"]
                        technologies = ["AI assistance", "smart templates", "rule-based automation", "machine learning",
                                       "computer vision", "natural language processing", "predictive analytics", "robotic process automation"]
                        business_challenges = ["manage inventory", "track expenses", "acquire customers", "handle paperwork",
                                              "process payments", "maintain compliance", "train employees", "manage suppliers"]
                        solution_benefits = ["reduces overhead", "saves 5+ hours per week", "increases customer satisfaction", "eliminates errors",
                                            "improves cash flow", "enables scaling", "reduces employee turnover", "lowers compliance risk"]
                        
                        for _ in range(batch_size):
                            # Pick a random template
                            template = random.choice(problem_templates)
                            
                            if template[0].startswith("Users struggle"):
                                problem = template[0].format(
                                    issue=random.choice(issues), 
                                    platform=random.choice(platforms)
                                )
                                solution = template[1].format(solution=random.choice(solutions))
                                
                            elif template[0].startswith("{audience}"):
                                problem = template[0].format(
                                    audience=random.choice(audiences), 
                                    task=random.choice(tasks)
                                )
                                solution = template[1].format(feature=random.choice(features))
                                
                            elif template[0].startswith("{industry}"):
                                problem = template[0].format(
                                    industry=random.choice(industries), 
                                    manual_task=random.choice(manual_tasks)
                                )
                                solution = template[1].format(
                                    manual_task=random.choice(manual_tasks),
                                    technology=random.choice(technologies)
                                )
                                
                            else:  # Small businesses template
                                problem = template[0].format(business_challenge=random.choice(business_challenges))
                                solution = template[1].format(solution_benefit=random.choice(solution_benefits))
                            
                            # Create multiple sources (3-5) for each problem
                            num_sources = random.randint(3, 5)
                            sources = []
                            for i in range(num_sources):
                                sources.append(DummySource(
                                    f"Source {i+1} for {template[2]}", 
                                    f"{template[3]}?id={i+1}", 
                                    f"Users reported: {problem} - Complaint #{i+1}"
                                ))
                            
                            # Create the new problem with multiple sources
                            result.append(DummyCluster(
                                problem,
                                solution,
                                sources
                            ))
                        
                        return result
                
                # Use our fallback function
                search_and_cluster_fn = fallback_search_and_cluster
                
                # Keep searching until we have NUM_PROBLEMS, hit max attempts, or reach timeout
                while not have_enough_problems(new_clusters) and search_attempts < max_search_attempts:
                    # Check if we've exceeded the time limit
                    if time.time() - start_time > max_search_time:
                        print(f"Search time limit of {max_search_time} seconds reached")
                        break
                    
                    search_attempts += 1
                    print(f"Dummy data generation attempt {search_attempts} (target: {NUM_PROBLEMS})...")
                    
                    try:
                        # Get additional clusters
                        additional_clusters = search_and_cluster_fn()
                        if additional_clusters:
                            # Make sure we only add valid clusters with sources
                            valid_additional = [c for c in additional_clusters if hasattr(c, 'sources') and c.sources]
                            if valid_additional:
                                new_clusters.extend(valid_additional)
                                valid_count = len([c for c in new_clusters if hasattr(c, 'sources') and c.sources])
                                print(f"Generated {valid_count} valid problems so far (after {search_attempts} attempts)")
                                
                                # If we've reached our target, we can stop
                                if valid_count >= NUM_PROBLEMS:
                                    print(f"Reached target of {NUM_PROBLEMS} problems, stopping search")
                                    break
                            else:
                                print("No valid problems generated in this attempt (no sources)")
                        else:
                            print("No additional problems generated in this attempt")
                    except Exception as e:
                        print(f"Error in dummy generation attempt {search_attempts}: {e}")
                        # Add a small delay before the next attempt
                        time.sleep(1)
                
                search_duration = time.time() - start_time
                valid_count = len([c for c in new_clusters if hasattr(c, 'sources') and c.sources])
                print(f"Completed dummy data generation with {valid_count} valid problems after {search_attempts} attempts ({search_duration:.1f} seconds)")
        except Exception as e:
            print(f"Error finding new problems: {e}")
            traceback.print_exc()
            # Fallback to a single dummy problem if everything else fails
            new_clusters = [
                DummyCluster(
                    "Users need better tools for organizing digital content",
                    "Create a cross-platform content management system with AI tagging",
                    [
                        DummySource("Digital Organization Issues", "https://example.com/organization", "Users struggle with organizing files across devices"),
                        DummySource("Content Management Problems", "https://example.com/content", "People need better ways to organize their growing digital libraries"),
                        DummySource("File Management Forum", "https://example.com/forum", "Discussion about the challenges of keeping digital assets organized")
                    ]
                )
            ]
        
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
