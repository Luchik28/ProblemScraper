#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Problem Aggregator — DuckDuckGo + Local AI (no OpenAI, no Reddit API)
--------------------------------------------------------------------
• Searches the open web via DuckDuckGo (free, no keys) for complaint/product-intent phrases
• Converts raw titles/snippets into generalized problem statements ("Need a way to …") using Flan‑T5 locally
• Clusters similar problems with Sentence-Transformers
• Outputs a list of problems with an indented list of sources under each

Install deps:
  pip install ddgs transformers sentence-transformers torch tqdm

Run:
  python problem_aggregator_ddg.py

Tune knobs in CONFIG below.
"""

import os
import re
import sys
import time
import math
import logging
import requests
import traceback
import gc
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Iterable, Optional, Set, Any
from concurrent.futures import ThreadPoolExecutor

# Suppress HF noise
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from transformers import pipeline, logging as hf_logging
hf_logging.set_verbosity_error()

from sentence_transformers import SentenceTransformer, util
from ddgs import DDGS
from tqdm import tqdm

# -----------------------------
# CONFIG
# -----------------------------
NUM_PROBLEMS: int = 15                      # how many problems to return (reduced from 20)
MAX_RESULTS_PER_QUERY: int = 20             # DDG results per query (reduced from 25)
EXPANSION_RESULTS_PER_PROBLEM: int = 8      # when we form a problem, search again for more sources (reduced from 12)
SIM_THRESHOLD: float = 0.85                 # clustering similarity threshold (0..1) - increased for better separation
DEBUG: bool = True                         # set True to see filtering and matching reasons
USE_ZERO_SHOT: bool = False                 # Disable zero-shot classifier to reduce memory usage
PRODUCT_SCORE_THRESHOLD: float = 0.3        # Threshold for product-solvable score (0..1) - lowered to be more inclusive

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
# DATA STRUCTURES
# -----------------------------
@dataclass
class Source:
    title: str
    url: str
    snippet: str = ""

@dataclass
class Cluster:
    problem: str
    embedding: Any
    sources: List[Source] = field(default_factory=list)
    solution: str = ""  # Field to store a potential solution if found
    solution_url: str = ""  # URL to the solution if available
    has_negative_reviews: bool = False  # Whether the solution has negative reviews
    review_url: str = ""  # URL with negative reviews if any

# -----------------------------
# HELPERS
# -----------------------------

def domain_of(url: str) -> str:
    try:
        return re.sub(r"^www\.", "", re.search(r"https?://([^/]+)/", url).group(1))
    except Exception:
        return ""


def is_non_english(url: str) -> bool:
    """Check if the URL is likely to contain non-English content."""
    domain = domain_of(url)
    non_english_domains = {"weblio.jp", "ejje.weblio.jp"}
    return any(domain.endswith(tld) or domain in non_english_domains for tld in [".cn", ".jp", ".kr", ".ru"])


def is_info_only(text: str) -> bool:
    t = text.lower()
    info_patterns = [
        r"\bwhat is\b", r"\bdifference between\b", r"\bmeaning of\b",
        r"\bexplain\b", r"\bhow does\b", r"\bdefinition\b",
        r"\bvs\b", r"\btutorial\b", r"\bguide\b", r"\bwho is\b",
        r"\bwhere can i learn\b", r"\bhow to\b", r"\bhow do i\b",
        r"\bwhat are\b", r"\bwhen to\b", r"\bwhy is\b"
    ]
    return any(re.search(p, t) for p in info_patterns)


def contains_nsfw_content(text: str) -> bool:
    """Check if the text contains NSFW terms."""
    t = text.lower()
    return any(term.lower() in t for term in NSFW_TERMS)


def is_already_resolved(text: str) -> bool:
    """Check if the issue already has a solution mentioned."""
    t = text.lower()
    resolved_patterns = [
        r"(just|finally) (found|bought|discovered|got)",
        r"(works great|solved|fixed|resolved)",
        r"(solution is|answer is)",
        r"(happy with|satisfied with)",
        r"(this solved|this fixed|this worked)"
    ]
    return any(re.search(p, t) for p in resolved_patterns)


def extract_solution(text: str, problem_statement: str = "", source_url: str = "") -> Tuple[str, str]:
    """
    Extract a potential solution from text if one exists.
    If problem_statement is provided, verify the solution is relevant to the problem.
    Returns a tuple of (solution_text, solution_url)
    """
    t = text.lower()
    
    # Common solution patterns
    solution_patterns = [
        r"solution(?:\s+is|:)\s+([^\.]+)",
        r"solved\s+(?:it|this)\s+(?:by|with)\s+([^\.]+)",
        r"fixed\s+(?:it|this)\s+(?:by|with)\s+([^\.]+)",
        r"works?\s+great(?:\s+with|:)\s+([^\.]+)",
        r"recommend\s+(?:using|trying)\s+([^\.]+)",
        r"found\s+(?:that|a)\s+([^\.]+\s+works)",
        r"(?:the\s+best|good)\s+(?:solution|tool|app)\s+(?:is|was)\s+([^\.]+)",
        r"(?:what\s+worked\s+for\s+me\s+was)\s+([^\.]+)",
    ]
    
    for pattern in solution_patterns:
        match = re.search(pattern, t)
        if match:
            solution = match.group(1).strip()
            if len(solution) > 10:  # Only return substantial solutions
                # If we have a problem statement, verify the solution is relevant
                if problem_statement and not is_solution_relevant_to_problem(solution, problem_statement):
                    continue  # Skip this solution if it's not relevant
                
                # Extract URLs from the solution text if any
                solution_url_from_text = extract_url_from_text(solution)
                # Use the source URL if we don't have a URL in the solution text
                final_url = solution_url_from_text or source_url
                
                return solution, final_url
    
    # Try to extract URLs from the entire text if we couldn't find a solution pattern
    if len(text) > 0:
        url_from_text = extract_url_from_text(text)
        if url_from_text:
            return "", url_from_text
    
    return "", source_url


def extract_url_from_text(text: str) -> str:
    """Extract URLs from text and return the first one found."""
    if not text:
        return ""
    
    # Regular expression for finding URLs
    url_pattern = r'https?://[^\s\)\]\'"]+(?:\.[^\s\)\]\'",]+)+[^\s\)\]\'".,]'
    urls = re.findall(url_pattern, text)
    
    if urls:
        # Clean the URL: remove tracking parameters, fragments, etc.
        url = urls[0]
        
        # Simple URL cleaning
        # Remove fragments
        url = re.sub(r'#[^?]*$', '', url)
        
        # Remove common tracking parameters
        url = re.sub(r'[?&]utm_[^&]*', '', url)
        url = re.sub(r'[?&]fbclid=[^&]*', '', url)
        url = re.sub(r'[?&]ref=[^&]*', '', url)
        
        # Fix trailing characters
        url = re.sub(r'[.,;:)]$', '', url)
        
        return url
    return ""


def check_solution_sentiment(solution_text: str, solution_url: str, problem_statement: str) -> Tuple[bool, str]:
    """
    Check if the solution has negative reviews or sentiment.
    Also verifies that the solution is relevant to the problem statement.
    Returns a tuple (has_negative_reviews, details)
    """
    # First, verify the solution is relevant to the problem
    if not is_solution_relevant_to_problem(solution_text, problem_statement):
        return False, ""
    
    # Extract the product/solution name from the solution text
    product_name = ""
    # Look for product names (typically capitalized words or words in quotes)
    product_match = re.search(r'["\']([\w\s\-\+]+)["\']|(?:[A-Z][\w\-\+]+(?:\s+[A-Z][\w\-\+]+){0,3})', solution_text)
    if product_match:
        product_name = product_match.group(0).strip('"\'')
    else:
        # If no clear product name found, take the first few words
        words = solution_text.split()
        if len(words) >= 2:
            product_name = " ".join(words[:min(3, len(words))])
    
    if not product_name:
        return False, ""
    
    # Search for reviews on the solution
    try:
        # Add the problem context to the review search query to find more relevant reviews
        review_query = f"{product_name} {problem_statement} reviews problems issues complaints"
        results = ddg_search(review_query, 5)
        
        if not results:
            return False, ""
            
        # Fetch content for these results
        review_results = fetch_contents_for_sources(results)
        
        # Look for negative sentiment in the reviews
        negative_terms = [
            "disappointing", "terrible", "awful", "useless", "waste", 
            "buggy", "unstable", "unreliable", "expensive", "overpriced",
            "doesn't work", "doesn't solve", "bad", "poor", "slow",
            "difficult", "complicated", "confusing", "frustrating",
            "negative reviews", "bad reviews", "not recommended",
            "stopped working", "crashes", "avoid", "stay away"
        ]
        
        negative_reviews = []
        for src in review_results:
            content = f"{src.title} {src.snippet}".lower()
            found_negatives = [term for term in negative_terms if term in content]
            
            # Verify this review is about the solution and relevant to the problem
            if found_negatives and is_review_relevant(content, product_name, problem_statement):
                negative_reviews.append((src.url, ", ".join(found_negatives)))
                
        if negative_reviews:
            # Return information about the negative reviews
            review_details = negative_reviews[0][0]  # URL of the first negative review
            return True, review_details
            
        return False, ""
    except Exception as e:
        if DEBUG:
            print(f"Error checking solution sentiment: {e}")
        return False, ""


def is_solution_relevant_to_problem(solution_text: str, problem_statement: str) -> bool:
    """
    Check if a solution is semantically relevant to the problem statement.
    Uses keyword matching, context overlap, and semantic similarity.
    """
    # Block common non-solutions that are coming from dictionary definitions
    blacklist_phrases = [
        "simple you need to spend less money",
        "a statement or explanation",
        "the state of being solved",
        "the answer to a problem",
        "definition of solution",
        "meaning of solution",
        "solution meaning",
        "dictionary definition",
        "the act of solving"
    ]
    
    solution_text_lower = solution_text.lower()
    
    # If the solution contains blacklisted phrases, reject it
    if any(phrase in solution_text_lower for phrase in blacklist_phrases):
        return False
        
    # Block solutions from dictionary sites
    dictionary_sites = [
        "merriam-webster.com", 
        "dictionary.com", 
        "oxforddictionaries.com", 
        "cambridge.org/dictionary",
        "britannica.com",
        "lexico.com",
        "vocabulary.com"
    ]
    
    if any(site in solution_text_lower for site in dictionary_sites):
        return False
    
    # Extract key terms from problem statement
    problem_text = problem_statement.lower()
    # Remove common prefixes like "Need a tool to" to get to the core problem
    problem_core = re.sub(r"^need a (tool|solution|platform|app|system) (to|for|that) ", "", problem_text)
    
    # Extract key nouns and verbs from the problem core
    problem_words = set(problem_core.split())
    
    # Common words to ignore in matching
    stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "of", "that", "this", "is", "are", "be", "been", "being", "was", "were", "has", "have", "had"}
    problem_key_terms = [w for w in problem_words if w not in stop_words and len(w) > 3]
    
    # Check for term overlap
    term_matches = sum(1 for term in problem_key_terms if term in solution_text_lower)
    
    # If the solution has several key terms from the problem, consider it relevant
    if term_matches >= min(2, len(problem_key_terms) / 2):
        return True
        
    # Check for concept matching (more advanced)
    problem_concepts = extract_concepts(problem_core)
    solution_concepts = extract_concepts(solution_text_lower)
    
    concept_overlap = len(problem_concepts.intersection(solution_concepts))
    if concept_overlap > 0:
        return True
    
    # If no clear indicators, it's probably not relevant
    return False


def is_review_relevant(review_text: str, product_name: str, problem_statement: str) -> bool:
    """
    Check if a review is actually about the product/solution and relevant to the problem.
    """
    # Ensure the review is actually about the product
    if product_name.lower() not in review_text.lower():
        return False
        
    # Extract problem key terms
    problem_text = problem_statement.lower()
    problem_core = re.sub(r"^need a (tool|solution|platform|app|system) (to|for|that) ", "", problem_text)
    problem_words = set(problem_core.split())
    
    # Common words to ignore
    stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", "of", "that", "this", "is", "are", "be", "been", "being", "was", "were", "has", "have", "had"}
    problem_key_terms = [w for w in problem_words if w not in stop_words and len(w) > 3]
    
    # Check if the review discusses issues related to the problem
    term_matches = sum(1 for term in problem_key_terms if term in review_text.lower())
    
    # Check for specific context mismatch indicators
    context_mismatch_patterns = [
        "business returns", "return policy", "refund policy",  # For consumer policy pages
        "dictionary", "definition", "etymology",  # For dictionary pages
        "legal advice", "terms of service", "policy"  # For legal pages
    ]
    
    # Return false if the review seems to be about an unrelated topic
    if any(pattern in review_text.lower() for pattern in context_mismatch_patterns):
        return False
    
    # If we have at least some term overlap, consider it relevant
    return term_matches >= 1


def extract_concepts(text: str) -> Set[str]:
    """
    Extract key concepts from text to help with semantic matching.
    """
    # Simple concept extraction based on common phrases and domain-specific terms
    concepts = set()
    
    # Management-related concepts
    if any(term in text for term in ["team", "manage", "collaborat", "communicat", "project"]):
        concepts.add("team_management")
        
    # Productivity concepts
    if any(term in text for term in ["productiv", "efficien", "track", "progress", "milestone"]):
        concepts.add("productivity")
        
    # Development concepts
    if any(term in text for term in ["code", "develop", "program", "software", "debug"]):
        concepts.add("software_development")
        
    # Music production concepts
    if any(term in text for term in ["music", "audio", "sound", "produc", "mix", "track"]):
        concepts.add("music_production")
        
    # Relationship concepts
    if any(term in text for term in ["relationship", "partner", "communicat", "conflict"]):
        concepts.add("relationships")
        
    # Family/education concepts
    if any(term in text for term in ["family", "child", "parent", "educate", "school", "teach"]):
        concepts.add("family_education")
        
    # Technology concepts
    if any(term in text for term in ["app", "tool", "platform", "software", "system", "tech"]):
        concepts.add("technology")
        
    return concepts


def search_for_solution(problem_statement: str) -> Tuple[str, str]:
    """
    Actively search for a solution to a given problem statement.
    Returns a tuple of (solution_text, solution_url).
    If negative reviews are found, includes that information in the solution text.
    """
    try:
        # Formulate a search query specifically looking for solutions
        # Make the query more specific by including additional context
        core_problem = re.sub(r"^need a (tool|solution|platform|app|system) (to|for|that) ", "", problem_statement.lower())
        solution_query = f"best tool software app for {core_problem} solution how to solve"
        
        # Search for solutions
        results = ddg_search(solution_query, 8)  # Increase to more results
        
        if not results:
            return "", ""
            
        # Fetch content for these results
        enhanced_results = fetch_contents_for_sources(results)
        
        # Skip sources from known dictionary and reference sites
        dictionary_sites = [
            "merriam-webster.com", 
            "dictionary.com", 
            "oxforddictionaries.com", 
            "cambridge.org/dictionary",
            "britannica.com",
            "lexico.com",
            "vocabulary.com",
            "wikipedia.org",
            "thesaurus.com",
            "wordreference.com",
            "yourdictionary.com"
        ]
        
        # Look for solution patterns in the results
        for src in enhanced_results:
            full_content = src.snippet
            
            # Skip dictionary and definition sites
            if any(site in src.url.lower() for site in dictionary_sites):
                continue
            
            # Check if this looks like a solution page (rather than another forum post with the same problem)
            solution_indicators = [
                "how to", "tutorial", "guide", "solution", "solved", "fix", "answer",
                "resolving", "workaround", "here's how", "this is how", "best tools",
                "recommended", "top 10", "best apps", "ultimate guide", "software for",
                "tool for", "best platform", "alternatives", "comparison"
            ]
            
            # Check title and content for solution indicators
            is_solution_page = any(indicator in full_content.lower() for indicator in solution_indicators) or \
                              any(indicator in src.title.lower() for indicator in solution_indicators)
            
            if is_solution_page:
                # Extract the potential solution
                solution_text, solution_url = extract_solution(full_content, problem_statement, src.url)
                if solution_text:
                    # Double-check the solution is relevant to the problem
                    if is_solution_relevant_to_problem(solution_text, problem_statement):
                        # Check if the solution has negative reviews
                        has_negative_reviews, review_url = check_solution_sentiment(solution_text, solution_url or src.url, problem_statement)
                        
                        solution_text_with_source = solution_text
                        if has_negative_reviews:
                            solution_text_with_source += " [WARNING: Has negative reviews]"
                        
                        return solution_text_with_source, solution_url or src.url
                else:
                    # Before returning just the URL, check if the title suggests it's actually a solution
                    solution_title_indicators = ["best", "top", "guide", "how to", "solution", "tool", "app", "software"]
                    if any(indicator in src.title.lower() for indicator in solution_title_indicators):
                        # Only return URLs that seem to be actual solution listings, not just mentions
                        if any(term in src.title.lower() for term in ["best", "top", "recommended", "tools", "apps", "software", "platforms", "solutions"]):
                            return f"Potential solutions listed at: {src.title}", src.url
        
        # If we didn't find a solution with the first query, try a more direct query
        direct_query = f"best tool app software for {core_problem} alternatives comparison"
        results = ddg_search(direct_query, 8)
        
        if results:
            enhanced_results = fetch_contents_for_sources(results)
            
            for src in enhanced_results:
                # Skip dictionary and definition sites
                if any(site in src.url.lower() for site in dictionary_sites):
                    continue
                
                # Try to extract recommendations from these results
                if "best" in src.title.lower() or "top" in src.title.lower() or "recommended" in src.title.lower():
                    # Extract the solution if possible
                    solution_text, solution_url = extract_solution(src.snippet, problem_statement, src.url)
                    if solution_text and is_solution_relevant_to_problem(solution_text, problem_statement):
                        # Check for negative reviews
                        has_negative_reviews, review_url = check_solution_sentiment(solution_text, solution_url or src.url, problem_statement)
                        
                        solution_text_with_source = solution_text
                        if has_negative_reviews:
                            solution_text_with_source += " [WARNING: Has negative reviews]"
                            
                        return solution_text_with_source, solution_url or src.url
                    else:
                        # Check if the title clearly indicates this is a solution list/recommendation
                        solution_title_indicators = ["best", "top", "recommended", "tools", "apps", "software", "alternatives", "comparison"]
                        if any(indicator in src.title.lower() for indicator in solution_title_indicators):
                            return f"List of solutions: {src.title}", src.url
        
        return "", ""
    except Exception as e:
        if DEBUG:
            print(f"Error searching for solution: {e}")
        return "", ""


def is_discussion_or_opinion(text: str) -> bool:
    """Check if the text is a discussion or opinion rather than a problem."""
    t = text.lower()
    discussion_patterns = [
        r"\bthoughts on\b", r"\bopinion on\b", r"\bwhat do you think\b",
        r"\banyone else\b", r"\bam i the only one\b", r"\bdoes anyone else\b",
        r"\byour favorite\b", r"\bpoll\b", r"\bvote\b", r"\bdebate\b"
    ]
    return any(re.search(p, t) for p in discussion_patterns)


def contains_actionable_verb(text: str) -> bool:
    """Check if the text contains an actionable verb indicating a product-solvable problem."""
    t = text.lower()
    return any(verb.lower() in t for verb in ACTIONABLE_VERBS)


def calculate_product_potential_score(text: str) -> float:
    """
    Calculate a score (0.0-1.0) representing how likely this problem can be solved with a product.
    Higher scores indicate better product potential.
    
    Optimized to be more generous with scoring to include more potential product opportunities.
    """
    t = text.lower()
    score = 0.2  # Start with a base score to be more inclusive
    
    # Check for actionable verbs (strong indicator of product potential)
    verb_count = sum(1 for verb in ACTIONABLE_VERBS if verb.lower() in t)
    if verb_count > 0:
        score += min(0.5, verb_count * 0.15)  # Up to 0.5 for verbs (increased)
    
    # Check for product opportunity terms
    product_term_count = sum(1 for term in PRODUCT_OPPORTUNITY_TERMS if term.lower() in t)
    if product_term_count > 0:
        score += min(0.4, product_term_count * 0.15)  # Up to 0.4 for product terms (increased)
    
    # Negative patterns (information-seeking) reduce score (less severe penalties)
    info_seeking_patterns = [
        r"\bwhat is\b", r"\bwhich is\b", r"\bwhere can i\b", 
        r"\bhow to\b", r"\bhow do i\b", r"\bfind the best\b",
        r"\brecommend\b", r"\bsuggestion\b", r"\bidea\b"
    ]
    info_pattern_count = sum(1 for p in info_seeking_patterns if re.search(p, t))
    if info_pattern_count > 0:
        score -= min(0.3, info_pattern_count * 0.08)  # Reduced penalty to 0.3 max
        
    # Positive indicators of product potential (expanded patterns)
    product_patterns = [
        r"\bautomate\b", r"\bstreamline\b", r"\boptimize\b", r"\btrack\b", r"\bsynch?ronize\b",
        r"\bwaste (time|money)\b", r"\bfrustrated\b", r"\bmanually\b", r"\bcan'?t find\b",
        r"\brepetitive\b", r"\btime-consuming\b", r"\berror[- ]prone\b", r"\bdifficult to\b", 
        r"\bwish there was\b", r"\bno (good|existing) (tool|solution|app)\b", r"\btired of\b",
        r"\bannoy(s|ing|ed)\b", r"\bhard to\b", r"\bkeeps? breaking\b", r"\bconstantly\b",
        r"\bwould (buy|pay for)\b", r"\bshut up and take my money\b", r"\bneed (a|an|to)\b"
    ]
    product_pattern_count = sum(1 for p in product_patterns if re.search(p, t))
    if product_pattern_count > 0:
        score += min(0.5, product_pattern_count * 0.12)  # Up to 0.5 for product patterns (increased)
    
    # Bonus for explicit tool mentions (increased)
    if re.search(r"\b(need|want|looking for) (a|an|some) (tool|app|solution|software)\b", t):
        score += 0.3
    
    # Penalty for "find the best X" patterns (reduced)
    if re.search(r"\bfind the best\b", t) or re.search(r"\bwhich (is|are) (the )?best\b", t):
        score -= 0.2
        
    # Ensure score stays in 0.0-1.0 range
    return max(0.0, min(1.0, score))


def is_pain_point(text: str) -> Tuple[bool, str]:
    """Enhanced heuristic filter for product-solvable pain points."""
    t = text.lower()
    
    # Filter out NSFW content
    if contains_nsfw_content(t):
        return False, "contains NSFW content"
        
    # Filter out information-only queries
    if is_info_only(t):
        return False, "info-only"
        
    # Filter out already resolved issues
    if is_already_resolved(t):
        return False, "already resolved"
        
    # Filter out discussions or opinions
    if is_discussion_or_opinion(t):
        return False, "discussion or opinion"

    # Complaint terms (existing)
    complaint_terms = [
        "broken", "broke", "doesn't work", "doesnt work", "won't work", "wont work",
        "can't", "cant", "lag", "slow", "overheating", "crashing", "crash",
        "drains", "battery life", "noisy", "loud", "buzzing", "annoying",
        "hate", "frustrated", "pain", "issue", "problem", "stuck",
    ]
    
    # Product intent terms (existing)
    product_intent = [
        "need", "looking for", "recommend", "recommendation", "replacement",
        "alternative", "upgrade", "fix", "repair", "best way to",
    ]
    
    # Advanced product opportunity signals
    product_opportunity = [
        "automate", "streamline", "optimize", "tool", "app", "solution",
        "waste time", "time-consuming", "manually", "repetitive",
        "wish there was", "app that can", "platform for"
    ]
    
    # Check if the text contains complaint terms or product intent terms
    has_complaint = any(term in t for term in complaint_terms)
    has_intent = any(term in t for term in product_intent)
    has_actionable = contains_actionable_verb(t)
    has_opportunity = any(term in t for term in product_opportunity)
    
    # Calculate product potential score
    product_score = calculate_product_potential_score(t)
    
    # Must have either a complaint, product intent, or contain an actionable verb
    # AND meet the minimum product score threshold
    if (has_complaint or has_intent or has_actionable or has_opportunity) and product_score >= PRODUCT_SCORE_THRESHOLD:
        return True, f"matches product criteria (score: {product_score:.2f})"
    
    return False, f"no signal or low product potential (score: {product_score:.2f})"


def dedupe_sources(sources: List[Source]) -> List[Source]:
    seen: Set[str] = set()
    out: List[Source] = []
    for s in sources:
        key = (s.title.strip().lower(), s.url.split('#')[0])
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out

# -----------------------------
# SEARCH LAYER (DuckDuckGo)
# -----------------------------

def fetch_page_content(url: str, timeout: int = 10) -> str:
    """Fetch the content of a webpage and extract the main text."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        # Use regex to extract text from HTML (more lightweight than BeautifulSoup)
        # Remove script and style elements
        html = response.text
        html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL)
        
        # Remove HTML tags but keep their content
        text = re.sub(r'<[^>]+>', ' ', html)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Keep only a reasonable amount of text (first 2000 characters)
        return text[:2000]
    except Exception as e:
        if DEBUG:
            print(f"Error fetching content from {url}: {e}")
        return ""

