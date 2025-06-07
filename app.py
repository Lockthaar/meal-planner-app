import sqlite3
import streamlit as st
import pandas as pd
import json
from collections import defaultdict
from typing import Optional
import io
from datetime import datetime

# ---------------------------------------------------------------------
# 1) INITIALISATION DE LA BASE (DROP + CREATE)
# ---------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # On vide les anciennes tables (mais on ne supprime pas le fichier)
    cursor.execute("DROP TABLE IF EXISTS users")
    cursor.execute("DROP TABLE IF EXISTS recipes")
    cursor.execute("DROP TABLE IF EXISTS mealplans")
    conn.commit()

    # Table users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            household_type TEXT,
            meals_per_day INTEGER,
            num_children INTEGER,
            num_adolescents INTEGER,
            num_adults INTEGER
        )
    """)

    # Table recipes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT,
            image_url TEXT,
            extras_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Table mealplans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            recipe_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()
    print("✅ init_db() exécuté – schéma réinitialisé.")

init_db()


# ---------------------------------------------------------------------
# 2) FONCTIONS CRUD
# ---------------------------------------------------------------------
def add_user(username: str, password: str) -> bool:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users(username, password) VALUES(?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username: str, password: str) -> Optional[int]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ? AND password = ?", (username, password))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_profile(user_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT household_type, meals_per_day, num_children, num_adolescents, num_adults
        FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "household_type": row[0],
            "meals_per_day": row[1],
            "num_children": row[2],
            "num_adolescents": row[3],
            "num_adults": row[4]
        }
    return {}

def update_user_profile(user_id: int, profile: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE users
        SET household_type = ?, meals_per_day = ?, num_children = ?, num_adolescents = ?, num_adults = ?
        WHERE id = ?
    """, (
        profile.get("household_type"),
        profile.get("meals_per_day"),
        profile.get("num_children"),
        profile.get("num_adolescents"),
        profile.get("num_adults"),
        user_id
    ))
    conn.commit()
    conn.close()

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, image_url, ingredients, instructions, extras_json FROM recipes WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def insert_recipe(user_id: int, name: str, image_url: str, ingredients_json: str,
                  instructions: str, extras_json: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO recipes(user_id, name, image_url, ingredients, instructions, extras_json)
        VALUES(?, ?, ?, ?, ?, ?)
    """, (user_id, name, image_url, ingredients_json, instructions, extras_json))
    conn.commit()
    conn.close()

def update_recipe(recipe_id: int, name: str, image_url: str, ingredients_json: str,
                  instructions: str, extras_json: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE recipes
        SET name = ?, image_url = ?, ingredients = ?, instructions = ?, extras_json = ?
        WHERE id = ?
    """, (name, image_url, ingredients_json, instructions, extras_json, recipe_id))
    conn.commit()
    conn.close()

