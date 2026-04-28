import sqlite3
conn = sqlite3.connect('movies.db')
titles = ['Magnolia', 'Sarfarosh', 'Black Adam', 'Deadpool', 'Free Guy', 'Green Lantern']
for t in titles:
    r = conn.execute('SELECT title, actors FROM movies WHERE title = ?', (t,)).fetchone()
    print(f"{t}: {r}")
