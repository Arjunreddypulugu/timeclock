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
import streamlit.components.v1 as components
from streamlit_lottie import st_lottie
import requests

# Initialize cookie controller
cookies = CookieController()

# Function to load Lottie animations
def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# Function to show confetti
def show_confetti():
    components.html(
        """
        <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.5.1/dist/confetti.browser.min.js"></script>
        <script>
        confetti({
            particleCount: 100,
            spread: 70,
            origin: { y: 0.6 }
        });
        </script>
        """,
        height=0,
    )

# Page configuration
st.set_page_config(
    page_title="Time Clock",
    page_icon="⏰",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Add custom CSS for better styling
st.markdown("""
<style>
    .main {
        padding: 1rem 1rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        height: 3rem;
        font-weight: bold;
        margin-top: 1rem;
    }
    div[data-testid="stSuccess"] {
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }
    h1 {
        text-align: center;
        margin-bottom: 2rem;
    }
    .subcontractor {
        font-size: 1.2rem;
        text-align: center;
        margin-bottom: 2rem;
        background-color: rgba(255, 255, 255, 0.1);
        padding: 0.5rem;
        border-radius: 10px;
    }
    .card {
        background-color: rgba(38, 39, 48, 0.2); 
        padding: 15px; 
        border-radius: 10px; 
        margin-bottom: 20px;
    }
    .card-title {
        text-align: center; 
        margin-top: 0;
    }
    .card-content {
        text-align: center; 
        margin-bottom: 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Device identification using cookies
stored_device_id = cookies.get("device_id")  

if not stored_device_id:
    # No cookie found, generate a new device ID
    device_id = str(uuid.uuid4())
    # Set cookie
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

# Display subcontractor name with better styling
st.markdown(f"<div class='subcontractor'>👷 Subcontractor: {sub}</div>", unsafe_allow_html=True)

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
        
        # User card with welcome message
        st.markdown(f"""
        <div class="card">
            <h3 class="card-title">✅ Welcome back!</h3>
            <p class="card-content">
                {st.session_state['user_name']}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Check if already clocked in
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ClockIn FROM TimeClock 
            WHERE Cookie = ? AND ClockOut IS NULL
        """, device_id)
        active_session = cursor.fetchone()
        cursor.close()
        
        if active_session:
            # Calculate time worked
            now = datetime.now()
            clock_in_time = datetime.strptime(str(active_session[0]), "%Y-%m-%d %H:%M:%S")
            elapsed = now - clock_in_time
            hours, remainder = divmod(elapsed.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # Show time worked in a card
            st.markdown(f"""
            <div class="card">
                <h3 class="card-title">⏱️ Current Session</h3>
                <p class="card-content" style="font-size: 1.2rem; font-weight: bold; margin-bottom: 5px;">
                    Time worked: {hours}h {minutes}m
                </p>
                <p class="card-content" style="color: #9e9e9e; margin-top: 0;">
                    Started at {clock_in_time.strftime('%H:%M:%S')}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
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
st.button("📍 Click to Fetch Location", type="primary", key="fetch_location_btn")

if st.session_state.get("fetch_location_btn", False):
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
                    
                    # Display customer info with better styling
                    st.markdown(f"""
                    <div class="card">
                        <h3 class="card-title">🛠️ Work Site</h3>
                        <p class="card-content">{customer}</p>
                    </div>
                    """, unsafe_allow_html=True)

                    # ─────────────────────────────────────────────
                    # 6. User registration or clock in/out
                    if st.session_state.get("registered", False):
                        # User is already registered - show clock in/out options
                        if st.session_state.get("clocked_in", False):
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
                                
                                # Show confetti and success animation
                                show_confetti()
                                success_lottie = load_lottieurl("https://assets2.lottiefiles.com/packages/lf20_touohxv0.json")
                                st_lottie(success_lottie, height=120, key="success_animation")
                                
                                st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                                st.session_state["clocked_in"] = False
                        else:
                            # User is registered but not clocked in - offer clock in
                            if st.button("⏱️ Clock In", type="primary"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, sub, st.session_state["user_name"], st.session_state["user_number"], 
                                   now, lat_float, lon_float, device_id)
                                conn.commit()
                                cursor.close()
                                
                                # Show confetti and success animation
                                show_confetti()
                                success_lottie = load_lottieurl("https://assets9.lottiefiles.com/packages/lf20_jbrw3hcz.json")
                                st_lottie(success_lottie, height=120, key="success_animation")
                                
                                st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                                st.session_state["clocked_in"] = True
                    else:
                        # New user registration with improved UI
                        st.markdown("""
                        <div class="card">
                            <h3 class="card-title">📝 New User Registration</h3>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            number = st.text_input("📱 Mobile Number:", placeholder="Enter your number")
                        with col2:
                            if number:
                                name = st.text_input("🧑 Your Name:", placeholder="Enter your name")
                        
                        if number:
                            # Check if number exists but on a different device
                            cursor = conn.cursor()
                            cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                            existing = cursor.fetchone()
                            cursor.close()
                            
                            if existing:
                                # User exists but on different device
                                if st.button("🔄 Link this device to your account", type="primary"):
                                    cursor = conn.cursor()
                                    cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                                    conn.commit()
                                    cursor.close()
                                    
                                    # Show success animation
                                    success_lottie = load_lottieurl("https://assets3.lottiefiles.com/packages/lf20_qpwbiyxf.json")
                                    st_lottie(success_lottie, height=120, key="link_success")
                                    
                                    st.success("✅ Device linked. You can now clock in/out.")
                                    st.rerun()
                            elif name:
                                # New user registration
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
                                    
                                    # Show confetti and success animation
                                    show_confetti()
                                    success_lottie = load_lottieurl("https://assets1.lottiefiles.com/packages/lf20_vyr9sizf.json")
                                    st_lottie(success_lottie, height=150, key="register_success")
                                    
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
        # Show loading animation
        loading_lottie = load_lottieurl("https://assets3.lottiefiles.com/packages/lf20_x62chJ.json")
        st_lottie(loading_lottie, height=200, key="location_loading")
        st.info("⏳ Getting your location...")
else:
    st.info("⌛ Click the location button above to get started.")

# Add feedback section
if st.session_state.get("registered", False):
    st.markdown("---")
    st.markdown("### How was your experience today?")
    feedback = st.radio("Rate your experience:", options=["😞", "😐", "🙂", "😀"], horizontal=True)
    
    if st.button("Submit Feedback"):
        st.success("Thanks for your feedback! We're constantly improving.")
