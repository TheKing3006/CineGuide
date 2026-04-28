import sqlite3
conn = sqlite3.connect('movies.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(movies)")
for row in cursor.fetchall():
    print(row)
conn.close()
