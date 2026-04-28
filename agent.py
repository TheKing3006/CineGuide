from google.adk.agents.llm_agent import Agent


# ============================
# Personalization helpers
# ============================

PROFILE_FILE = "user_profile.json"

try:
    from profile_builder import load_profile_context, extract_and_update_from_chat
    _PROFILE_BUILDER_AVAILABLE = True
except ImportError:
    _PROFILE_BUILDER_AVAILABLE = False
    def load_profile_context(profile_path=PROFILE_FILE): return ""
    def extract_and_update_from_chat(user_msg, ai_msg): pass


def _build_agent_instruction() -> str:
    """Build agent instruction, optionally prepending personalization context."""
    base = (
        "You are an elite movie expert and CineGuide assistant. "
        "STRICT RULE: NEVER guess or hallucinate cast members, directors, or plot details. "
        "If a user mentions a movie, you MUST call 'get_movie_from_db' to fetch the real data. "
        "If you are recommending movies, use 'search_movies_in_db' or 'get_top_movies'. "
        "Only talk about facts found in the database tools. "
        "Use the USER TASTE PROFILE below to personalize your recommendations."
    )
    context = load_profile_context(PROFILE_FILE)
    if context:
        return base + "\n\n" + context
    return base


root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A movie recommendation assistant with access to a local IMDB and Rotten Tomatoes database.',
    instruction=_build_agent_instruction(),
)

# ============================
# Database Tools
# ============================

import sqlite3
from typing import List, Optional

DB_FILE = "movies.db"

# ============================
# Aliases & Normalization
# ============================

MOVIE_ALIASES = {
    "avengers doomsday": "Avengers: Doomsday",
    "avengers 5": "Avengers: Doomsday",
    "mario galaxy": "The Super Mario Galaxy Movie",
    "mario movie 2": "The Super Mario Galaxy Movie",
    "mario 2": "The Super Mario Galaxy Movie",
    "dhurandhar 2": "Dhurandhar: The Revenge",
}

def normalize_text(text: str) -> str:
    """Remove punctuation and spaces for fuzzy comparison."""
    import re
    return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

def get_movie_from_db(title: str) -> str:
    """
    Get complete movie details from local database by title.
    
    Args:
        title: Movie title to search for
        
    Returns:
        Formatted movie details with all IMDB and RT data
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. Normalize and resolve aliases
        clean_query = title.lower().strip()
        target_title = MOVIE_ALIASES.get(clean_query, title)
        norm_query = normalize_text(target_title)

        # 2. SQL Search (Try exact, then partial)
        cursor.execute("""
            SELECT * FROM movies 
            WHERE (LOWER(title) = LOWER(?) OR LOWER(title) LIKE LOWER(?))
            AND enriched = 1
            ORDER BY imdb_rating DESC, imdb_votes DESC
            LIMIT 1
        """, (target_title, f'%{target_title}%'))
        
        row = cursor.fetchone()
        
        # 3. Fuzzy Fallback: Search for normalized title
        if not row:
            # Check for title matches by removing all punctuation/spaces
            cursor.execute("SELECT * FROM movies WHERE enriched = 1")
            candidates = cursor.fetchall()
            for cand in candidates:
                cand_title = cand[1] # title column
                if norm_query in normalize_text(cand_title) or normalize_text(cand_title) in norm_query:
                    row = cand
                    break
        
        conn.close()
        
        if not row:
            return f"❌ Movie not found in database: {title}"
        
        # Unpack all columns
        (imdb_id, title, year, runtime, genres, imdb_rating, imdb_votes,
         rt_critics, rt_audience, rated, released, director, writer, actors,
         plot, language, country, awards, poster, box_office, enriched) = row
        
        # Format output
        result = f"""
🎬 **{title}** ({year})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 **RATINGS**
   • IMDB: {imdb_rating}/10 ({imdb_votes:,} votes)
   • Rotten Tomatoes (Critics): {rt_critics or 'N/A'}
   • Rotten Tomatoes (Audience): {rt_audience or 'N/A'}

📝 **DETAILS**
   • Rated: {rated or 'N/A'}
   • Runtime: {runtime} minutes
   • Released: {released or 'N/A'}
   • Genre: {genres or 'N/A'}

🎭 **CAST & CREW**
   • Director: {director or 'N/A'}
   • Writer: {writer or 'N/A'}
   • Actors: {actors or 'N/A'}

📖 **PLOT**
{plot or 'N/A'}

🌍 **OTHER INFO**
   • Language: {language or 'N/A'}
   • Country: {country or 'N/A'}
   • Awards: {awards or 'N/A'}
   • Box Office: {box_office or 'N/A'}

🔗 **LINKS**
   • IMDB: https://www.imdb.com/title/{imdb_id}/
   • Poster: {poster or 'N/A'}
