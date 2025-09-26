# app.py
import streamlit as st
import pandas as pd
import sqlite3
import datetime as dt
import hashlib
import os

DB_FILE = "carbon.db"
EMISSION_FACTORS = {
    "car": 0.21, "bike": 0.08, "bus": 0.10,
    "electricity": 0.85, "meat_meal": 5.0, "veg_meal": 1.5
}

# ---------------- DB setup ----------------
def init_db():
    # create DB and tables if not exist
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
    # visits / events log
    c.execute("""
    CREATE TABLE IF NOT EXISTS visits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event TEXT,         -- 'register', 'login', 'page_view', etc.
        info TEXT,          -- optional extra info
        timestamp TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO entries 
        (user_id, date, car_km, bike_km, bus_km, electricity, meat_meals, veg_meals, 
        car_emission, bike_emission, bus_emission, electricity_emission, food_emission, total_emission)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, date, car, bike, bus, elec, meat, veg, car_em, bike_em, bus_em, elec_em, food_em, total))
    conn.commit()
    conn.close()
    return total

def get_entries(user_id):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM entries WHERE user_id=?", conn, params=(user_id,))
    conn.close()
    return df

def log_event(user_id, event, info=""):
    """Insert a row into visits table with timestamp"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    ts = dt.datetime.utcnow().isoformat()  # store UTC ISO timestamp
    c.execute("INSERT INTO visits (user_id, event, info, timestamp) VALUES (?,?,?,?)",
              (user_id, event, info, ts))
    conn.commit()
    conn.close()

def get_all_users_df():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT id, username FROM users ORDER BY id", conn)
    conn.close()
    return df

def get_visits_df(limit=1000):
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT v.id, v.user_id, u.username, v.event, v.info, v.timestamp "
                           "FROM visits v LEFT JOIN users u ON v.user_id = u.id "
                           "ORDER BY v.timestamp DESC LIMIT ?", conn, params=(limit,))
    conn.close()
    return df

def get_login_counts():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT user_id, COUNT(*) AS logins FROM visits WHERE event='login' GROUP BY user_id", conn)
    conn.close()
    return df

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Carbon Tracker", layout="centered")
st.title("🌿 Carbon Footprint Tracker")
init_db()

# Session State
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = None
if "logged_page_view" not in st.session_state:
    st.session_state.logged_page_view = False  # to avoid duplicate page_view logs on reruns

# --- Login/Register UI ---
st.sidebar.title("Account")
option = st.sidebar.selectbox("Choose", ["Login", "Register"])

if option == "Register":
    st.subheader("Create a new account")
    username = st.text_input("Username (no spaces)").strip()
    password = st.text_input("Password", type="password").strip()
    if st.button("Register"):
        if username and password:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            try:
                hashed = hash_password(password)
                c.execute("INSERT INTO users (username, password) VALUES (?,?)", (username, hashed))
                conn.commit()
                # fetch id
                c.execute("SELECT id FROM users WHERE username=?", (username,))
                uid = c.fetchone()[0]
                log_event(uid, "register", info="registered via app")
                st.success("Registered! Please switch to Login and sign in.")
            except sqlite3.IntegrityError:
                st.error("Username already exists. Choose another.")
            finally:
                conn.close()
        else:
            st.warning("Enter both username and password.")

elif option == "Login":
    st.subheader("Login to your account")
    username = st.text_input("Username").strip()
    password = st.text_input("Password", type="password").strip()
    if st.button("Login"):
        if username and password:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("SELECT id, password FROM users WHERE username=?", (username,))
            result = c.fetchone()
            conn.close()
            if result and hash_password(password) == result[1]:
                st.session_state.user_id = result[0]
                st.session_state.username = username
                st.success(f"Logged in as {username}")
                # log login event
                log_event(st.session_state.user_id, "login", info="successful login")
                # reset page_view flag so a page_view is logged once below
                st.session_state.logged_page_view = False
            else:
                st.error("Invalid username or password.")
        else:
            st.warning("Enter both username and password.")

# --- If logged in: log a page_view once per session/app load for that user ---
if st.session_state.user_id and not st.session_state.logged_page_view:
    # Log page view
    log_event(st.session_state.user_id, "page_view", info="opened app")
    st.session_state.logged_page_view = True

# --- If logged in: normal user UI ---
if st.session_state.user_id:
    user_id = st.session_state.user_id
    st.write(f"Welcome, **{st.session_state.username}**")
    st.subheader("Add Today's Carbon Data")
    with st.form("entry_form"):
        car = st.number_input("Car km", min_value=0, value=0)
        bike = st.number_input("Bike km", min_value=0, value=0)
        bus = st.number_input("Bus km", min_value=0, value=0)
        elec = st.number_input("Electricity kWh", min_value=0, value=0)
        meat = st.number_input("Meat meals", min_value=0, value=0)
        veg = st.number_input("Veg meals", min_value=0, value=0)
        submitted = st.form_submit_button("Add Entry")
        if submitted:
            total = add_entry(user_id, dt.date.today().isoformat(), car, bike, bus, elec, meat, veg)
            st.success(f"Entry added! Total CO2 today: {total:.2f} kg")

    st.subheader("Your Carbon Data History")
    df = get_entries(user_id)
    if not df.empty:
        st.dataframe(df[['date','car_km','bike_km','bus_km','electricity','meat_meals','veg_meals','total_emission']])
        st.write("Cumulative CO2:", float(df['total_emission'].sum()), "kg")
        # ensure date index for plotting
        try:
            st.line_chart(df[['date', 'total_emission']].set_index('date'))
        except Exception:
            pass
    else:
        st.info("No data yet.")

    # logout button
    if st.button("Logout"):
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.logged_page_view = False
        st.experimental_rerun()

# --- Admin Panel (visible only to username 'admin') ---
# If you want different admin username change the check accordingly.
if st.session_state.username == "admin":
    st.markdown("---")
    st.header("🔒 Admin Panel")
    st.subheader("All registered users")
    df_users = get_all_users_df()
    st.dataframe(df_users)

    st.subheader("Visit / Event Logs (most recent)")
    df_visits = get_visits_df(limit=1000)
    st.dataframe(df_visits)

    st.subheader("Login counts per user (how many times each user logged in)")
    df_counts = get_login_counts()
    # join with usernames for readability
    if not df_counts.empty:
        users = get_all_users_df().set_index('id')
        df_counts['username'] = df_counts['user_id'].apply(lambda uid: users['username'].get(uid, "(deleted)"))
        st.dataframe(df_counts[['user_id','username','logins']].sort_values('logins', ascending=False))
    else:
        st.info("No login events yet.")

    st.subheader("All entries (optionally filtered)")
    conn = sqlite3.connect(DB_FILE)
    df_entries = pd.read_sql_query("SELECT e.id, e.user_id, u.username, e.date, e.total_emission FROM entries e LEFT JOIN users u ON e.user_id=u.id ORDER BY e.date DESC", conn)
    conn.close()
    st.dataframe(df_entries)

    # optional: delete user or delete visit logs (careful)
    st.write("**Danger zone (admin actions)**")
    if st.button("Delete all visit logs (admin)"):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM visits")
        conn.commit()
        conn.close()
        st.success("All visit logs deleted.")
        st.experimental_rerun()

# If nobody logged in, show minimal message
if not st.session_state.user_id:
    st.write("You are not logged in. Register or login from the sidebar to track and view your data.")
