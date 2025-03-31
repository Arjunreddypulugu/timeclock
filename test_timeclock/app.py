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

# Improved page configuration with custom theme
st.set_page_config(
    page_title="Time Clock",
    page_icon="⏰",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        text-align: center;
    }
    .subcontractor {
        font-size: 1.2rem;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .status-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
        text-align: center;
    }
    .clock-btn {
        width: 100%;
        padding: 0.75rem !important;
        font-size: 1.2rem !important;
        margin: 1rem 0 !important;
    }
    .info-section {
        background-color: rgba(240, 242, 246, 0.1);
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .stButton button {
        width: 100%;
    }
    .map-container {
        margin: 1rem 0;
        border-radius: 0.5rem;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# App header with more visual appeal
st.markdown('<div class="main-header">🕒 Time Clock</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 1. Device identification using cookies
stored_device_id = cookies.get("device_id")  

if not stored_device_id:
    device_id = str(uuid.uuid4())
    cookies.set("device_id", device_id)
else:
    device_id = stored_device_id

# ─────────────────────────────────────────────
# 2. Decode subcontractor from URL
query_params = st.query_params
encoded_sub = query_params.get("s")  # Changed from 'sub' to shorter 's'

if not encoded_sub:
    st.error("Missing subcontractor code in URL. Use ?s=[encoded_value]")
    st.stop()

try:
    decoded_bytes = base64.b64decode(urllib.parse.unquote(encoded_sub))
    sub = decoded_bytes.decode('utf-8')
except Exception as e:
    st.error(f"Invalid subcontractor code. Error: {str(e)}")
    st.stop()

# Show subcontractor with nicer styling
st.markdown(f'<div class="subcontractor">👷 Subcontractor: <strong>{sub}</strong></div>', unsafe_allow_html=True)

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
        
        # More eye-catching welcome message
        st.markdown(f'<div class="status-box" style="background-color: rgba(45, 183, 66, 0.2);">✅ Welcome back, <strong>{st.session_state["user_name"]}</strong>!</div>', unsafe_allow_html=True)
        
        # Check if already clocked in
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ClockIn FROM TimeClock 
            WHERE Cookie = ? AND ClockOut IS NULL
        """, device_id)
        active_session = cursor.fetchone()
        cursor.close()
        
        if active_session:
            # More visible clock-in status
            st.markdown(f'<div class="status-box" style="background-color: rgba(54, 137, 214, 0.2);">⏱️ You are currently clocked in since <strong>{active_session[0]}</strong></div>', unsafe_allow_html=True)
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
st.session_state["fetch_location"] = True

if "fetch_location" in st.session_state and st.session_state["fetch_location"]:
    # Create two columns for better layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        location = streamlit_geolocation()
    
    with col2:
        # Show a little help text
        st.info("📱 Allow location access when prompted")

    if location and location != "No Location Info":
        if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
            lat = location['latitude']
            lon = location['longitude']

            if lat is not None and lon is not None:
                # Hide coordinates in an expander to reduce clutter
                with st.expander("📌 View Location Details"):
                    st.write(f"Latitude: {lat}")
                    st.write(f"Longitude: {lon}")
                
                # Display map with better styling
                st.markdown('<div class="map-container">', unsafe_allow_html=True)
                map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
                st.map(map_df)
                st.markdown('</div>', unsafe_allow_html=True)

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
                    
                    # More visible work site information
                    st.markdown(f'<div class="status-box" style="background-color: rgba(45, 183, 66, 0.2);">🛠️ Work Site: <strong>{customer}</strong></div>', unsafe_allow_html=True)

                    # ─────────────────────────────────────────────
                    # 6. User registration or clock in/out
                    if st.session_state.get("registered", False):
                        # User is already registered - show clock in/out options
                        if st.session_state.get("clocked_in", False):
                            # User is already clocked in - offer clock out
                            if st.button("🚪 Clock Out", type="primary", key="clock_out_btn", help="Click to record your clock out time"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE TimeClock SET ClockOut = ?
                                    WHERE Cookie = ? AND ClockOut IS NULL
                                """, now, device_id)
                                conn.commit()
                                cursor.close()
                                st.balloons()  # Add visual celebration
                                st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                                st.session_state["clocked_in"] = False
                        else:
                            # User is registered but not clocked in - offer clock in
                            if st.button("⏱️ Clock In", type="primary", key="clock_in_btn", help="Click to start tracking time"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, sub, st.session_state["user_name"], st.session_state["user_number"], 
                                   now, lat_float, lon_float, device_id)
                                conn.commit()
                                cursor.close()
                                st.balloons()  # Add visual celebration
                                st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                                st.session_state["clocked_in"] = True
                    else:
                        # New user registration - improved layout with columns
                        st.markdown('<div class="info-section">', unsafe_allow_html=True)
                        st.subheader("📝 New User Registration")
                        
                        # Instructions for new users
                        st.info("Please register to begin tracking your time at this job site.")
                        
                        number = st.text_input("📱 Enter your mobile number:", help="Enter your contact number")
                        
                        if number:
                            # Check if number exists but on a different device
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                            existing = cursor.fetchone()
                            cursor.close()
                            
                            if existing:
                                # User exists but on different device
                                st.warning("This number is already registered. Link this device to your existing account.")
                                if st.button("🔄 Link Device to Account", type="primary", help="Connect this device to your existing account"):
                                    cursor = conn.cursor()
