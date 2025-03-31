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

# Custom CSS to improve readability and centering
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        text-align: center;
        margin-bottom: 1.5rem;
    }
    
    /* Status messages styling */
    .status-message {
        background-color: rgba(38, 39, 48, 0.8);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        text-align: center;
        border: 1px solid rgba(250, 250, 250, 0.2);
    }
    
    /* Centered container for important information */
    .centered-container {
        text-align: center;
        margin: 1rem auto;
        max-width: 600px;
    }
    
    /* Highlighted time display */
    .time-highlight {
        font-weight: bold;
        font-size: 1.1em;
        color: #ff9d00;
        background-color: rgba(38, 39, 48, 0.8);
        padding: 5px 10px;
        border-radius: 5px;
        margin: 0 5px;
    }
    
    /* Info card with better contrast */
    .info-card {
        background-color: rgba(38, 39, 48, 0.9);
        border-radius: 10px;
        padding: 15px;
        margin: 15px 0;
        border: 1px solid rgba(250, 250, 250, 0.2);
    }
    
    /* Subcontractor display with better contrast */
    .subcontractor-info {
        background-color: rgba(38, 39, 48, 0.9);
        color: white;
        padding: 10px 15px;
        border-radius: 8px;
        margin-bottom: 15px;
        display: inline-block;
    }
    
    /* Button improvements */
    .stButton>button {
        width: 100%;
    }
    
    /* Location section styling */
    .location-section {
        margin-top: 15px;
        margin-bottom: 15px;
        padding: 15px;
        border-radius: 10px;
        background-color: rgba(38, 39, 48, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# App title in centered container
st.markdown('<div class="main-header"><h1>🕒 Time Clock</h1></div>', unsafe_allow_html=True)

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

# Display subcontractor with better contrast
st.markdown(f'<div class="centered-container"><div class="subcontractor-info">👷 Subcontractor: {sub}</div></div>', unsafe_allow_html=True)

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
        
        # Centered welcome message
        st.markdown(f'<div class="centered-container"><div class="status-message">✅ Welcome back, {st.session_state["user_name"]}!</div></div>', unsafe_allow_html=True)
        
        # Check if already clocked in
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ClockIn FROM TimeClock 
            WHERE Cookie = ? AND ClockOut IS NULL
        """, device_id)
        active_session = cursor.fetchone()
        cursor.close()
        
        if active_session:
            # Centered clock-in status with highlighted time
            st.markdown(f'<div class="centered-container"><div class="status-message">⏱️ You are currently clocked in since <span class="time-highlight">{active_session[0]}</span></div></div>', unsafe_allow_html=True)
            st.session_state["clocked_in"] = True
        else:
            st.session_state["clocked_in"] = False
    else:
        st.session_state["registered"] = False
except Exception as e:
    st.error(f"Database connection error: {str(e)}")
    st.session_state["registered"] = False

# ─────────────────────────────────────────────
# 4. Location handling - FIXED SECTION
if st.button("📍 Click to Fetch Location", type="primary"):
    st.session_state["fetch_location"] = True

if "fetch_location" in st.session_state and st.session_state["fetch_location"]:
    # Add a visually appealing location section
    st.markdown('<div class="location-section"></div>', unsafe_allow_html=True)
    
    # Simple location message
    st.info("📍 Please click the location icon below to share your location")
    
    # Get location using streamlit_geolocation
    location = streamlit_geolocation()

    if location and location != "No Location Info":
        if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
            lat = location['latitude']
            lon = location['longitude']

            if lat is not None and lon is not None:
                # Store location in session state for persistence
                st.session_state["lat"] = lat
                st.session_state["lon"] = lon
                
                # Display coordinates and map with better visibility
                st.markdown(f'<div class="centered-container"><div class="info-card">📌 Your Location: {lat}, {lon}</div></div>', unsafe_allow_html=True)
                map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
                st.map(map_df)

                # ─────────────────────────────────────────────
                # 5. Customer match
                try:
                    conn = get_connection()
                    
                    try:
                        lat_float = float(lat)
                        lon_float = float(lon)
                        
                        # Store the float values in session state too
                        st.session_state["lat_float"] = lat_float
                        st.session_state["lon_float"] = lon_float
                        
                        # Find customer based on location
                        customer = find_customer_from_location(lat_float, lon_float, conn)
                        # Store customer in session state
                        st.session_state["customer"] = customer
                        
                    except (TypeError, ValueError) as e:
                        st.error(f"Invalid location format: {str(e)}")
                        st.stop()

                    if not customer:
                        st.error("❌ Not a valid job site.")
                        st.stop()
                    
                    # Display work site with better visibility
                    st.markdown(f'<div class="centered-container"><div class="info-card">🛠️ Work Site: {customer}</div></div>', unsafe_allow_html=True)
                    
                    # ─────────────────────────────────────────────
                    # 6. User registration or clock in/out
                    if st.session_state.get("registered", False):
                        # User is already registered - show clock in/out options
                        if st.session_state.get("clocked_in", False):
                            # User is already clocked in - offer clock out
                            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Clocked In</div></div>', unsafe_allow_html=True)
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                if st.button("🚪 Clock Out"):
                                    now = datetime.now()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE TimeClock SET ClockOut = ?
                                        WHERE Cookie = ? AND ClockOut IS NULL
                                    """, now, device_id)
                                    conn.commit()
                                    cursor.close()
                                    
                                    # Update session state
                                    st.session_state["clocked_in"] = False
                                    time_str = now.strftime('%H:%M:%S')
                                    
                                    # Show success message
                                    st.markdown(f'<div class="centered-container"><div class="status-message">👋 Clocked out at <span class="time-highlight">{time_str}</span></div></div>', unsafe_allow_html=True)
                                    st.rerun()  # Rerun to update UI immediately
                        else:
                            # User is registered but not clocked in - offer clock in
                            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Not Clocked In</div></div>', unsafe_allow_html=True)
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
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
                                    
                                    # Update session state
                                    st.session_state["clocked_in"] = True
                                    time_str = now.strftime('%H:%M:%S')
                                    
                                    # Show success message
                                    st.markdown(f'<div class="centered-container"><div class="status-message">✅ Clocked in at <span class="time-highlight">{time_str}</span></div></div>', unsafe_allow_html=True)
                                    st.balloons()
                                    st.rerun()  # Rerun to update UI immediately
                    else:
                        # New user registration
                        st.markdown('<div class="centered-container"><h3>📝 New User Registration</h3></div>', unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        with col1:
                            number = st.text_input("📱 Enter your mobile number:")
                        
                        if number:
                            # Check if number exists but on a different device
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                            existing = cursor.fetchone()
                            cursor.close()
                            
                            if existing:
                                # User exists but on different device
                                st.markdown('<div class="centered-container">This number is already registered. Link this device to your existing account.</div>', unsafe_allow_html=True)
                                if st.button("🔄 Link this device to your account"):
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                                    conn.commit()
                                    cursor.close()
                                    st.markdown('<div class="centered-container"><div class="status-message">✅ Device linked. You can now clock in/out.</div></div>', unsafe_allow_html=True)
                                    st.session_state["registered"] = True
                                    st.rerun()
                            else:
                                # New user registration
                                with col2:
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
                                        
                                        # Update session state
                                        st.session_state["registered"] = True
                                        st.session_state["user_name"] = name
                                        st.session_state["user_number"] = number
                                        st.session_state["clocked_in"] = True
                                        
                                        time_str = now.strftime('%H:%M:%S')
                                        st.markdown(f'<div class="centered-container"><div class="status-message">✅ Registered and clocked in at <span class="time-highlight">{time_str}</span></div></div>', unsafe_allow_html=True)
                                        st.balloons()
                                        st.rerun()  # Rerun to update UI immediately
                    
                except Exception as e:
                    st.error(f"Database error: {str(e)}")
            else:
                st.warning("📍 Please click on the location icon above to get started.")
        else:
            st.warning("Incomplete location data. Please try again.")
    else:
        st.info("⏳ Waiting for location... Please click the location icon that appears")
# If user has already fetched location (stored in session state), display it again
elif "lat" in st.session_state and "lon" in st.session_state:
    # Use stored location data
    lat = st.session_state["lat"]
    lon = st.session_state["lon"]
    
    # Display coordinates and map
    st.markdown(f'<div class="centered-container"><div class="info-card">📌 Your Location: {lat}, {lon}</div></div>', unsafe_allow_html=True)
    map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
    st.map(map_df)
    
    # Display stored customer info
    if "customer" in st.session_state:
        st.markdown(f'<div class="centered-container"><div class="info-card">🛠️ Work Site: {st.session_state["customer"]}</div></div>', unsafe_allow_html=True)
    
    # Show appropriate clock in/out UI based on current status
    if st.session_state.get("registered", False):
        if st.session_state.get("clocked_in", False):
            # Show clock out UI
            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Clocked In</div></div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚪 Clock Out"):
                    now = datetime.now()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE TimeClock SET ClockOut = ?
                        WHERE Cookie = ? AND ClockOut IS NULL
                    """, now, device_id)
                    conn.commit()
                    cursor.close()
                    
                    # Update session state
                    st.session_state["clocked_in"] = False
                    time_str = now.strftime('%H:%M:%S')
                    
                    # Show success message
                    st.markdown(f'<div class="centered-container"><div class="status-message">👋 Clocked out at <span class="time-highlight">{time_str}</span></div></div>', unsafe_allow_html=True)
                    st.rerun()
        else:
            # Show clock in UI
            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Not Clocked In</div></div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("⏱️ Clock In"):
                    now = datetime.now()
                    lat_float = st.session_state["lat_float"]
                    lon_float = st.session_state["lon_float"]
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, sub, st.session_state["user_name"], st.session_state["user_number"], 
                       now, lat_float, lon_float, device_id)
                    conn.commit()
                    cursor.close()
                    
                    # Update session state
                    st.session_state["clocked_in"] = True
                    time_str = now.strftime('%H:%M:%S')
                    
                    # Show success message and celebration
                    st.markdown(f'<div class="centered-container"><div class="status-message">✅ Clocked in at <span class="time-highlight">{time_str}</span></div></div>', unsafe_allow_html=True)
                    st.balloons()
                    st.rerun()
else:
    st.markdown('<div class="centered-container"><div class="status-message">⌛</div></div>', unsafe_allow_html=True)
