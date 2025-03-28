import streamlit as st
import uuid
from datetime import datetime
import pandas as pd
from db_config import get_connection
from utils import find_customer_from_location
from streamlit_geolocation import streamlit_geolocation

# App Configuration
st.set_page_config(page_title="Time Clock", layout="centered")
st.title("🕒 Time Clock")

# ─────────────────────────────────────────────
# 1. Subcontractor from URL
query_params = st.query_params
sub = query_params.get("sub")

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: `{sub}`")

# ─────────────────────────────────────────────
# 2. Auto-fetch Location
# Fetch location automatically using streamlit-geolocation
location = streamlit_geolocation()

if location and 'latitude' in location and 'longitude' in location:
    lat = location['latitude']
    lon = location['longitude']
    st.session_state["location"] = (lat, lon)
    
    # Display fetched coordinates (optional for debugging)
    st.success(f"📌 Coordinates: ({lat:.5f}, {lon:.5f})")
    
    # ─────────────────────────────────────────────
    # 3. Customer Lookup
    try:
        conn = get_connection()  # Connect to the database
        customer = find_customer_from_location(lat, lon, conn)  # Match location to customer
        
        if not customer:
            st.error("❌ No matching customer found for this location.")
        else:
            st.success(f"🛠️ Work Site: {customer}")
    except Exception as e:
        st.error(f"Database error: {str(e)}")
else:
    st.info("⏳ Waiting for location... Please allow browser access to your location.")
        
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
                    """, sub, name, number, now, lat, lon, device_id)
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
    st.info("⏳ Waiting for location... Please click the location button above.")
