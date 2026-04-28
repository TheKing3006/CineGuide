"""
profile_builder.py — CineGuide User Personalization Module

Handles user profile management, saving/loading, and real-time preference
extraction from chat messages.
"""

import json
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, List

# ============================
# Constants & File Paths
# ============================

PROFILE_FILE = "user_profile.json"
DB_FILE = "movies.db"

# ============================
# Knowledge Base (Mappings)
# ============================

GENRE_ALIASES = {
    'romantic': 'romance', 'romcom': 'romance', 'rom-com': 'romance',
    'scary': 'horror', 'frightening': 'horror', 'funny': 'comedy',
    'hilarious': 'comedy', 'scifi': 'sci-fi', 'science fiction': 'sci-fi',
    'superhero': 'action', 'spy': 'thriller', 'suspense': 'thriller',
    'cartoon': 'animation', 'animated': 'animation',
}

LANGUAGE_ALIASES = {
    'hindi': 'Hindi', 'english': 'English', 'spanish': 'Spanish',
    'french': 'French', 'german': 'German', 'italian': 'Italian',
    'japanese': 'Japanese', 'korean': 'Korean', 'chinese': 'Chinese',
    'tamil': 'Tamil', 'telugu': 'Telugu', 'malayalam': 'Malayalam',
    'bengali': 'Bengali',
}

MOVIE_ACRONYMS = {
    'ddlj': 'Dilwale Dulhania Le Jayenge', 'k3g': 'Kabhi Khushi Kabhie Gham',
    'znmd': 'Zindagi Na Milegi Dobara', 'yjhd': 'Yeh Jawaani Hai Deewani',
    'adhm': 'Ae Dil Hai Mushkil', 'khnh': 'Kal Ho Naa Ho',
    'kkhh': 'Kuch Kuch Hota Hai', 'hahk': 'Hum Aapke Hain Koun',
    'dlkh': 'Dum Laga Ke Haisha', 'got': 'Game of Thrones',
    'gotg': 'Guardians of the Galaxy', 'lotr': 'The Lord of the Rings',
    'rotk': 'The Return of the King', 'fotr': 'The Fellowship of the Ring',
    'ttt': 'The Two Towers', 'hp': 'Harry Potter',
    'sw': 'Star Wars', 'esb': 'The Empire Strikes Back',
    'rotj': 'Return of the Jedi', 'tpm': 'The Phantom Menace',
    'aotc': 'Attack of the Clones', 'rots': 'Revenge of the Sith',
    'tfa': 'The Force Awakens', 'tlj': 'The Last Jedi',
    'tros': 'The Rise of Skywalker', 'mcu': 'Marvel Cinematic Universe',
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
    'star wars 1': 'The Phantom Menace', 'star wars 2': 'Attack of The Clones',
    'star wars 3': 'Revenge of the Sith', 'star wars 4': 'A New Hope',
    'star wars 5': 'The Empire Strikes Back', 'star wars 6': 'Return of the Jedi',
    'star wars 7': 'The Force Awakens', 'star wars 8': 'The Last Jedi',
    'star wars 9': 'The Rise of Skywalker',
    'avengers 1': 'The Avengers', 'avengers 2': 'Avengers: Age of Ultron',
    'avengers 3': 'Avengers: Infinity War', 'avengers 4': 'Avengers: Endgame',
    'avengers 5': 'Avengers: Doomsday', 'avengers 6': 'Avengers: Secret Wars',
    'dhurandhar 2': 'Dhurandhar: The Revenge',
    'lotr 1': 'The Fellowship of the Ring', 'lotr 2': 'The Two Towers',
    'lotr 3': 'The Return of the King',
    'fast and furious 1': 'The Fast and the Furious', 'fast and furious 2': '2 Fast 2 Furious',
    'fast and furious 3': 'Tokyo Drift', 'fast and furious 4': 'Fast & Furious',
    'fast and furious 5': 'Fast Five', 'fast and furious 6': 'Fast & Furious 6',
    'fast and furious 7': 'Furious 7', 'fast and furious 8': 'The Fate of the Furious',
    'fast and furious 9': 'F9', 'fast and furious 10': 'Fast X',
    'mission impossible 1': 'Mission: Impossible', 'mission impossible 2': 'Mission: Impossible II',
    'mission impossible 3': 'Mission: Impossible III', 'mission impossible 4': 'Ghost Protocol',
    'mission impossible 5': 'Rogue Nation', 'mission impossible 6': 'Fallout',
    'mission impossible 7': 'Dead Reckoning Part One', 'mission impossible 8': 'The Final Reckoning',
    'toy story 1': 'Toy Story', 'toy story 2': 'Toy Story 2',
    'toy story 3': 'Toy Story 3', 'toy story 4': 'Toy Story 4',
    'godfather 1': 'The Godfather', 'godfather 2': 'The Godfather Part II',
    'godfather 3': 'The Godfather Part III',
    'iron man 1': 'Iron Man', 'iron man 2': 'Iron Man 2', 'iron_man_3': 'Iron Man 3',
}

