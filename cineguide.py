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


# GUI imports
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


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
MODEL_NAME = "gemini-2.0-flash"


# Load API key from environment variable
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    # Fallback: Try loading from .env file
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("GOOGLE_API_KEY="):
                    GOOGLE_API_KEY = line.split("=", 1)[1].strip()
                    break

if not GOOGLE_API_KEY:
    print("⚠️ WARNING: GOOGLE_API_KEY not found!")
    print("Please set it as an environment variable or create a .env file with:")
    print("GOOGLE_API_KEY=your_key_here")
else:
    os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY


# Dark mode color scheme
COLORS = {
    'bg_dark': '#0a0a0a',           # Pure black background
    'bg_medium': '#1a1a1a',         # Slightly lighter black
    'bg_light': '#2a2a2a',          # Card backgrounds
    'neon_cyan': '#00ffff',         # Neon cyan accent
    'neon_purple': '#bf00ff',       # Neon purple accent
    'neon_pink': '#ff00ff',         # Neon pink accent
    'neon_green': '#00ff00',        # Neon green accent
    'text_primary': '#ffffff',      # White text
    'text_secondary': '#b0b0b0',    # Gray text
}


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
# Genre & Language Mapping
# ============================

GENRE_ALIASES = {
    'romantic': 'romance',
    'romcom': 'romance',
    'rom-com': 'romance',
    'scary': 'horror',
    'frightening': 'horror',
    'funny': 'comedy',
    'hilarious': 'comedy',
    'scifi': 'sci-fi',
    'science fiction': 'sci-fi',
    'superhero': 'action',
    'spy': 'thriller',
    'suspense': 'thriller',
    'cartoon': 'animation',
    'animated': 'animation',
}

LANGUAGE_ALIASES = {
    'hindi': 'Hindi',
    'english': 'English',
    'spanish': 'Spanish',
    'french': 'French',
    'german': 'German',
    'italian': 'Italian',
    'japanese': 'Japanese',
    'korean': 'Korean',
    'chinese': 'Chinese',
    'tamil': 'Tamil',
    'telugu': 'Telugu',
    'malayalam': 'Malayalam',
    'bengali': 'Bengali',
}

MOVIE_ACRONYMS = {
    'ddlj': 'Dilwale Dulhania Le Jayenge',
    'k3g': 'Kabhi Khushi Kabhie Gham',
    'znmd': 'Zindagi Na Milegi Dobara',
    'yjhd': 'Yeh Jawaani Hai Deewani',
    'adhm': 'Ae Dil Hai Mushkil',
    'khnh': 'Kal Ho Naa Ho',
    'kkhh': 'Kuch Kuch Hota Hai',
    'hahk': 'Hum Aapke Hain Koun',
    'dlkh': 'Dum Laga Ke Haisha',
    'got': 'Game of Thrones',
    'gotg': 'Guardians of the Galaxy',
    'lotr': 'The Lord of the Rings',
    'rotk': 'The Return of the King',
    'fotr': 'The Fellowship of the Ring',
    'ttt': 'The Two Towers',
    'hp': 'Harry Potter',
    'sw': 'Star Wars',
    'esb': 'The Empire Strikes Back',
    'rotj': 'Return of the Jedi',
    'tpm': 'The Phantom Menace',
    'aotc': 'Attack of the Clones',
    'rots': 'Revenge of the Sith',
    'tfa': 'The Force Awakens',
    'tlj': 'The Last Jedi',
    'tros': 'The Rise of Skywalker',
    'mcu': 'Marvel Cinematic Universe',
    'dceu': 'DC Extended Universe',
}

