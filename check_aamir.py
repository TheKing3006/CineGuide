import sqlite3
conn = sqlite3.connect('movies.db')
cursor = conn.cursor()
cursor.execute("SELECT title, imdb_votes, imdb_rating FROM movies WHERE actors LIKE '%Aamir Khan%' ORDER BY imdb_votes DESC LIMIT 5")
for row in cursor.fetchall():
    print(row)
conn.close()
