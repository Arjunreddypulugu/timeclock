import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation

st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")

if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())
device_id = st.session_state["device_id"]

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: {sub}")

# ─────────────────────────────────────────────
# 2. Location handling
#st.info(" Click the location button below to get started.")

# Get location using streamlit-geolocation
location = streamlit_geolocation()

# Only proceed if we have valid location data
if location and location != "No Location Info":
    if isinstance(location, dict) and 'latitude' in location and 'longitude' in location:
        if location['latitude'] is not None and location['longitude'] is not None:
            # Extract coordinates
            lat = location['latitude']
            lon = location['longitude']
            
            # Display location info (without format specifiers that would cause errors)
            st.success(f"📌 Coordinates: {lat}, {lon}")
            
            # Display map
            try:
                map_df = pd.DataFrame([{"lat": lat, "lon": lon}])
                st.map(map_df)
            except Exception as e:
                st.warning(f"Could not display map: {str(e)}")
            
            # ─────────────────────────────────────────────
            # 3. Customer match with robust error handling
            try:
                conn = get_connection()
                cursor = conn.cursor()
                
                # Convert location to float to prevent comparison errors
                try:
                    lat_float = float(lat)
                    lon_float = float(lon)
                    customer = find_customer_from_location(lat_float, lon_float, conn)
                except (TypeError, ValueError) as e:
                    st.error(f"Invalid location format: {str(e)}")
                    st.stop()
                
                if not customer:
                    st.error("❌ Not a valid job site.")
                    st.stop()
                else:
                    st.success(f"🛠️ Work Site: {customer}")
                
                # ─────────────────────────────────────────────
                # 4. Registration
                cursor.execute("SELECT * FROM SubContractorEmployees WHERE Cookies = ?", device_id)
                record = cursor.fetchone()
                
                if not record:
                    number = st.text_input("📱 Enter your mobile number:")
                    if number:
                        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                        existing = cursor.fetchone()
                        if existing:
                            cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                            conn.commit()
                            st.success("✅ Device linked.")
                        else:
                            name = st.text_input("🧑 Enter your name:")
                            if name:
                                cursor.execute("""
                                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                                    VALUES (?, ?, ?, ?)
                                """, sub, name, number, device_id)
                                conn.commit()
                                st.success("✅ Registered successfully.")
                else:
                    st.info("✅ Device recognized.")
                
                # ─────────────────────────────────────────────
                # 5. Clock In / Out
                action = st.radio("Select action:", ["Clock In", "Clock Out"])
                
                if st.button("Submit", key="submit_btn"):
                    now = datetime.now()
                    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
                    user = cursor.fetchone()
                    
                    if not user:
                        st.error("⚠️ Could not verify user.")
                    else:
                        name, number = user
                        if action == "Clock In":
                            cursor.execute("""
                                INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, sub, name, number, now, lat_float, lon_float, device_id)
                            conn.commit()
                            st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                        elif action == "Clock Out":
                            cursor.execute("""
                                UPDATE TimeClock SET ClockOut = ?
                                WHERE Cookie = ? AND ClockOut IS NULL
                            """, now, device_id)
                            conn.commit()
                            st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                            
            except Exception as e:
                st.error(f"Database error: {str(e)}")
        else:
            st.warning("Waiting patiently, for you to click the icon 📍 above.")
    else:
        st.warning("Incomplete location data. Please try again.")
else:
    # Just wait for the location to be provided
    pass
