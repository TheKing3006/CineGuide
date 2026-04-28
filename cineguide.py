"""
CineGuide - Your AI-Powered Movie Companion

An intelligent movie recommendation system with 700K+ movies in the database.
Features conversational AI chat and random movie roulette with advanced filters.
"""


# ============================
# Imports & Configuration
# ============================


from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import json
import time
import os
import sqlite3
import asyncio
import re
import random
import math
from pathlib import Path
import threading
from datetime import datetime
import webbrowser


# GUI imports
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageFilter, ImageEnhance, ImageTk, ImageDraw, ImageFont, ImageGrab

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


# ADK imports
from google.adk.agents.llm_agent import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.genai.types import Content, Part


# ============================
# Configuration
# ============================


APP_NAME = "CineGuide"
MEMORY_FILE = "memory.json"
LOG_FILE = "logs.txt"
DB_FILE = "movies.db"
PROFILE_FILE = "user_profile.json"
MODEL_NAME = "gemini-2.5-flash"


# Load API key — .env file takes priority so a newly updated key is always used.
GOOGLE_API_KEY = None

env_file = Path(".env")
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("GOOGLE_API_KEY=") and not line.startswith("#"):
                GOOGLE_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

# Fallback: system / conda environment variable
if not GOOGLE_API_KEY:
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("⚠️ WARNING: GOOGLE_API_KEY not found!")
    print("Please set it as an environment variable or create a .env file with:")
    print("GOOGLE_API_KEY=your_key_here")
else:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY


# ============================
# Personalization helpers
# ============================

try:
    from profile_builder import (
        load_profile_context, extract_and_update_from_chat, 
        get_personalized_picks, load_profile, save_profile,
        FRANCHISE_MAP, detect_franchise, expand_query, 
        GENRE_ALIASES, LANGUAGE_ALIASES,
        MOVIE_ACRONYMS, FRANCHISE_NUMBERS
    )
    _PROFILE_BUILDER_AVAILABLE = True
except ImportError:
    _PROFILE_BUILDER_AVAILABLE = False
    GENRE_ALIASES = {}
    LANGUAGE_ALIASES = {}
    MOVIE_ACRONYMS = {}
    FRANCHISE_NUMBERS = {}
    FRANCHISE_MAP = {}
    def load_profile_context(profile_path=PROFILE_FILE): return ""
    def rotate_logs_if_needed(log_path=LOG_FILE, max_lines=500): return False
    def get_personalized_picks(n): return []
    def extract_and_update_from_chat(u, a): pass
    def load_profile(p): return {}
    def save_profile(p): pass
    def expand_query(q): return q
    def detect_franchise(m): return None


def _build_agent_instruction() -> str:
    """Build agent instruction, optionally prepending personalization context."""
    base = (
        'You are a friendly and enthusiastic movie assistant. '
        'Be conversational, helpful, and show genuine interest in movies. '
        'Keep responses brief and natural.'
    )
    context = load_profile_context(PROFILE_FILE)
    if context:
        return base + "\n\n" + context
    return base




# ============================
# SF PRO FONT SYSTEM
# ============================

def get_font(size=13, weight="normal", slant="roman"):
    """
    Returns the best available font for the current system.
    Priority: SF Pro Display → SF Pro Text → SF Pro → 
              Inter → Segoe UI → Helvetica Neue → Arial
    """
    SF_FONTS = [
        "SF Pro Display",
        "SF Pro Text", 
        "SF Pro",
        "SF Compact Display",
        ".SF NS Display",
        ".SF NS Text",
    ]
    FALLBACK_FONTS = [
        "Inter",
        "Segoe UI",      # Windows default
        "Helvetica Neue",
        "Helvetica",
        "Arial",
    ]
    
    # Preferred font is SF Pro Display. Tkinter will auto-fallback if missing.
    preferred = "SF Pro Display"
    
    if weight == "normal" and slant == "roman":
        return (preferred, size)
    
    style = []
    if weight != "normal": style.append(weight)
    if slant != "roman": style.append(slant)
    
    if not style:
        return (preferred, size)
    return (preferred, size, " ".join(style))

# Global font scale
# Global Font System (using tuples for pre-root safety)
FONT_TITLE      = get_font(size=28, weight="bold")
FONT_HEADING    = get_font(size=18, weight="bold")
FONT_SUBHEADING = get_font(size=15, weight="bold")
FONT_BODY       = get_font(size=13)
FONT_LABEL      = get_font(size=12, weight="bold")
FONT_SMALL      = get_font(size=11)
FONT_BUTTON     = get_font(size=15, weight="bold")
FONT_ITALIC     = get_font(size=13, slant="italic")
FONT_CARD_TITLE = get_font(size=14, weight="bold")

# Resize debouncing globals
_resize_job = None
_last_state = None


# ============================
# COLOR SYSTEM
# ============================

# Backgrounds
BG_ROOT          = "#08080f"   # Deep space black with blue tint
BG_GLASS         = "#16161c" # 6% white blend
BG_GLASS_HOVER   = "#25252b" # 12% white blend
BG_CARD          = "#111118"   # Slightly lighter than root for cards
BG_MODAL         = "#1a1a2a"   # Modal/overlay inner frame
BG_INPUT         = "#1c1c2e"   # Input fields

# Borders (glass edges)
BORDER_GLASS     = "#2d2d33" # 15% white blend
BORDER_HIGHLIGHT = "#45454d" # 25% white blend

# Accent colors
ACCENT_CYAN      = "#00d4ff"   # Primary accent (titles, icons)
ACCENT_PURPLE    = "#bf5af2"   # Secondary accent (buttons, reasons)
ACCENT_PINK      = "#ff375f"   # Destructive (X buttons, warnings)
ACCENT_GREEN     = "#30d158"   # Success states

# Text
TEXT_PRIMARY     = "#ffffff"   # Full white — headings
TEXT_SECONDARY   = "#b0b0b0"   # Light grey
TEXT_MUTED       = "#666666"   # Muted grey
TEXT_LINK        = "#bf5af2"   # Purple — clickable links

# Ratings star color
STAR_COLOR       = "#ffd60a"   # Apple yellow


# ============================
# GLASSFRAME WIDGET
# ============================

class GlassFrame(ctk.CTkFrame):
    """
    Static glass simulation — no live screen capture.
    Uses border + subtle gradient tint to suggest glass.
    Eliminates ALL ImageGrab performance overhead.
    """
    def __init__(self, parent, corner_radius=16, **kwargs):
        super().__init__(
            parent,
            fg_color="#1a1a2e",
            border_color=BORDER_GLASS,
            border_width=1,
            corner_radius=corner_radius,
            **kwargs
        )
        self.inner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.inner_frame.pack(fill=tk.BOTH, expand=True)


# ============================
# Database Initialization
# ============================

def initialize_database():
    """Fix NULL votes in database on startup."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE movies 
            SET imdb_votes = 0 
            WHERE imdb_votes IS NULL
        """)
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"✅ Fixed {cursor.rowcount} movies with NULL votes")
        
        conn.close()
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")


# ============================
# Utility: Logging
# ============================


# ============================
# Utility: Logging
# ============================


def log_event(event_type: str, data: Dict[str, Any]) -> None:
    """Simple observability hook."""
    entry = {
        "ts": time.time(),
        "type": event_type,
        "data": data,
    }
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ============================
# Database Access Functions
# ============================


def get_movie_from_db_direct(movie_name: str, year: Optional[int] = None) -> Optional[str]:
    """Get specific movie details."""
    try:
        expanded_result = expand_query(movie_name)
        
        if isinstance(expanded_result, tuple):
            expanded_name, preferred_year = expanded_result
            if year is None and preferred_year is not None:
                year = preferred_year
        else:
            expanded_name = expanded_result
        
        log_event("query_expansion", {"original": movie_name, "expanded": expanded_name, "year": year})
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 2. Try Standard Search
        if year:
            cursor.execute("""
                SELECT * FROM movies 
                WHERE (LOWER(title) = LOWER(?) OR LOWER(title) LIKE LOWER(?))
                AND year = ?
                ORDER BY COALESCE(imdb_votes, 0) DESC, COALESCE(imdb_rating, 0) DESC
                LIMIT 1
            """, (expanded_name, f'%{expanded_name}%', year))
        else:
            cursor.execute("""
                SELECT * FROM movies 
                WHERE (LOWER(title) = LOWER(?) OR LOWER(title) LIKE LOWER(?))
                ORDER BY COALESCE(imdb_votes, 0) DESC, COALESCE(imdb_rating, 0) DESC
                LIMIT 1
            """, (expanded_name, f'%{expanded_name}%'))
        
        row = cursor.fetchone()
        
        # 3. Fuzzy Fallback (Normalized search)
        if not row:
            from agent import normalize_text
            cursor.execute("SELECT * FROM movies WHERE enriched = 1")
            candidates = cursor.fetchall()
            norm_q = normalize_text(expanded_name)
            for cand in candidates:
                if norm_q in normalize_text(cand[1]):
                    row = cand
                    break
        
        conn.close()
        
        if not row:
            log_event("movie_not_found", {"expanded": expanded_name, "year": year})
            return None
        
        (imdb_id, title, year, runtime, genres, imdb_rating, imdb_votes,
         rt_critics, rt_audience, rated, released, director, writer, actors,
         plot, language, country, awards, poster, box_office, enriched) = row
        
        log_event("movie_lookup", {"title": title, "imdb_id": imdb_id, "year": year, "votes": imdb_votes})
        
        def get_val(val):
            return str(val) if val and str(val) not in ['None', 'N/A', ''] else None

        result = f"""🎬 **{title}** ({year or 'Year unknown'})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **RATINGS**
   • IMDB: {get_val(imdb_rating) or 'N/A'}/10 ({imdb_votes or 0:,} votes)"""

        rtc = get_val(rt_critics)
        rta = get_val(rt_audience)
        if rtc or rta:
            result += f"\n   • Rotten Tomatoes: {rtc or 'N/A'} (Critics) | {rta or 'N/A'} (Audience)"

        result += f"""

📝 **DETAILS**
   • Runtime: {get_val(runtime) or 'N/A'} minutes
   • Genre: {get_val(genres) or 'N/A'}"""

        rate = get_val(rated)
        rel = get_val(released)
        if rate: result += f"\n   • Rated: {rate}"
        if rel: result += f"\n   • Released: {rel}"

        dir_ = get_val(director)
        wri = get_val(writer)
        act = get_val(actors)
        if dir_ or wri or act:
            result += "\n\n🎭 **CAST & CREW**"
            if dir_: result += f"\n   • Director: {dir_}"
            if wri: result += f"\n   • Writer: {wri}"
            if act: result += f"\n   • Actors: {act}"

        p_ = get_val(plot)
        if p_:
            result += f"\n\n📖 **PLOT**\n{p_}"

        lang = get_val(language)
        cou = get_val(country)
        awa = get_val(awards)
        box = get_val(box_office)
        if lang or cou or awa or box:
            result += "\n\n🌍 **OTHER INFO**"
            if lang: result += f"\n   • Language: {lang}"
            if cou: result += f"\n   • Country: {cou}"
            if awa: result += f"\n   • Awards: {awa}"
            if box: result += f"\n   • Box Office: {box}"

        result += f"\n\n🔗 **IMDB LINK**\n   • https://www.imdb.com/title/{imdb_id}/"

        if poster and str(poster) not in ['None', 'N/A', '']:
            result += f"\nHIDDEN_POSTER:{poster}"
        
        return result
        
    except Exception as e:
        log_event("error", {"error": str(e), "movie": movie_name, "year": year})
        return None


