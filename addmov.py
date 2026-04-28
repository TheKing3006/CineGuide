import sqlite3
import requests
import os
import sys
import re
from pathlib import Path

# Ensure UTF-8 for Windows console
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ============================
# Configuration & API Keys
# ============================

OMDB_API_KEY = "afa9c21d"
DB_FILE = "movies.db"

# Load TMDB_API_KEY from .env
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                if line.startswith("TMDB_API_KEY="):
                    TMDB_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break

# ============================
# Helper Functions
# ============================

def extract_imdb_id(text):
    """Extract ttXXXXX from a URL or string."""
    match = re.search(r'tt\d+', text)
    return match.group(0) if match else None

def fetch_tmdb_poster(imdb_id):
    """Fetch high-quality poster URL from TMDB."""
    if not TMDB_API_KEY:
        return None
    try:
        url = f"https://api.themoviedb.org/3/find/{imdb_id}"
        params = {'api_key': TMDB_API_KEY, 'external_source': 'imdb_id'}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('movie_results', [])
            if results:
                path = results[0].get('poster_path')
                if path:
                    return f"https://image.tmdb.org/t/p/w500{path}"
    except Exception as e:
        print(f"  ⚠️  TMDB Error for {imdb_id}: {e}")
    return None

def fetch_omdb_details(imdb_id):
    """Fetch full movie details from OMDB."""
    try:
        params = {
            'apikey': OMDB_API_KEY,
            'i': imdb_id,
            'plot': 'full',
            'r': 'json'
        }
        resp = requests.get("http://www.omdbapi.com/", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('Response') == 'True':
            return data
    except Exception as e:
        print(f"  ⚠️  OMDB Error for {imdb_id}: {e}")
    return None

def fetch_tmdb_details(imdb_id):
    """Fetch movie details from TMDB as a fallback."""
    if not TMDB_API_KEY:
        return None
    try:
        # First find TMDB ID from IMDb ID
        url = f"https://api.themoviedb.org/3/find/{imdb_id}"
        params = {'api_key': TMDB_API_KEY, 'external_source': 'imdb_id'}
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('movie_results', [])
            if results:
                tmdb_id = results[0].get('id')
                # Now fetch full details
                movie_url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
                resp2 = requests.get(movie_url, params={'api_key': TMDB_API_KEY}, timeout=10)
                if resp2.status_code == 200:
                    m = resp2.json()
                    # Convert TMDB format to a mock OMDB format for the adder
                    return {
                        'Title': m.get('title'),
                        'Year': m.get('release_date', '').split('-')[0],
                        'Genre': ', '.join([g['name'] for g in m.get('genres', [])]),
                        'Runtime': f"{m.get('runtime')} min",
                        'imdbRating': str(m.get('vote_average')),
                        'imdbVotes': str(m.get('vote_count')),
                        'Plot': m.get('overview'),
                        'Director': 'N/A', # TMDB needs separate call for credits
                        'Actors': 'N/A',
                        'Language': m.get('original_language'),
                        'Country': 'N/A',
                        'Response': 'True'
                    }
    except Exception as e:
        print(f"  ⚠️  TMDB Detail Error for {imdb_id}: {e}")
    return None

def add_movie_by_id(imdb_id):
    """Enrich and add movie to database."""
    print(f"\n🔍 Processing IMDb ID: {imdb_id}...")
    
    # 1. Fetch details from OMDB
    data = fetch_omdb_details(imdb_id)
    
    # 2. Fallback to TMDB if OMDB fails
    if not data:
        print(f"  ⚠️  OMDB enrichment failed. Trying TMDB fallback...")
        data = fetch_tmdb_details(imdb_id)
        
    if not data:
        print(f"❌ Could not find movie details for {imdb_id}")
        return
    
    title = data.get('Title')
    year = data.get('Year')
    print(f"🎬 Found: {title} ({year})")
    
    # 3. Fetch poster from TMDB (already handled in fallback if data came from TMDB)
    poster_url = data.get('Poster') if 'Poster' in data and data['Poster'].startswith('http') else None
    if not poster_url:
        print(f"🖼️  Fetching poster from TMDB...")
        poster_url = fetch_tmdb_poster(imdb_id)
    
    # 4. Extract RT Scores
    rt_critics = None
    rt_audience = None
    for rating in data.get('Ratings', []):
        source = rating.get('Source', '')
        if source == 'Rotten Tomatoes':
            rt_critics = rating.get('Value')
        elif 'Audience' in source:
            rt_audience = rating.get('Value')
            
    # 5. Prepare fields
    # Parse numbers
    try:
        rating_str = str(data.get('imdbRating', '0'))
        clean_rating = float(rating_str) if rating_str != 'N/A' else None
    except: clean_rating = None
    
    try:
        votes_str = str(data.get('imdbVotes', '0')).replace(',', '')
        clean_votes = int(votes_str) if votes_str != 'N/A' else 0
    except: clean_votes = 0
    
    try:
        runtime_str = str(data.get('Runtime', '0')).split(' ')[0]
        clean_runtime = int(runtime_str) if runtime_str != 'N/A' else None
    except: clean_runtime = None
    
    try:
        year_str = str(data.get('Year', '0'))
        clean_year = int(re.search(r'\d{4}', year_str).group()) if year_str else None
    except: clean_year = None

    # 6. Save to Database
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO movies (
                imdb_id, title, year, runtime_minutes, genres,
                imdb_rating, imdb_votes, rt_critics_score, rt_audience_score,
                rated, released, director, writer, actors, plot,
                language, country, awards, poster, box_office, enriched
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            imdb_id,
            title,
            clean_year,
            clean_runtime,
            data.get('Genre'),
            clean_rating,
            clean_votes,
            rt_critics,
            rt_audience,
            data.get('Rated'),
            data.get('Released'),
            data.get('Director'),
            data.get('Writer'),
            data.get('Actors'),
            data.get('Plot'),
            data.get('Language'),
            data.get('Country'),
            data.get('Awards'),
            poster_url,
            data.get('BoxOffice'),
            1 # Enriched!
        ))
        conn.commit()
        conn.close()
        print(f"✅ Successfully added/updated: {title}")
        if poster_url:
            print(f"   🖼️ Poster URL: {poster_url}")
    except Exception as e:
        print(f"❌ Database error: {e}")

# ============================
# Main Execution
# ============================

def main():
    print("=" * 50)
    print("🎬 CINEGUIDE MOVIE ADDER (Manual Entry)")
    print("=" * 50)
    print("Paste an IMDb link (e.g., https://www.imdb.com/title/tt1234567/)")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("IMDb Link or ID: ").strip()
        
        if user_input.lower() in {'exit', 'quit', 'q'}:
            break
            
        imdb_id = extract_imdb_id(user_input)
        if not imdb_id:
            print("⚠️  Invalid input. Please provide a valid IMDb URL or tt-id.")
            continue
            
        add_movie_by_id(imdb_id)
        print("\n" + "-" * 30)

if __name__ == "__main__":
    # If arguments are passed (for automated testing)
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            imdb_id = extract_imdb_id(arg)
            if imdb_id:
                add_movie_by_id(imdb_id)
    else:
        main()
