# utils.py
from db_config import get_connection

def find_customer_from_location(lat, lon):
    with get_connection() as conn:  # Use context manager
        cursor = conn.cursor()
        cursor.execute("""
            SELECT customer_name, min_latitude, max_latitude, min_longitude, max_longitude
            FROM LocationCustomerMapping
        """)
        rows = cursor.fetchall()
        for row in rows:
            if row.min_latitude <= lat <= row.max_latitude and row.min_longitude >= lon >= row.max_longitude:
                return row.customer_name
        return None