FRANCHISE_MAP = {
    "mcu": ["Iron Man", "The Incredible Hulk", "Iron Man 2", "Thor", "Captain America: The First Avenger", "Marvel's The Avengers", "Iron Man 3", "Thor: The Dark World", "Captain America: The Winter Soldier", "Guardians of the Galaxy", "Avengers: Age of Ultron", "Ant-Man", "Captain America: Civil War", "Doctor Strange", "Guardians of the Galaxy Vol. 2", "Spider-Man: Homecoming", "Thor: Ragnarok", "Avengers: Infinity War", "Ant-Man and the Wasp", "Captain Marvel", "Avengers: Endgame", "Spider-Man: Far From Home", "Black Widow", "Shang-Chi and the Legend of the Ten Rings", "Eternals", "Spider-Man: No Way Home", "Doctor Strange in the Multiverse of Madness", "Thor: Love and Thunder", "Black Panther: Wakanda Forever", "Ant-Man and the Wasp: Quantumania", "Guardians of the Galaxy Vol. 3", "The Marvels", "Deadpool & Wolverine"],
    "dceu": ["Man of Steel", "Batman v Superman: Dawn of Justice", "Suicide Squad", "Wonder Woman", "Justice League", "Aquaman", "Shazam!", "Birds of Prey", "Wonder Woman 1984", "The Suicide Squad", "Black Adam", "Shazam! Fury of the Gods", "The Flash", "Aquaman and the Lost Kingdom", "Joker"],
    "star wars": ["Star Wars", "The Empire Strikes Back", "Return of the Jedi", "The Phantom Menace", "Attack of the Clones", "Revenge of the Sith", "The Force Awakens", "Rogue One: A Star Wars Story", "The Last Jedi", "Solo: A Star Wars Story", "The Rise of Skywalker"],
    "harry potter": ["Harry Potter and the Sorcerer's Stone", "Harry Potter and the Chamber of Secrets", "Harry Potter and the Prisoner of Azkaban", "Harry Potter and the Goblet of Fire", "Harry Potter and the Order of the Phoenix", "Harry Potter and the Half-Blood Prince", "Harry Potter and the Deathly Hallows: Part 1", "Harry Potter and the Deathly Hallows: Part 2"],
    "lotr": ["The Lord of the Rings: The Fellowship of the Ring", "The Lord of the Rings: The Two Towers", "The Lord of the Rings: The Return of the King"],
    "dark knight": ["Batman Begins", "The Dark Knight", "The Dark Knight Rises"],
    "john wick": ["John Wick", "John Wick: Chapter 2", "John Wick: Chapter 3 - Parabellum", "John Wick: Chapter 4"],
    "mission impossible": ["Mission: Impossible", "Mission: Impossible 2", "Mission: Impossible III", "Mission: Impossible - Ghost Protocol", "Mission: Impossible - Rogue Nation", "Mission: Impossible - Fallout", "Mission: Impossible – Dead Reckoning Part One", "Mission: Impossible – The Final Reckoning"],
    "fast and furious": ["The Fast and the Furious", "2 Fast 2 Furious", "Fast & Furious", "Fast Five", "Fast & Furious 6", "Furious 7", "The Fate of the Furious", "F9", "Fast X"],
    "toy story": ["Toy Story", "Toy Story 2", "Toy Story 3", "Toy Story 4"],
    "godfather": ["The Godfather", "The Godfather Part II", "The Godfather Part III"],
    "dhoom": ["Dhoom", "Dhoom:2", "Dhoom 3"],
    "golmaal": ["Golmaal: Fun Unlimited", "Golmaal Returns", "Golmaal 3", "Golmaal Again"],
    "krish": ["Koi... Mil Gaya", "Krish", "Krish 3"],
    "don": ["Don", "Don 2"],
}
FRANCHISE_MAP["marvel"] = FRANCHISE_MAP["mcu"]
FRANCHISE_MAP["sw"] = FRANCHISE_MAP["star wars"]
FRANCHISE_MAP["hp"] = FRANCHISE_MAP["harry potter"]