def normalize_genre(genre: str) -> str:
    """Normalize genre name using aliases."""
    if not genre: return ""
    g = genre.lower().strip()
    return GENRE_ALIASES.get(g, g)


def normalize_language(language: str) -> str:
    """Normalize language name using aliases."""
    if not language: return ""
    l = language.lower().strip()
    return LANGUAGE_ALIASES.get(l, language)


def search_movies(query: str, limit: int = 10) -> Optional[str]:
    """Search for movies by title or genre."""
    try:
        normalized_query = normalize_genre(query)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT title, year, imdb_rating, genres, imdb_votes
            FROM movies
            WHERE (LOWER(title) LIKE LOWER(?) OR LOWER(genres) LIKE LOWER(?)
                   OR LOWER(title) LIKE LOWER(?) OR LOWER(genres) LIKE LOWER(?))
            AND imdb_rating IS NOT NULL
            ORDER BY COALESCE(imdb_votes, 0) DESC, imdb_rating DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', f'%{normalized_query}%', f'%{normalized_query}%', limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        log_event("search", {"query": query, "normalized": normalized_query, "results": len(rows)})
        
        result = f"🔍 **Found {len(rows)} movies matching '{query}':**\n\n"
        for idx, (title, year, rating, genres, votes) in enumerate(rows, 1):
            result += f"{idx}. **{title}** ({year or '?'}) - ⭐ {rating}/10\n"
            result += f"   {genres} • {votes or 0:,} votes\n\n"
        
        result += "💡 *Ask 'tell me about [movie name]' for full details!*"
        return result
        
    except Exception as e:
        log_event("error", {"error": str(e), "search": query})
        return None


def get_top_movies(genre: Optional[str] = None, language: Optional[str] = None, limit: int = 10) -> Optional[str]:
    """Get top rated movies, optionally by genre and/or language."""
    try:
        if genre:
            genre = normalize_genre(genre)
        if language:
            language = normalize_language(language)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        if genre and language:
            cursor.execute("""
                SELECT title, year, imdb_rating, genres, imdb_votes
                FROM movies
                WHERE LOWER(genres) LIKE LOWER(?)
                AND (
                    LOWER(language) = LOWER(?)
                    OR LOWER(language) LIKE LOWER(?) || ',%'
                )
                AND imdb_rating IS NOT NULL
                AND COALESCE(imdb_votes, 0) > 10000
                ORDER BY imdb_rating DESC, COALESCE(imdb_votes, 0) DESC
                LIMIT ?
            """, (f'%{genre}%', language, language, limit))
        elif genre:
            cursor.execute("""
                SELECT title, year, imdb_rating, genres, imdb_votes
                FROM movies
                WHERE LOWER(genres) LIKE LOWER(?)
                AND imdb_rating IS NOT NULL
                AND COALESCE(imdb_votes, 0) > 10000
                ORDER BY imdb_rating DESC, COALESCE(imdb_votes, 0) DESC
                LIMIT ?
            """, (f'%{genre}%', limit))
        elif language:
            cursor.execute("""
                SELECT title, year, imdb_rating, genres, imdb_votes
                FROM movies
                WHERE (
                    LOWER(language) = LOWER(?)
                    OR LOWER(language) LIKE LOWER(?) || ',%'
                )
                AND imdb_rating IS NOT NULL
                AND COALESCE(imdb_votes, 0) > 5000
                ORDER BY imdb_rating DESC, COALESCE(imdb_votes, 0) DESC
                LIMIT ?
            """, (language, language, limit))
        else:
            cursor.execute("""
                SELECT title, year, imdb_rating, genres, imdb_votes
                FROM movies
                WHERE imdb_rating IS NOT NULL
                AND COALESCE(imdb_votes, 0) > 50000
                ORDER BY imdb_rating DESC, COALESCE(imdb_votes, 0) DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        log_event("top_movies", {"genre": genre, "language": language, "results": len(rows)})
        
        title_parts = []
        if genre:
            title_parts.append(genre.title())
        if language:
            title_parts.append(language)
        
        title_text = " ".join(title_parts) if title_parts else ""
        result = f"⭐ **Top {title_text} Movies:**\n\n" if title_text else f"⭐ **Top Movies:**\n\n"
        
        for idx, (title, year, rating, genres, votes) in enumerate(rows, 1):
            result += f"{idx}. **{title}** ({year or '?'}) - ⭐ {rating}/10\n"
            result += f"   {genres} • {votes or 0:,} votes\n\n"
        
        result += "💡 *Ask 'tell me about [movie name]' for full details!*"
        return result
        
    except Exception as e:
        log_event("error", {"error": str(e), "genre": genre, "language": language})
        return None


def get_similar_movies(movie_name: str, limit: int = 5) -> Optional[str]:
    """Find movies similar to the given movie."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT genres, imdb_rating FROM movies
            WHERE LOWER(title) LIKE LOWER(?)
            AND imdb_rating IS NOT NULL
            ORDER BY COALESCE(imdb_votes, 0) DESC, imdb_rating DESC
            LIMIT 1
        """, (f'%{movie_name}%',))
        
        target = cursor.fetchone()
        if not target:
            conn.close()
            return None
        
        genres, rating = target
        if not genres:
            conn.close()
            return None
        
        primary_genre = genres.split(',')[0].strip()
        
        cursor.execute("""
            SELECT title, year, imdb_rating, genres, imdb_votes
            FROM movies
            WHERE LOWER(genres) LIKE LOWER(?)
            AND LOWER(title) NOT LIKE LOWER(?)
            AND imdb_rating IS NOT NULL
            AND imdb_rating BETWEEN ? AND ?
            AND COALESCE(imdb_votes, 0) > 10000
            ORDER BY COALESCE(imdb_votes, 0) DESC, imdb_rating DESC
            LIMIT ?
        """, (f'%{primary_genre}%', f'%{movie_name}%', rating - 1.5, rating + 1.5, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return None
        
        log_event("similar_movies", {"movie": movie_name, "results": len(rows)})
        
        result = f"🎯 **Movies similar to {movie_name.title()}:**\n\n"
        for idx, (title, year, rating, genres, votes) in enumerate(rows, 1):
            result += f"{idx}. **{title}** ({year or '?'}) - ⭐ {rating}/10\n"
            result += f"   {genres} • {votes or 0:,} votes\n\n"
        
        result += "💡 *Ask 'tell me about [movie name]' for full details!*"
        return result
        
    except Exception as e:
        log_event("error", {"error": str(e), "similar": movie_name})
        return None


def get_random_movies(count: int = 3, genre: Optional[str] = None, language: Optional[str] = None, 
                      year_min: Optional[int] = None, year_max: Optional[int] = None) -> List[Tuple]:
    """Get random movies with optional filters and quality cap."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Base query components
        base_select = "SELECT title, year, imdb_rating, genres FROM movies WHERE imdb_rating IS NOT NULL"
        filter_sql = ""
        params = []
        
        if genre:
            genre = normalize_genre(genre)
            filter_sql += " AND LOWER(genres) LIKE LOWER(?)"
            params.append(f'%{genre}%')
        
        if language:
            language = normalize_language(language)
            filter_sql += " AND (LOWER(language) = LOWER(?) OR LOWER(language) LIKE LOWER(?) || ',%')"
            params.extend([language, language])
        
        if year_min:
            filter_sql += " AND year >= ?"
            params.append(year_min)
        
        if year_max:
            filter_sql += " AND year <= ?"
            params.append(year_max)
        
        # Primary Attempt: Rating >= 7.0
        # Fetch a larger pool to allow for weighted randomization in Python
        pool_size = count * 20
        primary_query = base_select + filter_sql + f" AND imdb_rating >= 7.0 ORDER BY RANDOM() LIMIT {pool_size}"
        
        cursor.execute(primary_query, params)
        rows = cursor.fetchall()
        
        # Fallback: Normalized randomization (no rating cap) if no high-rated movies found
        if not rows:
            fallback_query = base_select + filter_sql + f" ORDER BY RANDOM() LIMIT {pool_size}"
            cursor.execute(fallback_query, params)
            rows = cursor.fetchall()
            if rows:
                log_event("random_fallback", {"filters": filter_sql, "results": len(rows)})
        
        conn.close()
        
        if not rows:
            return []

        # Weighted Randomization: Favor higher ratings while keeping it random
        # We use (rating - 6.0)^2 as weight to give higher rated movies more "slots"
        # but since they are all >= 7.0 in primary, it's a smooth bias.
        import random
        try:
            # weights = [(row[2] - 6.0)**2 for row in rows] # row[2] is imdb_rating
            # Actually, let's use a simpler bias: sort by rating and pick from the top N
            # with decreasing probability.
            rows.sort(key=lambda x: x[2], reverse=True)
            
            final_selection = []
            available_indices = list(range(len(rows)))
            
            while len(final_selection) < min(count, len(rows)):
                # Exponential bias: pick index i with probability proportional to 0.8^i
                # This favors top results but allows any to be picked.
                idx_choice = 0
                for i in range(len(available_indices)):
                    if random.random() < 0.2 or i == len(available_indices) - 1:
                        idx_choice = i
                        break
                
                real_idx = available_indices.pop(idx_choice)
                final_selection.append(rows[real_idx])
            
            return final_selection
        except Exception as e:
            print(f"Weighted random error: {e}")
            # Fallback to simple shuffle if weighting fails
            import random
            random.shuffle(rows)
            return rows[:count]
        
    except Exception as e:
        log_event("error", {"error": str(e), "random_movies": count})
        return []


# ============================
# Query Pattern Matching
# ============================


def parse_user_query(user_input: str) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
    """Parse user input to determine intent and extract parameters."""
    user_lower = user_input.lower().strip()
    
    if user_lower in MOVIE_ACRONYMS:
        return ('movie_details', user_lower, None)
    
    franchise_num_pattern = r'^([a-z\s]+)\s+(\d+)$'
    match = re.match(franchise_num_pattern, user_lower)
    if match:
        franchise = match.group(1).strip()
        number = match.group(2)
        potential_key = f"{franchise} {number}"
        if potential_key in FRANCHISE_NUMBERS:
            return ('movie_details', potential_key, None)
    
    if user_lower.startswith('avengers ') and 'tell me' not in user_lower:
        return ('movie_details', user_lower, None)
    
    movie_year_pattern = r"(.+?)\s+(\d{4})"
    match = re.search(movie_year_pattern, user_lower)
    if match:
        if any(word in user_lower for word in ['tell me about', 'show me', 'what is', "what's", 'details', 'info']):
            movie_name = match.group(1).strip()
            year = int(match.group(2))
            movie_name = re.sub(r'\s+(movie|film)$', '', movie_name)
            for trigger in ['tell me about', 'show me', 'what is', "what's", 'details about', 'info about']:
                movie_name = movie_name.replace(trigger, '').strip()
            return ('movie_details', movie_name, {'year': year})
    
    movie_patterns = [
        r"tell me about (.+)",
        r"what is (.+?) about",
        r"what's (.+?) about",
        r"details (?:for|on|about) (.+)",
        r"info (?:for|on|about) (.+)",
        r"show me (.+)",
    ]
    
    for pattern in movie_patterns:
        match = re.search(pattern, user_lower)
        if match:
            movie_name = match.group(1).strip()
            movie_name = re.sub(r'\s+(movie|film)$', '', movie_name)
            return ('movie_details', movie_name, None)
    
    if any(keyword in user_lower for keyword in ['search', 'find', 'look for']):
        for keyword in ['search for', 'find', 'look for']:
            if keyword in user_lower:
                parts = user_lower.split(keyword, 1)
                if len(parts) > 1:
                    search_term = parts[1].strip()
                    search_term = re.sub(r'\s+(movie|movies|film|films)$', '', search_term)
                    return ('search', search_term, None)
    
    top_numeric_pattern = r"(?:top|best) (\d+) movies"
    match = re.search(top_numeric_pattern, user_lower)
    if match:
        limit = int(match.group(1))
        return ('top_movies', None, {'limit': limit})
    
    for lang_key in LANGUAGE_ALIASES.keys():
        if lang_key in user_lower:
            if 'top' in user_lower or 'best' in user_lower:
                genre_match = None
                for genre_key in GENRE_ALIASES.keys():
                    if genre_key in user_lower:
                        genre_match = genre_key
                        break
                
                return ('top_movies', genre_match, {'language': lang_key})
    
    top_patterns = [
        r"(?:what are the |show me |give me )?(?:top|best) (\w+) movies",
        r"(?:top|best) movies (?:in |about )?(\w+)",
        r"(?:what are the |show me |give me )?(?:top|best) movies",
    ]
    
    for pattern in top_patterns:
        match = re.search(pattern, user_lower)
        if match:
            if match.groups():
                genre = match.group(1).strip()
                return ('top_movies', genre, None)
            else:
                return ('top_movies', None, None)
    
    similar_patterns = [
        r"movies (?:like|similar to) (.+)",
        r"similar to (.+)",
        r"recommend (?:movies )?like (.+)",
    ]
    
    for pattern in similar_patterns:
        match = re.search(pattern, user_lower)
        if match:
            movie_name = match.group(1).strip()
            movie_name = re.sub(r'\s+(movie|film)$', '', movie_name)
            return ('similar', movie_name, None)
    
    return ('chat', None, None)


# ============================
# ADK Agent Setup
# ============================


root_agent = Agent(
    model=MODEL_NAME,
    name='cineguide_agent',
    description='Friendly movie assistant',
    instruction=_build_agent_instruction(),
    tools=[]
)

session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

runner = Runner(
    agent=root_agent,
    app_name="cineguide_app",
    session_service=session_service,
    memory_service=memory_service,
)

async def auto_save_to_memory(callback_context):
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )

