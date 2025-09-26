# app.py
import streamlit as st
import pandas as pd
import sqlite3
import datetime as dt
import os

DB_FILE = "carbon.db"
EMISSION_FACTORS = {
    "car": 0.21, "bike": 0.08, "bus": 0.10,
    "electricity": 0.85, "meat_meal": 5.0, "veg_meal": 1.5
}

# ---------------- DB setup ----------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        car_km REAL, bike_km REAL, bus_km REAL,
        electricity REAL, meat_meals INTEGER, veg_meals INTEGER,
        car_emission REAL, bike_emission REAL, bus_emission REAL,
        electricity_emission REAL, food_emission REAL, total_emission REAL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

def calculate_emissions(car, bike, bus, elec, meat, veg):
    car_em = car*EMISSION_FACTORS["car"]
    bike_em = bike*EMISSION_FACTORS["bike"]
    bus_em = bus*EMISSION_FACTORS["bus"]
    elec_em = elec*EMISSION_FACTORS["electricity"]
    food_em = meat*EMISSION_FACTORS["meat_meal"] + veg*EMISSION_FACTORS["veg_meal"]
    total = car_em + bike_em + bus_em + elec_em + food_em
    return car_em, bike_em, bus_em, elec_em, food_em, total

def add_entry(user_id, date, car, bike, bus, elec, meat, veg):
    car_em, bike_em, bus_em, elec_em, food_em, total = calculate_emissions(car, bike, bus, elec, meat, veg)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""INSERT INTO entries 
        (user_id, date, car_km, bike_km, bus_km, electricity, meat_meals, veg_meals, 
        car_emission, bike_emission, bus_emission, electricity_emission, food_emission, total_emission)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, date, car, bike, bus, elec, meat, veg, car_em, bike_em, bus_em, elec_em, food_em, total)
    )
    conn.commit()
    conn.close()
    return total

# ---------------- Streamlit UI ----------------
st.title("🌿 Carbon Footprint Tracker")
init_db()

# --- Login/Register ---
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()

option = st.sidebar.selectbox("Login/Register", ["Login", "Register"])

if option == "Register":
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Register"):
        try:
            c.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, password))
            conn.commit()
            st.success("Registered! Please login.")
        except:
            st.error("Username already exists.")
elif option == "Login":
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        result = c.fetchone()
        if result:
            user_id = result[0]
            st.success(f"Logged in as {username}")

            # --- Add Entry Form ---
            st.subheader("Add Today's Carbon Data")
            with st.form("entry_form"):
                car = st.number_input("Car km", 0)
                bike = st.number_input("Bike km", 0)
                bus = st.number_input("Bus km", 0)
                elec = st.number_input("Electricity kWh", 0)
                meat = st.number_input("Meat meals", 0)
                veg = st.number_input("Veg meals", 0)
                submitted = st.form_submit_button("Add Entry")
                if submitted:
                    total = add_entry(user_id, dt.date.today().isoformat(), car, bike, bus, elec, meat, veg)
                    st.success(f"Entry added! Total CO2 today: {total:.2f} kg")

            # --- Show All Entries ---
            st.subheader("Your Carbon Data History")
            df = pd.read_sql_query(f"SELECT * FROM entries WHERE user_id={user_id}", conn)
            if not df.empty:
                st.dataframe(df[['date','car_km','bike_km','bus_km','electricity','meat_meals','veg_meals','total_emission']])
                st.write("Cumulative CO2:", df['total_emission'].sum(), "kg")
            else:
                st.info("No data yet.")
        else:
            st.error("Invalid username or password.")

conn.close()
