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
st.markdown("""<style>
    /* Your existing CSS styles */
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
