import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation
import streamlit.components.v1 as components

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Get device ID from localStorage (persistence across sessions)
# Create a placeholder for device ID
if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())  # Temporary ID

# Get persistent device ID from localStorage
# Using a regular string instead of f-string to avoid parsing issues
device_id_js = """
<script>
    // Check if device ID exists in localStorage
    const storedDeviceId = localStorage.getItem('timeClockDeviceId');
    
    if (storedDeviceId) {
        // Use existing ID - send it to Streamlit
        window.parent.postMessage(
            {type: 'streamlit:setComponentValue', value: storedDeviceId}, '*'
        );
    } else {
        // No stored ID - store the temporary one
        const serverDeviceId = "DEVICE_ID_PLACEHOLDER";
        // Store new ID in localStorage for future visits
        localStorage.setItem('timeClockDeviceId', serverDeviceId);
        // Send confirmation back to Streamlit
        window.parent.postMessage(
            {type: 'streamlit:setComponentValue', value: serverDeviceId}, '*'
        );
    }
</script>
"""

# Replace placeholder with actual device ID
device_id_js = device_id_js.replace("DEVICE_ID_PLACEHOLDER", st.session_state["device_id"])

components.html(device_id_js, height=0, width=0, key="device_id_component")

# Receive the device ID from the component
if "device_id_component" in st.session_state:
    st.session_state["device_id"] = st.session_state["device_id_component"]

device_id = st.session_state["device_id"]

# ─────────────────────────────────────────────
# 2. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: {sub}")

# ─────────────────────────────────────────────
# 3. Check if user is already registered (before location)
already_registered = False
user_name = None
user_number = None

try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
    user_data = cursor.fetchone()
    cursor.close()
    
    if user_data:
        already_registered = True
        user_name, user_number = user_data
        st.success(f"✅ Welcome back, {user_name}!")
        
        # Check if already clocked in
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ClockIn FROM TimeClock 
            WHERE Cookie = ? AND ClockOut IS NULL
        """, device_id)
        active_session = cursor.fetchone()
        cursor.close()
        
        if active_session:
            st.info(f"⏱️ You are currently clocked in since {active_session[0]}")
except Exception as e:
    st.error(f"Database connection error: {str(e)}")

# ─────────────────────────────────────────────
# 4. Location handling
location_button = st.button("📍 Click to Fetch Location", key="fetch_location")

if location_button:
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
                # 5. Customer match with robust cursor management
                try:
                    conn = get_connection()
                    
                    # Convert location to float to prevent comparison errors
                    try:
                        lat_float = float(lat)
                        lon_float = float(lon)
                        
                        # Find customer based on location
                        customer = find_customer_from_location(lat_float, lon_float, conn)
                        
                    except (TypeError, ValueError) as e:
                        st.error(f"Invalid location format: {str(e)}")
                        st.stop()

                    if not customer:
                        st.error("❌ Not a valid job site.")
                        st.stop()
                    
                    st.success(f"🛠️ Work Site: {customer}")

                    # ─────────────────────────────────────────────
                    # 6. User registration or clock in/out
                    if already_registered:
                        # User is already registered - show clock in/out options
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT ClockIn FROM TimeClock 
                            WHERE Cookie = ? AND ClockOut IS NULL
                        """, device_id)
                        active_session = cursor.fetchone()
                        cursor.close()
                        
                        if active_session:
                            # User is already clocked in - offer clock out
                            if st.button("🚪 Clock Out", type="primary"):
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
                            # User is registered but not clocked in - offer clock in
                            if st.button("⏱️ Clock In", type="primary"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, sub, user_name, user_number, now, lat_float, lon_float, device_id)
                                conn.commit()
                                cursor.close()
                                st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                    else:
                        # New user registration
                        st.subheader("📝 New User Registration")
                        number = st.text_input("📱 Enter your mobile number:")
                        
                        if number:
                            # Check if number exists but on a different device
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                            existing = cursor.fetchone()
                            cursor.close()
                            
                            if existing:
                                # User exists but on different device
                                if st.button("🔄 Link this device to your account"):
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                                    conn.commit()
                                    cursor.close()
                                    st.success("✅ Device linked. You can now clock in/out.")
                                    st.rerun()
                            else:
                                # New user registration
                                name = st.text_input("🧑 Enter your name:")
                                if name:
                                    if st.button("✅ Register & Clock In", type="primary"):
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
                st.warning("📍 Location coordinates are missing. Please try again.")
        else:
            st.warning("Incomplete location data. Please try again.")
    else:
        st.info("⏳ Waiting for location...")
else:
    st.info("⌛ Click the location button above to get started.")
