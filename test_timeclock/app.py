import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation
import json

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")

# Better device identification using Local Storage
# This persists even when browser is closed
if "device_id" not in st.session_state:
    # Use browser's local storage to check for existing device ID
    device_check = st.empty()
    device_check.html("""
    <script>
    const storedDeviceId = localStorage.getItem('timeClockDeviceId');
    if (storedDeviceId) {
        window.parent.postMessage({type: 'device_id', value: storedDeviceId}, '*');
    } else {
        const newDeviceId = crypto.randomUUID();
        localStorage.setItem('timeClockDeviceId', newDeviceId);
        window.parent.postMessage({type: 'device_id', value: newDeviceId}, '*');
    }
    </script>
    """, height=0)
    
    # Create a placeholder for device ID
    st.session_state["device_id"] = str(uuid.uuid4())  # Temporary ID until browser provides one

# JavaScript message handler to receive the device ID from browser storage
components_js = """
<script>
window.addEventListener('message', function(event) {
    if (event.data.type === 'device_id') {
        const input = window.parent.document.querySelector('input[data-testid="stTextInput"]');
        if (input) {
            input.value = event.data.value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
});
</script>
"""
st.components.v1.html(components_js, height=0)

# Hidden field to receive device ID from JavaScript
device_id_input = st.text_input("Device ID", key="device_id_input", label_visibility="collapsed")
if device_id_input and device_id_input != st.session_state["device_id"]:
    st.session_state["device_id"] = device_id_input

device_id = st.session_state["device_id"]

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: {sub}")

# ─────────────────────────────────────────────
# 2. Location handling

# Get location using streamlit-geolocation
location = streamlit_geolocation()

if location and location != "No Location Info":
    if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
        lat = location['latitude']
        lon = location['longitude']

        if lat is not None and lon is not None:
            # Display coordinates and map
            st.success(f"📌 Coordinates: {lat}, {lon}")
            map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
            st.map(map_df)

            # ─────────────────────────────────────────────
            # 3. Check if device is already registered to someone else
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # First, check if this device is already associated with a user
                cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
                existing_user = cursor.fetchone()
                cursor.close()
                
                if existing_user:
                    # Device is already registered to a user
                    employee_name, employee_number = existing_user
                    st.info(f"📱 This device is registered to: {employee_name}")
                    
                    # Get location-based customer
                    cursor = conn.cursor()
                    lat_float = float(lat)
                    lon_float = float(lon)
                    customer = find_customer_from_location(lat_float, lon_float, conn)
                    cursor.close()
                    
                    if not customer:
                        st.error("❌ Not a valid job site.")
                        st.stop()
                    
                    st.success(f"🛠️ Work Site: {customer}")
                    
                    # Check if already clocked in
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT ClockIn FROM TimeClock 
                        WHERE Cookie = ? AND ClockOut IS NULL
                    """, device_id)
                    current_session = cursor.fetchone()
                    cursor.close()
                    
                    if current_session:
                        # User is already clocked in
                        clock_in_time = current_session[0]
                        st.warning(f"⏰ You are currently clocked in since {clock_in_time}")
                        
                        if st.button("⏱️ Clock Out Now"):
                            now = datetime.now()
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE TimeClock SET ClockOut = ?
                                WHERE Cookie = ? AND ClockOut IS NULL
                            """, now, device_id)
                            conn.commit()
                            cursor.close()
                            st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                    else:
                        # User is not clocked in
                        if st.button("⏱️ Clock In Now"):
                            now = datetime.now()
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, sub, employee_name, employee_number, now, lat_float, lon_float, device_id)
                            conn.commit()
                            cursor.close()
                            st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                
                else:
                    # New registration flow
                    number = st.text_input("📱 Enter your mobile number:")
                    
                    if number:
                        cursor = conn.cursor()
                        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                        existing = cursor.fetchone()
                        cursor.close()
                        
                        if existing:
                            # User exists but using a new device
                            if st.button("Link this device to your account"):
                                cursor = conn.cursor()
                                cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                                conn.commit()
                                cursor.close()
                                st.success("✅ Device linked. Refresh the page to continue.")
                        else:
                            # Completely new user
                            name = st.text_input("🧑 Enter your name:")
                            if name:
                                # Check if device is already registered
                                lat_float = float(lat)
                                lon_float = float(lon)
                                customer = find_customer_from_location(lat_float, lon_float, conn)
                                
                                if not customer:
                                    st.error("❌ Not a valid job site.")
                                    st.stop()
                                
                                st.success(f"🛠️ Work Site: {customer}")
                                
                                if st.button("Register & Clock In"):
                                    now = datetime.now()
                                    
                                    # Register user
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                                        VALUES (?, ?, ?, ?)
                                    """, sub, name, number, device_id)
                                    conn.commit()
                                    cursor.close()
                                    
                                    # Clock in
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, sub, name, number, now, lat_float, lon_float, device_id)
                                    conn.commit()
                                    cursor.close()
                                    
                                    st.success(f"✅ Registered and clocked in at {now.strftime('%H:%M:%S')}")
            except Exception as e:
                st.error(f"Database error: {str(e)}")
        else:
            st.warning("📍 Please click the location icon above to get started.")
    else:
        st.warning("Incomplete location data. Please try again.")
else:
    st.info("⏳ Waiting for location... Please click the location button above.")
