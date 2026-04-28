import sqlite3
conn = sqlite3.connect('movies.db')
cursor = conn.cursor()
cursor.execute("SELECT language, COUNT(*) FROM movies WHERE language IS NOT NULL GROUP BY language ORDER BY COUNT(*) DESC LIMIT 10")
for row in cursor.fetchall():
    print(row)
conn.close()