def fetch_contents_for_sources(sources: List[Source], max_workers: int = 5) -> List[Source]:
    """Fetch content for multiple sources in parallel."""
    def fetch_for_source(source: Source):
        content = fetch_page_content(source.url)
        if content:
            source.snippet = content
        return source
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        return list(executor.map(fetch_for_source, sources))

def ddg_search(query: str, max_results: int) -> List[Source]:
    """Search DuckDuckGo and return list of Source(title,url,snippet)."""
    results: List[Source] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results, safesearch="moderate"):
                url = r.get("href") or r.get("url") or ""
                if not url:
                    continue
                    
                d = domain_of(url)
                
                # Skip blacklisted domains
                if any(bad in d for bad in DOMAIN_BLACKLIST):
                    if DEBUG:
                        print(f"skip (blacklisted domain: {d}): {url}")
                    continue
                
                title = (r.get("title") or "").strip()
                body = (r.get("body") or "").strip()
                
                # Skip results with empty title and body
                if not title and not body:
                    if DEBUG:
                        print(f"skip (empty content): {url}")
                    continue
                
                # Skip results that contain Japanese or other non-Latin characters
                if any(ord(c) > 127 for c in title + body):
                    if DEBUG:
                        print(f"skip (non-Latin characters): {url}")
                    continue
                
                results.append(Source(title=title or body[:80], url=url, snippet=body))
    except Exception as e:
        if DEBUG:
            print(f"DDG error for '{query}': {e}")
    return results