root_agent.after_agent_callback = auto_save_to_memory


# ============================
# GUI - Main Application
# ============================


class CineGuideApp:
    """Main application with title screen navigation."""
    
    def __init__(self, root: ctk.CTk):
        self.root = root
        self.root.title(f"{APP_NAME}")
        self.root.geometry("1280x800")
        self.root.minsize(900, 600)
        self.root.configure(fg_color=BG_ROOT)
        
        self.session_id = f"gui_session_{int(time.time())}"
        self.user_id = "local_user"
        asyncio.run(self._init_session())

        # Register close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.container = ctk.CTkFrame(self.root, fg_color=BG_ROOT)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.screens = {}
        self.screens['title'] = TitleScreen(self.container, self)
        self.screens['chat'] = ChatScreen(self.container, self)
        self.screens['roulette'] = RouletteScreen(self.container, self)
        self.screens['profile'] = ProfileScreen(self.container, self)

        self.show_screen('title')
        
        self.root.bind("<Configure>", self.on_window_resize)

    def on_window_resize(self, event):
        global _resize_job, _last_state
        if event.widget is not self.root:
            return
            
        current_state = self.root.state()
        if current_state in ("iconic", "withdrawn"):
            _last_state = current_state
            return
            
        # Only trigger if dimensions actually changed or state changed
        w, h = self.root.winfo_width(), self.root.winfo_height()
        last_w = getattr(self.root, '_last_w', 0)
        last_h = getattr(self.root, '_last_h', 0)
        
        if w == last_w and h == last_h and current_state == _last_state:
            return
            
        self.root._last_w = w
        self.root._last_h = h
        _last_state = current_state

        if _resize_job:
            self.root.after_cancel(_resize_job)
        _resize_job = self.root.after(400, self.handle_resize)

    def handle_resize(self):
        """Only re-wrap card text — no GlassFrame renders."""
        state = self.root.state()
        if state in ("iconic", "withdrawn"):
            return
            
        # Trigger text wrapping update without destroying/recreating widgets
        if self.screens['title'].winfo_viewable():
            self.screens['title']._update_all_wraplengths()

    def after(self, ms, func):
        return self.root.after(ms, func)

    def _on_close(self):
        """Graceful shutdown: rotate logs if needed."""
        try:
            rotate_logs_if_needed(LOG_FILE)
        except Exception:
            pass
        self.root.destroy()
        
    async def _init_session(self):
        """Initialize ADK session."""
        await session_service.create_session(
            app_name="cineguide_app",
            user_id=self.user_id,
            session_id=self.session_id
        )
    
    def show_screen(self, screen_name):
        """Show a specific screen."""
        for name, screen in self.screens.items():
            if name == screen_name:
                screen.pack(fill=tk.BOTH, expand=True)
            else:
                screen.pack_forget()


# ============================
# Profile Screen
# ============================


