# db_config.py
import pyodbc
import streamlit as st

class DBConnection:
    def __init__(self):
        self.conn = None
        
    def __enter__(self):
        db = st.secrets["database"]
        connection_string = (
            f"Driver={{{db['driver']}}};"
            f"Server={db['server']};"
            f"Database={db['database']};"
            f"UID={db['username']};"
            f"PWD={db['password']};"
            f"MARS_Connection=Yes;"
        )
        self.conn = pyodbc.connect(connection_string)
        return self.conn
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            # Instead of closing, reset the connection
            self.conn.commit()
            if self.conn.closed:  # Only reset if connection is still open
                self.conn.close()

# Remove caching completely
def get_connection():
    return DBConnection()