# -----------------------------
# AI LAYER (Local models)
# -----------------------------

# Models will be initialized when needed, not at import time
_problem_gen = None
_intent_classifier = None
_embed_model = None

def init_models():
    """Initialize AI models on-demand to prevent resource leaks"""
    global _problem_gen, _intent_classifier, _embed_model
    
    if _problem_gen is None:
        _problem_gen = pipeline("text2text-generation", model="google/flan-t5-base")
    
    if USE_ZERO_SHOT and _intent_classifier is None:
        _intent_classifier = pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1  # CPU
        )
    
    if _embed_model is None:
        _embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def classify_intent(text: str) -> str:
    """Classify text into intent categories using zero-shot classification or heuristics."""
    # If zero-shot is disabled, use heuristics
    if not USE_ZERO_SHOT:
        t = text.lower()
        if is_info_only(t):
            return "information request"
        if is_discussion_or_opinion(t):
            return "discussion or opinion"
        if contains_actionable_verb(t) or is_pain_point(t)[0]:
            return "product-solvable problem"
        return "product-solvable problem"  # Default to product solvable
    
    # Initialize models if needed
    init_models()
    
    # Use zero-shot classifier
    candidates = [
        "product-solvable problem",
        "information request",
        "discussion or opinion"
    ]
    try:
        result = _intent_classifier(text, candidates)
        return result['labels'][0]  # Return the highest probability label
    except Exception as e:
        if DEBUG:
            print(f"Intent classification error: {e}")
        # Default to assuming it's a product-solvable problem
        return "product-solvable problem"


