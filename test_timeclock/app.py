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

if not sub:
    st.error("Missing subcontractor in URL. Use ?sub=Alpha%20Electrical")
    st.stop()

st.markdown(f"👷 Subcontractor: `{sub}`")
print(f"[DEBUG] Subcontractor from URL: {sub}")

# ─────────────────────────────────────────────
# 2. Initialize device_id
if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())
device_id = st.session_state["device_id"]
print(f"[DEBUG] Device ID: {device_id}")

# ─────────────────────────────────────────────
# 3. Try DB connection
try:
    conn = get_connection()
    cursor = conn.cursor()
    print("[DEBUG] ✅ Database connection successful.")
except Exception as e:
    st.error(f"❌ Could not connect to DB: {e}")
    print(f"[ERROR] Database connection failed: {e}")
    st.stop()

# ─────────────────────────────────────────────
# 4. Fetch location using streamlit-geolocation
st.info("📍 Fetching your location. If prompted, please allow location access.")
location = streamlit_geolocation()

if location and 'latitude' in location and 'longitude' in location:
    lat = location['latitude']
    lon = location['longitude']
    st.session_state["location"] = (lat, lon)
    st.success(f"📌 Coordinates: ({lat:.5f}, {lon:.5f})")
    print(f"[DEBUG] Location fetched: lat={lat}, lon={lon}")

    # Optional: Display map
    st.map(pd.DataFrame([{"lat": lat, "lon": lon}]))

    # ─────────────────────────────────────────────
    # 5. Identify customer site
    try:
        customer = find_customer_from_location(lat, lon, conn)
        if not customer:
            st.error("❌ You're not on a valid job site.")
            print("[DEBUG] No customer matched this location.")
            st.stop()
        else:
            st.success(f"🛠️ Work Site: {customer}")
            print(f"[DEBUG] Customer found: {customer}")
    except Exception as e:
        st.error(f"❌ Error finding customer: {e}")
        print(f"[ERROR] Customer lookup failed: {e}")
        st.stop()

    # ─────────────────────────────────────────────
    # 6. Employee Verification
    try:
        cursor.execute("SELECT * FROM SubContractorEmployees WHERE Cookies = ?", device_id)
        record = cursor.fetchone()
        print(f"[DEBUG] Employee cookie lookup: {record}")

        if not record:
            number = st.text_input("📱 Enter your mobile number:")
            if number:
                cursor.execute("SELECT * FROM SubContractorEmployees WHERE Number = ?", number)
                existing = cursor.fetchone()
                print(f"[DEBUG] Number lookup: {existing}")
                if existing:
                    cursor.execute("UPDATE SubContractorEmployees SET Cookies = ? WHERE Number = ?", device_id, number)
                    conn.commit()
                    st.success("✅ Device linked.")
                    print("[DEBUG] Existing employee, cookie updated.")
                else:
                    name = st.text_input("🧑 Enter your name:")
                    if name:
                        cursor.execute("""
                            INSERT INTO SubContractorEmployees (SubContractor, Employee, Number, Cookies)
                            VALUES (?, ?, ?, ?)
                        """, sub, name, number, device_id)
                        conn.commit()
                        st.success("✅ Registered successfully.")
                        print("[DEBUG] New employee registered.")
        else:
            st.info("✅ Device recognized.")
            print("[DEBUG] Device matched existing employee.")

    except Exception as e:
        st.error(f"❌ Error during registration: {e}")
        print(f"[ERROR] Registration failed: {e}")
        st.stop()

    # ─────────────────────────────────────────────
    # 7. Clock In / Out
    action = st.radio("Select action:", ["Clock In", "Clock Out"])

    if st.button("Submit", key="submit_btn"):
        try:
            now = datetime.now()
            cursor.execute("SELECT Employee, Number FROM SubContractorEmployees WHERE Cookies = ?", device_id)
            user = cursor.fetchone()
            print(f"[DEBUG] User fetched for clocking: {user}")

            if not user:
                st.error("⚠️ Could not verify user.")
                print("[ERROR] User not found during clock in/out.")
            else:
                name, number = user
                if action == "Clock In":
                    cursor.execute("""
                        INSERT INTO TimeClock (SubContractor, Employee, Number, ClockIn, Lat, Lon, Cookie)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, sub, name, number, now, lat, lon, device_id)
                    conn.commit()
                    st.success(f"✅ Clocked in at {now.strftime('%H:%M:%S')}")
                    print("[DEBUG] Clock-in successful.")
                elif action == "Clock Out":
                    cursor.execute("""
                        UPDATE TimeClock SET ClockOut = ?
                        WHERE Cookie = ? AND ClockOut IS NULL
                    """, now, device_id)
                    conn.commit()
                    st.success(f"👋 Clocked out at {now.strftime('%H:%M:%S')}")
                    print("[DEBUG] Clock-out successful.")
        except Exception as e:
            st.error(f"❌ Error during clock-in/out: {e}")
            print(f"[ERROR] Clock-in/out error: {e}")
else:
    st.info("⏳ Waiting for location... Please allow location access.")
    print("[DEBUG] Location not yet available.")
