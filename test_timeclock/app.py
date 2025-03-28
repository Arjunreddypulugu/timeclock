import streamlit as st
from streamlit_geolocation import geolocation
from datetime import datetime
import uuid
from db_config import get_connection
from utils import find_customer_from_location
import pyodbc
import pandas as pd

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# ─────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")
device_id = str(uuid.uuid4())

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"**👷 Subcontractor:** `{sub}`")

# ─────────────────────────────────────
# 2. Get user location using streamlit-geolocation
location = geolocation("📍 Click to Fetch Location", key="get_location")

if location is None or location.get("latitude") is None:
    st.info("📡 Waiting for location… Please click the button and allow browser access.")
    st.stop()

lat = location["latitude"]
lon = location["longitude"]
st.session_state["location"] = (lat, lon)

st.success(f"📌 Coordinates: ({lat:.5f}, {lon:.5f})")
st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))

# ─────────────────────────────────────
# 3. Find matching customer from bounding box
conn = get_connection()
cursor = conn.cursor()

customer = find_customer_from_location(lat, lon, conn)

if not customer:
    st.error("❌ You are not on a valid job site.")
    st.stop()
else:
    st.success(f"🛠️ Work Site: {customer}")

# ─────────────────────────────────────
# 4. Check or register employee by device ID
cursor.execute("SELECT * FROM SubContractorEmployees WHERE Cookies = ?", device_id)
record = cursor.fetchone()

if not record:
    number = st.text_input("📱 Enter your mobile number:")
    if number:
        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
            conn.commit()
            st.success("✅ Device linked to existing user.")
        else:
            name = st.text_input("🧑 Enter your name:")
            if name:
                cursor.execute("""
                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                    VALUES (?, ?, ?, ?)
                """, sub, name, number, device_id)
                conn.commit()
                st.success("✅ New user registered.")
else:
    st.info("✅ Device recognized. Welcome back!")

# ─────────────────────────────────────
# 5. Clock In / Clock Out
action = st.radio("Select action:", ["Clock In", "Clock Out"])

if st.button("Submit", key="submit_btn"):
    now = datetime.now()
    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
    user = cursor.fetchone()

    if not user:
        st.error("⚠️ Could not verify user. Please re-enter mobile number.")
    else:
        name, number = user
        if action == "Clock In":
            cursor.execute("""
                INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, sub, name, number, now, lat, lon, device_id)
            conn.commit()
            st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
        elif action == "Clock Out":
            cursor.execute("""
                UPDATE TimeClock SET ClockOut = ?
                WHERE Cookie = ? AND ClockOut IS NULL
            """, now, device_id)
            conn.commit()
            st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
