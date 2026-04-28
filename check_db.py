import sqlite3
conn = sqlite3.connect('movies.db')
cursor = conn.cursor()
cursor.execute("SELECT title, actors FROM movies WHERE title LIKE '%Munna Bhai%'")
for row in cursor.fetchall():
    print(row)
conn.close()
