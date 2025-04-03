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

# Custom CSS styles (unchanged)
#st.markdown("""<style>
    #/* Your existing CSS styles */
#</style>""", unsafe_allow_html=True)

# Add this updated CSS block at the beginning of your app.py
st.markdown("""<style>
    /* Professional Color Scheme */
    :root {
        --primary: #2c3e50;
        --secondary: #3498db;
        --background: #f8f9fa;
        --text: #2c3e50;
        --success: #27ae60;
        --warning: #f1c40f;
        --error: #e74c3c;
    }

    /* Modern Typography */
    html, body, .stApp {
        font-family: 'Segoe UI', system-ui, sans-serif;
        line-height: 1.6;
    }

    .main-header h1 {
        font-weight: 600;
        letter-spacing: -0.5px;
        margin: 0.8rem 0;
        color: var(--primary);
    }

    /* Card-like Containers */
    .status-message, .info-card, .subcontractor-info {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border: none !important;
        transition: transform 0.2s ease;
    }

    .status-message:hover, .info-card:hover {
        transform: translateY(-2px);
    }

    /* Enhanced Form Elements */
    .stTextInput input, .stTextInput textarea {
        border: 1px solid #dfe6e9 !important;
        border-radius: 8px !important;
        padding: 0.8rem !important;
    }

    .stButton>button {
        border-radius: 8px !important;
        padding: 0.75rem 1.5rem !important;
        font-weight: 500 !important;
        transition: all 0.3s ease !important;
    }

    .stButton>button:enabled:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Professional Status Indicators */
    .status-message {
        background: white !important;
        border-left: 4px solid var(--secondary) !important;
        text-align: left !important;
        padding: 1.25rem !important;
    }

    .time-highlight {
        color: var(--secondary) !important;
        background: transparent !important;
        font-weight: 600;
        padding: 0 !important;
    }

    /* Map Container Enhancements */
    .stMap {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e0e0e0 !important;
    }

    /* Grid Layout Improvements */
    .stColumns {
        gap: 1rem;
    }

    /* Subtle Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .centered-container {
        animation: fadeIn 0.4s ease-out;
    }

    /* Professional Badges */
    .subcontractor-info {
        background: var(--primary) !important;
        color: white !important;
        font-size: 1.1rem;
        letter-spacing: 0.5px;
        margin: 1.5rem 0;
    }

    /* Enhanced Input Labels */
    .stTextInput label, .stNumberInput label {
        font-weight: 500 !important;
        color: var(--text) !important;
        margin-bottom: 0.5rem !important;
    }

    /* Consistent Spacing */
    .block-container {
        padding: 2rem 1rem;
    }

    /* Error Message Styling */
    .stAlert {
        border-radius: 8px !important;
        border-left: 4px solid var(--error) !important;
    }
</style>""", unsafe_allow_html=True)


# Logo and title
st.markdown(f"""
<div class="centered-container">
    <img src="https://vdrs.com/wp-content/uploads/2022/08/VDRS-lockup-mod-8-19-22-350.png" style="max-width: 300px; display: block; margin: 0 auto;">
</div>
""", unsafe_allow_html=True)
st.markdown('<div class="main-header"><h1>🕒 Time Clock</h1></div>', unsafe_allow_html=True)

# Device identification
stored_device_id = cookies.get("device_id")  
device_id = stored_device_id or str(uuid.uuid4())
if not stored_device_id:
    cookies.set("device_id", device_id)

# Decode subcontractor from URL
query_params = st.query_params
encoded_sub = query_params.get("s")

if not encoded_sub:
    st.error("Missing subcontractor code in URL. Use ?s=[encoded_value]")
    st.stop()

try:
    decoded_bytes = base64.b64decode(urllib.parse.unquote(encoded_sub))
    sub = decoded_bytes.decode('utf-8')
except Exception as e:
    st.error(f"Invalid subcontractor code: {str(e)}")
    st.stop()

st.markdown(f'<div class="centered-container"><div class="subcontractor-info">👷 Subcontractor: {sub}</div></div>', unsafe_allow_html=True)