# ============================
# Extraction Patterns
# ============================

LIKED_TRIGGERS = [
    r"i loved him in (.+)", r"i loved her in (.+)", r"i loved them in (.+)",
    r"loved him in (.+)", r"loved her in (.+)",
    r"i liked him in (.+)", r"i liked her in (.+)",
    r"he was great in (.+)", r"she was great in (.+)",
    r"he was fantastic in (.+)", r"she was fantastic in (.+)",
    r"he was brilliant in (.+)", r"she was brilliant in (.+)",
    r"his best film is (.+)", r"her best film is (.+)",
    r"his best movie is (.+)", r"her best movie is (.+)",
    r"watched (.+) because of him", r"watched (.+) because of her",
    r"i loved (.+)", r"yes i loved (.+)", r"i really loved (.+)",
    r"i really liked (.+)", r"i really enjoyed (.+)",
    r"absolutely loved (.+)", r"i absolutely loved (.+)",
    r"i liked (.+)", r"i enjoyed (.+)", r"i recommend (.+)",
    r"you should watch (.+)", r"one of my favorites is (.+)",
    r"one of my favourites is (.+)", r"my favorite movie is (.+)",
    r"my favourite movie is (.+)", r"have you seen (.+)",
    r"i've seen (.+)", r"i have seen (.+)"
]

DISLIKED_TRIGGERS = [
    r"i hated (.+)", r"i didn't like (.+)", r"i didnt like (.+)",
    r"i don't like (.+)", r"i dont like (.+)", r"it was terrible (.+)",
    r"it was awful (.+)", r"don't watch (.+)", r"dont watch (.+)",
    r"i was(?:n't|nt| not) a fan of (.+)"
]

ACTOR_TRIGGERS = [
    r"huge fan of ([a-z\s]+)", r"big fan of ([a-z\s]+)",
    r"i love ([a-z\s]+)", r"i like ([a-z\s]+)",
    r"favourite actor is ([a-z\s]+)", r"favorite actor is ([a-z\s]+)",
]

AFFIRMATIONS = [
    "yes", "yeah", "yep", "oh yes", "absolutely", "definitely", "sure", "of course"
]

# ============================
# Helper Functions
# ============================

