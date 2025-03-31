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
from streamlit_lottie import st_lottie
import requests
import json

# Initialize cookie controller
cookies = CookieController()

# Page configuration with wide layout for better spacing
st.set_page_config(
    page_title="Time Clock", 
    layout="wide", 
    page_icon="⏰",
    initial_sidebar_state="collapsed"
)

# Load Lottie animations
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# Lottie animations
clock_animation = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_ystsffqy.json")
success_animation = load_lottieurl("https://assets2.lottiefiles.com/packages/lf20_touohxv0.json")
location_animation = load_lottieurl("https://assets3.lottiefiles.com/packages/lf20_UgZWvP.json")

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        margin-bottom: 1rem;
        text-align: center;
    }
    .subheader {
        font-size: 1.5rem;
        margin-bottom: 1rem;
    }
    .card {
        padding: 1.5rem;
        border-radius: 0.7rem;
        background: #f0f2f6;
        box-shadow: 0 0.15rem 1.75rem 0 rgba(58, 59, 69, 0.15);
        margin: 1rem 0;
    }
    .dark-card {
        background: #262730;
        color: #fff;
    }
    .big-button {
        font-size: 1.2rem !important;
        height: 3rem !important;
        margin: 1rem 0 !important;
    }
    .clock-display {
        font-size: 2rem;
        font-weight: bold;
        text-align: center;
        margin: 1rem 0;
    }
    .centered {
        display: flex;
        justify-content: center;
    }
    .location-section {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid #e6e6e6;
    }
    .status-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    .divider {
        height: 3px;
        background-color: #e6e6e6;
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# App header with animation
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    st.markdown('<div class="main-header">🕒 Time Clock</div>', unsafe_allow_html=True)
    st_lottie(clock_animation, height=150, key="clock_anim")

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

# Subcontractor info in a card
st.markdown(f"""
<div class="card">
    <h3>👷 Subcontractor: {sub}</h3>
    <p>Time Clock System</p>
</div>
""", unsafe_allow_html=True)

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
st.session_state["fetch_location"] = True

if "fetch_location" in st.session_state and st.session_state["fetch_location"]:
    # Add a visually appealing location section
    st.markdown('<div class="location-section"></div>', unsafe_allow_html=True)
    
    location_col1, location_col2 = st.columns([1, 3])
    with location_col1:
        st_lottie(location_animation, height=150, key="location_anim")
    with location_col2:
        st.markdown('<h3>📍 Location Services</h3>', unsafe_allow_html=True)
        st.write("We need your location to identify your work site.")
        location = streamlit_geolocation()

    if location and location != "No Location Info":
        if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
            lat = location['latitude']
            lon = location['longitude']

            if lat is not None and lon is not None:
                # Display coordinates and map in a card
                st.markdown(f"""
                <div class="card">
                    <h3>📌 Your Location</h3>
                    <p>Coordinates: {lat}, {lon}</p>
                </div>
                """, unsafe_allow_html=True)
                
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
                    
                    # Display work site in a card
                    st.markdown(f"""
                    <div class="card">
                        <h3>🛠️ Work Site</h3>
                        <p>{customer}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Add a visual divider
                    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

                    # ─────────────────────────────────────────────
                    # 6. User registration or clock in/out
                    if st.session_state.get("registered", False):
                        # User is already registered - show clock in/out options
                        if st.session_state.get("clocked_in", False):
                            # User is already clocked in - offer clock out
                            st.markdown(f"""
                            <div class="card dark-card">
                                <h3>⏱️ Current Status: Clocked In</h3>
                                <p>You are currently on the clock at {customer}.</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Enhanced clock out button
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                if st.button("🚪 Clock Out", key="clock_out_btn", use_container_width=True):
                                    now = datetime.now()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE TimeClock SET ClockOut = ?
                                        WHERE Cookie = ? AND ClockOut IS NULL
                                    """, now, device_id)
                                    conn.commit()
                                    cursor.close()
                                    
                                    # Show success animation and message
                                    st_lottie(success_animation, height=200, key="success_anim")
                                    st.success(f"👋 Clocked out successfully at {now.strftime('%H:%M:%S')}")
                                    st.session_state["clocked_in"] = False
                        else:
                            # User is registered but not clocked in - offer clock in
                            st.markdown(f"""
                            <div class="card dark-card">
                                <h3>⏱️ Current Status: Not Clocked In</h3>
                                <p>Ready to start work at {customer}?</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Enhanced clock in button
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                if st.button("⏱️ Clock In", key="clock_in_btn", type="primary", use_container_width=True):
                                    now = datetime.now()
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, sub, st.session_state["user_name"], st.session_state["user_number"], 
                                       now, lat_float, lon_float, device_id)
                                    conn.commit()
                                    cursor.close()
                                    
                                    # Show celebration effects
                                    st_lottie(success_animation, height=200, key="success_anim")
                                    st.balloons()
                                    st.success(f"✅ Clocked in successfully at {now.strftime('%H:%M:%S')}")
                                    st.session_state["clocked_in"] = True
                    else:
                        # New user registration with improved UI
                        st.markdown('<h2 class="subheader">📝 New User Registration</h2>', unsafe_allow_html=True)
                        
                        # Registration form in columns for better layout
                        col1, col2 = st.columns(2)
                        with col1:
                            number = st.text_input("📱 Mobile Number:", placeholder="Enter your mobile number")
                        
                        if number:
                            # Check if number exists but on a different device
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                            existing = cursor.fetchone()
                            cursor.close()
                            
                            if existing:
                                # User exists but on different device
                                st.info("⚠️ This number is already registered. Link this device to your existing account.")
                                if st.button("🔄 Link Device to Account", type="primary", use_container_width=True):
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                                    conn.commit()
                                    cursor.close()
                                    st.success("✅ Device linked successfully!")
                                    # Show animation
                                    st_lottie(success_animation, height=150, key="link_success")
                                    st.rerun()
                            else:
                                # New user registration
                                with col2:
                                    name = st.text_input("🧑 Full Name:", placeholder="Enter your full name")
                                
                                if name:
                                    if st.button("✅ Register & Clock In", type="primary", use_container_width=True):
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
                                        
                                        # Show celebration effects
                                        st_lottie(success_animation, height=200, key="registration_success")
                                        st.balloons()
                                        st.success(f"✅ Welcome aboard! You've been registered and clocked in at {now.strftime('%H:%M:%S')}")
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
        # More visually appealing waiting message with animation
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info("⏳ Waiting for location...")
            st_lottie(location_animation, height=200, key="waiting_location")
else:
    st.info("⌛ Click the location button above to get started.")

# Footer
st.markdown("""
<div style="text-align: center; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e6e6e6;">
    <p>© 2025 Time Clock System</p>
</div>
""", unsafe_allow_html=True)