def extract_need_and_object(text: str) -> Tuple[str, str]:
    """Extract the primary need/verb and object from the text."""
    # Common need patterns
    need_patterns = [
        r"(?:need|want|looking for)(?: a| an| to)? (.+?)(?:\.|\?|!|$)",
        r"(?:how (?:do|can) (?:i|you|we)) (.+?)(?:\.|\?|!|$)",
        r"(?:recommend|suggest)(?: a| an| me| some)? (.+?)(?:\.|\?|!|$)",
        r"(?:trying to) (.+?)(?:\.|\?|!|$)",
        r"(?:help with) (.+?)(?:\.|\?|!|$)",
        r"(?:way to|tool for) (.+?)(?:\.|\?|!|$)",
    ]
    
    # Try to extract using patterns
    for pattern in need_patterns:
        match = re.search(pattern, text.lower())
        if match:
            extracted = match.group(1).strip()
            # Try to extract a verb + object structure
            verb_match = re.search(r"(\w+)(?:\s+)(.+)", extracted)
            if verb_match:
                verb = verb_match.group(1)
                obj = verb_match.group(2)
                return verb, obj
            return "have", extracted  # Default verb if no clear verb found
    
    # Fallback: Use the text as is
    return "solve", "this problem"


def clean_text(text: str) -> str:
    """Clean text by removing filler words, emojis, and extra punctuation."""
    # Remove emoji pattern
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # Geometric Shapes
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251" 
        "]+", flags=re.UNICODE
    )
    text = emoji_pattern.sub(r'', text)
    
    # Remove filler words
    filler_words = [
        r'\bjust\b', r'\bbasically\b', r'\bliterally\b', r'\bactually\b',
        r'\bso\b', r'\blike\b', r'\byou know\b', r'\bi mean\b', r'\bum\b',
        r'\buh\b', r'\bhmm\b', r'\bwell\b', r'\bokay\b', r'\bsure\b'
    ]
    for word in filler_words:
        text = re.sub(word, '', text, flags=re.IGNORECASE)
    
    # Clean up extra whitespace and punctuation
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
    text = re.sub(r'[!?]+', '?', text)  # Replace multiple ! or ? with a single one
    
    return text.strip()


