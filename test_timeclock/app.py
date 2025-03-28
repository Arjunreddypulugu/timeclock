import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid
from db_config import get_connection
from utils import find_customer_from_location
import pyodbc

st.title("🕒 Time Clock")

# ───────────────────────────────
# JavaScript to fetch geolocation
components.html("""
<script>
navigator.geolocation.getCurrentPosition(
    function(position) {
        const coords = position.coords.latitude + "," + position.coords.longitude;
        const url = new URL(window.location.href);
        url.searchParams.set("location", coords);
        window.location.href = url.toString();
    },
    function(error) {
        const url = new URL(window.location.href);
        url.searchParams.set("location", "ERROR");
        window.location.href = url.toString();
    }
);
</script>
""", height=0)

# ───────────────────────────────
# Get query parameters the new way
query_params = st.query_params

location = query_params.get("location")
user_param = query_params.get("user")
device_id = query_params.get("device_id", str(uuid.uuid4()))

# ───────────────────────────────
# Location handling
if not location or location == "ERROR":
    st.warning("⚠️ Waiting for your device's location...")
    st.stop()

try:
    lat, lon = map(float, location.split(","))
except:
    st.error("❌ Invalid location format.")
    st.stop()

st.session_state['lat'] = lat
st.session_state['lon'] = lon

# ───────────────────────────────
# Connect to database and lookup customer
conn = get_connection()
cursor = conn.cursor()

customer = find_customer_from_location(lat, lon, conn)
if not customer:
    st.error("❌ You're not on a valid site.")
    st.stop()

st.subheader(f"🛠️ Site: {customer}")

# ───────────────────────────────
# Get subcontractor from user param
sub = None
if user_param:
    cursor.execute("SELECT SubContractor FROM SubContractorEmployees WHERE Employee = ?", user_param)
    result = cursor.fetchone()
    if result:
        sub = result[0]

if not sub:
    st.error("Could not determine subcontractor from URL. Please contact admin.")
    st.stop()
else:
    st.success(f"👷 Subcontractor: {sub}")

# ───────────────────────────────
# Check if user already exists by cookie
cursor.execute("SELECT * FROM SubContractorEmployees WHERE Cookies = ?", device_id)
record = cursor.fetchone()

if not record:
    number = st.text_input("Enter your mobile number:")
    if number:
        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
        existing = cursor.fetchone()
        if existing:
            # Update with new cookie
            cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
            conn.commit()
        else:
            # New user registration
            name = st.text_input("Enter your name:")
            if name:
                cursor.execute("""
                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                    VALUES (?, ?, ?, ?)
                """, sub, name, number, device_id)
                conn.commit()
        st.success("✅ Cookie assigned. You may now clock in.")

# ───────────────────────────────
# Clock In / Clock Out options
action = st.radio("Select action:", ["Clock In", "Clock Out"])

if st.button("Submit"):
    now = datetime.now()
    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
    employee_record = cursor.fetchone()

    if not employee_record:
        st.error("Could not find your record. Please re-enter details.")
    else:
        name, number = employee_record
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
