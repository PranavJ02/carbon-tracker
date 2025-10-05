# app.py
import streamlit as st
import pandas as pd
import datetime as dt
import hashlib
from supabase import create_client

# ---------------- Supabase Setup ----------------
SUPABASE_URL = "https://dcvfrsofpjmqcmckeauu.supabase.co"      # Your project URL
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRjdmZyc29mcGptcWNtY2tlYXV1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTkwNjg1MDQsImV4cCI6MjA3NDY0NDUwNH0.p3ad-nUXq1eqmVc7SvLoU-uZiVZdm71qSnh8Fhyc88s"                                  # Your anon key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- Constants ----------------
EMISSION_FACTORS = {
    "car": 0.21, "bike": 0.08, "bus": 0.10,
    "electricity": 0.85, "meat_meal": 5.0, "veg_meal": 1.5
}

# ---------------- Utils ----------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------------- User Functions ----------------
def register_user(username, password):
    username = username.strip()
    password = password.strip()
    if not username or not password:
        return False
    # Check if user exists
    res = supabase.table("users").select("*").eq("username", username).execute()
    if res.data:
        return False
    # Insert new user with hashed password
    password_hash = hash_password(password)
    supabase.table("users").insert({
        "username": username,
        "password": password_hash
    }).execute()
    return True

def login_user(username, password):
    username = username.strip()
    password_hash = hash_password(password)
    res = supabase.table("users").select("*").eq("username", username).execute()
    if res.data and res.data[0]["password"] == password_hash:
        return res.data[0]["id"]
    return None

# ---------------- Carbon Entry ----------------
def calculate_emissions(car, bike, bus, elec, meat, veg):
    car_em = car * EMISSION_FACTORS["car"]
    bike_em = bike * EMISSION_FACTORS["bike"]
    bus_em = bus * EMISSION_FACTORS["bus"]
    elec_em = elec * EMISSION_FACTORS["electricity"]
    food_em = meat * EMISSION_FACTORS["meat_meal"] + veg * EMISSION_FACTORS["veg_meal"]
    total = car_em + bike_em + bus_em + elec_em + food_em
    return car_em, bike_em, bus_em, elec_em, food_em, total

def add_entry(user_id, date, car, bike, bus, elec, meat, veg):
    car_em, bike_em, bus_em, elec_em, food_em, total = calculate_emissions(car, bike, bus, elec, meat, veg)
    supabase.table("entries").insert({
        "user_id": user_id,
        "date": date,
        "car_km": car,
        "bike_km": bike,
        "bus_km": bus,
        "electricity": elec,
        "meat_meals": meat,
        "veg_meals": veg,
        "car_emission": car_em,
        "bike_emission": bike_em,
        "bus_emission": bus_em,
        "electricity_emission": elec_em,
        "food_emission": food_em,
        "total_emission": total
    }).execute()
    return total

def get_entries(user_id):
    res = supabase.table("entries").select("*").eq("user_id", user_id).order("date", desc=False).execute()
    if res.data:
        return pd.DataFrame(res.data)
    else:
        return pd.DataFrame()

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Carbon Tracker", layout="centered")
st.title("🌿 Carbon Footprint Tracker")

# Session State
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None

# Sidebar: Login / Register
st.sidebar.title("Account")
option = st.sidebar.selectbox("Choose", ["Login", "Register"])

# --- Register ---
if option == "Register":
    st.subheader("Create a new account")
    username = st.text_input("Username", key="reg_user").strip()
    password = st.text_input("Password", type="password", key="reg_pass").strip()
    if st.button("Register"):
        success = register_user(username, password)
        if success:
            st.success("Registered successfully! Please login from sidebar.")
        else:
            st.error("Username already exists or invalid input.")

# --- Login ---
elif option == "Login":
    st.subheader("Login to your account")
    username = st.text_input("Username", key="login_user").strip()
    password = st.text_input("Password", type="password", key="login_pass").strip()
    if st.button("Login"):
        user_id = login_user(username, password)
        if user_id:
            st.session_state.user_id = user_id
            st.session_state.username = username
            st.success(f"Logged in as {username}")
        else:
            st.error("Invalid username or password.")

# --- Main App ---
if st.session_state.user_id:
    st.write(f"Welcome, **{st.session_state.username}**!")

    st.subheader("Add Today's Carbon Data")
    with st.form("entry_form"):
        car = st.number_input("Car km", min_value=0)
        bike = st.number_input("Bike km", min_value=0)
        bus = st.number_input("Bus km", min_value=0)
        elec = st.number_input("Electricity kWh", min_value=0)
        meat = st.number_input("Meat meals", min_value=0)
        veg = st.number_input("Veg meals", min_value=0)
        submitted = st.form_submit_button("Add Entry")
        if submitted:
            total = add_entry(st.session_state.user_id, dt.date.today().isoformat(),
                              car, bike, bus, elec, meat, veg)
            st.success(f"Entry added! Total CO2 today: {total:.2f} kg")

    st.subheader("Your Carbon Data History")
    df = get_entries(st.session_state.user_id)
    if not df.empty:
        st.dataframe(df[['date','car_km','bike_km','bus_km','electricity','meat_meals','veg_meals','total_emission']])
        st.write("Cumulative CO2:", float(df['total_emission'].sum()), "kg")
        try:
            st.line_chart(df[['date','total_emission']].set_index('date'))
        except:
            pass
    else:
        st.info("No data yet.")

    if st.button("Logout"):
        st.session_state.user_id = None
        st.session_state.username = None
        st.experimental_rerun()

# Message if not logged in
if not st.session_state.user_id:
    st.info("Please login or register from the sidebar.")