def to_problem_statement(text: str, full_content: str = "") -> Optional[str]:
    """
    Convert raw text into a generalized problem statement focused on product opportunities.
    Uses pattern matching and NLP to extract the core need.
    If full_content is provided, it will be used to enhance the problem statement.
    
    Modified to be more inclusive in generating product opportunities.
    """
    # First, clean the text
    cleaned_text = clean_text(text)
    
    # If we have full content, add it to the cleaned text for better context
    context_text = cleaned_text
    if full_content and len(full_content) > 50:
        # Use both the title/snippet and the full content, but truncate to a reasonable size
        full_content_cleaned = clean_text(full_content[:1500])
        context_text = f"{cleaned_text}. {full_content_cleaned}"
    
    # Product-focused patterns - prioritize these over general patterns
    
    # "Tool/app to X" pattern
    tool_pattern = re.compile(r"(?:need|want|looking for) (?:a |an |some )?(?:tool|app|software|solution) (?:to|for|that can) ([^\.\?\,]+)", re.IGNORECASE)
    tool_match = tool_pattern.search(context_text)
    if tool_match:
        action = tool_match.group(1).strip()
        if action and len(action) > 3:
            return f"Need a tool to {action}."
    
    # "Automate/streamline X" pattern
    automate_pattern = re.compile(r"(?:automate|streamline|simplify|optimize) ([^\.\?\,]+)", re.IGNORECASE)
    automate_match = automate_pattern.search(context_text)
    if automate_match:
        process = automate_match.group(1).strip()
        if process and len(process) > 3:
            return f"Need a way to automate {process}."
    
    # "Tired of manually X" pattern
    manual_pattern = re.compile(r"(?:tired of|sick of|hate|frustrated with|annoyed by) (?:manually|constantly|always having to|repeatedly) ([^\.\?\,]+)", re.IGNORECASE)
    manual_match = manual_pattern.search(context_text)
    if manual_match:
        task = manual_match.group(1).strip()
        if task and len(task) > 3:
            return f"Need a solution to automate {task}."
    
    # "Waste time X" pattern
    waste_pattern = re.compile(r"(?:waste|spend) (?:too much |a lot of )?(?:time|hours|effort) ([^\.\?\,]+)", re.IGNORECASE)
    waste_match = waste_pattern.search(context_text)
    if waste_match:
        activity = waste_match.group(1).strip()
        if activity and len(activity) > 3:
            return f"Need a tool to reduce time spent {activity}."
    
    # "No way to X" pattern
    no_way_pattern = re.compile(r"(?:no way to|can't|cannot|impossible to|difficult to) ([^\.\?\,]+)", re.IGNORECASE)
    no_way_match = no_way_pattern.search(context_text)
    if no_way_match:
        capability = no_way_match.group(1).strip()
        if capability and len(capability) > 3:
            return f"Need a solution that enables users to {capability}."
    
    # "X doesn't integrate with Y" pattern
    integrate_pattern = re.compile(r"([^\.\?\,]+) (?:doesn't|does not|won't|can't) (?:integrate|connect|work) with ([^\.\?\,]+)", re.IGNORECASE)
    integrate_match = integrate_pattern.search(context_text)
    if integrate_match:
        system1 = integrate_match.group(1).strip()
        system2 = integrate_match.group(2).strip()
        if system1 and system2 and len(system1) > 2 and len(system2) > 2:
            return f"Need a tool to integrate {system1} with {system2}."
    
    # "Hard to X" pattern
    hard_pattern = re.compile(r"(?:hard|difficult|challenging|impossible|frustrating) to ([^\.\?\,]+)", re.IGNORECASE)
    hard_match = hard_pattern.search(context_text)
    if hard_match:
        challenge = hard_match.group(1).strip()
        if challenge and len(challenge) > 3:
            return f"Need a tool that makes it easy to {challenge}."
    
    # "Frustrated with X" pattern (expanded to capture more frustration signals)
    frustration_pattern = re.compile(r"(?:frustrated|annoyed|fed up|upset|tired) (?:with|by|about) ([^\.\?\,]+)", re.IGNORECASE)
    frustration_match = frustration_pattern.search(context_text)
    if frustration_match:
        issue = frustration_match.group(1).strip()
        if issue and len(issue) > 3:
            # Try to extract a potential product opportunity from the frustration
            if re.search(r"\b(app|tool|software|website|platform|system)\b", issue, re.IGNORECASE):
                return f"Need a better alternative to {issue}."
            else:
                return f"Need a solution to address frustrations with {issue}."
    
    # "Problem with X" pattern (new)
    problem_pattern = re.compile(r"(?:problem|issue|trouble) (?:with|when) ([^\.\?\,]+)", re.IGNORECASE)
    problem_match = problem_pattern.search(context_text)
    if problem_match:
        pain_point = problem_match.group(1).strip()
        if pain_point and len(pain_point) > 3:
            return f"Need a tool to solve problems when {pain_point}."
    
    # "Keeps breaking/failing" pattern (new)
    breaking_pattern = re.compile(r"([^\.\?\,]+) (?:keeps|constantly) (?:breaking|failing|crashing)", re.IGNORECASE)
    breaking_match = breaking_pattern.search(context_text)
    if breaking_match:
        item = breaking_match.group(1).strip()
        if item and len(item) > 3:
            return f"Need a more reliable solution for {item}."
    
    # Handle "Need a new X" or general pattern only if no product pattern matched
    need_new_pattern = re.compile(r"(?:need|looking for|want) (?:a )?(?:new|replacement|better) ([^\.\?\,]+)", re.IGNORECASE)
    need_new_match = need_new_pattern.search(cleaned_text)
    if need_new_match:
        item = need_new_match.group(1).strip()
        if item and len(item) > 2:
            # Convert "need a new X" to a more product-focused statement
            if re.search(r"\b(app|tool|software|platform)\b", item, re.IGNORECASE):
                return f"Need a better {item} with improved features."
            else:
                # Only create a product-focused statement for appropriate items
                product_items = ["tracker", "manager", "organizer", "planner", "system", "software", "solution"]
                # More generous - try to turn more items into product opportunities
                if any(prod_item in item.lower() for prod_item in product_items):
                    return f"Need a tool to replace or improve upon existing {item}."
                else:
                    # Try to infer a product opportunity from the context
                    # Look for words like "managing", "tracking", "organizing"
                    activity_words = ["manag", "track", "organiz", "schedul", "automat", "sync"]
                    if any(word in context_text.lower() for word in activity_words):
                        return f"Need a tool for better {item} management."
    
    # If we couldn't match a specific product pattern, try extracting need and object
    if len(context_text) > 10:
        verb, obj = extract_need_and_object(context_text)
        
        # More generous - even if the verb isn't in ACTIONABLE_VERBS, try to construct a statement
        if verb and obj and len(verb) > 2 and len(obj) > 2:
            # If the verb is a known actionable verb, use it directly
            if verb in ACTIONABLE_VERBS:
                problem = f"Need a tool to help {verb} {obj}"
            else:
                # Otherwise, try to map it to a product opportunity
                problem = f"Need a solution for {obj}"
            
            if not problem.endswith((".", "?", "!")):
                problem += "."
            return problem
    
    # Fallback to AI-based generation with a product focus
    try:
        # Initialize models if needed
        init_models()
        
        # Create a product-focused prompt
        prompt = (
            "Extract a product-solvable problem from the following text. "
            "Create a statement describing a problem that could be solved with a SOFTWARE TOOL, APP, or PLATFORM. "
            "Focus on automation, efficiency, integration, or analytics opportunities. "
            "Start with 'Need a tool to...' or 'Need a platform for...'. "
            "If the problem is just asking for information or recommendations, return SKIP.\n\n"
            f"Text: {context_text}\n\n"
            "Product-Solvable Problem:"
        )
        
        out = _problem_gen(prompt, max_new_tokens=64, do_sample=False)[0]["generated_text"].strip()
        
        # Check if the model decided to skip
        if out.upper() == "SKIP" or "information" in out.lower() or "recommend" in out.lower():
            return None
        
        # Normalize style
        out = re.sub(r"^\s*(Problem:|Statement:|Task:)\s*", "", out, flags=re.I)
        
        # Ensure it starts with an appropriate phrase
        product_starters = ["need a tool to", "need a platform for", "need a solution to", "need an app to", "need a system for"]
        if not any(out.lower().startswith(starter) for starter in product_starters):
            out = "Need a tool to " + out.lstrip().rstrip(".")
        
        # Clean up the output to ensure it's well-formed
        out = out.strip().rstrip(".")
        
        # Make sure the output isn't too long or too short
        if len(out.split()) > 15:
            # Try to shorten by removing unnecessary words
            out = re.sub(r"\b(in order|basically|essentially|actually|simply|just)\b", "", out, flags=re.I)
            # If still too long, truncate and ensure it makes sense
            if len(out.split()) > 15:
                words = out.split()
                out = " ".join(words[:15])
                
        # Final check - if it contains "find the best" pattern, it's probably not a good product opportunity
        if re.search(r"find the best", out, flags=re.I):
            return None
                
        return out + "."
    except Exception as e:
        if DEBUG:
            print(f"Problem generation error: {e}")
        
        # We'll return None instead of a fallback, as we only want good product opportunities
        return None


