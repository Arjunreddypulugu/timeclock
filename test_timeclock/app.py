import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime
import uuid
from db_config import get_connection
from utils import find_customer_from_location
import pyodbc

st.title("🕒 Time Clock")

# Fetch geolocation using JavaScript
components.html("""
<script>
navigator.geolocation.getCurrentPosition(
    function(position) {
        const coords = position.coords.latitude + "," + position.coords.longitude;
        window.parent.postMessage(coords, "*");
    },
    function(error) {
        window.parent.postMessage("ERROR", "*");
    }
);
</script>
""", height=0)

location = st.experimental_get_query_params().get("location")
user_param = st.experimental_get_query_params().get("user", [None])[0]

if not location or location[0] == "ERROR":
    st.warning("⚠️ Waiting for your device's location...")
    st.stop()

lat, lon = map(float, location[0].split(","))
st.session_state['lat'] = lat
st.session_state['lon'] = lon

conn = get_connection()
cursor = conn.cursor()

# Determine customer from geolocation
customer = find_customer_from_location(lat, lon, conn)
if not customer:
    st.error("❌ You're not on a valid site.")
    st.stop()
st.subheader(f"🛠️ Site: {customer}")

# Subcontractor from user query param
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

# Simulate or read cookie (UUID)
device_id = st.experimental_get_query_params().get("device_id", [str(uuid.uuid4())])[0]

# Identify or register employee
cursor.execute("SELECT * FROM SubContractorEmployees WHERE Cookies = ?", device_id)
record = cursor.fetchone()

if not record:
    number = st.text_input("Enter your mobile number:")
    if number:
        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
        existing = cursor.fetchone()
        if existing:
            cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
            conn.commit()
        else:
            name = st.text_input("Enter your name:")
            if name:
                cursor.execute("""
                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                    VALUES (?, ?, ?, ?)
                """, sub, name, number, device_id)
                conn.commit()
        st.success("✅ Cookie assigned. You may now clock in.")

# Clock In / Out
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
