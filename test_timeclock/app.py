import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation
import streamlit.components.v1 as components

st.set_page_config(page_title="Time Clock", layout="centered", page_icon="⏰", initial_sidebar_state="collapsed")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")

if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())
device_id = st.session_state["device_id"]

# Store device ID in browser's local storage for persistence
components.html("""
<script>
    // Check if we already have a stored device ID
    const storedDeviceId = localStorage.getItem('timeClockDeviceId');
    
    if (storedDeviceId) {
        // Use existing ID
        console.log("Using existing device ID");
    } else {
        // Store the server-generated ID
        const serverDeviceId = window.parent.streamlitPythonData["device_id"];
        localStorage.setItem('timeClockDeviceId', serverDeviceId);
        console.log("Storing new device ID");
    }
</script>
""", height=0, width=0)

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: {sub}")

# ─────────────────────────────────────────────
# 2. Location handling
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
                # 3. Customer match with robust cursor management
                try:
                    conn = get_connection()
                    cursor = conn.cursor()

                    # Convert location to float to prevent comparison errors
                    try:
                        lat_float = float(lat)
                        lon_float = float(lon)
                        
                        # Find customer based on location
                        customer = find_customer_from_location(lat_float, lon_float, conn)
                        cursor.close()  # Close the cursor after use
                        
                    except (TypeError, ValueError) as e:
                        st.error(f"Invalid location format: {str(e)}")
                        st.stop()

                    if not customer:
                        st.error("❌ Not a valid job site.")
                        st.stop()
                    else:
                        st.success(f"🛠️ Work Site: {customer}")

                    # ─────────────────────────────────────────────
                    # 4. Check if device is already registered
                    cursor = conn.cursor()
                    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
                    registered_user = cursor.fetchone()
                    cursor.close()

                    if registered_user:
                        # Device already registered to a user
                        employee_name, employee_number = registered_user
                        st.info(f"✅ Device registered to: {employee_name}")
                        
                        # Check if user is already clocked in
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT ClockIn FROM TimeClock 
                            WHERE Cookie = ? AND ClockOut IS NULL
                        """, device_id)
                        active_session = cursor.fetchone()
                        cursor.close()
                        
                        if active_session:
                            # User is clocked in, show clock out option
                            clock_in_time = active_session[0]
                            st.warning(f"⏰ You are currently clocked in since {clock_in_time}")
                            
                            if st.button("🚪 Clock Out", type="primary"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    UPDATE TimeClock SET ClockOut = ?
                                    WHERE Cookie = ? AND ClockOut IS NULL
                                """, now, device_id)
                                conn.commit()
                                cursor.close()
                                st.balloons()
                                st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                        else:
                            # User is not clocked in, show clock in option
                            if st.button("⏱️ Clock In", type="primary"):
                                now = datetime.now()
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, sub, employee_name, employee_number, now, lat_float, lon_float, device_id)
                                conn.commit()
                                cursor.close()
                                st.balloons()
                                st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                    else:
                        # New user registration needed
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
                                        
                                        st.balloons()
                                        st.success(f"✅ Registered and clocked in at {now.strftime('%H:%M:%S')}")

                except Exception as e:
                    st.error(f"Database error: {str(e)}")
                    st.exception(e)
            else:
                st.warning("📍 Location coordinates are missing. Please try again.")
        else:
            st.warning("Incomplete location data. Please try again.")
    else:
        st.info("⏳ Waiting for location...")
else:
    st.info("⌛ Waiting for location... Please click the location button above.")