def embed(text: str):
    # Initialize models if needed
    init_models()
    return _embed_model.encode(text, convert_to_tensor=True)

# -----------------------------
# CORE LOGIC
# -----------------------------

def search_and_cluster() -> List[Cluster]:
    clusters: List[Cluster] = []
    visited_queries: Set[str] = set()
    unmatched_sources: List[Tuple[Source, any]] = []  # Sources that don't match any cluster

    # Build initial query list (seed queries with site hints)
    initial_queries: List[str] = []
    for q in SEED_QUERIES:
        if SITE_HINTS:
            initial_queries.extend([f"{q} {site}" for site in SITE_HINTS])
        else:
            initial_queries.append(q)

    to_search: List[str] = initial_queries[:]

    pbar = tqdm(total=0, unit="hits", bar_format="{l_bar}{bar}| {n_fmt} {unit}")

    while to_search and len(clusters) < NUM_PROBLEMS:
        query = to_search.pop(0)
        if query in visited_queries:
            continue
        visited_queries.add(query)

        results = ddg_search(query, MAX_RESULTS_PER_QUERY)
        pbar.update(len(results))
        
        # Filter results first (to avoid fetching content for non-promising sources)
        filtered_results = []
        for src in results:
            combined_text = f"{src.title} {src.snippet}"
            
            # Check for non-English content
            if is_non_english(src.url) or any(ord(c) > 127 for c in combined_text):
                if DEBUG:
                    print(f"skip (non-Latin characters): {src.url}")
                continue
                
            # First check for NSFW content
            if contains_nsfw_content(combined_text):
                if DEBUG:
                    print(f"skip (NSFW content): {src.title}")
                continue
                
            # Filter to product-solvable problems using enhanced filtering
            ok, why = is_pain_point(combined_text)
            if not ok:
                if DEBUG:
                    print(f"skip ({why}): {src.title}")
                continue
                
            # Additional intent classification for better filtering
            intent = classify_intent(combined_text)
            if intent != "product-solvable problem":
                if DEBUG:
                    print(f"skip (intent: {intent}): {src.title}")
                continue
                
            filtered_results.append(src)
        
        # For the promising sources, fetch the full content (in parallel)
        if filtered_results:
            enhanced_results = fetch_contents_for_sources(filtered_results)
            
            for src in enhanced_results:
                # Get full content (could be the original snippet if fetch failed)
                full_content = src.snippet
                
                # Calculate product potential score to prioritize good opportunities
                combined_text = f"{src.title} {full_content[:300]}"
                product_score = calculate_product_potential_score(combined_text)
                
                # Skip sources with low product potential
                if product_score < PRODUCT_SCORE_THRESHOLD:
                    if DEBUG:
                        print(f"skip (low product potential score: {product_score:.2f}): {src.title}")
                    continue
                
                # Turn into improved problem statement using the full content
                problem = to_problem_statement(src.title, full_content)
                
                # Skip if the problem statement is None (not a good product opportunity)
                if problem is None:
                    if DEBUG:
                        print(f"skip (not a product opportunity): {src.title}")
                    continue
                    
                # Skip generic problem statements
                if problem == "Need a way to solve this problem.":
                    if DEBUG:
                        print(f"skip (generic problem statement): {src.title}")
                    continue
                    
                # Make sure the problem statement doesn't just repeat the original text
                if problem.lower().startswith("need a way to need"):
                    if DEBUG:
                        print(f"skip (invalid problem statement): {problem}")
                    continue
                    
                # Skip "find the best" patterns which aren't good product opportunities
                if "find the best" in problem.lower():
                    if DEBUG:
                        print(f"skip (information-seeking pattern): {problem}")
                    continue
                    
                emb = embed(problem)

                # Try to match an existing cluster with higher threshold
                matched: Optional[Cluster] = None
                best_sim = 0.0
                for cl in clusters:
                    sim = float(util.cos_sim(emb, cl.embedding))
                    if sim > best_sim:
                        best_sim = sim
                    if sim >= SIM_THRESHOLD:
                        matched = cl
                        break

                if matched:
                    matched.sources.append(src)
                    
                    # Check if this source contains a solution
                    if not matched.solution:  # Only check if we don't already have a solution
                        solution_text, solution_url = extract_solution(f"{src.title} {full_content}", "", src.url)
                        if solution_text:
                            matched.solution = solution_text
                            matched.solution_url = solution_url
                            # Check for negative reviews
                            matched.has_negative_reviews, matched.review_url = check_solution_sentiment(solution_text, solution_url or src.url, matched.problem)
                            
                    continue

                # If couldn't match to existing cluster but collected enough clusters
                if len(clusters) >= NUM_PROBLEMS:
                    # Add to unmatched sources list for potential secondary processing
                    unmatched_sources.append((src, emb))
                    continue
                    
                # New cluster
                solution_text, solution_url = extract_solution(f"{src.title} {full_content}", "", src.url)
                new_cluster = Cluster(problem=problem, embedding=emb, sources=[src], solution=solution_text, solution_url=solution_url)
                if solution_text:
                    # Check for negative reviews
                    new_cluster.has_negative_reviews, new_cluster.review_url = check_solution_sentiment(solution_text, solution_url or src.url, new_cluster.problem)
                clusters.append(new_cluster)

                # Expand search with the generalized problem (to gather more sources)
                expansion_q = f"\"{problem}\""
                to_search.append(expansion_q)

                # Optional: also search without quotes to catch paraphrases
                to_search.append(problem)

    pbar.close()

    # For each newly formed cluster, try a small expansion pass to gather more sources
    for cl in clusters:
        if len(cl.sources) >= EXPANSION_RESULTS_PER_PROBLEM:
            continue
        extra = ddg_search(f"{cl.problem} { ' OR '.join(SITE_HINTS[:2]) }", 8)
        
        # Filter and fetch content for expansion results
        filtered_extra = []
        for src in extra:
            combined_text = f"{src.title} {src.snippet}"
            if contains_nsfw_content(combined_text):
                continue
                
            ok, _ = is_pain_point(combined_text)
            if not ok:
                continue
                
            # Avoid duplicates
            if any(src.url.split('#')[0] == s.url.split('#')[0] for s in cl.sources):
                continue
                
            filtered_extra.append(src)
            
        # Fetch content for filtered expansion results
        if filtered_extra:
            enhanced_extra = fetch_contents_for_sources(filtered_extra)
            cl.sources.extend(enhanced_extra)
            
            # Check if any of these new sources contain solutions
            if not cl.solution:  # Only if we don't already have a solution
                for src in enhanced_extra:
                    solution_text, solution_url = extract_solution(f"{src.title} {src.snippet}", "", src.url)
                    if solution_text:
                        cl.solution = solution_text
                        cl.solution_url = solution_url
                        # Check for negative reviews
                        cl.has_negative_reviews, cl.review_url = check_solution_sentiment(solution_text, solution_url or src.url, cl.problem)
                        break

    # If we don't have enough clusters, try to create more from unmatched sources
    while len(clusters) < NUM_PROBLEMS and unmatched_sources:
        src, emb = unmatched_sources.pop(0)
        # Check again to make sure it still doesn't match any cluster
        # (clusters might have changed since we first checked)
        matched = False
        for cl in clusters:
            sim = float(util.cos_sim(emb, cl.embedding))
            if sim >= SIM_THRESHOLD:
                cl.sources.append(src)
                matched = True
                break
                
        if not matched:
            # Create a new cluster from this source
            problem = to_problem_statement(src.title, src.snippet)
            # Skip if the problem statement is invalid
            if problem.lower().startswith("need a way to need"):
                continue
            
            solution_text, solution_url = extract_solution(f"{src.title} {src.snippet}", "", src.url)    
            new_cluster = Cluster(problem=problem, embedding=emb, sources=[src], solution=solution_text, solution_url=solution_url)
            if solution_text:
                # Check for negative reviews
                new_cluster.has_negative_reviews, new_cluster.review_url = check_solution_sentiment(solution_text, solution_url or src.url, new_cluster.problem)
            clusters.append(new_cluster)
            
            # Try to find more sources for this new cluster
            for i, (other_src, other_emb) in enumerate(unmatched_sources[:]):
                sim = float(util.cos_sim(emb, other_emb))
                if sim >= SIM_THRESHOLD:
                    new_cluster.sources.append(other_src)
                    unmatched_sources.pop(i)

    # Dedupe sources and trim
    for cl in clusters:
        cl.sources = dedupe_sources(cl.sources)[: max(EXPANSION_RESULTS_PER_PROBLEM, 6)]
        
        # Clean up problem statements
        cl.problem = postprocess_problem_statement(cl.problem)
        
        # If we don't have a solution yet, actively search for one
        if not cl.solution:
            solution_text, solution_url = search_for_solution(cl.problem)
            if solution_text:
                cl.solution = solution_text
                cl.solution_url = solution_url
                
                # Parse negative review info if present
                if "[WARNING: Has negative reviews]" in solution_text:
                    cl.has_negative_reviews = True
                if "[WARNING: Has negative reviews:" in solution_text:
                    cl.has_negative_reviews = True
                    # Extract the review URL
                    review_match = re.search(r"\[WARNING: Has negative reviews: (https?://[^\]]+)\]", solution_text)
                    if review_match:
                        cl.review_url = review_match.group(1)
                        # Remove the warning from the solution text to keep it clean
                        cl.solution = solution_text.split("[WARNING:")[0].strip()

    return clusters[:NUM_PROBLEMS]

