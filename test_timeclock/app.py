import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation
import streamlit.components.v1 as components

st.set_page_config(page_title="Time Clock", layout="centered", page_icon="⏰")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")

# Initialize device ID using session state
if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())
device_id = st.session_state["device_id"]

# Store device ID in browser's localStorage for persistence across sessions
components.html(
    f"""
    <script>
    (function() {{
        // Check if device ID exists in localStorage
        const storedDeviceId = localStorage.getItem('timeClockDeviceId');
        
        if (!storedDeviceId) {{
            // Store the current device ID
            localStorage.setItem('timeClockDeviceId', '{device_id}');
        }}
    }})();
    </script>
    """, 
    height=0, 
    width=0
)

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: {sub}")

# ─────────────────────────────────────────────
# 2. Check if user is already registered
try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
    user_data = cursor.fetchone()
    cursor.close()
    
    if user_data:
        st.session_state["registered"] = True
        st.session_state["user_name"] = user_data[0]
        st.session_state["user_number"] = user_data[1]
        
        st.success(f"✅ Welcome back, {st.session_state['user_name']}!")
        
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
            st.session_state["clocked_in"] = True
        else:
            st.session_state["clocked_in"] = False
    else:
        st.session_state["registered"] = False
except Exception as e:
    st.error(f"Database connection error: {str(e)}")
    st.session_state["registered"] = False

# ─────────────────────────────────────────────
# 3. Location handling
if st.button("📍 Click to Fetch Location", type="primary"):
    st.session_state["fetch_location"] = True

if "fetch_location" in st.session_state and st.session_state["fetch_location"]:
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
                # 4. Customer match with robust cursor management
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
                    # 5. User registration or clock in/out
                    if st.session_state.get("registered", False):
                        # User is already registered - show clock in/out options
                        if st.session_state.get("clocked_in", False):
                            # User is already clocked in - offer clock out
                            if st.button("🚪 Clock Out"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE TimeClock SET ClockOut = ?
                                    WHERE Cookie = ? AND ClockOut IS NULL
                                """, now, device_id)
                                conn.commit()
                                cursor.close()
                                st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                                st.session_state["clocked_in"] = False
                        else:
                            # User is registered but not clocked in - offer clock in
                            if st.button("⏱️ Clock In"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, sub, st.session_state["user_name"], st.session_state["user_number"], 
                                   now, lat_float, lon_float, device_id)
                                conn.commit()
                                cursor.close()
                                st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                                st.session_state["clocked_in"] = True
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
                                    if st.button("✅ Register & Clock In"):
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
                                        st.session_state["registered"] = True
                                        st.session_state["user_name"] = name
                                        st.session_state["user_number"] = number
                                        st.session_state["clocked_in"] = True

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
