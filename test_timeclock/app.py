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

# Custom CSS (unchanged)
st.markdown("""<style>
    [Your existing CSS styles here]
</style>""", unsafe_allow_html=True)

# Logo and title (unchanged)
st.markdown(f"""
<div class="centered-container">
    <img src="https://vdrs.com/wp-content/uploads/2022/08/VDRS-lockup-mod-8-19-22-350.png" style="max-width: 300px; display: block; margin: 0 auto;">
</div>
""", unsafe_allow_html=True)
st.markdown('<div class="main-header"><h1>🕒 Time Clock</h1></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 1. Device identification (unchanged)
stored_device_id = cookies.get("device_id")  
if not stored_device_id:
    device_id = str(uuid.uuid4())
    cookies.set("device_id", device_id)
else:
    device_id = stored_device_id

# ─────────────────────────────────────────────
# 2. Decode subcontractor (unchanged)
query_params = st.query_params
encoded_sub = query_params.get("s")

if not encoded_sub:
    st.error("Missing subcontractor code in URL. Use ?s=[encoded_value]")
    st.stop()

try:
    decoded_bytes = base64.b64decode(urllib.parse.unquote(encoded_sub))
    sub = decoded_bytes.decode('utf-8')
except Exception as e:
    st.error(f"Invalid subcontractor code. Error: {str(e)}")
    st.stop()

st.markdown(f'<div class="centered-container"><div class="subcontractor-info">👷 Subcontractor: {sub}</div></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. Check registration with connection management
try:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
            user_data = cursor.fetchone()
            
            if user_data:
                st.session_state["registered"] = True
                st.session_state["user_name"] = user_data[0]
                st.session_state["user_number"] = user_data[1]
                st.markdown(f'<div class="centered-container"><div class="status-message">✅ Welcome back, {st.session_state["user_name"]}!</div></div>', unsafe_allow_html=True)
                
                # Check active sessions
                with conn.cursor() as session_cursor:
                    session_cursor.execute("SELECT ClockIn FROM TimeClock WHERE Cookie = ? AND ClockOut IS NULL", device_id)
                    active_session = session_cursor.fetchone()
                    st.session_state["clocked_in"] = bool(active_session)
                    if active_session:
                        st.markdown(f'<div class="centered-container"><div class="status-message">⏱️ You are currently clocked in since <span class="time-highlight">{active_session[0]}</span></div></div>', unsafe_allow_html=True)
            else:
                st.session_state["registered"] = False
except Exception as e:
    st.error(f"Database connection error: {str(e)}")
    st.session_state["registered"] = False

# ─────────────────────────────────────────────
# 4. Location handling
st.session_state["fetch_location"] = True

if "fetch_location" in st.session_state and st.session_state["fetch_location"]:
    st.markdown('<div class="location-section"></div>', unsafe_allow_html=True)
    st.info("📍 Please click the location icon below to share your location")
    
    location = streamlit_geolocation()

    if location and location != "No Location Info":
        if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
            lat = location['latitude']
            lon = location['longitude']

            if lat is not None and lon is not None:
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
                    
                    # ─────────────────────────────────────────────
                    # 5. Registration/Clock operations
                    if st.session_state.get("registered"):
                        if st.session_state.get("clocked_in"):
                            st.markdown('<div class="centered-container"><div class="status-message">⏱️ Current Status: Clocked In</div></div>', unsafe_allow_html=True)
                            col1, col2, col3 = st.columns([1, 2, 1])
                            with col2:
                                if st.button("🚪 Clock Out"):
                                    with get_connection() as conn:
                                        with conn.cursor() as cursor:
                                            now = datetime.now()
                                            cursor.execute("UPDATE TimeClock SET ClockOut = ? WHERE Cookie = ? AND ClockOut IS NULL", 
                                                         now, device_id)
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
                        st.markdown('<div class="centered-container"><h3>📝 New User Registration</h3></div>', unsafe_allow_html=True)
                        col1, col2 = st.columns(2)
                        with col1:
                            number = st.text_input("📱 Enter your mobile number:")
                        
                        if number:
                            with get_connection() as conn:
                                with conn.cursor() as cursor:
                                    cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                                    existing = cursor.fetchone()
                                    
                                    if existing:
                                        st.markdown('<div class="centered-container">This number is already registered. Link this device to your existing account.</div>', unsafe_allow_html=True)
                                        if st.button("🔄 Link this device to your account"):
                                            with conn.cursor() as update_cursor:
                                                update_cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", 
                                                                    device_id, number)
                                                conn.commit()
                                                st.session_state["registered"] = True
                                                st.rerun()
                                    else:
                                        with col2:
                                            name = st.text_input("🧑 Enter your name:")
                                        if name and st.button("✅ Register & Clock In"):
                                            with conn.cursor() as insert_cursor:
                                                now = datetime.now()
                                                insert_cursor.execute("""
                                                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                                                    VALUES (?, ?, ?, ?)
                                                """, (sub, name, number, device_id))
                                                insert_cursor.execute("""
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
            else:
                st.warning('Please click above to proceed')
        else:
            st.warning("Incomplete location data. Please try again.")
    else:
        st.info("⏳ Waiting for location... Please click the location icon that appears")

# Existing stored location handling
elif "lat" in st.session_state and "lon" in st.session_state:
    # [Your existing stored location handling code here]
    # (Replace all connection blocks similarly with context managers)

else:
    st.markdown('<div class="centered-container"><div class="status-message">⌛</div></div>', unsafe_allow_html=True)