FRANCHISE_NUMBERS = {
    'harry potter 1': 'Harry Potter and the Sorcerer\'s Stone',
    'harry potter 2': 'Harry Potter and the Chamber of Secrets',
    'harry potter 3': 'Harry Potter and the Prisoner of Azkaban',
    'harry potter 4': 'Harry Potter and the Goblet of Fire',
    'harry potter 5': 'Harry Potter and the Order of the Phoenix',
    'harry potter 6': 'Harry Potter and the Half-Blood Prince',
    'harry potter 7': 'Harry Potter and the Deathly Hallows',
    'harry potter 8': 'Harry Potter and the Deathly Hallows: Part 2',
    'star wars 1': 'The Phantom Menace',
    'star wars 2': 'Attack of The Clones',
    'star wars 3': 'Revenge of the Sith',
    'star wars 4': 'A New Hope',
    'star wars 5': 'The Empire Strikes Back',
    'star wars 6': 'Return of the Jedi',
    'star wars 7': 'The Force Awakens',
    'star wars 8': 'The Last Jedi',
    'star wars 9': 'The Rise of Skywalker',
    'avengers 1': 'The Avengers',
    'avengers 2': 'Age of Ultron',
    'avengers 3': 'Infinity War',
    'avengers 4': 'Endgame',
    'avengers 5': 'Doomsday',
    'avengers 6': 'Secret Wars',
    'lotr 1': 'The Fellowship of the Ring',
    'lotr 2': 'The Two Towers',
    'lotr 3': 'The Return of the King',
    'fast and furious 1': 'The Fast and the Furious',
    'fast and furious 2': '2 Fast 2 Furious',
    'fast and furious 3': 'Tokyo Drift',
    'fast and furious 4': 'Fast & Furious',
    'fast and furious 5': 'Fast Five',
    'fast and furious 6': 'Fast & Furious 6',
    'fast and furious 7': 'Furious 7',
    'fast and furious 8': 'The Fate of the Furious',
    'fast and furious 9': 'F9',
    'fast and furious 10': 'Fast X',
    'mission impossible 1': 'Mission: Impossible',
    'mission impossible 2': 'Mission: Impossible II',
    'mission impossible 3': 'Mission: Impossible III',
    'mission impossible 4': 'Ghost Protocol',
    'mission impossible 5': 'Rogue Nation',
    'mission impossible 6': 'Fallout',
    'mission impossible 7': 'Dead Reckoning Part One',
    'mission impossible 8': 'The Final Reckoning',
    'toy story 1': 'Toy Story',
    'toy story 2': 'Toy Story 2',
    'toy story 3': 'Toy Story 3',
    'toy story 4': 'Toy Story 4',
    'godfather 1': 'The Godfather',
    'godfather 2': 'The Godfather Part II',
    'godfather 3': 'The Godfather Part III',
    'iron man 1': 'Iron Man',
    'iron man 2': 'Iron Man 2',
    'iron man 3': 'Iron Man 3',
}

def normalize_genre(genre: str) -> str:
    """Normalize genre name to handle variations."""
    genre_lower = genre.lower().strip()
    return GENRE_ALIASES.get(genre_lower, genre_lower)

def normalize_language(language: str) -> str:
    """Normalize language name to handle variations."""
    language_lower = language.lower().strip()
    return LANGUAGE_ALIASES.get(language_lower, language.title())