# User registration check
try:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
            user_data = cursor.fetchone()
            
            if user_data:
                st.session_state.update({
                    "registered": True,
                    "user_name": user_data[0],
                    "user_number": user_data[1]
                })
                
                # Check for active sessions by phone number
                cursor.execute("""
                    SELECT TOP 1 ClockIn FROM TimeClock 
                    WHERE Number = ? AND ClockOut IS NULL 
                    ORDER BY ClockIn DESC
                """, user_data[1])
                active_session = cursor.fetchone()
                
                if active_session:
                    st.markdown(f'<div class="centered-container"><div class="status-message">⏱️ Active session: Clocked in since <span class="time-highlight">{active_session[0]}</span></div></div>', unsafe_allow_html=True)
                    st.session_state["clocked_in"] = True
                else:
                    st.session_state["clocked_in"] = False
                
                st.markdown(f'<div class="centered-container"><div class="status-message">✅ Welcome back, {user_data[0]}!</div></div>', unsafe_allow_html=True)
            else:
                st.session_state["registered"] = False
except Exception as e:
    st.error(f"Database error: {str(e)}")
    st.session_state["registered"] = False

# Location handling
if "fetch_location" not in st.session_state:
    st.session_state["fetch_location"] = True

if st.session_state.get("fetch_location"):
    st.markdown('<div class="location-section"></div>', unsafe_allow_html=True)
    st.info("📍 Please click the location icon below to share your location")
    
    location = streamlit_geolocation()

    if location and isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
        lat = location['latitude']
        lon = location['longitude']
        
        if lat and lon:
            st.session_state.update({
                "lat": lat,
                "lon": lon,
                "lat_float": float(lat),
                "lon_float": float(lon)
            })
            
            st.markdown(f'<div class="centered-container"><div class="info-card">📌 Your Location: {lat}, {lon}</div></div>', unsafe_allow_html=True)
            st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))
            
            try:
                customer = find_customer_from_location(st.session_state["lat_float"], st.session_state["lon_float"])
                if not customer:
                    st.error("❌ Not a valid job site.")
                    st.stop()
                
                st.session_state["customer"] = customer
                st.markdown(f'<div class="centered-container"><div class="info-card">🛠️ Work Site: {customer}</div></div>', unsafe_allow_html=True)

                # Main workflow
                if st.session_state.get("registered"):
                    if st.session_state.get("clocked_in"):
                        # Clock Out UI
                        st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Clocked In</div></div>', unsafe_allow_html=True)
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            if st.button("🚪 Clock Out"):
                                with get_connection() as conn:
                                    with conn.cursor() as cursor:
                                        now = datetime.now()
                                        cursor.execute("""
                                            UPDATE TimeClock SET ClockOut = ? 
                                            WHERE Number = ? AND ClockOut IS NULL
                                        """, (now, st.session_state["user_number"]))
                                        conn.commit()
                                        st.session_state["clocked_in"] = False
                                        st.markdown(f'<div class="centered-container"><div class="status-message">👋 Clocked out at <span class="time-highlight">{now.strftime("%H:%M:%S")}</span></div></div>', unsafe_allow_html=True)
                                        st.rerun()
                    else:
                        # Clock In UI
                        st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Not Clocked In</div></div>', unsafe_allow_html=True)
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            if st.button("⏱️ Clock In"):
                                with get_connection() as conn:
                                    with conn.cursor() as cursor:
                                        now = datetime.now()
                                        cursor.execute("""
                                            INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, (sub, st.session_state["user_name"], st.session_state["user_number"], 
                                            now, st.session_state["lat_float"], st.session_state["lon_float"], device_id))
                                        conn.commit()
                                        st.session_state["clocked_in"] = True
                                        st.markdown(f'<div class="centered-container"><div class="status-message">✅ Clocked in at <span class="time-highlight">{now.strftime("%H:%M:%S")}</span></div></div>', unsafe_allow_html=True)
                                        st.balloons()
                                        st.rerun()
                else:
                    # New User Registration
                    st.markdown('<div class="centered-container"><h3>📝 New User Registration</h3></div>', unsafe_allow_html=True)
                    col1, col2 = st.columns(2)
                    with col1:
                        number = st.text_input("📱 Enter your mobile number:")
                    
                    if number:
                        with get_connection() as conn:
                            with conn.cursor() as cursor:
                                # Check existing number
                                cursor.execute("""
                                    SELECT Employee, Cookies 
                                    FROM SubContractorEmployees 
                                    WHERE Number = ?
                                """, number)
                                existing = cursor.fetchone()
                                
                                if existing:
                                    # Update device ID and check sessions
                                    cursor.execute("""
                                        UPDATE SubContractorEmployees 
                                        SET Cookies = ? 
                                        WHERE Number = ?
                                    """, (device_id, number))
                                    conn.commit()
                                    
                                    # Check for existing session
                                    cursor.execute("""
                                        SELECT TOP 1 ClockIn FROM TimeClock 
                                        WHERE Number = ? AND ClockOut IS NULL
                                    """, number)
                                    active_session = cursor.fetchone()
                                    
                                    st.session_state.update({
                                        "registered": True,
                                        "user_name": existing.Employee,
                                        "user_number": number,
                                        "clocked_in": bool(active_session)
                                    })
                                    st.rerun()
                                else:
                                    with col2:
                                        name = st.text_input("🧑 Enter your name:")
                                    if name and st.button("✅ Register & Clock In"):
                                        now = datetime.now()
                                        cursor.execute("""
                                            INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                                            VALUES (?, ?, ?, ?)
                                        """, (sub, name, number, device_id))
                                        cursor.execute("""
                                            INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, (sub, name, number, now, 
                                            st.session_state["lat_float"], st.session_state["lon_float"], device_id))
                                        conn.commit()
                                        st.session_state.update({
                                            "registered": True,
                                            "user_name": name,
                                            "user_number": number,
                                            "clocked_in": True
                                        })
                                        st.markdown(f'<div class="centered-container"><div class="status-message">✅ Registered and clocked in at <span class="time-highlight">{now.strftime("%H:%M:%S")}</span></div></div>', unsafe_allow_html=True)
                                        st.balloons()
                                        st.rerun()
            except Exception as e:
                st.error(f"Database error: {str(e)}")

