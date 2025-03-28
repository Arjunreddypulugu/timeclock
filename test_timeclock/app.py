import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid
from db_config import get_connection
from utils import find_customer_from_location
import pyodbc
import pandas as pd

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")
device_id = str(uuid.uuid4())

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"**👷 Subcontractor:** `{sub}`")

# ─────────────────────────────────────────────
# 2. User must click to allow location access
clicked = st.button("📍 Click to Fetch Location")

if clicked:
    components.html("""
    <script>
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const coords = position.coords.latitude + "," + position.coords.longitude;
                localStorage.setItem("geo_location", coords);
                const input = window.parent.document.querySelector('input[data-testid="stTextInput"]');
                if (input) {
                    input.value = coords;
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            },
            function(error) {
                const input = window.parent.document.querySelector('input[data-testid="stTextInput"]');
                if (input) {
                    input.value = "ERROR";
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
        );
    </script>
    """, height=0)

    # Hidden input to receive coordinates from JS
    location_input = st.text_input("🔒", label_visibility="collapsed")

    if not location_input:
        st.info("⏳ Waiting for location…")
        st.stop()
    elif location_input == "ERROR":
        st.error("❌ Location access denied. Please allow location.")
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
else:
    st.stop()

# ─────────────────────────────────────────────
# 3. Customer match
conn = get_connection()
cursor = conn.cursor()
lat, lon = st.session_state["location"]

customer = find_customer_from_location(lat, lon, conn)
if not customer:
    st.error("❌ Not a valid job site.")
    st.stop()
else:
    st.success(f"🛠️ Work Site: {customer}")

# ─────────────────────────────────────────────
# 4. Registration (same as before)
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
            st.success("✅ Device linked.")
        else:
            name = st.text_input("🧑 Enter your name:")
            if name:
                cursor.execute("""
                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                    VALUES (?, ?, ?, ?)
                """, sub, name, number, device_id)
                conn.commit()
                st.success("✅ Registered successfully.")
else:
    st.info("✅ Device recognized.")

# ─────────────────────────────────────────────
# 5. Clock In / Out
action = st.radio("Select action:", ["Clock In", "Clock Out"])

if st.button("Submit", key="submit_btn"):
    now = datetime.now()
    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
    user = cursor.fetchone()

    if not user:
        st.error("⚠️ Could not verify user.")
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