# Clean up problem statements
# Clean up problem statements
def postprocess_problem_statement(problem: str) -> str:
    """Clean up problem statements to ensure they are well-formed, clear, and product-focused."""
    if problem is None:
        return "Need a tool to solve a specific problem."
    
    # First, normalize the problem statement
    problem = problem.strip()
    if not problem.endswith((".", "!", "?")):
        problem += "."
    
    # Make it product-focused - convert "Need a way to" to "Need a tool to" if appropriate
    if problem.lower().startswith("need a way to"):
        # For product-oriented problems, make them explicitly about tools
        if any(verb in problem.lower() for verb in ACTIONABLE_VERBS):
            problem = "Need a tool to" + problem[len("Need a way to"):]
    
    # Remove common issues
    problem = re.sub(r"\s+for replacement\s*\.", ".", problem, flags=re.I)
    problem = re.sub(r"\s+r/\w+\s+", " ", problem, flags=re.I)
    problem = re.sub(r"\s+r/\w+\.\s*", ".", problem, flags=re.I)
    problem = re.sub(r"\s+\|\s+MacRumors\s+Forums.*", "", problem, flags=re.I)
    problem = re.sub(r"\s+\-\s+Reddit.*", "", problem, flags=re.I)
    problem = re.sub(r"\s+\-\s+Super\s+User.*", "", problem, flags=re.I)
    
    # Replace generic problem statements with more specific ones
    if problem in ["Need a solution for this problem.", "Need a solution."]:
        return "Need a tool to solve this specific problem more effectively."
        
    # Fix "find the best" patterns - convert to product opportunities when possible
    if "find the best" in problem.lower():
        item = re.search(r"find the best ([^\.]+)", problem, flags=re.I)
        if item:
            item_text = item.group(1).strip()
            
            # Special case handling for common items
            if "tire" in item_text:
                return "Need a tool to compare tire options based on car model, driving habits, and budget."
            elif "battery" in item_text:
                return "Need a tool to recommend compatible batteries based on device specifications."
            elif "car" in item_text:
                return "Need a platform to match users with the ideal vehicle based on their needs and budget."
            elif "computer" in item_text or "laptop" in item_text:
                return "Need a tool to recommend the ideal computer specs based on user's specific use cases."
            elif "a/c" in item_text.lower() or "ac unit" in item_text.lower():
                return "Need a tool to calculate optimal A/C unit size and efficiency for specific spaces."
            elif "app" in item_text or "tool" in item_text or "software" in item_text:
                return f"Need a platform to discover and compare {item_text} based on specific requirements."
            else:
                return f"Need a recommendation engine for {item_text} based on user preferences and needs."
    
    # Make frustration statements more product-focused
    if "address frustrations with" in problem:
        # Extract what they're frustrated with
        match = re.search(r"address frustrations with ([^\.]+)", problem)
        if match:
            frustration_topic = match.group(1).strip()
            
            # Try to map common frustration topics to product-focused statements
            topic_map = {
                "dating": "Need a dating app with better matching algorithms and compatibility indicators.",
                "coworker": "Need a team collaboration tool with conflict resolution features and communication tracking.",
                "team members": "Need a team management platform with performance analytics and communication improvement tools.",
                "producing": "Need a music production assistant that helps overcome creative blocks and streamlines workflow.",
                "my friend": "Need a relationship management tool to improve communication and resolve conflicts.",
                "him": "Need a family/child management platform to track progress and reduce conflict.",
                "objective-c code": "Need a better IDE or conversion tool for Objective-C development that simplifies syntax and improves productivity.",
                "simple verilog": "Need an improved Verilog development environment with better debugging and simulation tools.",
                "atom": "Need a more reliable text editor with better extension management and fewer configuration issues.",
                "laravel 5 blades": "Need a template debugging tool for Laravel that visualizes component relationships and simplifies blade syntax.",
                "gnome documentation": "Need a better documentation browser that indexes and makes GNOME APIs more accessible.",
                "my lack of progress": "Need a progress tracking tool with analytics and milestone management for personal development."
            }
            
            # Use the mapped product statement or create a generic one
            for topic, replacement in topic_map.items():
                if topic in frustration_topic.lower():
                    return replacement
                
            # If no direct match, make a more product-focused statement using the topic
            product_words = ["tool", "platform", "app", "solution", "system", "manager"]
            for word in product_words:
                if word in frustration_topic.lower():
                    return f"Need an improved {frustration_topic} with better reliability and user experience."
            
            # If no product word is found, create a general management tool statement
            return f"Need a management tool for {frustration_topic} that improves efficiency and reduces frustration."
    
    # Check for incomplete statements
    if "enables users to be posted and votes cannot be cast" in problem:
        return "Need a social media management tool that prevents posting/voting errors and improves content moderation."
        
    # Add more specific capabilities to vague statements
    if "reduce time spent" in problem and "rotations" in problem:
        return "Need a medical rotation scheduling system that optimizes assignments based on preferences and educational value."
    
    # Fix common "need a way to" patterns that aren't product-focused
    if problem.lower().startswith("need a way to determine when to replace"):
        item = re.search(r"determine when to replace ([^\.]+)", problem, flags=re.I)
        if item:
            item_text = item.group(1).strip()
            return f"Need a diagnostic tool that predicts when {item_text} should be replaced."
    
    if problem.lower().startswith("need a way to fix"):
        item = re.search(r"fix ([^\.]+) when it stops working", problem, flags=re.I)
        if item:
            item_text = item.group(1).strip()
            return f"Need a troubleshooting assistant for {item_text} problems."
    
    # Fix incomplete/malformed sentences
    if re.search(r"Need a (way|tool|platform) to (some|in a|to the|the best to|new column,|achieve this if)", problem, flags=re.I):
        # Special handling for specific cases based on content
        if "host resolution" in problem.lower() or "command line" in problem.lower():
            return "Need a tool to simplify host resolution management via command line."
        elif "column" in problem.lower() and "excel" in problem.lower():
            return "Need an Excel add-in for automating value mapping between columns."
        elif "windows" in problem.lower() or "enterprise" in problem.lower():
            return "Need a deployment tool to streamline Windows installation and activation."
        elif "file" in problem.lower() and "overwrite" in problem.lower():
            return "Need a file management tool with smart overwrite rules based on date and content."
        elif "battery" in problem.lower():
            return "Need a battery health monitor and replacement recommendation tool."
        elif "car" in problem.lower() or "vehicle" in problem.lower():
            return "Need a vehicle recommendation platform based on user needs and budget."
        else:
            return "Need a tool to solve this specific problem."
    
    # Fix sentences with strange formatting
    if "{" in problem or "}" in problem:
        problem = re.sub(r"\{[^}]*\}", "", problem)
        problem = problem.strip()
        if not problem.endswith("."):
            problem += "."
    
    # Fix sentences that are too short
    if len(problem.split()) < 5:
        if "one?" in problem.lower():
            return "Need a decision support tool to evaluate when new devices are necessary."
        else:
            return "Need a tool to solve this specific problem."
    
    # Double check correct format
    problem = problem.strip()
    if not problem.endswith((".", "!", "?")):
        problem += "."
        
    return problem