"""
        return result.strip()
        
    except Exception as e:
        return f"❌ Database error: {str(e)}"


def search_movies_in_db(query: str, limit: int = 10) -> str:
    """
    Search for movies in database by title, genre, or keywords.
    
    Args:
        query: Search query
        limit: Maximum number of results
        
    Returns:
        List of matching movies
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # 1. Standard Search
        cursor.execute("""
            SELECT title, year, imdb_rating, genres, imdb_id, enriched
            FROM movies
            WHERE (LOWER(title) LIKE LOWER(?) OR LOWER(genres) LIKE LOWER(?))
            ORDER BY imdb_rating DESC, imdb_votes DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', limit))
        
        rows = cursor.fetchall()
        
        # 2. Fuzzy/Alias Fallback (if no results or few results)
        if len(rows) < 3:
            cursor.execute("SELECT title, year, imdb_rating, genres, imdb_id, enriched FROM movies WHERE enriched = 1")
            all_enriched = cursor.fetchall()
            norm_query = normalize_text(query)
            
            seen_titles = {r[0].lower() for r in rows}
            for candidate in all_enriched:
                if norm_query in normalize_text(candidate[0]) and candidate[0].lower() not in seen_titles:
                    rows.append(candidate)
                    if len(rows) >= limit: break

        conn.close()
        
        if not rows:
            return f"❌ No movies found matching: {query}"
        
        result = f"🔍 **Search Results for '{query}':**\n\n"
        for idx, (title, year, rating, genres, imdb_id, enriched) in enumerate(rows, 1):
            rating_display = f"{rating}/10" if rating else "N/A"
            result += f"{idx}. **{title}** ({year}) - {rating_display}\n"
            result += f"   Genre: {genres}\n"
            result += f"   IMDB: https://www.imdb.com/title/{imdb_id}/\n\n"
        
        return result.strip()
        
    except Exception as e:
        return f"❌ Database error: {str(e)}"


def get_top_movies(genre: Optional[str] = None, limit: int = 10) -> str:
    """
    Get top-rated movies, optionally filtered by genre.
    
    Args:
        genre: Optional genre filter (e.g., 'Action', 'Drama', 'Sci-Fi')
        limit: Number of movies to return
        
    Returns:
        List of top movies
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        if genre:
            cursor.execute("""
                SELECT title, year, imdb_rating, genres, imdb_id
                FROM movies
                WHERE LOWER(genres) LIKE LOWER(?)
                AND imdb_rating IS NOT NULL
                AND imdb_votes > 10000
                ORDER BY imdb_rating DESC, imdb_votes DESC
                LIMIT ?
            """, (f'%{genre}%', limit))
        else:
            cursor.execute("""
                SELECT title, year, imdb_rating, genres, imdb_id
                FROM movies
                WHERE imdb_rating IS NOT NULL
                AND imdb_votes > 50000
                ORDER BY imdb_rating DESC, imdb_votes DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"❌ No movies found"
        
        genre_text = f" {genre}" if genre else ""
        result = f"⭐ **Top{genre_text} Movies:**\n\n"
        for idx, (title, year, rating, genres, imdb_id) in enumerate(rows, 1):
            result += f"{idx}. **{title}** ({year}) - {rating}/10\n"
            result += f"   Genre: {genres}\n"
            result += f"   IMDB: https://www.imdb.com/title/{imdb_id}/\n\n"
        
        return result.strip()
        
    except Exception as e:
        return f"❌ Database error: {str(e)}"


# Add tools to agent
root_agent.tools = [get_movie_from_db, search_movies_in_db, get_top_movies]

# ============================
# Memory, Sessions, Runner (same as before)
# ============================

import asyncio
import os
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.genai.types import Content, Part

APP_NAME = "cineguide_app"
USER_ID = "local_user"

session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    memory_service=memory_service,
)

async def auto_save_to_memory(callback_context):
    await callback_context._invocation_context.memory_service.add_session_to_memory(
        callback_context._invocation_context.session
    )

root_agent.after_agent_callback = auto_save_to_memory

async def run_cli():
    print("=== CineGuide Agent CLI ===")
    print("Type your message (or 'quit' to exit)\n")
    
    session_id = "cli_session_001"
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id
    )
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        message = Content(parts=[Part(text=user_input)], role="user")
        
        print("\nAgent: ", end="", flush=True)
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=message
        ):
            if event.is_final_response() and event.content and event.content.parts:
                response_text = event.content.parts[0].text
                print(response_text)
                # Part 3: Real-time profile extraction
                if _PROFILE_BUILDER_AVAILABLE:
                    extract_and_update_from_chat(user_input, response_text)

if __name__ == "__main__":
    print("🎬 CineGuide Agent with Local Database!")
    print("\nRun: adk web")
    print("Then open: http://localhost:8000\n")
    
    # asyncio.run(run_cli())
