def find_customer_from_location(lat, lon, conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT CustomerName, MinLat, MaxLat, MinLon, MaxLon
        FROM LocationCustomerMapping
    """)
    for row in cursor.fetchall():
        if row.MinLat <= lat <= row.MaxLat and row.MinLon <= lon <= row.MaxLon:
            return row.CustomerName
    return None