def expand_query(query: str) -> Tuple[str, Optional[int]]:
    """Expand acronyms and franchise numbers."""
    query_lower = query.lower().strip()
    
    SPECIAL_CASES = {
        'ddlj': ('Dilwale Dulhania Le Jayenge', 1995),
        '3 idiots': ('3 Idiots', 2009),
        'dilwale dulhaniya le jayenge': ('Dilwale Dulhania Le Jayenge', 1995),
        'dilwale dulhania le jayenge': ('Dilwale Dulhania Le Jayenge', 1995),
        'avengers doomsday': ('Avengers Doomsday', 2026),
    }
    
    if query_lower in SPECIAL_CASES:
        return SPECIAL_CASES[query_lower]
    
    acronym_number_pattern = r'^([a-z]+)(\d+)$'
    match = re.match(acronym_number_pattern, query_lower)
    if match:
        acronym = match.group(1)
        number = match.group(2)
        
        if acronym in MOVIE_ACRONYMS:
            franchise = MOVIE_ACRONYMS[acronym].lower()
            franchise_with_num = f"{franchise} {number}"
            
            if franchise_with_num in FRANCHISE_NUMBERS:
                return (FRANCHISE_NUMBERS[franchise_with_num], None)
    
    if query_lower in FRANCHISE_NUMBERS:
        subtitle = FRANCHISE_NUMBERS[query_lower]
        
        if query_lower.startswith('avengers '):
            return (f"Avengers {subtitle}", None)
        
        return (subtitle, None)
    
    if query_lower in MOVIE_ACRONYMS:
        return (MOVIE_ACRONYMS[query_lower], None)
    
    return (query, None)


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
        
        if year:
            cursor.execute("""
                SELECT * FROM movies 
                WHERE LOWER(title) LIKE LOWER(?)
                AND year = ?
                ORDER BY COALESCE(imdb_votes, 0) DESC, COALESCE(imdb_rating, 0) DESC
                LIMIT 1
            """, (f'%{expanded_name}%', year))
        else:
            cursor.execute("""
                SELECT * FROM movies 
                WHERE LOWER(title) LIKE LOWER(?)
                ORDER BY COALESCE(imdb_votes, 0) DESC, COALESCE(imdb_rating, 0) DESC
                LIMIT 1
            """, (f'%{expanded_name}%',))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            log_event("movie_not_found", {"expanded": expanded_name, "year": year})
            return None
        
        (imdb_id, title, year, runtime, genres, imdb_rating, imdb_votes,
         rt_critics, rt_audience, rated, released, director, writer, actors,
         plot, language, country, awards, poster, box_office, enriched) = row
        
        log_event("movie_lookup", {"title": title, "imdb_id": imdb_id, "year": year, "votes": imdb_votes})
        
        result = f"""🎬 **{title}** ({year or 'Year unknown'})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **RATINGS**
   • IMDB: {imdb_rating or 'N/A'}/10 ({imdb_votes or 0:,} votes)"""

        if rt_critics or rt_audience:
            result += f"""
   • Rotten Tomatoes (Critics): {rt_critics or 'N/A'}
   • Rotten Tomatoes (Audience): {rt_audience or 'N/A'}"""
        
        result += f"""

📝 **DETAILS**
   • Runtime: {runtime or 'N/A'} minutes
   • Genre: {genres or 'N/A'}"""
        
        if rated:
            result += f"\n   • Rated: {rated}"
        if released:
            result += f"\n   • Released: {released}"
        
        if director or writer or actors:
            result += f"""

🎭 **CAST & CREW**"""
            if director:
                result += f"\n   • Director: {director}"
            if writer:
                result += f"\n   • Writer: {writer}"
            if actors:
                result += f"\n   • Actors: {actors}"
        
        if plot:
            result += f"""

📖 **PLOT**
{plot}"""
        
        if language or country or awards or box_office:
            result += f"""

🌍 **OTHER INFO**"""
            if language:
                result += f"\n   • Language: {language}"
            if country:
                result += f"\n   • Country: {country}"
            if awards:
                result += f"\n   • Awards: {awards}"
            if box_office:
                result += f"\n   • Box Office: {box_office}"
        
        result += f"""

🔗 **IMDB LINK**
   • https://www.imdb.com/title/{imdb_id}/"""
        
        return result
        
    except Exception as e:
        log_event("error", {"error": str(e), "movie": movie_name, "year": year})
        return None


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
    """Get random movies with optional filters."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        query = "SELECT title, year, imdb_rating, genres FROM movies WHERE imdb_rating IS NOT NULL"
        params = []
        
        if genre:
            genre = normalize_genre(genre)
            query += " AND LOWER(genres) LIKE LOWER(?)"
            params.append(f'%{genre}%')
        
        if language:
            language = normalize_language(language)
            query += " AND (LOWER(language) = LOWER(?) OR LOWER(language) LIKE LOWER(?) || ',%')"
            params.extend([language, language])
        
        if year_min:
            query += " AND year >= ?"
            params.append(year_min)
        
        if year_max:
            query += " AND year <= ?"
            params.append(year_max)
        
        query += " ORDER BY RANDOM() LIMIT ?"
        params.append(count)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return rows
        
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
    instruction='You are a friendly and enthusiastic movie assistant. Be conversational, helpful, and show genuine interest in movies. Keep responses brief and natural.',
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
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} - Your Personal Movie Companion")
        self.root.geometry("1000x750")
        self.root.configure(bg=COLORS['bg_dark'])
        
        self.session_id = f"gui_session_{int(time.time())}"
        self.user_id = "local_user"
        asyncio.run(self._init_session())
        
        self.container = tk.Frame(self.root, bg=COLORS['bg_dark'])
        self.container.pack(fill=tk.BOTH, expand=True)
        
        self.screens = {}
        self.screens['title'] = TitleScreen(self.container, self)
        self.screens['chat'] = ChatScreen(self.container, self)
        self.screens['roulette'] = RouletteScreen(self.container, self)
        
        self.show_screen('title')
        
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
# Title Screen
# ============================


class TitleScreen(tk.Frame):
    """Main title screen with navigation buttons."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS['bg_dark'])
        self.app = app
        
        title = tk.Label(
            self,
            text="🎬 CineGuide",
            font=("Arial", 52, "bold"),
            bg=COLORS['bg_dark'],
            fg=COLORS['neon_cyan']
        )
        title.pack(pady=60)
        
        subtitle = tk.Label(
            self,
            text="Your AI-Powered Movie Companion with 700K+ Movies",
            font=("Arial", 16),
            bg=COLORS['bg_dark'],
            fg=COLORS['text_secondary']
        )
        subtitle.pack(pady=10)
        
        button_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        button_frame.pack(pady=60)
        
        chat_btn = tk.Button(
            button_frame,
            text="💬 Let's Talk Movies!",
            command=lambda: self.app.show_screen('chat'),
            font=("Arial", 18, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['neon_purple'],
            activebackground=COLORS['neon_purple'],
            activeforeground=COLORS['bg_dark'],
            width=30,
            height=3,
            cursor="hand2",
            borderwidth=2,
            relief=tk.FLAT
        )
        chat_btn.pack(pady=15)
        
        roulette_btn = tk.Button(
            button_frame,
            text="🎰 I Can't Decide...",
            command=lambda: self.app.show_screen('roulette'),
            font=("Arial", 18, "bold"),
            bg=COLORS['bg_light'],
            fg=COLORS['neon_pink'],
            activebackground=COLORS['neon_pink'],
            activeforeground=COLORS['bg_dark'],
            width=30,
            height=3,
            cursor="hand2",
            borderwidth=2,
            relief=tk.FLAT
        )
        roulette_btn.pack(pady=15)


# ============================
# Chat Screen
# ============================


class ChatScreen(tk.Frame):
    """Chat screen with AI-powered conversation."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS['bg_dark'])
        self.app = app
        self.chat_started = False
        
        back_btn = tk.Button(
            self,
            text="← Back to Main Menu",
            command=lambda: app.show_screen('title'),
            font=("Arial", 10),
            bg=COLORS['bg_medium'],
            fg=COLORS['text_secondary'],
            activebackground=COLORS['bg_light'],
            activeforeground=COLORS['neon_cyan'],
            borderwidth=0,
            relief=tk.FLAT
        )
        back_btn.pack(anchor=tk.NW, padx=10, pady=10)
        
        self.welcome_label = tk.Label(
            self,
            text="🎬 Welcome to CineGuide Chat!\n\n"
                 "Ask me anything about movies:\n"
                 "• 'Tell me about Inception'\n"
                 "• 'Best Hindi movies'\n"
                 "• 'ddlj' (movie acronyms work too!)\n"
                 "• 'Top 10 action movies'\n\n"
                 "Type your message below to start!",
            font=("Arial", 14),
            justify=tk.CENTER,
            pady=50,
            bg=COLORS['bg_dark'],
            fg=COLORS['text_primary']
        )
        self.welcome_label.pack(fill=tk.BOTH, expand=True)
        
        self.text_area = scrolledtext.ScrolledText(
            self,
            wrap=tk.WORD,
            width=100,
            height=30,
            font=("Consolas", 10),
            bg=COLORS['bg_medium'],
            fg=COLORS['text_primary'],
            insertbackground=COLORS['neon_cyan'],
            selectbackground=COLORS['neon_purple'],
            selectforeground=COLORS['text_primary']
        )
        
        input_frame = tk.Frame(self, bg=COLORS['bg_dark'])
        input_frame.pack(padx=10, pady=10, fill=tk.X, side=tk.BOTTOM)
        
        self.input_entry = tk.Entry(
            input_frame,
            width=80,
            font=("Arial", 11),
            bg=COLORS['bg_medium'],
            fg=COLORS['text_primary'],
            insertbackground=COLORS['neon_cyan'],
            selectbackground=COLORS['neon_purple'],
            selectforeground=COLORS['text_primary'],
            borderwidth=2,
            relief=tk.FLAT
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.input_entry.bind("<Return>", lambda e: self.on_send())
        
        self.send_button = tk.Button(
            input_frame,
            text="Send",
            command=self.on_send,
            width=10,
            bg=COLORS['neon_green'],
            fg=COLORS['bg_dark'],
            font=("Arial", 10, "bold"),
            activebackground=COLORS['neon_cyan'],
            activeforeground=COLORS['bg_dark'],
            borderwidth=0,
            relief=tk.FLAT
        )
        self.send_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = tk.Button(
            input_frame,
            text="Clear",
            command=self.on_clear,
            width=10,
            bg=COLORS['bg_light'],
            fg=COLORS['text_primary'],
            font=("Arial", 10),
            activebackground=COLORS['neon_pink'],
            activeforeground=COLORS['bg_dark'],
            borderwidth=0,
            relief=tk.FLAT
        )
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
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
        self.text_area.insert(tk.END, f"You: {user_input}\n\n")
        self.send_button.config(state=tk.DISABLED)
        self.text_area.insert(tk.END, "CineGuide: ")
        self.text_area.update()
        
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
                result = asyncio.run(self._get_agent_response(user_input))
            
            self.text_area.insert(tk.END, f"{result}\n\n")
            self.text_area.insert(tk.END, "-" * 80 + "\n\n")
            
        except Exception as e:
            self.text_area.insert(tk.END, f"❌ Error: {str(e)}\n\n")
            log_event("error", {"error": str(e), "input": user_input})
        
        self.send_button.config(state=tk.NORMAL)
        self.input_entry.focus()
    
    async def _get_agent_response(self, user_input: str) -> str:
        message = Content(parts=[Part(text=user_input)], role="user")
        
        response_text = ""
        async for event in runner.run_async(
            user_id=self.app.user_id,
            session_id=self.app.session_id,
            new_message=message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text
        
        return response_text
    
    def on_clear(self):
        self.text_area.delete(1.0, tk.END)


# ============================
# Roulette Screen
# ============================


class RouletteScreen(tk.Frame):
    """Roulette screen with movie randomizer."""
    
    def __init__(self, parent, app):
        super().__init__(parent, bg=COLORS['bg_dark'])
        self.app = app
        
        back_btn = tk.Button(
            self,
            text="← Back to Main Menu",
            command=lambda: app.show_screen('title'),
            font=("Arial", 10),
            bg=COLORS['bg_medium'],
            fg=COLORS['text_secondary'],
            activebackground=COLORS['bg_light'],
            activeforeground=COLORS['neon_cyan'],
            borderwidth=0,
            relief=tk.FLAT
        )
        back_btn.pack(anchor=tk.NW, padx=10, pady=10)
        
        title = tk.Label(
            self,
            text="🎰 Random Movie Roulette",
            font=("Arial", 24, "bold"),
            pady=20,
            bg=COLORS['bg_dark'],
            fg=COLORS['neon_pink']
        )
        title.pack()
        
        filter_frame = tk.LabelFrame(
            self,
            text="Filters (Optional)",
            padx=20,
            pady=10,
            bg=COLORS['bg_medium'],
            fg=COLORS['text_primary'],
            font=("Arial", 11, "bold")
        )
        filter_frame.pack(padx=20, pady=10, fill=tk.X)
        
        tk.Label(filter_frame, text="Genre:", bg=COLORS['bg_medium'], fg=COLORS['text_primary']).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.genre_var = tk.StringVar()
        genres = [''] + list(set(GENRE_ALIASES.values())) + ['action', 'comedy', 'drama', 'horror', 'romance', 'thriller']
        self.genre_combo = ttk.Combobox(filter_frame, textvariable=self.genre_var, values=sorted(set(genres)))
        self.genre_combo.grid(row=0, column=1, padx=5, pady=5)
        
        tk.Label(filter_frame, text="Language:", bg=COLORS['bg_medium'], fg=COLORS['text_primary']).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.language_var = tk.StringVar()
        languages = [''] + list(LANGUAGE_ALIASES.values())
        self.language_combo = ttk.Combobox(filter_frame, textvariable=self.language_var, values=sorted(set(languages)))
        self.language_combo.grid(row=0, column=3, padx=5, pady=5)
        
        tk.Label(filter_frame, text="Year Range:", bg=COLORS['bg_medium'], fg=COLORS['text_primary']).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.year_min_var = tk.StringVar()
        self.year_max_var = tk.StringVar()
        year_min_entry = tk.Entry(filter_frame, textvariable=self.year_min_var, width=10, bg=COLORS['bg_light'], fg=COLORS['text_primary'])
        year_min_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        tk.Label(filter_frame, text="to", bg=COLORS['bg_medium'], fg=COLORS['text_primary']).grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        year_max_entry = tk.Entry(filter_frame, textvariable=self.year_max_var, width=10, bg=COLORS['bg_light'], fg=COLORS['text_primary'])
        year_max_entry.grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        
        self.canvas = tk.Canvas(self, width=300, height=300, bg=COLORS['bg_medium'], highlightthickness=0)
        self.canvas.pack(pady=10)
        
        self.spin_button = tk.Button(
            self,
            text="🎰 SPIN THE ROULETTE!",
            command=self.spin_roulette,
            font=("Arial", 16, "bold"),
            bg=COLORS['neon_pink'],
            fg=COLORS['bg_dark'],
            activebackground=COLORS['neon_purple'],
            activeforeground=COLORS['bg_dark'],
            padx=20,
            pady=10,
            borderwidth=0,
            relief=tk.FLAT
        )
        self.spin_button.pack(pady=10)
        
        self.results_frame = tk.LabelFrame(
            self,
            text="Your Random Movies",
            padx=20,
            pady=10,
            bg=COLORS['bg_medium'],
            fg=COLORS['text_primary'],
            font=("Arial", 11, "bold")
        )
        self.results_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)
        
        self.results_text = scrolledtext.ScrolledText(
            self.results_frame,
            wrap=tk.WORD,
            height=8,
            font=("Consolas", 10),
            bg=COLORS['bg_light'],
            fg=COLORS['text_primary'],
            selectbackground=COLORS['neon_purple'],
            selectforeground=COLORS['text_primary']
        )
        self.results_text.pack(fill=tk.BOTH, expand=True)
        
        self.spinning = False
        self.angle = 0
        
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
        self.spin_button.config(state=tk.DISABLED)
        
        genre = self.genre_var.get().strip() or None
        language = self.language_var.get().strip() or None
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
            self.spin_button.config(state=tk.NORMAL)
            callback()
    
    def draw_roulette(self):
        """Draw the roulette wheel."""
        self.canvas.delete("all")
        
        colors = [COLORS['neon_pink'], COLORS['neon_cyan'], COLORS['neon_purple'], 
                  COLORS['neon_green'], "#ff6b6b", "#4ecdc4"]
        for i in range(6):
            start_angle = self.angle + i * 60
            self.canvas.create_arc(
                25, 25, 275, 275,
                start=start_angle,
                extent=60,
                fill=colors[i],
                outline=COLORS['bg_dark'],
                width=2
            )
        
        self.canvas.create_polygon(
            150, 10, 140, 30, 160, 30,
            fill=COLORS['text_primary']
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
    
    root = tk.Tk()
    app = CineGuideApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
