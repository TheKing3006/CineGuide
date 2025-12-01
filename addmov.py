import sqlite3

conn = sqlite3.connect("movies.db")
cursor = conn.cursor()

# Movies to add
movies_to_add = [
    {
        'imdb_id': 'tt21357150',
        'title': 'Avengers: Doomsday',
        'year': 2026,
        'runtime_minutes': None,  # Not released yet
        'genres': 'Action,Adventure,Sci-Fi',
        'imdb_rating': None,
        'imdb_votes': 0,
        'enriched': 0
    },
    {
        'imdb_id': 'tt28650488',
        'title': 'The Super Mario Galaxy Movie',
        'year': 2026,
        'runtime_minutes': None,
        'genres': 'Animation,Adventure,Comedy',
        'imdb_rating': None,
        'imdb_votes': 0,
        'enriched': 0
    }
]

print("=== ADDING MOVIES ===\n")

for movie in movies_to_add:
    try:
        cursor.execute("""
            INSERT INTO movies (
                imdb_id, title, year, runtime_minutes, genres, 
                imdb_rating, imdb_votes, enriched
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            movie['imdb_id'],
            movie['title'],
            movie['year'],
            movie['runtime_minutes'],
            movie['genres'],
            movie['imdb_rating'],
            movie['imdb_votes'],
            movie['enriched']
        ))
        conn.commit()
        print(f"✅ Added: {movie['title']} ({movie['year']})")
    except sqlite3.IntegrityError:
        print(f"⚠️  Already exists: {movie['title']}")
    except Exception as e:
        print(f"❌ Error adding {movie['title']}: {e}")

print("\n=== VERIFYING ADDITIONS ===\n")

# Verify Avengers Doomsday
cursor.execute("""
    SELECT title, year, imdb_id FROM movies 
    WHERE imdb_id = 'tt21357150'
""")
result = cursor.fetchone()
if result:
    print(f"✅ Found: {result}")
else:
    print("❌ Avengers: Doomsday not found")

# Verify Super Mario Galaxy Movie
cursor.execute("""
    SELECT title, year, imdb_id FROM movies 
    WHERE imdb_id = 'tt28650488'
""")
result = cursor.fetchone()
if result:
    print(f"✅ Found: {result}")
else:
    print("❌ Super Mario Galaxy Movie not found")

conn.close()

print("\n🎬 Done! Now 'avengers 5' and 'super mario galaxy' should work in your app!")
