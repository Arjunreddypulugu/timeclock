import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid
from db_config import get_connection
from utils import find_customer_from_location
import pyodbc

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# 🔹 Step 1: Get query parameters
query_params = st.query_params
sub = query_params.get("sub")
device_id = str(uuid.uuid4())  # Simulated device ID for testing

# 🔸 Error if no subcontractor provided
if not sub:
    st.error("Missing subcontractor in URL. Use a valid link like '?sub=Alpha%20Electrical'")
    st.stop()

st.markdown(f"**👷 Subcontractor:** `{sub}`")

# 🔹 Step 2: JavaScript to fetch browser location and send it to Streamlit
if "location" not in st.session_state:
    components.html("""
    <script>
        navigator.geolocation.getCurrentPosition(
            function(position) {
                const coords = position.coords.latitude + "," + position.coords.longitude;
                localStorage.setItem("geo_location", coords);
                window.parent.postMessage(coords, "*");
            },
            function(error) {
                window.parent.postMessage("ERROR", "*");
            }
        );
    </script>
    """, height=0)

    location_input = st.text_input("📍 Location (auto-filled from browser)", key="loc_input")
    if not location_input or location_input == "ERROR":
        st.warning("⚠️ Waiting for your device's location...")
        st.stop()

    try:
        lat, lon = map(float, location_input.split(","))
        st.session_state["location"] = (lat, lon)
    except:
        st.error("Invalid location format.")
        st.stop()
else:
    lat, lon = st.session_state["location"]

# 🔹 Step 3: Get site/customer based on GPS
conn = get_connection()
cursor = conn.cursor()

customer = find_customer_from_location(lat, lon, conn)
if not customer:
    st.error("❌ You're not on a valid work site.")
    st.stop()

st.success(f"🛠️ Site Location: {customer}")

# 🔹 Step 4: Identify or register employee by device cookie
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
            st.success("✅ Device re-linked to existing user.")
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
    st.info("✅ Recognized device. Welcome back!")

# 🔹 Step 5: Clock In / Out
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