def delete_recipe(recipe_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name, timestamp FROM mealplans WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in plan_df.iterrows():
        cursor.execute("""
            INSERT INTO mealplans(user_id, day, meal, recipe_name, timestamp)
            VALUES(?, ?, ?, ?, ?)
        """, (user_id, row["Day"], row["Meal"], row["Recipe"], now_str))
    conn.commit()
    conn.close()

def parse_ingredients(ing_str: str) -> list:
    try:
        return json.loads(ing_str)
    except:
        return []

def parse_extras(extras_str: str) -> list:
    try:
        return json.loads(extras_str)
    except:
        return []


# ---------------------------------------------------------------------
# 3) CONFIGURATION STREAMLIT & CSS
# ---------------------------------------------------------------------
st.set_page_config(page_title="Batchist", page_icon="🥘", layout="wide")
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
  * { font-family: 'Poppins', sans-serif !important; }
  #MainMenu, footer { visibility: hidden; }
  .header { position: fixed; top:0; left:0; width:100%; background:#fffccccc; backdrop-filter:blur(8px); z-index:1000; }
  .header-content { max-width:1200px; margin:0 auto; padding:10px 20px; display:flex; justify-content:space-between; align-items:center; }
  .nav-item { margin-left:20px; cursor:pointer; font-weight:500; color:#333; }
  .nav-item:hover { color:#ffa500; }
  .streamlit-container { padding-top:70px !important; }
  .hero { position:relative; height:260px; background:url('https://images.unsplash.com/photo-1565895405132-ac3e0ffb5e15?auto=format&fit=crop&w=1200&q=80') center/cover no-repeat; margin-bottom:32px; }
  .hero-overlay { position:absolute; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.4); }
  .hero-text { position:relative; z-index:1; top:50%; transform:translateY(-50%); text-align:center; color:#fff; }
  .hero-text h1 { font-size:2.8rem; margin-bottom:8px; }
  .hero-text p { font-size:1.1rem; opacity:0.9; }
  .modal-background { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1001; }
  .modal-content { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:#fff; padding:24px; border-radius:8px; width:90%; max-width:380px; box-shadow:0 4px 20px rgba(0,0,0,0.2); z-index:1002; }
  .modal-close { position:absolute; top:8px; right:12px; cursor:pointer; font-weight:700; color:#666; }
  .modal-close:hover { color:#333; }
  .modal-title { font-size:1.3rem; font-weight:700; margin-bottom:16px; text-align:center; color:#333; }
  .btn-share, .btn-delete { border:none; border-radius:4px; color:#fff; padding:4px 8px; font-size:0.9rem; cursor:pointer; }
  .btn-share { background:#ffa500; margin-right:6px; }
  .btn-delete { background:#d32f2f; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 4) NAVBAR + HERO
# ---------------------------------------------------------------------
st.markdown("""
<div class="header">
  <div class="header-content">
    <div style="display:flex;align-items:center;">
      <img src="https://img.icons8.com/fluency/48/000000/cutlery.png" width="32"/>
      <span style="font-size:1.4rem;font-weight:700;margin-left:8px;color:#333;">Batchist</span>
    </div>
    <div>
      <span class="nav-item" onclick="window.location.hash='#Accueil'">Accueil</span>
      <span class="nav-item" onclick="window.location.hash='#Recettes'">Recettes</span>
      <span class="nav-item" onclick="window.location.hash='#Planificateur'">Planificateur</span>
      <span class="nav-item" onclick="window.location.hash='#Courses'">Liste de courses</span>
      <span class="nav-item" onclick="window.location.hash='#Astuces'">Conseils</span>
      <span class="nav-item" onclick="window.location.hash='#Profil'">Profil</span>
    </div>
    <div id="clock" style="font-size:0.9rem;color:#333;"></div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div id="Accueil" class="hero">
  <div class="hero-overlay"></div>
  <div class="hero-text">
    <h1>Batchist</h1>
    <p>Vos recettes personnelles, votre batch cooking simplifié.</p>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<script>
function updateClock(){
  const now=new Date();
  let h=now.getHours(), m=now.getMinutes(), s=now.getSeconds();
  if(h<10)h='0'+h; if(m<10)m='0'+m; if(s<10)s='0'+s;
  document.getElementById('clock').innerText=`🕒 ${h}:${m}:${s}`;
}
setInterval(updateClock,1000);
updateClock();
</script>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# 5) AUTHENTIFICATION + ONBOARDING
# ---------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 0
if "household_type" not in st.session_state:
    st.session_state.household_type = None
if "meals_per_day" not in st.session_state:
    st.session_state.meals_per_day = None

def show_login_page():
    st.markdown('<div id="Accueil"></div>', unsafe_allow_html=True)
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["🔐 Connexion", "✍️ Inscription"])

    with tab1:
        st.write("Connectez-vous pour accéder à Batchist.")
        with st.form("login_form"):
            user = st.text_input("Nom d'utilisateur", key="login_user")
            pwd  = st.text_input("Mot de passe", type="password", key="login_pwd")
            if st.form_submit_button("Se connecter"):
                uid = verify_user(user.strip(), pwd)
                if uid:
                    st.session_state.user_id = uid
                    st.session_state.username = user.strip()
                    profile = get_user_profile(uid)
                    if not profile.get("household_type") or not profile.get("meals_per_day"):
                        st.session_state.onboard_step = 1
                    else:
                        st.session_state.onboard_step = 3
                    st.experimental_rerun()
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    with tab2:
        st.write("Créez votre compte.")
        with st.form("register_form"):
            user2 = st.text_input("Nom d'utilisateur", key="reg_user")
            pwd2  = st.text_input("Mot de passe", type="password", key="reg_pwd")
            pwd3  = st.text_input("Confirmez mot de passe", type="password", key="reg_pwd2")
            if st.form_submit_button("Créer mon compte"):
                if not user2.strip():
                    st.error("❌ Nom d’utilisateur vide.")
                elif pwd2 != pwd3:
                    st.error("❌ Mots de passe différents.")
                else:
                    if add_user(user2.strip(), pwd2):
                        st.success("✅ Compte créé, connectez-vous.")
                    else:
                        st.error("❌ Nom d’utilisateur déjà pris.")

if st.session_state.user_id is None:
    show_login_page()
    st.stop()

# Onboarding étape 1
if st.session_state.onboard_step == 1:
    st.markdown('<div class="modal-background"></div>', unsafe_allow_html=True)
    st.markdown("""
      <div class="modal-content">
        <div class="modal-close" onclick="window._closeOnb()">✕</div>
        <div class="modal-title">Comment vivez-vous ?</div>
      </div>
    """, unsafe_allow_html=True)
    st.markdown("""
      <script>
      window._closeOnb = ()=>{
        window.location.reload();
      }
      </script>
    """, unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("Solo"):
            st.session_state.household_type="Solo"
            st.session_state.onboard_step=2
            st.experimental_rerun()
    with c2:
        if st.button("Couple"):
            st.session_state.household_type="Couple"
            st.session_state.onboard_step=2
            st.experimental_rerun()
    with c3:
        if st.button("Famille"):
            st.session_state.household_type="Famille"
            st.session_state.onboard_step=2
            st.experimental_rerun()
    st.stop()

# Onboarding étape 2
if st.session_state.onboard_step == 2:
    st.markdown('<div class="modal-background"></div>', unsafe_allow_html=True)
    st.markdown("""
      <div class="modal-content">
        <div class="modal-close" onclick="window._closeOnb()">✕</div>
        <div class="modal-title">Repas par jour ?</div>
      </div>
    """, unsafe_allow_html=True)
    n = st.number_input("Repas / jour", min_value=1, max_value=10, value=3)
    if st.button("Valider repas"):
        prof = {
          "household_type": st.session_state.household_type,
          "meals_per_day": n,
          "num_children": 0,
          "num_adolescents": 0,
          "num_adults": 1 if st.session_state.household_type=="Solo" else 2
        }
        update_user_profile(st.session_state.user_id, prof)
        st.session_state.onboard_step=3
        st.experimental_rerun()
    st.stop()

# ---------------------------------------------------------------------
# 6) UTILISATEUR CONNECTÉ – CONTENU PRINCIPAL
# ---------------------------------------------------------------------
USER_ID = st.session_state.user_id
profile = get_user_profile(USER_ID)

# Navigation en haut
sections = ["Accueil","Mes recettes","Planificateur","Liste de courses","Conseils & Astuces","Profil"]
if "section" not in st.session_state:
    st.session_state.section = "Accueil"

cols = st.columns(len(sections))
for i,sec in enumerate(sections):
    if cols[i].button(sec):
        st.session_state.section = sec
        st.experimental_rerun()

st.markdown("---")

# 7) Accueil
if st.session_state.section == "Accueil":
    st.header("🏠 Tableau de bord")
    st.write("…")

# 8) Mes recettes
elif st.session_state.section == "Mes recettes":
    st.header("📋 Mes recettes")
    st.write("…")

# 9) Planificateur
elif st.session_state.section == "Planificateur":
    st.header("📅 Planificateur")
    st.write("…")

# 10) Liste de courses
elif st.session_state.section == "Liste de courses":
    st.header("🛒 Liste de courses")
    st.write("…")

# 11) Conseils
elif st.session_state.section == "Conseils & Astuces":
    st.header("💡 Conseils & Astuces")
    st.write("…")

# 12) Profil
else:
    st.header("👤 Profil")
    st.write(f"Bonjour **{st.session_state.username}** !")
