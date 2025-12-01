from google.adk.agents.llm_agent import Agent


root_agent = Agent(
    model='gemini-2.5-flash',
    name='root_agent',
    description='A movie recommendation assistant with access to a local IMDB and Rotten Tomatoes database.',
    instruction=(
        'You are a helpful movie recommendation assistant with access to a comprehensive local movie database. '
        'When users ask about specific movies or request recommendations, use the available tools to query the database. '
        'Always provide complete information including IMDB ratings, Rotten Tomatoes scores, cast, plot, and other details when available. '
        'If a user mentions a movie title, immediately use get_movie_from_db to fetch its details. '
        'Be conversational and helpful in your responses.'
    ),
)

# ============================
# Database Tools
# ============================

import sqlite3
from typing import List, Optional

DB_FILE = "movies.db"

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
        
        # Search for movie (case-insensitive, partial match)
        cursor.execute("""
            SELECT * FROM movies 
            WHERE LOWER(title) LIKE LOWER(?)
            AND enriched = 1
            ORDER BY imdb_rating DESC, imdb_votes DESC
            LIMIT 1
        """, (f'%{title}%',))
        
        row = cursor.fetchone()
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
        
        cursor.execute("""
            SELECT title, year, imdb_rating, genres, imdb_id
            FROM movies
            WHERE (LOWER(title) LIKE LOWER(?) OR LOWER(genres) LIKE LOWER(?))
            AND imdb_rating IS NOT NULL
            ORDER BY imdb_rating DESC, imdb_votes DESC
            LIMIT ?
        """, (f'%{query}%', f'%{query}%', limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f"❌ No movies found matching: {query}"
        
        result = f"🔍 **Search Results for '{query}':**\n\n"
        for idx, (title, year, rating, genres, imdb_id) in enumerate(rows, 1):
            result += f"{idx}. **{title}** ({year}) - {rating}/10\n"
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
                print(event.content.parts[0].text)

if __name__ == "__main__":
    print("🎬 CineGuide Agent with Local Database!")
    print("\nRun: adk web")
    print("Then open: http://localhost:8000\n")
    
    # asyncio.run(run_cli())