def expand_query(query: str) -> Tuple[str, Optional[int]]:
    """Expand acronyms and franchise numbers."""
    query_lower = query.lower().strip()

    SPECIAL_CASES = {
        'ddlj': ('Dilwale Dulhania Le Jayenge', 1995),
        '3 idiots': ('3 Idiots', 2009),
        'dilwale dulhaniya le jayenge': ('Dilwale Dulhania Le Jayenge', 1995),
        'avengers doomsday': ('Avengers: Doomsday', 2026),
        'avengers 5': ('Avengers: Doomsday', 2026),
        'dhurandhar 2': ('Dhurandhar: The Revenge', 2026),
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
        return (subtitle, None)

    if query_lower in MOVIE_ACRONYMS:
        return (MOVIE_ACRONYMS[query_lower], None)

    return (query, None)

def detect_franchise(user_message: str) -> Optional[str]:
    """Detects franchise keywords in message."""
    msg = user_message.lower().strip().replace("’", "'").replace("`", "'")
    phrases = [
        "fan of all the {f}", "love all the {f}", "huge fan of {f}",
        "huge fan of the {f}", "big fan of {f}", "i love {f}",
        "i like {f}", "all the {f} movies", "every {f} movie", "all {f} movies"
    ]
    for k in FRANCHISE_MAP:
        for p in phrases:
            if p.format(f=k) in msg:
                return k
    return None

def _empty_profile() -> dict:
    return {
        "liked_movies": [], "disliked_movies": [],
        "preferred_genres": {}, "avoided_genres": {},
        "preferred_languages": {}, "preferred_directors": [],
        "preferred_actors": [], "inferred_mood_tags": [],
        "last_updated": None,
    }

def save_profile(profile_data: dict, profile_path: str = PROFILE_FILE) -> None:
    """Centralized atomic write."""
    try:
        profile_data["last_updated"] = datetime.now().isoformat(timespec="seconds")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[profile_builder] Error saving profile: {e}")

def load_profile(profile_path: str = PROFILE_FILE) -> dict:
    """Centralized read."""
    try:
        p = Path(profile_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[profile_builder] Error loading profile: {e}")
    return _empty_profile()

def lookup_movie_in_db(title: str, db_path: str = DB_FILE) -> Optional[dict]:
    """Fetch movie data from DB."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT title, year, genres, imdb_rating, director, actors FROM movies "
            "WHERE LOWER(title) = LOWER(?) ORDER BY COALESCE(imdb_votes, 0) DESC LIMIT 1",
            (title,)
        )
        res = cursor.fetchone()
        conn.close()
        if res:
            return {
                "title": res[0], "year": res[1], "genre": res[2],
                "rating": res[3], "director": res[4], "actors": res[5]
            }
    except: pass
    return None

# ============================
# Pipeline Components
# ============================

def extract_and_update_from_chat(user_message: str, ai_response: str = "",
                                 profile_path: str = PROFILE_FILE,
                                 db_path: str = DB_FILE) -> None:
    """Locked Atomic Pipeline: Resolve -> Validate -> Save."""
    added = extract_franchise_from_message(user_message)

    msg = user_message.lower().strip().replace("’", "'").replace("`", "'")
    for aff in AFFIRMATIONS:
        if msg.startswith(aff + " "):
            msg = msg[len(aff):].strip()
            break

    profile = load_profile(profile_path)
    changed = False

    def process_match(candidate, is_like):
        nonlocal changed
        resolved, _ = expand_query(candidate)
        m = lookup_movie_in_db(resolved, db_path)
        if m:
            key = "liked_movies" if is_like else "disliked_movies"
            if any(x["title"].lower() == m["title"].lower() for x in profile[key]):
                return

            entry = {
                "title": m["title"], "year": m["year"], "genre": m["genre"],
                "rating": m["rating"], "added_at": datetime.now().isoformat()
            }
            profile[key].append(entry)
            if is_like:
                for g in (m["genre"] or "").split(","):
                    g = g.strip().lower()
                    can = GENRE_ALIASES.get(g, g)
                    profile["preferred_genres"][can] = profile["preferred_genres"].get(can, 0) + 1
                if m["director"] and m["director"] not in profile["preferred_directors"]:
                    profile["preferred_directors"].append(m["director"])
            changed = True

    for p in LIKED_TRIGGERS:
        match = re.search(p, msg)
        if match: process_match(match.group(1).strip(".,!? "), True)

    for p in DISLIKED_TRIGGERS:
        match = re.search(p, msg)
        if match: process_match(match.group(1).strip(".,!? "), False)

    for p in ACTOR_TRIGGERS:
        match = re.search(p, msg)
        if match:
            name = match.group(1).strip().title()
            if not any(re.search(lp, msg) for lp in LIKED_TRIGGERS):
                if name not in profile["preferred_actors"]:
                    m_data = lookup_movie_in_db(name)
                    if not m_data:
                        conn = sqlite3.connect(db_path)
                        if conn.execute("SELECT 1 FROM movies WHERE actors LIKE ? LIMIT 1", (f"%{name}%",)).fetchone():
                            profile["preferred_actors"].append(name)
                            changed = True
                        conn.close()

    if changed:
        save_profile(profile, profile_path)

def extract_franchise_from_message(user_message: str) -> int:
    key = detect_franchise(user_message)
    if not key: return 0
    profile = load_profile()
    added = 0
    existing = {m["title"].lower() for m in profile["liked_movies"]}
    for title in FRANCHISE_MAP[key]:
        if title.lower() not in existing:
            m = lookup_movie_in_db(title)
            if m:
                profile["liked_movies"].append({
                    "title": m["title"], "year": m["year"], "genre": m["genre"],
                    "rating": m["rating"], "added_at": datetime.now().isoformat()
                })
                added += 1
    if added > 0: save_profile(profile)
    return added

# ============================
# Recommendation Engine — Slot-Based Allocation
# ============================

import random as _random


def get_personalized_picks(n: int = 5, profile_path: str = PROFILE_FILE,
                           db_path: str = DB_FILE) -> list:
    """
    NEW ARCHITECTURE — SLOT-BASED ALLOCATION
    
    1. Actor-based picks:     2 slots
    2. Genre-based picks:     2 slots
    3. Wildcard/quality pick: 1 slot
    """
    profile = load_profile(profile_path)
    pref_actors_raw = profile.get("preferred_actors", [])
    pref_genres = profile.get("preferred_genres", {})
    liked = {m["title"].lower() for m in profile["liked_movies"]}
    disliked = {m["title"].lower() for m in profile["disliked_movies"]}
    seen_this_refresh = set()
    final_picks = []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    def score_movie_internal(row, bonus_actor=None, bonus_genre=None):
        """Scoring weights as per user spec (unchanged)."""
        score = 0
        genres_str = row["genres"] or ""
        actors_str = row["actors"] or ""
        director_str = row["director"] or ""
        gs = [g.strip().lower() for g in genres_str.split(",")]
        cast_lower = [a.strip().lower() for a in actors_str.split(",")]
        rating = row["imdb_rating"] or 0
        votes = row["imdb_votes"] or 0
        year = row["year"] or 2000

        # Taste match (max 40 pts)
        pref_directors = [d.lower() for d in (profile.get("preferred_directors") or [])]
        if bonus_genre and any(bonus_genre.lower() in g for g in gs):
            score += 40
        elif gs and gs[0] in pref_genres:
            score += 25
        elif any(g in pref_genres for g in gs):
            score += 15

        if director_str:
            dirs_lower = [d.strip().lower() for d in director_str.split(",")]
            if any(d in pref_directors for d in dirs_lower):
                score += 15 # Updated from 10 to match 'director +15' spec

        # Actor bonus
        if bonus_actor and bonus_actor.lower() in cast_lower:
            score += 20
        elif cast_lower and any(a.lower() in cast_lower for a in pref_actors_raw):
            score += 10 # lead bonus

        # Popularity (max 35 pts)
        score += min(votes // 200000, 35)

        # Quality (max 15 pts)
        score += min(int((rating - 6.8) * 5), 15)

        # Recency (max 10 pts)
        if year >= 2010:
            score += min((year - 2010) * 0.8, 10)

        # Penalties
        if (row["title"] or "").lower() in disliked:
            score -= 50

        return score

    def build_candidate_pool(sql, params, bonus_actor=None, bonus_genre=None, limit=20):
        c.execute(sql, params)
        rows = c.fetchall()
        pool = []
        for row in rows:
            tl = (row["title"] or "").lower()
            if tl in liked or tl in disliked or tl in seen_this_refresh:
                continue
            
            score = score_movie_internal(row, bonus_actor, bonus_genre)
            pool.append({
                "title": row["title"],
                "year": row["year"],
                "genres": row["genres"] or "",
                "imdb_rating": row["imdb_rating"],
                "director": row["director"],
                "poster": row["poster"] if "poster" in row.keys() else None,
                "score": score
            })
        
        pool.sort(key=lambda x: x["score"], reverse=True)
        return pool[:limit]

    def sample_from_pool(pool, top_n=10, has_poster_priority=False):
        if not pool: return None
        
        # Poster Constraint: if we need a poster, scan the WHOLE pool for them
        if has_poster_priority:
            with_poster = [c for c in pool if c.get("poster")]
            if with_poster:
                # Still take from the relatively high-scoring ones with posters
                candidates = with_poster[:min(top_n, len(with_poster))]
                return _random.choice(candidates)
        
        # Standard top-N random sampling
        candidates = pool[:min(top_n, len(pool))]
        return _random.choice(candidates)

    # ── Fallback Chain: Empty Profile ───────────────────────────────────
    if not pref_actors_raw and not pref_genres:
        wildcard_sql = """
            SELECT * FROM movies 
            WHERE imdb_rating >= 7.5 AND imdb_votes >= 100000 
            ORDER BY (imdb_rating * imdb_votes / 1000000.0) DESC LIMIT 100
        """
        pool = build_candidate_pool(wildcard_sql, (), limit=100)
        _random.shuffle(pool)
        for p in pool[:50]:
            if len(final_picks) >= 5: break
            p["reason"] = f"Highly rated • {(p['genres'] or '').split(',')[0]}"
            final_picks.append(p)
            seen_this_refresh.add(p["title"].lower())
        conn.close()
        return final_picks

    # ── SLOTS 1 & 2: Actor-Based ────────────────────────────────────────
    actors_to_use = list(pref_actors_raw)
    _random.shuffle(actors_to_use)
    
    actor_slots_needed = 2
    if not pref_actors_raw:
        actor_slots_needed = 0
    elif len(pref_actors_raw) == 1:
        actor_slots_needed = 1

    for i in range(actor_slots_needed):
        actor = actors_to_use[i]
        no_poster_count = sum(1 for p in final_picks if not p.get("poster"))
        # Relaxed for upcoming movies
        sql_base = """
            SELECT * FROM movies 
            WHERE actors LIKE ? 
            AND ( (imdb_rating >= 4.0 AND imdb_votes >= 100) OR (year >= 2025) )
        """
        
        # 1. Try finding a poster-enriched movie first
        pool = build_candidate_pool(sql_base + " AND poster IS NOT NULL LIMIT 400", (f"%{actor}%",), bonus_actor=actor, limit=400)
        
        # 2. If no poster found, and we haven't used our non-poster allowance, take anything
        if not pool and no_poster_count == 0:
            pool = build_candidate_pool(sql_base + " LIMIT 400", (f"%{actor}%",), bonus_actor=actor, limit=400)
            
        pick = sample_from_pool(pool, top_n=30, has_poster_priority=(no_poster_count >= 1))
        
        if pick:
            g_main = (pick["genres"] or "").split(",")[0]
            pick["reason"] = f"Stars {actor} • Matches your {g_main} taste"
            final_picks.append(pick)
            seen_this_refresh.add(pick["title"].lower())

    # ── SLOTS 3 & 4: Genre-Based ────────────────────────────────────────
    genres_needed = 4 - len(final_picks)
    if genres_needed > 0 and pref_genres:
        genre_items = sorted(pref_genres.items(), key=lambda x: x[1], reverse=True)
        genres_available = [g for g, _ in genre_items]
        genre_weights = [max(s, 1) for _, s in genre_items]
        
        selected_genres = []
        while len(selected_genres) < genres_needed and genres_available:
            g = _random.choices(genres_available, weights=genre_weights, k=1)[0]
            if g not in selected_genres:
                selected_genres.append(g)
            elif len(genres_available) == 1: 
                selected_genres.append(g)
                break
            else:
                continue

        for g in selected_genres:
            no_poster_count = sum(1 for p in final_picks if not p.get("poster"))
            # Relaxed for upcoming
            sql_base = """
                SELECT * FROM movies 
                WHERE genres LIKE ? 
                AND ( (imdb_rating >= 5.5 AND imdb_votes >= 500) OR (year >= 2025) )
            """
            
            # 1. Try finding a poster-enriched movie first
            pool = build_candidate_pool(sql_base + " AND poster IS NOT NULL LIMIT 400", (f"%{g}%",), bonus_genre=g, limit=400)
            
            # 2. If no poster found, and we haven't used our non-poster allowance, take anything
            if not pool and no_poster_count == 0:
                pool = build_candidate_pool(sql_base + " LIMIT 400", (f"%{g}%",), bonus_genre=g, limit=400)
            
            # 3. If STILL no pool (allowance used and no posters found), broaden the search to ANY poster movie in this genre
            if not pool:
                pool = build_candidate_pool("SELECT * FROM movies WHERE genres LIKE ? AND poster IS NOT NULL LIMIT 200", (f"%{g}%",), bonus_genre=g, limit=200)

            pick = sample_from_pool(pool, top_n=20, has_poster_priority=(no_poster_count >= 1))
            
            if pick:
                pick["reason"] = f"Matches your taste for {g.title()}"
                final_picks.append(pick)
                seen_this_refresh.add(pick["title"].lower())

    # ── SLOT 5: Wildcard ────────────────────────────────────────────────
    if len(final_picks) < 5:
        no_poster_count = sum(1 for p in final_picks if not p.get("poster"))
        # Relaxed for upcoming
        sql_base = """
            SELECT * FROM movies 
            WHERE ( (imdb_rating >= 7.0 AND imdb_votes >= 5000) OR (year >= 2025) )
        """
        
        # 1. Try finding a poster first
        pool = build_candidate_pool(sql_base + " AND poster IS NOT NULL LIMIT 400", (), limit=400)
        
        # 2. Fallback to non-poster if allowed
        if not pool and no_poster_count == 0:
            pool = build_candidate_pool(sql_base + " LIMIT 400", (), limit=400)
            
        # 3. Last resort: Any highly rated movie with a poster
        if not pool:
            pool = build_candidate_pool("SELECT * FROM movies WHERE imdb_rating >= 6.5 AND poster IS NOT NULL LIMIT 200", (), limit=200)
            
        pick = sample_from_pool(pool, top_n=50, has_poster_priority=(no_poster_count >= 1))
        
        if pick:
            g_main = (pick["genres"] or "").split(",")[0]
            pick["reason"] = f"Highly rated • {g_main}"
            final_picks.append(pick)
            seen_this_refresh.add(pick["title"].lower())

    # Final fill (Rare)
    if len(final_picks) < 5:
        no_poster_count = sum(1 for p in final_picks if not p.get("poster"))
        backup_sql = "SELECT * FROM movies WHERE imdb_rating >= 6.0 AND imdb_votes >= 1000"
        
        if no_poster_count >= 1:
            pool = build_candidate_pool(backup_sql + " AND poster IS NOT NULL LIMIT 200", ())
        else:
            pool = build_candidate_pool(backup_sql + " LIMIT 200", ())

        for p in pool:
            if len(final_picks) >= 5: break
            p["reason"] = "Popular pick for you"
            final_picks.append(p)
            seen_this_refresh.add(p["title"].lower())

    conn.close()
    _random.shuffle(final_picks)
    return final_picks[:n]

def load_profile_context(profile_path: str = PROFILE_FILE) -> str:
    """Returns a rich summary of user's taste for the AI agent context."""
    p = load_profile(profile_path)

    parts = []
    liked = [m["title"] for m in p["liked_movies"][-5:]]
    if liked: parts.append(f"User's recently liked movies: {', '.join(liked)}.")

    disliked = [m["title"] for m in p["disliked_movies"][-3:]]
    if disliked: parts.append(f"User dislikes: {', '.join(disliked)}.")

    actors = p.get("preferred_actors", [])
    if actors: parts.append(f"Favorite actors: {', '.join(actors)}.")

    directors = p.get("preferred_directors", [])
    if directors: parts.append(f"Favorite directors: {', '.join(directors)}.")

    if not parts: return "User profile is new. Ask about their favorite movies/actors!"
    return "USER TASTE PROFILE: " + " ".join(parts)