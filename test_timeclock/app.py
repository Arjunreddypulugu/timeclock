import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid
from db_config import get_connection
from utils import find_customer_from_location
import pyodbc
import pandas as pd
import time

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# 1. Get subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")
device_id = str(uuid.uuid4())

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"**👷 Subcontractor:** `{sub}`")

# 2. JS: Auto-request location on load and store in localStorage
components.html("""
<script>
    navigator.geolocation.getCurrentPosition(
        function(position) {
            const coords = position.coords.latitude + "," + position.coords.longitude;
            localStorage.setItem("geo_location", coords);
        },
        function(error) {
            localStorage.setItem("geo_location", "ERROR");
        }
    );
</script>
""", height=0)

# 3. Poll location from localStorage into hidden field
components.html("""
<script>
    const coords = localStorage.getItem("geo_location");
    if (coords) {
        const input = window.parent.document.querySelector('input[data-testid="stTextInput"]');
        if (input) {
            input.value = coords;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
</script>
""", height=0)

# 4. Hidden field to pipe location from JS to Python
location_input = st.text_input("🔒", label_visibility="collapsed")

if not location_input:
    st.info("📍 Waiting for location... Check if browser asked for GPS access.")
    st.stop()
elif location_input == "ERROR":
    st.error("❌ Location denied. Please refresh and allow GPS.")
    st.stop()
else:
    try:
        lat, lon = map(float, location_input.split(","))
        st.session_state["location"] = (lat, lon)
        st.success(f"📌 Coordinates: ({lat:.5f}, {lon:.5f})")
        st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))
    except:
        st.error("❌ Invalid location format.")
        st.stop()

# 5. Lookup customer from location
conn = get_connection()
cursor = conn.cursor()
lat, lon = st.session_state["location"]

customer = find_customer_from_location(lat, lon, conn)

if not customer:
    st.error("❌ You are not on a valid work site.")
    st.stop()
else:
    st.success(f"🛠️ Work Site: {customer}")

# 6. Rest of app (registration + clock-in/out remains same as previous version)
# You can now safely re-use the remaining parts of app.py
# ─────────────────────────────
# 4. User verification
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

# ─────────────────────────────
# 5. Clock In / Clock Out
action = st.radio("Select action:", ["Clock In", "Clock Out"])

if st.button("Submit"):
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
