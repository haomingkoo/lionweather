from app.db.database import get_connection

con = get_connection()
cursor = con.cursor()

cursor.execute('''
    SELECT DISTINCT location, latitude, longitude, COUNT(*) 
    FROM weather_records 
    WHERE country = "singapore" 
    GROUP BY location, latitude, longitude
''')

print('Singapore locations in database:')
for row in cursor.fetchall():
    print(f'  {row[0]}: ({row[1]}, {row[2]}) - {row[3]} records')

con.close()
