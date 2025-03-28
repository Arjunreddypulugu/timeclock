def find_customer_from_location(lat, lon, conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT CustomerName, MinLat, MaxLat, MinLon, MaxLon
        FROM LocationCustomerMapping
    """)
    rows = cursor.fetchall()
    for row in rows:
        if row.MinLat <= lat <= row.MaxLat and row.MinLon >= lon >= row.MaxLon:
            return row.CustomerName
    return None
