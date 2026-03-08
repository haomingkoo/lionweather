from app.db.database import get_connection

con = get_connection()
cursor = con.cursor()

cursor.execute('SELECT COUNT(*) FROM weather_records')
total = cursor.fetchone()[0]
print(f'Total records: {total}')

cursor.execute('SELECT COUNT(DISTINCT country) FROM weather_records')
countries = cursor.fetchone()[0]
print(f'Countries: {countries}')

cursor.execute('SELECT country, COUNT(*) FROM weather_records GROUP BY country')
print('By country:')
for row in cursor.fetchall():
    print(f'  {row[0]}: {row[1]}')

con.close()
