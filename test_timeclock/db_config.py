import pyodbc
import streamlit as st

@st.cache_resource
def get_connection():
    db = st.secrets["database"]
    connection_string = (
        f"Driver={{{db['driver']}}};"
        f"Server={db['server']};"
        f"Database={db['database']};"
        f"UID={db['username']};"
        f"PWD={db['password']};"
        f"MARS_Connection=Yes;"  # Enable MARS
    )
    return pyodbc.connect(connection_string)
