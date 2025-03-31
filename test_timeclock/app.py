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
#st.info("📍 Click the location button below to get started.")

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
                    
                    # Ensure previous result sets are consumed before executing new queries
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
                # 4. Registration with proper cursor handling
                cursor = conn.cursor()  # Reopen a new cursor for registration queries
                cursor.execute("SELECT * FROM SubContractorEmployees WHERE Cookies = ?", device_id)
                record = cursor.fetchone()
                cursor.close()  # Close the cursor after fetching

                if not record:
                    number = st.text_input("📱 Enter your mobile number:")
                    if number:
                        cursor = conn.cursor()  # Open a new cursor for subsequent queries
                        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                        existing = cursor.fetchone()
                        cursor.close()  # Close the cursor after fetching

                        if existing:
                            cursor = conn.cursor()
                            cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                            conn.commit()
                            cursor.close()
                            st.success("✅ Device linked.")
                        else:
                            name = st.text_input("🧑 Enter your name:")
                            if name:
                                cursor = conn.cursor()
                                cursor.execute("""
                                    INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                                    VALUES (?, ?, ?, ?)
                                """, sub, name, number, device_id)
                                conn.commit()
                                cursor.close()
                                st.success("✅ Registered successfully.")
                else:
                    st.info("✅ Device recognized.")

                # ─────────────────────────────────────────────
                # 5. Clock In / Out with proper result set handling
                action = st.radio("Select action:", ["Clock In", "Clock Out"])

                if st.button("Submit", key="submit_btn"):
                    now = datetime.now()
                    
                    cursor = conn.cursor()  # Open a new cursor for clock-in/out queries
                    cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
                    user = cursor.fetchone()
                    cursor.close()

                    if not user:
                        st.error("⚠️ Could not verify user.")
                    else:
                        name, number = user

                        if action == "Clock In":
                            cursor = conn.cursor()
                            cursor.execute("""
                                INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, sub, name, number, now, lat_float, lon_float, device_id)
                            conn.commit()
                            cursor.close()
                            st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                        elif action == "Clock Out":
                            cursor = conn.cursor()
                            cursor.execute("""
                                UPDATE TimeClock SET ClockOut = ?
                                WHERE Cookie = ? AND ClockOut IS NULL
                            """, now, device_id)
                            conn.commit()
                            cursor.close()
                            st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")

            except Exception as e:
                st.error(f"Database error: {str(e)}")
        else:
            st.warning("📍 Please click the location icon above to get started.")
    else:
        st.warning("Incomplete location data. Please try again.")
else:
    pass  # Wait for the user to provide location data.