# -----------------------------
# OUTPUT
# -----------------------------

def print_report(clusters: List[Cluster]):
    print("\nProblems found:\n")
    for i, cl in enumerate(clusters, 1):
        print(f"{i}. {cl.problem}")
        if cl.solution:
            solution_text = cl.solution
            if cl.has_negative_reviews:
                solution_text += f" (WARNING: Has negative reviews: {cl.review_url})"
            print(f"   SOLUTION FOUND: {solution_text}")
        for s in cl.sources:
            title = s.title if s.title else (s.snippet[:80] + "…")
            print(f"   - {title}\n     {s.url}")
        print()


def save_markdown(clusters: List[Cluster], path: str = "problems.md"):
    lines: List[str] = ["# Problem List\n"]
    lines.append("## Summary\n")
    lines.append("These problems were identified using enhanced filtering for product-solvable issues only, ")
    lines.append("improved problem statement generation, and tighter semantic clustering. ")
    lines.append("Problems with existing solutions are marked with `SOLUTION FOUND`. ")
    lines.append("Solutions with negative reviews are marked with `⚠️ WARNING: NEGATIVE REVIEWS`.\n")
    
    for i, cl in enumerate(clusters, 1):
        problem_header = cl.problem
        if cl.solution:
            problem_header += " `SOLUTION FOUND`"
            if cl.has_negative_reviews:
                problem_header += " `⚠️ WARNING: NEGATIVE REVIEWS`"
        lines.append(f"\n## {i}. {problem_header}\n")
        
        if cl.solution:
            solution_text = f"**Solution:** {cl.solution}"
            if cl.solution_url:
                solution_text += f"\n\n**Solution Link:** [{cl.solution_url}]({cl.solution_url})"
            if cl.has_negative_reviews and cl.review_url:
                solution_text += f"\n\n**Warning:** This solution has [negative reviews]({cl.review_url})."
            lines.append(f"{solution_text}\n")
            
        for s in cl.sources:
            title = s.title if s.title else (s.snippet[:100] + "…")
            lines.append(f"- [{title}]({s.url})")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nSaved: {path}")

# -----------------------------
# MAIN
# -----------------------------
def cleanup_resources():
    """Clean up resources to prevent memory leaks"""
    global _problem_gen, _intent_classifier, _embed_model
    
    # Delete model variables to release resources
    _problem_gen = None
    _intent_classifier = None
    _embed_model = None
    
    # Force garbage collection
    import gc
    gc.collect()


if __name__ == "__main__":
    try:
        print("\n📊 Problem Finder MVP - Enhanced Version")
        print("------------------------------------------")
        print("✅ Improved filtering for product-solvable problems")
        print("✅ Better problem statement generation")
        print("✅ Enhanced clustering with NSFW filtering")
        print("------------------------------------------\n")
        
        clusters = search_and_cluster()
        print_report(clusters)
        # Also save to Markdown for easier review
        save_markdown(clusters)
    finally:
        # Make sure we clean up resources even if there's an error
        cleanup_resources()