class ProfileScreen(ctk.CTkFrame):
    """Integrated screen for user profile management."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_ROOT)
        self.app = app
        
        # Header with Back Button
        header_frame = ctk.CTkFrame(self, fg_color="transparent", height=80)
        header_frame.pack(fill=tk.X, padx=20, pady=20)
        
        back_btn = ctk.CTkButton(
            header_frame, text="← Back", command=self._on_back,
            font=FONT_BUTTON, fg_color="transparent", text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER_GLASS, hover_color=BG_GLASS_HOVER,
            corner_radius=8, height=32, width=100
        )
        back_btn.pack(side=tk.LEFT)

        ctk.CTkLabel(
            header_frame, text="My Profile", 
            font=FONT_TITLE, 
            fg_color="transparent", text_color=ACCENT_CYAN
        ).pack(side=tk.LEFT, expand=True, padx=(0, 100))

        # Scrollable area
        self.scroll_container = ctk.CTkScrollableFrame(
            self, fg_color="transparent", 
            scrollbar_button_color=BORDER_GLASS,
            scrollbar_button_hover_color=ACCENT_CYAN
        )
        self.scroll_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Initial render will be called on show_screen
        self.bind("<Visibility>", lambda e: self._render_sections())

    def _render_sections(self):
        """Clear and rebuild profile sections instantly from JSON."""
        for w in self.scroll_container.winfo_children():
            w.destroy()

        profile = load_profile(PROFILE_FILE)

        # Section A: Liked Movies
        self._add_movie_list_section("Movies I Like", profile.get("liked_movies", []), "liked")
        
        # Section B: Disliked Movies
        self._add_movie_list_section("Movies I Dislike", profile.get("disliked_movies", []), "disliked")

        # Section C: Taste Profile
        self._add_taste_section(profile)

    def _on_back(self):
        """Return to title and refresh picks."""
        self.app.screens['title']._refresh_picks()
        self.app.show_screen('title')

    def _add_movie_list_section(self, title, movies, list_type):
        """Renders the list using rich data from JSON — Zero DB calls."""
        ctk.CTkLabel(
            self.scroll_container, text=title, font=FONT_HEADING,
            fg_color="transparent", text_color=TEXT_PRIMARY
        ).pack(anchor=tk.W, pady=(20, 10))
        
        if not movies:
            msg = "Nothing here yet — tell CineGuide what you love!" if list_type == "liked" else "No dislikes yet."
            ctk.CTkLabel(
                self.scroll_container, text=msg, font=FONT_ITALIC,
                fg_color="transparent", text_color=TEXT_SECONDARY
            ).pack(anchor=tk.W, padx=10)
            return

        for movie in movies:
            title_text = movie.get('title', 'Unknown')
            year = movie.get('year', '?')
            rating = movie.get('rating', 'N/A')
            
            item_glass = GlassFrame(self.scroll_container, height=52, corner_radius=10)
            item_glass.pack(fill=tk.X, pady=4)
            
            text = f"{title_text} ({year}) • {rating} ⭐"
            
            ctk.CTkLabel(
                item_glass.inner_frame, text=text, font=FONT_BODY, fg_color="transparent", text_color=TEXT_PRIMARY,
                anchor=tk.W, justify=tk.LEFT
            ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)

            ctk.CTkButton(
                item_glass.inner_frame, text="✕", command=lambda m=title_text: self._remove_movie(m, list_type),
                font=FONT_SMALL, fg_color="transparent", text_color=ACCENT_PINK,
                border_color=ACCENT_PINK, hover_color="#200a0f",
                width=32, height=32, corner_radius=8
            ).pack(side=tk.RIGHT, padx=10)

    def _add_taste_section(self, profile):
        taste_glass = GlassFrame(self.scroll_container, corner_radius=16)
        taste_glass.pack(fill=tk.X, pady=20)
        
        inner = taste_glass.inner_frame

        ctk.CTkLabel(
            inner, text="My Taste Profile", font=FONT_HEADING,
            fg_color="transparent", text_color=TEXT_PRIMARY
        ).pack(anchor=tk.W, padx=20, pady=(20, 15))

        genres = profile.get("preferred_genres", {})
        if genres:
            ctk.CTkLabel(inner, text="Top Genres:", font=FONT_LABEL, fg_color="transparent", text_color=ACCENT_CYAN).pack(anchor=tk.W, padx=20)
            sorted_genres = sorted(genres.items(), key=lambda x: x[1], reverse=True)[:8]
            genre_text = ", ".join([f"{g.title()}" for g, score in sorted_genres])
            ctk.CTkLabel(inner, text=genre_text, font=FONT_BODY, fg_color="transparent", text_color=TEXT_SECONDARY).pack(anchor=tk.W, pady=(0, 10), padx=20)

        dirs = profile.get("preferred_directors", [])
        if dirs:
            ctk.CTkLabel(inner, text="Favorite Directors:", font=FONT_LABEL, fg_color="transparent", text_color=ACCENT_PURPLE).pack(anchor=tk.W, padx=20)
            ctk.CTkLabel(inner, text=", ".join(dirs[:5]), font=FONT_BODY, fg_color="transparent", text_color=TEXT_SECONDARY).pack(anchor=tk.W, pady=(0, 10), padx=20)

        # Favourite Actors (Fix 4)
        actors_data = profile.get("preferred_actors", {})
        if actors_data:
            ctk.CTkLabel(
                inner, text="Favourite Actors:", font=FONT_LABEL, 
                fg_color="transparent", text_color=ACCENT_CYAN
            ).pack(anchor=tk.W, padx=20)
            
            if isinstance(actors_data, dict):
                sorted_actors = sorted(
                    actors_data.items(),
                    key=lambda x: x[1] if isinstance(x[1], (int,float)) else 0,
                    reverse=True
                )
                display_list = [name for name, _ in sorted_actors]
            elif isinstance(actors_data, list):
                display_list = actors_data
            else:
                display_list = []
            
            if display_list:
                actors_text = ", ".join(display_list[:8])
                ctk.CTkLabel(
                    inner, text=actors_text, font=FONT_BODY, 
                    fg_color="transparent", text_color=TEXT_SECONDARY
                ).pack(anchor=tk.W, pady=(0, 10), padx=20)
            else:
                ctk.CTkLabel(
                    inner, text="  No favourite actors found.",
                    font=FONT_BODY, text_color=TEXT_MUTED, anchor=tk.W
                ).pack(anchor=tk.W, padx=20, pady=4)
        else:
            ctk.CTkLabel(
                inner, text="  No favourite actors yet — tell CineGuide who you love watching!",
                font=FONT_BODY, text_color=TEXT_MUTED, anchor=tk.W
            ).pack(anchor=tk.W, padx=20, pady=4)

        tags = profile.get("inferred_mood_tags", [])
        if tags:
            ctk.CTkLabel(inner, text="Tags:", font=FONT_LABEL, fg_color="transparent", text_color=ACCENT_PINK).pack(anchor=tk.W, padx=20)
            ctk.CTkLabel(inner, text=", ".join(tags), font=FONT_BODY, fg_color="transparent", text_color=TEXT_SECONDARY, wraplength=700, justify=tk.LEFT).pack(anchor=tk.W, padx=20, pady=(0, 20))

    def _get_movie_quick_info(self, title):
        try:
            conn = sqlite3.connect(DB_FILE)
            r = conn.execute("SELECT year, imdb_rating FROM movies WHERE LOWER(title) = LOWER(?) LIMIT 1", (title,)).fetchone()
            conn.close()
            if r: return {"year": r[0] or "?", "rating": r[1] or "N/A"}
        except: pass
        return {"year": "?", "rating": "N/A"}

    def _remove_movie(self, title, list_type):
        """Removes movie from profile and persists to disk immediately (Bug 2)."""
        try:
            profile = load_profile(PROFILE_FILE)
            key = "liked_movies" if list_type == "liked" else "disliked_movies"
            
            # Filter the list of objects
            original_len = len(profile[key])
            profile[key] = [m for m in profile[key] if m['title'] != title]
            
            if len(profile[key]) < original_len:
                save_profile(profile, PROFILE_FILE)
                self._render_sections()
        except Exception as e:
            print(f"Error removing movie: {e}")


class TitleScreen(ctk.CTkFrame):
    """Main title screen with personalised recommendations and navigation."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_ROOT)
        self.app = app
        self._recs_container = None
        self._overlay = None
        self.card_label_map = {} # {card_frame: [labels]}

        # Main scrollable frame for the whole screen
        self.main_scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", 
            scrollbar_button_color=BORDER_GLASS,
            scrollbar_button_hover_color=ACCENT_CYAN
        )
        self.main_scroll.pack(fill=tk.BOTH, expand=True)

        # Bind Escape globally for this screen
        self.app.root.bind("<Escape>", self._close_overlay_esc)

        # ── Header Area ──────────────────────────────────────────────────
        header_area = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        header_area.pack(fill=tk.X, padx=20, pady=(40, 20))

        # Logo (Centered)
        self.logo_lbl = ctk.CTkLabel(
            header_area, text="CineGuide", font=FONT_TITLE,
            fg_color="transparent", text_color=ACCENT_CYAN
        )
        self.logo_lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Profile Icon Button (Right)
        self.profile_btn = ctk.CTkButton(
            header_area, text="👤", command=self._open_profile,
            font=("Arial", 20), fg_color="transparent", text_color=TEXT_SECONDARY,
            hover_color=BG_GLASS_HOVER, corner_radius=20, width=40, height=40
        )
        self.profile_btn.pack(side=tk.RIGHT, padx=5)

        # Navigation Buttons (Right, Larger, Renamed, Switched Order)
        self.roulette_nav_btn = ctk.CTkButton(
            header_area, text="🎰 I Can't Decide...", command=lambda: self.app.show_screen('roulette'),
            font=get_font(size=13, weight="bold"), fg_color="transparent", text_color=ACCENT_PINK,
            hover_color=BG_GLASS_HOVER, corner_radius=12, width=180, height=40,
            border_width=1, border_color=ACCENT_PINK
        )
        self.roulette_nav_btn.pack(side=tk.RIGHT, padx=5)

        self.chat_nav_btn = ctk.CTkButton(
            header_area, text="💬 Let's Talk Movies!", command=lambda: self.app.show_screen('chat'),
            font=get_font(size=13, weight="bold"), fg_color="transparent", text_color=ACCENT_PURPLE,
            hover_color=BG_GLASS_HOVER, corner_radius=12, width=180, height=40,
            border_width=1, border_color=ACCENT_PURPLE
        )
        self.chat_nav_btn.pack(side=tk.RIGHT, padx=5)

        # Tagline (Centered below header)
        ctk.CTkLabel(
            self.main_scroll, text="Your AI-Powered Movie Companion",
            font=get_font(size=14), fg_color="transparent", text_color=TEXT_MUTED
        ).pack(pady=(0, 20))

        # ── Personalised Recommendations ─────────────────────────────────
        self._build_recs_section()

        # Bottom nav buttons removed per user request

    def _open_profile(self):
        self.app.show_screen('profile')

    def _build_recs_section(self):
        """Build the outer frame, header row, and initial cards area."""
        section = ctk.CTkFrame(self.main_scroll, fg_color="transparent")
        section.pack(fill=tk.X, padx=20)

        # Header row: centered title + refresh button
        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill=tk.X, pady=10)

        ctk.CTkLabel(
            header, text="Recommended For You", font=FONT_HEADING,
            fg_color="transparent", text_color=ACCENT_CYAN
        ).pack(side=tk.LEFT, expand=True, padx=(40, 0))

        # Refresh button
        ctk.CTkButton(
            header, text="Refresh ↻", command=self._refresh_picks,
            font=FONT_SMALL, fg_color="transparent", text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER_GLASS, hover_color=BG_GLASS_HOVER,
            corner_radius=8, height=32, width=100
        ).pack(side=tk.RIGHT)

        # Cards container
        self._recs_container = ctk.CTkFrame(section, fg_color="transparent", height=520)
        self._recs_container.pack(fill=tk.X, pady=20)

        self._load_and_render()

    def _refresh_picks(self):
        self._load_and_render()

    def _load_and_render(self):
        for w in self._recs_container.winfo_children():
            w.destroy()

        picks = []
        if _PROFILE_BUILDER_AVAILABLE:
            try:
                picks = get_personalized_picks(5)
            except: pass

        if picks:
            self._render_cards(picks)
        else:
            self._render_placeholder()

    def _render_placeholder(self):
        cta = ctk.CTkLabel(
            self._recs_container,
            text="💬 Chat with CineGuide to get personalised picks →",
            font=FONT_ITALIC, fg_color=BG_INPUT, text_color=TEXT_SECONDARY,
            height=60, corner_radius=12
        )
        cta.pack(fill=tk.X, pady=20)
        cta.bind("<Button-1>", lambda _e: self.app.show_screen('chat'))

    def _render_cards(self, picks):
        """Render a row of movie cards that reflow and are centered."""
        self._current_picks = picks  # Store for reflow
        if hasattr(self, 'card_row') and self.card_row:
            self.card_row.destroy()
            
        self.card_row = ctk.CTkFrame(self._recs_container, fg_color="transparent")
        self.card_row.pack(fill=tk.X, expand=True, pady=10)
        
        # Configure grid for equal distribution/centering
        for i in range(len(picks)):
            self.card_row.grid_columnconfigure(i, weight=1)

        self._reflow_cards()

    def _reflow_cards(self):
        """Recalculate card widths and re-render."""
        if not hasattr(self, '_current_picks') or not self._current_picks:
            return

        for w in self.card_row.winfo_children():
            w.destroy()

        self.card_label_map = {}

        for i, pick in enumerate(self._current_picks):
            card = self._make_card(self.card_row, pick, i)
            # Use grid for centering weights to work
            card.grid(row=0, column=i, padx=15, pady=15, sticky="n")

        # Schedule wraplength update after layout settles
        self.app.root.after(100, self._update_all_wraplengths)

    def _update_all_wraplengths(self):
        """Force update all card labels based on actual rendered width."""
        for card, labels in self.card_label_map.items():
            actual_w = card.winfo_width()
            wrap = actual_w - 32 if actual_w > 10 else 200
            for lbl in labels:
                if lbl.winfo_exists():
                    lbl.configure(wraplength=wrap)

    def _make_card(self, parent, pick, index):
        """Build a single styled movie card with GlassFrame and hover animation."""
        card = GlassFrame(parent, corner_radius=20)
        # Note: Geometry management (grid) is handled by the caller (_reflow_cards)
        
        inner = card.inner_frame

        # Poster Area with Placeholder
        poster_container = ctk.CTkFrame(inner, width=220, height=330, fg_color="#121225", corner_radius=12)
        poster_container.pack(pady=(16, 0))
        poster_container.pack_propagate(False)

        placeholder_lbl = ctk.CTkLabel(
            poster_container, text="CineGuide", font=get_font(size=16, weight="bold"),
            text_color="#2a2a40" # Muted light version of theme
        )
        placeholder_lbl.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        poster_url = pick.get('poster')
        if poster_url and str(poster_url) not in ['None', 'N/A', '']:
            def fetch_poster():
                try:
                    import requests
                    from PIL import Image, ImageTk
                    from io import BytesIO
                    resp = requests.get(poster_url, timeout=3)
                    if resp.status_code == 200:
                        img = Image.open(BytesIO(resp.content))
                        img.thumbnail((220, 330), Image.Resampling.LANCZOS)
                        self.app.root.after(0, lambda: _set_poster(img))
                except Exception:
                    pass
            def _set_poster(img):
                try:
                    from PIL import ImageTk
                    if poster_container.winfo_exists():
                        photo = ImageTk.PhotoImage(img)
                        # Create label to cover the placeholder
                        img_lbl = tk.Label(poster_container, image=photo, bg="#1a1a2e", bd=0)
                        img_lbl.image = photo
                        img_lbl.place(x=0, y=0, relwidth=1, relheight=1)
                except Exception:
                    pass
            threading.Thread(target=fetch_poster, daemon=True).start()

        # Title
        title_lbl = ctk.CTkLabel(
            inner, text=pick['title'], font=FONT_CARD_TITLE,
            fg_color="transparent", text_color=ACCENT_CYAN,
            wraplength=220, justify=tk.LEFT, anchor=tk.W
        )
        title_lbl.pack(fill=tk.X, padx=16, pady=(8, 0))

        # Year + Rating
        meta = ctk.CTkFrame(inner, fg_color="transparent")
        meta.pack(fill=tk.X, pady=(4, 0), padx=16)
        
        year_text = f"({pick.get('year') or '?'})"
        year_lbl = ctk.CTkLabel(
            meta, text=year_text, font=FONT_SMALL,
            fg_color="transparent", text_color=TEXT_MUTED
        )
        year_lbl.pack(side=tk.LEFT)
        
        rating = pick.get('imdb_rating') or 0
        rating_lbl = ctk.CTkLabel(
            meta, text=f"  ⭐ {rating:.1f}", font=FONT_SMALL,
            fg_color="transparent", text_color=STAR_COLOR
        )
        rating_lbl.pack(side=tk.LEFT)

        # Genre
        genre = (pick.get('genres') or 'N/A').split(',')[0].strip()
        genre_lbl = ctk.CTkLabel(
            inner, text=genre, font=get_font(size=12, weight="bold"),
            fg_color="transparent", text_color=TEXT_SECONDARY, anchor=tk.W,
            wraplength=220, justify=tk.LEFT
        )
        genre_lbl.pack(fill=tk.X, pady=(6, 0), padx=20)

        # Reason
        reason_lbl = ctk.CTkLabel(
            inner, text=pick.get('reason', ''), font=get_font(size=13, slant="italic"),
            fg_color="transparent", text_color=ACCENT_PURPLE,
            wraplength=220, justify=tk.LEFT, anchor=tk.W
        )
        reason_lbl.pack(fill=tk.X, pady=(12, 24), padx=20)

        # Map labels for future updates
        self.card_label_map[card] = [title_lbl, genre_lbl, reason_lbl]

        # ── Event Bindings ───────────────────────────────────────────────
        for w in [card, inner, title_lbl, meta, year_lbl, rating_lbl, genre_lbl, reason_lbl]:
            w.configure(cursor="hand2")

        def on_click(e):
            self._show_movie_overlay(pick)

        for w in [card, inner, title_lbl, meta, year_lbl, rating_lbl, genre_lbl, reason_lbl]:
            w.bind("<Button-1>", on_click)
        
        # Hover feedback
        def on_enter(e):
            inner.configure(fg_color=BG_GLASS_HOVER)
            
        def on_leave(e):
            inner.configure(fg_color="transparent")

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        return card

    def _animate_hover(self, card, start, end):
        """Static hover animation: just change border color."""
        # Removed live render calls for performance
        pass

    def _show_movie_overlay(self, pick):
        """Open a centered modal overlay with movie details."""
        if self._overlay:
            self._overlay.destroy()

        root_window = self.app.root
        root_window.update_idletasks()

        win_w = root_window.winfo_width()
        win_h = root_window.winfo_height()

        # ── Step 1 & 2: Outer overlay frame (full window) ──
        self._overlay = tk.Frame(root_window, bg="#0d0d0d", bd=0)
        self._overlay.place(x=0, y=0, width=win_w, height=win_h)
        self._overlay.lift()
        
        def on_overlay_click(e):
            self._close_overlay()
        self._overlay.bind("<Button-1>", on_overlay_click)

        # ── Step 4: Calculate modal dimensions ──
        modal_w = max(int(win_w * 0.72), 780)
        modal_h = max(int(win_h * 0.82), 580)
        modal_x = (win_w - modal_w) // 2
        modal_y = (win_h - modal_h) // 2

        # ── Step 5: Create inner modal as tk.Frame on OVERLAY ──
        inner = tk.Frame(
            self._overlay,  # Parent is OVERLAY, not root
            bg="#1a1a2e",
            bd=1,
            relief="flat",
            highlightbackground="#555555",
            highlightthickness=1
        )
        inner.place(x=modal_x, y=modal_y, width=modal_w, height=modal_h)
        inner.lift()  # Lift ABOVE bg_label
        self._overlay.lift()  # Lift overlay ABOVE main content
        self._modal_inner = inner

        # ── Step 6: Close button row (non-scrolling, at top of inner) ──
        close_row = tk.Frame(inner, bg="#1a1a2e", height=44)
        close_row.pack(fill="x", side="top")
        close_row.pack_propagate(False)

        close_btn = tk.Button(
            close_row,
            text="✕  Close",
            command=self._close_overlay,
            bg="#1a1a2e",
            fg="#ff375f",
            activebackground="#2a1a2e",
            activeforeground="#ff375f",
            bd=0,
            font=("Segoe UI", 11),
            cursor="hand2",
            padx=12, pady=8
        )
        close_btn.pack(side="right", padx=8, pady=4)

        # ── Step 7: Scrollable content area INSIDE inner modal ──
        canvas = tk.Canvas(
            inner,
            bg="#1a1a2e",
            bd=0,
            highlightthickness=0
        )
        scrollbar = tk.Scrollbar(
            inner,
            orient="vertical",
            command=canvas.yview,
            bg="#333355"
        )
        content_frame = tk.Frame(canvas, bg="#1a1a2e")

        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        canvas_window = canvas.create_window(
            0, 0,
            anchor="nw",
            window=content_frame,
            width=modal_w - 20  # Explicit width = modal minus scrollbar
        )

        def on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        content_frame.bind("<Configure>", on_frame_configure)

        # ── Step 8: Universal Mousewheel scrolling ──
        def on_mousewheel(e):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        
        self.app.root.bind_all("<MouseWheel>", on_mousewheel)

        self._overlay_content_frame = content_frame

        # ── Step 8: Loading state ──
        title_text = pick.get('title', 'Movie')
        year_text = pick.get('year', '?')

        loading_lbl = tk.Label(
            content_frame,
            text=f"🎬  {title_text}\n\nLoading details...",
            bg="#1a1a2e",
            fg="#00d4ff",
            font=("Segoe UI", 16, "bold"),
            justify="left",
            wraplength=modal_w - 60,
            pady=40, padx=20
        )
        loading_lbl.pack(fill="x", anchor="w")

        self._overlay.update()  # Force render so loading state is visible

        # ── Step 9: Bind close events ──
        root_window.bind("<Escape>", self._close_overlay_esc)

        # ── Step 10: Background thread fetch ──
        title = pick['title']
        year = pick.get('year')

        def background_fetch():
            movie_data = self._fetch_full_movie_data(title, year)
            if not movie_data:
                movie_data = self._fetch_from_omdb(title, year)
                
            img_data = None
            if movie_data and movie_data.get('poster') and movie_data['poster'].startswith('http'):
                import requests
                from io import BytesIO
                from PIL import Image
                try:
                    resp = requests.get(movie_data['poster'], timeout=5)
                    if resp.status_code == 200:
                        img = Image.open(BytesIO(resp.content))
                        img.thumbnail((300, 450), Image.LANCZOS)
                        img_data = img
                except Exception as e:
                    print("Error downloading poster:", e)
                    
            root_window.after(0, lambda: self._render_overlay_content(
                content_frame, loading_lbl, movie_data, img_data, modal_w - 60
            ))

        threading.Thread(target=background_fetch, daemon=True).start()

    def _fetch_from_omdb(self, title, year):
        """Fetch movie details from OMDb API as fallback."""
        import requests
        try:
            api_key = "dd21cf1d"
            params = {
                'apikey': api_key,
                't': title,
                'plot': 'full',
                'r': 'json'
            }
            if year:
                params['y'] = year
            resp = requests.get("http://www.omdbapi.com/", params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('Response') == 'True':
                    # Extract Rotten Tomatoes
                    rt_critics = None
                    rt_audience = None
                    for r in data.get('Ratings', []):
                        if r.get('Source') == 'Rotten Tomatoes':
                            rt_critics = r.get('Value')
                        elif 'Audience' in r.get('Source', ''):
                            rt_audience = r.get('Value')

                    return {
                        'title': data.get('Title', title),
                        'year': data.get('Year', year),
                        'imdb_id': data.get('imdbID', ''),
                        'imdb_rating': data.get('imdbRating', 'N/A'),
                        'imdb_votes': data.get('imdbVotes', 'N/A'),
                        'runtime': data.get('Runtime', 'N/A'),
                        'genres': data.get('Genre', 'N/A'),
                        'rated': data.get('Rated', 'N/A'),
                        'released': data.get('Released', 'N/A'),
                        'director': data.get('Director', 'N/A'),
                        'writer': data.get('Writer', 'N/A'),
                        'actors': data.get('Actors', 'N/A'),
                        'plot': data.get('Plot', 'N/A'),
                        'language': data.get('Language', 'N/A'),
                        'country': data.get('Country', 'N/A'),
                        'awards': data.get('Awards', 'N/A'),
                        'box_office': data.get('BoxOffice', 'N/A'),
                        'rt_critics': rt_critics,
                        'rt_audience': rt_audience,
                    }
        except Exception as e:
            print(f"OMDb fetch error: {e}")
        return None

    def _render_overlay_content(self, content_frame, loading_lbl, movie_data, img_data, wrap):
        """Populate the overlay with full movie data once fetched."""
        try:
            loading_lbl.destroy()
        except Exception:
            pass

        if not movie_data:
            tk.Label(
                content_frame, text="❌ Could not fetch movie details.",
                font=("Segoe UI", 14), bg="#1a1a2e", fg="#ff4444"
            ).pack(pady=40)
            return

        # Container for poster and initial details
        top_container = tk.Frame(content_frame, bg="#1a1a2e")
        top_container.pack(fill="x", pady=(0, 20))
        
        if img_data:
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img_data)
            poster_lbl = tk.Label(top_container, image=photo, bg="#1a1a2e", bd=0)
            poster_lbl.image = photo
            poster_lbl.pack(side="left", padx=(0, 20), anchor="n")
            
        text_container = tk.Frame(top_container, bg="#1a1a2e")
        text_container.pack(side="left", fill="both", expand=True)

        def add_label(parent, text, color, font_size=12, bold=False, pady=(0, 4)):
            weight = "bold" if bold else "normal"
            lbl = tk.Label(
                parent,
                text=text,
                bg="#1a1a2e",
                fg=color,
                font=("Segoe UI", font_size, weight),
                anchor="w",
                justify="left",
                wraplength=wrap,
                padx=20
            )
            lbl.pack(fill="x", pady=pady, anchor="w")
            return lbl

        def add_separator():
            sep = tk.Frame(content_frame, bg="#333333", height=1)
            sep.pack(fill="x", padx=20, pady=8)

        # Title
        title = movie_data.get('title', '?')
        year = movie_data.get('year', '?')
        add_label(text_container, f"🎬  {title} ({year})", "#ffffff", 20, bold=True, pady=8)
        # Cyan line under title
        tk.Frame(text_container, bg="#00d4ff", height=2).pack(fill="x", pady=(0, 12))

        # RATINGS
        add_label(text_container, "📊  RATINGS", "#00d4ff", 14, bold=True, pady=(8, 2))
        imdb_rating = movie_data.get('imdb_rating')
        imdb_votes = movie_data.get('imdb_votes')
        if imdb_rating and str(imdb_rating) != 'None':
            add_label(text_container, f"• IMDb:  {imdb_rating}/10  ({imdb_votes or 0} votes)", "#cccccc", 13)
        
        def format_rt(score):
            if not score or str(score) == 'None' or str(score) == 'N/A':
                return None
            s = str(score).strip()
            if not s.endswith('%'):
                s += '%'
            return s

        rt_critics = format_rt(movie_data.get('rt_critics'))
        if rt_critics:
            add_label(text_container, f"• Rotten Tomatoes:  {rt_critics}", "#cccccc", 13)
            
        rt_audience = format_rt(movie_data.get('rt_audience'))
        if rt_audience:
            add_label(text_container, f"• Rotten Tomatoes Audience:  {rt_audience}", "#cccccc", 13)
            
        # DETAILS
        add_label(text_container, "📝  DETAILS", "#00d4ff", 14, bold=True, pady=(16, 2))
        runtime = movie_data.get('runtime_minutes')
        if runtime and str(runtime) != 'None':
            add_label(text_container, f"• Runtime:   {runtime} min", "#cccccc")
        
        def get_val(key):
            v = movie_data.get(key)
            return str(v) if v and str(v) != 'None' else 'N/A'

        add_label(text_container, f"• Genre:     {get_val('genres')}", "#cccccc")
        add_label(text_container, f"• Rated:     {get_val('rated')}", "#cccccc")
        add_label(text_container, f"• Released:  {get_val('released')}", "#cccccc")
        
        add_separator()

        # CAST & CREW
        add_label(content_frame, "🎭  CAST & CREW", "#00d4ff", 14, bold=True, pady=(8, 2))
        add_label(content_frame, f"• Director:  {get_val('director')}", "#cccccc")
        add_label(content_frame, f"• Writer:    {get_val('writer')}", "#cccccc")
        add_label(content_frame, f"• Actors:    {get_val('actors')}", "#cccccc")
        add_separator()

        # PLOT
        # PLOT
        add_label(content_frame, "📖  PLOT", "#00d4ff", 14, bold=True, pady=(8, 2))
        plot = movie_data.get('plot')
        if plot and str(plot) != 'None':
            add_label(content_frame, plot, "#ffffff", 13, pady=4)
        add_separator()

        # OTHER INFO
        add_label(content_frame, "🌍  OTHER INFO", "#00d4ff", 14, bold=True, pady=(8, 2))
        add_label(content_frame, f"• Language:    {get_val('language')}", "#cccccc")
        add_label(content_frame, f"• Country:     {get_val('country')}", "#cccccc")
        add_label(content_frame, f"• Awards:      {get_val('awards')}", "#cccccc")
        box_office = movie_data.get('box_office')
        if box_office and str(box_office) != 'None':
            add_label(content_frame, f"• Box Office:  {box_office}", "#cccccc")
        add_separator()

        # IMDB LINK
        imdb_id = movie_data.get('imdb_id', '')
        if imdb_id and str(imdb_id) != 'None' and imdb_id != '':
            link_url = f"https://www.imdb.com/title/{imdb_id}/"
            link = tk.Label(
                content_frame,
                text=f"🔗  {link_url}",
                bg="#1a1a2e",
                fg="#bf5af2",
                font=("Segoe UI", 12),
                anchor="w",
                cursor="hand2",
                padx=20,
                wraplength=wrap
            )
            link.pack(fill="x", pady=(4, 20), anchor="w")
            link.bind("<Button-1>", lambda e: webbrowser.open(link_url))


    def _fetch_full_movie_data(self, title, year):
        """Fetch all fields for a movie from movies.db."""
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if year:
                cursor.execute("SELECT * FROM movies WHERE LOWER(title) = LOWER(?) AND year = ? LIMIT 1", (title, year))
            else:
                cursor.execute("SELECT * FROM movies WHERE LOWER(title) = LOWER(?) ORDER BY imdb_votes DESC LIMIT 1", (title,))
            
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            print(f"Error fetching movie data: {e}")
            return None

    def _close_overlay(self):
        if hasattr(self, 'app') and hasattr(self.app, 'root'):
            self.app.root.unbind_all("<MouseWheel>")
            self.app.root.unbind("<Escape>")
        if hasattr(self, '_overlay') and self._overlay:
            self._overlay.destroy()
            self._overlay = None
        if hasattr(self, '_modal_inner') and self._modal_inner:
            self._modal_inner.destroy()
            self._modal_inner = None

    def _close_overlay_esc(self, event):
        self._close_overlay()



