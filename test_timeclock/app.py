import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation
from streamlit_cookies_controller import CookieController
import base64
import urllib.parse

# Initialize cookie controller
cookies = CookieController()

st.set_page_config(page_title="Time Clock", layout="centered", page_icon="⏰")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Device identification using cookies
stored_device_id = cookies.get("device_id")  

if not stored_device_id:
    # No cookie found, generate a new device ID
    device_id = str(uuid.uuid4())
    # Set cookie - using correct parameter syntax
    cookies.set("device_id", device_id)
else:
    # Use existing device ID from cookie
    device_id = stored_device_id

# ─────────────────────────────────────────────
# 2. Decode subcontractor from URL
query_params = st.query_params
encoded_sub = query_params.get("s")  # Changed from 'sub' to shorter 's'

if not encoded_sub:
    st.error("Missing subcontractor code in URL. Use ?s=[encoded_value]")
    st.stop()

try:
    # URL decode then base64 decode
    decoded_bytes = base64.b64decode(urllib.parse.unquote(encoded_sub))
    sub = decoded_bytes.decode('utf-8')
except Exception as e:
    st.error(f"Invalid subcontractor code. Error: {str(e)}")
    st.stop()

st.markdown(f"👷 Subcontractor: {sub}")

# ─────────────────────────────────────────────
# 3. Check if user is already registered
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
# 4. Location handling
#if st.button("📍 Click to Fetch Location", type="primary"):
st.session_state["fetch_location"] = True

if "fetch_location" in st.session_state and st.session_state["fetch_location"]:
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
                # 5. Customer match
                try:
                    conn = get_connection()
                    
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
                st.warning("📍 Please click on the location icon above to get started.")
        else:
            st.warning("Incomplete location data. Please try again.")
    else:
        st.info("⏳ Waiting for location...")
else:
    st.info("⌛ Click the location button above to get started.")