# Handle existing location data
elif "lat" in st.session_state and "lon" in st.session_state:
    st.markdown(f'<div class="centered-container"><div class="info-card">📌 Your Location: {st.session_state["lat"]}, {st.session_state["lon"]}</div></div>', unsafe_allow_html=True)
    st.map(pd.DataFrame([{"lat": st.session_state["lat"], "lon": st.session_state["lon"]}]))
    
    if "customer" in st.session_state:
        st.markdown(f'<div class="centered-container"><div class="info-card">🛠️ Work Site: {st.session_state["customer"]}</div></div>', unsafe_allow_html=True)

    # Handle clock in/out with existing location
    if st.session_state.get("registered"):
        if st.session_state.get("clocked_in"):
            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Clocked In</div></div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚪 Clock Out"):
                    with get_connection() as conn:
                        with conn.cursor() as cursor:
                            now = datetime.now()
                            cursor.execute("""
                                UPDATE TimeClock SET ClockOut = ? 
                                WHERE Number = ? AND ClockOut IS NULL
                            """, (now, st.session_state["user_number"]))
                            conn.commit()
                            st.session_state["clocked_in"] = False
                            st.markdown(f'<div class="centered-container"><div class="status-message">👋 Clocked out at <span class="time-highlight">{now.strftime("%H:%M:%S")}</span></div></div>', unsafe_allow_html=True)
                            st.rerun()
        else:
            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Not Clocked In</div></div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("⏱️ Clock In"):
                    with get_connection() as conn:
                        with conn.cursor() as cursor:
                            now = datetime.now()
                            cursor.execute("""
                                INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (sub, st.session_state["user_name"], st.session_state["user_number"], 
                                now, st.session_state["lat_float"], st.session_state["lon_float"], device_id))
                            conn.commit()
                            st.session_state["clocked_in"] = True
                            st.markdown(f'<div class="centered-container"><div class="status-message">✅ Clocked in at <span class="time-highlight">{now.strftime("%H:%M:%S")}</span></div></div>', unsafe_allow_html=True)
                            st.balloons()
                            st.rerun()

else:
    st.markdown('<div class="centered-container"><div class="status-message">⌛</div></div>', unsafe_allow_html=True)