# ============================
# Chat Screen
# ============================


class ChatScreen(ctk.CTkFrame):
    """Chat screen with AI-powered conversation."""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_ROOT)
        self.app = app
        self.chat_started = False
        
        # Header frame
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=20)
        
        back_btn = ctk.CTkButton(
            header, text="← Back", command=lambda: app.show_screen('title'),
            font=FONT_SMALL, fg_color="transparent", text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER_GLASS, hover_color=BG_GLASS_HOVER,
            corner_radius=8, height=32, width=100
        )
        back_btn.pack(side=tk.LEFT)

        ctk.CTkLabel(
            header, text="CineGuide Chat", font=FONT_HEADING,
            fg_color="transparent", text_color=ACCENT_CYAN
        ).pack(side=tk.LEFT, expand=True, padx=(0, 100))
        
        self.welcome_label = ctk.CTkLabel(
            self,
            text="Welcome to CineGuide Chat!\n\n"
                 "Ask me anything about movies:\n"
                 "• 'Tell me about Inception'\n"
                 "• 'Best Hindi movies'\n"
                 "• 'ddlj' (movie acronyms work too!)\n"
                 "• 'Top 10 action movies'\n\n"
                 "Type your message below to start!",
            font=FONT_HEADING,
            justify=tk.CENTER,
            fg_color="transparent",
            text_color=TEXT_PRIMARY
        )
        self.welcome_label.pack(fill=tk.BOTH, expand=True)
        
        self.text_area = ctk.CTkTextbox(
            self,
            wrap=tk.WORD,
            font=FONT_BODY,
            fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            border_color=BORDER_GLASS,
            border_width=1,
            corner_radius=12,
            scrollbar_button_color=BORDER_GLASS,
            scrollbar_button_hover_color=ACCENT_CYAN
        )
        
        # Configure tags for styling in the textbox
        self.text_area._textbox.tag_config("user", foreground=ACCENT_PURPLE, font=FONT_HEADING)
        self.text_area._textbox.tag_config("ai", foreground=ACCENT_CYAN, font=FONT_HEADING)
        self.text_area._textbox.tag_config("header", foreground=ACCENT_CYAN, font=FONT_HEADING)
        self.text_area._textbox.tag_config("label", foreground=TEXT_PRIMARY, font=FONT_BODY)
        self.text_area._textbox.tag_config("value", foreground=TEXT_SECONDARY, font=FONT_BODY)
        self.text_area._textbox.tag_config("link", foreground=ACCENT_PURPLE, font=FONT_BODY)
        
        input_container = ctk.CTkFrame(self, fg_color="transparent")
        input_container.pack(padx=20, pady=20, fill=tk.X, side=tk.BOTTOM)

        input_frame = GlassFrame(input_container, height=60, corner_radius=12)
        input_frame.pack(fill=tk.X)
        
        self.input_entry = ctk.CTkEntry(
            input_frame.inner_frame,
            placeholder_text="Type your message...",
            font=FONT_BODY,
            fg_color="transparent",
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED,
            border_width=0
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15)
        self.input_entry.bind("<Return>", lambda e: self.on_send())
        
        self.send_button = ctk.CTkButton(
            input_frame.inner_frame,
            text="Send",
            command=self.on_send,
            width=80,
            height=40,
            fg_color=ACCENT_CYAN,
            text_color="#000000",
            hover_color="#00b8e6",
            corner_radius=10,
            font=FONT_BUTTON
        )
        self.send_button.pack(side=tk.RIGHT, padx=10)
        
        self.clear_button = ctk.CTkButton(
            input_container,
            text="Clear Chat",
            command=self.on_clear,
            font=FONT_SMALL,
            fg_color="transparent",
            text_color=TEXT_SECONDARY,
            border_width=1,
            border_color=BORDER_GLASS,
            hover_color=BG_GLASS_HOVER,
            corner_radius=8,
            height=32,
            width=100
        )
        self.clear_button.pack(side=tk.RIGHT, pady=(10, 0))
        
    def start_chat(self):
        """Hide welcome, show chat area."""
        if not self.chat_started:
            self.welcome_label.pack_forget()
            self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
            self.chat_started = True
            self.input_entry.focus()
    
    def on_send(self):
        user_input = self.input_entry.get().strip()

        if not user_input:
            return

        self.start_chat()

        self.input_entry.delete(0, tk.END)
        self.text_area.insert(tk.END, "You\n", "user")
        self.text_area.insert(tk.END, f"{user_input}\n\n", "label")
        self.send_button.configure(state=tk.DISABLED)
        self.text_area.insert(tk.END, "CineGuide\n", "ai")
        self.text_area.see(tk.END)

        # Run all processing in background thread to avoid blocking UI
        def process_in_background():
            try:
                intent, param, extra = parse_user_query(user_input)
                log_event("query", {"input": user_input, "intent": intent, "param": param, "extra": extra})

                result = None

                if intent == 'movie_details':
                    year = None
                    if extra and 'year' in extra:
                        year = extra['year']

                    result = get_movie_from_db_direct(param, year=year)
                    if not result:
                        year_text = f" ({year})" if year else ""
                        result = f"I couldn't find '{param}{year_text}' in my database. Try checking the spelling or search for it!"

                elif intent == 'search':
                    result = search_movies(param)
                    if not result:
                        result = f"No movies found matching '{param}'. Try a different search term!"

                elif intent == 'top_movies':
                    limit = 10
                    language = None

                    if extra:
                        if 'limit' in extra:
                            limit = extra['limit']
                        if 'language' in extra:
                            language = extra['language']

                    result = get_top_movies(genre=param, language=language, limit=limit)

                    if not result and language:
                        log_event("language_fallback", {"language": language})
                        result = search_movies(language, limit=limit)
                        if result:
                            result = f"ℹ️ Language filter didn't work, showing search results instead:\n\n{result}"

                    if not result:
                        result = "No movies found matching your criteria. Try different filters!"

                elif intent == 'similar':
                    result = get_similar_movies(param)
                    if not result:
                        result = f"I couldn't find movies similar to '{param}'. Try asking about a different movie!"

                else:
                    # Run async agent response in the background thread
                    result = asyncio.run(self._get_agent_response(user_input))

                # Update UI on main thread
                self.app.root.after(0, lambda: self._finish_send(result))

            except Exception as e:
                self.app.root.after(0, lambda: self._finish_send(f"❌ Error: {str(e)}\n\n"))
                log_event("error", {"error": str(e), "input": user_input})

        threading.Thread(target=process_in_background, daemon=True).start()

    def _finish_send(self, result):
        """Called on main thread after background processing completes."""
        try:
            self._insert_styled_response(result)
            self.text_area.insert(tk.END, "\n" + "─" * 40 + "\n\n", "value")
            self.text_area.see(tk.END)
        except Exception:
            pass
        finally:
            self.send_button.configure(state=tk.NORMAL)
            self.input_entry.focus()
    
    def _insert_styled_response(self, text):
        """Helper to style movie detail blocks in chat with improved spacing."""
        if not hasattr(self.text_area, 'image_refs'):
            self.text_area.image_refs = []
            
        lines = text.split('\n')
        for line in lines:
            if not line.strip():
                self.text_area.insert(tk.END, '\n', "value")
                continue

            if line.startswith('HIDDEN_POSTER:'):
                url = line.split(':', 1)[1].strip()
                try:
                    import requests
                    from PIL import Image, ImageTk
                    from io import BytesIO
                    resp = requests.get(url, timeout=5)
                    if resp.status_code == 200:
                        img = Image.open(BytesIO(resp.content))
                        img.thumbnail((240, 360), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(img)
                        self.text_area.image_refs.append(photo)
                        self.text_area.insert(tk.END, "\n   ")
                        self.text_area.image_create(tk.END, image=photo)
                        self.text_area.insert(tk.END, "\n")
                except Exception:
                    pass
                continue # Don't print the hidden tag

            if line.startswith('🎬'):
                self.text_area.insert(tk.END, line + '\n', "header")
            elif line.startswith('━━━━━━━━'):
                self.text_area.insert(tk.END, line + '\n', "value")
            elif line.startswith('📊') or line.startswith('📝') or line.startswith('🎭') or line.startswith('📖') or line.startswith('🌍') or line.startswith('🔗'):
                self.text_area.insert(tk.END, '\n' + line + '\n', "header")
            elif '•' in line:
                parts = line.split('•', 1)
                self.text_area.insert(tk.END, '  •', "label")
                if ':' in parts[1]:
                    label_val = parts[1].split(':', 1)
                    self.text_area.insert(tk.END, label_val[0] + ':', "label")
                    self.text_area.insert(tk.END, label_val[1] + '\n', "value")
                else:
                    self.text_area.insert(tk.END, parts[1] + '\n', "value")
            elif line.startswith('   • http'):
                self.text_area.insert(tk.END, line + '\n', "link")
            else:
                self.text_area.insert(tk.END, line + '\n', "value")

    async def _get_agent_response(self, user_input: str) -> str:
        message = Content(parts=[Part(text=user_input)], role="user")

        response_text = ""
        try:
            async for event in runner.run_async(
                user_id=self.app.user_id,
                session_id=self.app.session_id,
                new_message=message
            ):
                if event.is_final_response() and event.content and event.content.parts:
                    response_text = event.content.parts[0].text
                    # Part 3: Real-time profile extraction
                    if _PROFILE_BUILDER_AVAILABLE:
                        extract_and_update_from_chat(user_input, response_text)
        except Exception as e:
            err = str(e)
            if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                response_text = (
                    "⚠️ **API Quota Exceeded**\n\n"
                    "The Gemini free-tier daily limit has been reached for this API key.\n\n"
                    "**Options:**\n"
                    "• Wait until the quota resets (usually midnight Pacific Time)\n"
                    "• Create a new API key from a *different* Google account at "
                    "https://aistudio.google.com/apikey\n"
                    "• Enable billing on your Google Cloud project for higher limits\n\n"
                    "*Note: Movie lookups, search, and roulette still work "
                    "— only the AI chat is affected.*"
                )
                log_event("quota_exceeded", {"model": MODEL_NAME, "input": user_input})
            else:
                raise  # re-raise non-quota errors so on_send can catch them

        return response_text
    
    def on_clear(self):
        self.text_area.delete(1.0, tk.END)


# ============================
# Roulette Screen
# ============================


class RouletteScreen(ctk.CTkFrame):
    """Roulette screen with movie randomizer."""
    
    def __init__(self, parent, app):
        super().__init__(parent, fg_color=BG_ROOT)
        self.app = app
        
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, padx=20, pady=20)
        
        back_btn = ctk.CTkButton(
            header, text="← Back", command=lambda: app.show_screen('title'),
            font=FONT_SMALL, fg_color="transparent", text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER_GLASS, hover_color=BG_GLASS_HOVER,
            corner_radius=8, height=32, width=100
        )
        back_btn.pack(side=tk.LEFT)

        ctk.CTkLabel(
            header, text="Movie Roulette", font=FONT_HEADING,
            fg_color="transparent", text_color=ACCENT_PURPLE
        ).pack(side=tk.LEFT, expand=True, padx=(0, 100))
        
        self.main_scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_scroll.pack(fill=tk.BOTH, expand=True, padx=20)

        filter_glass = GlassFrame(self.main_scroll, height=140, corner_radius=16)
        filter_glass.pack(fill=tk.X, pady=10)
        filter_frame = filter_glass.inner_frame
        
        ctk.CTkLabel(filter_frame, text="Genre:", font=FONT_LABEL, text_color=TEXT_PRIMARY).grid(row=0, column=0, sticky=tk.W, padx=15, pady=10)
        self.genre_var = tk.StringVar(value="All Genres")
        
        # Build unique genre list from aliases + defaults
        base_genres = set(GENRE_ALIASES.values()) | {'action', 'comedy', 'drama', 'horror', 'romance', 'thriller'}
        genres = ["All Genres"] + sorted(list(base_genres))
        
        self.genre_combo = ctk.CTkOptionMenu(
            filter_frame, variable=self.genre_var, values=genres,
            fg_color=BG_INPUT, button_color=BORDER_GLASS, button_hover_color=BG_GLASS_HOVER,
            dropdown_fg_color=BG_MODAL, text_color=TEXT_PRIMARY, corner_radius=8
        )
        self.genre_combo.grid(row=0, column=1, padx=10, pady=10)
        
        ctk.CTkLabel(filter_frame, text="Language:", font=FONT_LABEL, text_color=TEXT_PRIMARY).grid(row=0, column=2, sticky=tk.W, padx=15, pady=10)
        self.language_var = tk.StringVar(value="All Languages")
        languages = ["All Languages"] + sorted(list(LANGUAGE_ALIASES.values()))
        self.language_combo = ctk.CTkOptionMenu(
            filter_frame, variable=self.language_var, values=languages,
            fg_color=BG_INPUT, button_color=BORDER_GLASS, button_hover_color=BG_GLASS_HOVER,
            dropdown_fg_color=BG_MODAL, text_color=TEXT_PRIMARY, corner_radius=8
        )
        self.language_combo.grid(row=0, column=3, padx=10, pady=10)
        
        ctk.CTkLabel(filter_frame, text="Year Range:", font=FONT_LABEL, text_color=TEXT_PRIMARY).grid(row=1, column=0, sticky=tk.W, padx=15, pady=10)
        self.year_min_var = tk.StringVar()
        self.year_max_var = tk.StringVar()
        
        year_frame = ctk.CTkFrame(filter_frame, fg_color="transparent")
        year_frame.grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=10)
        
        ctk.CTkEntry(year_frame, textvariable=self.year_min_var, width=80, placeholder_text="Min", fg_color=BG_INPUT, border_color=BORDER_GLASS, corner_radius=8).pack(side=tk.LEFT)
        ctk.CTkLabel(year_frame, text=" to ", font=FONT_BODY).pack(side=tk.LEFT, padx=5)
        ctk.CTkEntry(year_frame, textvariable=self.year_max_var, width=80, placeholder_text="Max", fg_color=BG_INPUT, border_color=BORDER_GLASS, corner_radius=8).pack(side=tk.LEFT)
        
        self.spinning = False
        self.angle = 0
        
        self.canvas = tk.Canvas(self.main_scroll, width=300, height=300, bg=BG_ROOT, highlightthickness=0)
        self.canvas.pack(pady=20, expand=True)
        self.draw_roulette()
        
        self.spin_button = ctk.CTkButton(
            self.main_scroll,
            text="🎰 SPIN THE ROULETTE!",
            command=self.spin_roulette,
            font=FONT_BUTTON,
            fg_color=ACCENT_PURPLE,
            text_color=TEXT_PRIMARY,
            hover_color="#a044d8",
            corner_radius=14,
            height=56,
            width=300
        )
        self.spin_button.pack(pady=10)
        
        results_glass = GlassFrame(self.main_scroll, height=200, corner_radius=16)
        results_glass.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.results_text = ctk.CTkTextbox(
            results_glass.inner_frame,
            wrap=tk.WORD,
            font=FONT_BODY,
            fg_color="transparent",
            text_color=TEXT_PRIMARY,
            scrollbar_button_color=BORDER_GLASS,
            scrollbar_button_hover_color=ACCENT_CYAN
        )
        self.results_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
    def spin_roulette(self):
        """Spin the roulette with validation."""
        if self.spinning:
            return
        
        year_min_str = self.year_min_var.get().strip()
        year_max_str = self.year_max_var.get().strip()
        
        if year_min_str and not year_min_str.isdigit():
            messagebox.showwarning("Invalid Input", "Year Min must be a number or left blank!")
            return
        
        if year_max_str and not year_max_str.isdigit():
            messagebox.showwarning("Invalid Input", "Year Max must be a number or left blank!")
            return
        
        self.spinning = True
        self.spin_button.configure(state=tk.DISABLED)
        
        genre = self.genre_var.get().strip()
        if genre == "All Genres": genre = None
        
        language = self.language_var.get().strip()
        if language == "All Languages": language = None
        
        year_min = int(year_min_str) if year_min_str else None
        year_max = int(year_max_str) if year_max_str else None
        
        self.animate_spin(60, lambda: self.show_results(genre, language, year_min, year_max))
    
    def animate_spin(self, spins_left, callback):
        """Animate the roulette spinning."""
        if spins_left > 0:
            self.angle = (self.angle + (60 - spins_left + 1) * 5) % 360
            self.draw_roulette()
            self.after(50, lambda: self.animate_spin(spins_left - 1, callback))
        else:
            self.spinning = False
            self.spin_button.configure(state=tk.NORMAL)
            callback()
    
    def draw_roulette(self):
        """Draw the roulette wheel."""
        self.canvas.delete("all")
        
        wheel_colors = [ACCENT_CYAN, ACCENT_PURPLE, "#ff9f0a", ACCENT_GREEN, ACCENT_PINK, "#0a84ff"]
        for i in range(6):
            start_angle = self.angle + i * 60
            self.canvas.create_arc(
                25, 25, 275, 275,
                start=start_angle,
                extent=60,
                fill=wheel_colors[i],
                outline=BG_ROOT,
                width=2
            )
        
        self.canvas.create_polygon(
            150, 10, 140, 30, 160, 30,
            fill=TEXT_PRIMARY
        )
    
    def show_results(self, genre, language, year_min, year_max):
        """Show random movie results."""
        self.results_text.delete(1.0, tk.END)
        
        movies = get_random_movies(3, genre, language, year_min, year_max)
        
        if not movies:
            self.results_text.insert(tk.END, "❌ No movies found with these filters. Try adjusting them!")
            return
        
        timestamp = time.strftime("%H:%M:%S")
        self.results_text.insert(tk.END, f"🎬 Your Random Movies (Spin at {timestamp}):\n\n")
        for idx, (title, year, rating, genres) in enumerate(movies, 1):
            self.results_text.insert(tk.END, f"{idx}. {title} ({year or '?'}) - ⭐ {rating}/10\n")
            self.results_text.insert(tk.END, f"   {genres}\n\n")


# ============================
# Entry Point
# ============================


def main():
    """Launch CineGuide application."""
    if not Path(DB_FILE).exists():
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Database Not Found",
            f"Error: {DB_FILE} not found!\n\n"
            "Please run 'python build_movie_database.py' first."
        )
        root.destroy()
        return

    initialize_database()

    root = ctk.CTk()
    app = CineGuideApp(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        try:
            root.destroy()
        except:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
