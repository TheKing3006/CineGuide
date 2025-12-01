"""
build_movie_database.py
Downloads IMDB data and enriches it with OMDb API to create a local movie database.
Run this ONCE to build your database, then the agent queries it locally.
"""

import os
import sqlite3
import requests
import gzip
import shutil
import time
from pathlib import Path
import csv

# ============================
# Configuration
# ============================

OMDB_API_KEY = "dd21cf1d"  # Your OMDb API key
DB_FILE = "movies.db"

# IMDB official dataset URLs (updated daily)
IMDB_TITLE_BASICS_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"
IMDB_RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"

# We'll fetch top N movies to enrich with OMDb (to stay within API limits)
TOP_N_MOVIES = 1000  # Adjust based on your API key limits

# ============================
# Database Schema
# ============================

def create_database():
    """Create SQLite database with movie tables."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Main movies table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            imdb_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            year INTEGER,
            runtime_minutes INTEGER,
            genres TEXT,
            imdb_rating REAL,
            imdb_votes INTEGER,
            rt_critics_score TEXT,
            rt_audience_score TEXT,
            rated TEXT,
            released TEXT,
            director TEXT,
            writer TEXT,
            actors TEXT,
            plot TEXT,
            language TEXT,
            country TEXT,
            awards TEXT,
            poster TEXT,
            box_office TEXT,
            enriched INTEGER DEFAULT 0
        )
    """)
    
    # Create indexes for fast lookups
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_title ON movies(title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_year ON movies(year)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rating ON movies(imdb_rating)")
    
    conn.commit()
    conn.close()
    print("✅ Database created successfully")

# ============================
# Download and Load IMDB Data
# ============================

def download_file(url, filename):
    """Download gzipped file from IMDB."""
    print(f"📥 Downloading {filename}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"✅ Downloaded {filename}")

def extract_gz(gz_file, output_file):
    """Extract gzipped file."""
    print(f"📂 Extracting {gz_file}...")
    with gzip.open(gz_file, 'rb') as f_in:
        with open(output_file, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"✅ Extracted to {output_file}")

def load_imdb_basics(tsv_file):
    """Load basic movie info from IMDB TSV."""
    print("📊 Loading IMDB basics data into database...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    count = 0
    with open(tsv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            # Only movies (not TV shows, episodes, etc.)
            if row['titleType'] != 'movie':
                continue
            
            # Skip adult content
            if row['isAdult'] == '1':
                continue
            
            imdb_id = row['tconst']
            title = row['primaryTitle']
            year = row['startYear'] if row['startYear'] != '\\N' else None
            runtime = row['runtimeMinutes'] if row['runtimeMinutes'] != '\\N' else None
            genres = row['genres'] if row['genres'] != '\\N' else None
            
            cursor.execute("""
                INSERT OR IGNORE INTO movies (imdb_id, title, year, runtime_minutes, genres)
                VALUES (?, ?, ?, ?, ?)
            """, (imdb_id, title, year, runtime, genres))
            
            count += 1
            if count % 10000 == 0:
                print(f"  Processed {count} movies...")
    
    conn.commit()
    conn.close()
    print(f"✅ Loaded {count} movies from IMDB basics")

def load_imdb_ratings(tsv_file):
    """Load ratings from IMDB TSV."""
    print("⭐ Loading IMDB ratings data...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    count = 0
    with open(tsv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        
        for row in reader:
            imdb_id = row['tconst']
            rating = float(row['averageRating']) if row['averageRating'] != '\\N' else None
            votes = int(row['numVotes']) if row['numVotes'] != '\\N' else None
            
            cursor.execute("""
                UPDATE movies 
                SET imdb_rating = ?, imdb_votes = ?
                WHERE imdb_id = ?
            """, (rating, votes, imdb_id))
            
            count += 1
            if count % 10000 == 0:
                print(f"  Updated {count} ratings...")
    
    conn.commit()
    conn.close()
    print(f"✅ Updated ratings for {count} movies")

# ============================
# Enrich with OMDb API
# ============================

def enrich_top_movies():
    """Enrich top-rated movies with detailed OMDb data."""
    print(f"🎬 Enriching top {TOP_N_MOVIES} movies with OMDb data...")
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get top movies by rating (with sufficient votes)
    cursor.execute("""
        SELECT imdb_id, title 
        FROM movies 
        WHERE imdb_rating IS NOT NULL 
        AND imdb_votes > 10000
        AND enriched = 0
        ORDER BY imdb_rating DESC, imdb_votes DESC
        LIMIT ?
    """, (TOP_N_MOVIES,))
    
    movies = cursor.fetchall()
    
    for idx, (imdb_id, title) in enumerate(movies, 1):
        print(f"  [{idx}/{len(movies)}] Enriching: {title}")
        
        try:
            # Call OMDb API
            params = {
                'apikey': OMDB_API_KEY,
                'i': imdb_id,  # Search by IMDB ID (more accurate)
                'plot': 'full',
                'r': 'json'
            }
            
            response = requests.get("http://www.omdbapi.com/", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('Response') == 'True':
                # Extract Rotten Tomatoes scores
                ratings = data.get('Ratings', [])
                rt_critics = None
                rt_audience = None
                
                for rating in ratings:
                    source = rating.get('Source', '')
                    if source == 'Rotten Tomatoes':
                        rt_critics = rating.get('Value')
                    elif 'Audience' in source:
                        rt_audience = rating.get('Value')
                
                # Update database with enriched data
                cursor.execute("""
                    UPDATE movies SET
                        rated = ?,
                        released = ?,
                        director = ?,
                        writer = ?,
                        actors = ?,
                        plot = ?,
                        language = ?,
                        country = ?,
                        awards = ?,
                        poster = ?,
                        box_office = ?,
                        rt_critics_score = ?,
                        rt_audience_score = ?,
                        enriched = 1
                    WHERE imdb_id = ?
                """, (
                    data.get('Rated'),
                    data.get('Released'),
                    data.get('Director'),
                    data.get('Writer'),
                    data.get('Actors'),
                    data.get('Plot'),
                    data.get('Language'),
                    data.get('Country'),
                    data.get('Awards'),
                    data.get('BoxOffice'),
                    rt_critics,
                    rt_audience,
                    imdb_id
                ))
                
                conn.commit()
            
            # Rate limiting (free tier: 1000/day)
            time.sleep(1)  # 1 second between requests
            
        except Exception as e:
            print(f"    ⚠️  Error enriching {title}: {e}")
            continue
    
    conn.close()
    print(f"✅ Enriched {len(movies)} movies with OMDb data")

# ============================
# Main Execution
# ============================

def main():
    """Build the complete movie database."""
    print("=" * 50)
    print("CINEGUIDE MOVIE DATABASE BUILDER")
    print("=" * 50)
    
    # Step 1: Create database
    create_database()
    
    # Step 2: Download IMDB datasets
    basics_gz = "title.basics.tsv.gz"
    ratings_gz = "title.ratings.tsv.gz"
    basics_tsv = "title.basics.tsv"
    ratings_tsv = "title.ratings.tsv"
    
    if not Path(basics_tsv).exists():
        download_file(IMDB_TITLE_BASICS_URL, basics_gz)
        extract_gz(basics_gz, basics_tsv)
    else:
        print(f"ℹ️  {basics_tsv} already exists, skipping download")
    
    if not Path(ratings_tsv).exists():
        download_file(IMDB_RATINGS_URL, ratings_gz)
        extract_gz(ratings_gz, ratings_tsv)
    else:
        print(f"ℹ️  {ratings_tsv} already exists, skipping download")
    
    # Step 3: Load IMDB data
    load_imdb_basics(basics_tsv)
    load_imdb_ratings(ratings_tsv)
    
    # Step 4: Enrich with OMDb
    enrich_top_movies()
    
    print("\n" + "=" * 50)
    print("✅ DATABASE BUILD COMPLETE!")
    print(f"📁 Database file: {DB_FILE}")
    print("=" * 50)

if __name__ == "__main__":
    main()
