import sqlite3
import streamlit as st
import pandas as pd
import json
from collections import defaultdict
from typing import Optional
import io
from datetime import datetime

# ---------------------------------------------------------------------
# 1) INITIALISATION DE LA BASE
# ---------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    """
    Crée les tables si elles n'existent pas.
    Ne supprime jamais le fichier ni la table.
    """
    conn = get_connection()
    cursor = conn.cursor()
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

init_db()

# ---------------------------------------------------------------------
# 2) FONCTIONS CRUD POUR USERS
# ---------------------------------------------------------------------
def add_user(username: str, password: str) -> bool:
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username: str, password: str) -> Optional[int]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    r = c.fetchone()
    conn.close()
    return r[0] if r else None

def fetch_all_users() -> list[tuple]:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id,username FROM users")
    rows = c.fetchall()
    conn.close()
    return rows

# ---------------------------------------------------------------------
# 3) FONCTIONS CRUD POUR RECIPES & MEALPLANS (à compléter)
# ---------------------------------------------------------------------
def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM recipes WHERE user_id=?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def insert_recipe(user_id: int, name: str, img: str, ingredients: str, instr: str, extras: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO recipes(user_id,name,image_url,ingredients,instructions,extras_json)
        VALUES(?,?,?,?,?,?)
    """, (user_id,name,img,ingredients,instr,extras))
    conn.commit(); conn.close()

def delete_recipe(recipe_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
    conn.commit(); conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM mealplans WHERE user_id=?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, df_plan: pd.DataFrame):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM mealplans WHERE user_id=?", (user_id,))
    conn.commit()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _,r in df_plan.iterrows():
        c.execute("""
          INSERT INTO mealplans(user_id,day,meal,recipe_name,timestamp)
          VALUES(?,?,?,?,?)
        """, (user_id,r["Day"],r["Meal"],r["Recipe"],now))
    conn.commit(); conn.close()

# ---------------------------------------------------------------------
# 4) UTILITAIRES JSON
# ---------------------------------------------------------------------
def parse_ingredients(s: str) -> list:
    try: return json.loads(s)
    except: return []

def parse_extras(s: str) -> list:
    try: return json.loads(s)
    except: return []

# ---------------------------------------------------------------------
# 5) CONFIGURATION STREAMLIT + CSS
# ---------------------------------------------------------------------
st.set_page_config(page_title="Batchist", layout="wide")
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
  * {font-family:'Poppins',sans-serif!important;}
  #MainMenu, footer {visibility:hidden;}
  .header{position:fixed;top:0;width:100%;background:#fffccccc;backdrop-filter:blur(8px);z-index:1000;}
  .header-content{max-width:1200px;margin:0 auto;padding:10px 20px;display:flex;justify-content:space-between;align-items:center;}
  .nav-item{margin-left:20px;cursor:pointer;color:#333;font-weight:500;}
  .nav-item:hover{color:#ffa500;}
  .streamlit-container{padding-top:70px!important;}
  .hero{position:relative;height:260px;background:url('https://images.unsplash.com/photo-1565895405132-ac3e0ffb5e15?auto=format&fit=crop&w=1200&q=80') center/cover no-repeat;margin-bottom:32px;}
  .hero-overlay{position:absolute;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.4);}
  .hero-text{position:relative;z-index:1;top:50%;transform:translateY(-50%);text-align:center;color:#fff;}
  .hero-text h1{font-size:2.8rem;margin-bottom:8px;}
  .hero-text p{font-size:1.1rem;opacity:0.9;}
  .modal-background{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:1001;}
  .modal-content{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:#fff;padding:24px;border-radius:8px;width:90%;max-width:380px;box-shadow:0 4px 20px rgba(0,0,0,0.2);z-index:1002;}
  .modal-close{position:absolute;top:8px;right:12px;cursor:pointer;color:#666;font-weight:700;}
  .modal-close:hover{color:#333;}
  .modal-title{font-size:1.3rem;font-weight:700;margin-bottom:16px;text-align:center;color:#333;}
  .btn-share,.btn-delete{border:none;border-radius:4px;color:#fff;padding:4px 8px;font-size:0.9rem;cursor:pointer;}
  .btn-share{background:#ffa500;margin-right:6px;}
  .btn-delete{background:#d32f2f;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# 6) NAVBAR + HERO
# ---------------------------------------------------------------------
st.markdown("""
<div class="header"><div class="header-content">
  <div style="display:flex;align-items:center;">
    <img src="https://img.icons8.com/fluency/48/000000/cutlery.png" width="32"/>
    <span style="font-weight:700;font-size:1.4rem;margin-left:8px;color:#333;">Batchist</span>
  </div>
  <div>
    <span class="nav-item" onclick="window.location.hash='#Accueil'">Accueil</span>
    <span class="nav-item" onclick="window.location.hash='#Mes recettes'">Mes recettes</span>
    <span class="nav-item" onclick="window.location.hash='#Planificateur'">Planif.</span>
    <span class="nav-item" onclick="window.location.hash='#Liste de courses'">Courses</span>
    <span class="nav-item" onclick="window.location.hash='#Conseils & Astuces'">Astuces</span>
    <span class="nav-item" onclick="window.location.hash='#Profil'">Profil</span>
  </div>
  <div id="clock" style="font-size:0.9rem;color:#333;"></div>
</div></div>
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
  let h=now.getHours(),m=now.getMinutes(),s=now.getSeconds();
  if(h<10)h='0'+h; if(m<10)m='0'+m; if(s<10)s='0'+s;
  document.getElementById('clock').innerText=`🕒 ${h}:${m}:${s}`;
}
setInterval(updateClock,1000);
updateClock();
</script>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------
# 7) AUTHENTIFICATION
# ---------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if st.session_state.user_id is None:
    st.markdown('<div id="Accueil"></div>', unsafe_allow_html=True)
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["🔐 Connexion", "✍️ Inscription"])

    with tab1:
        with st.form("login_form"):
            login_user = st.text_input("Nom d'utilisateur", key="login_user")
            login_pwd  = st.text_input("Mot de passe", type="password", key="login_pwd")
            if st.form_submit_button("Se connecter"):
                uid = verify_user(login_user.strip(), login_pwd)
                if uid:
                    st.session_state.user_id = uid
                    st.success(f"✅ Connecté en tant que '{login_user.strip()}' (id={uid})")
                    st.experimental_rerun()
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    with tab2:
        with st.form("register_form"):
            new_user    = st.text_input("Nom d'utilisateur", key="reg_user")
            new_pwd     = st.text_input("Mot de passe", type="password", key="reg_pwd")
            confirm_pwd = st.text_input("Confirmez mot de passe", type="password", key="reg_pwd2")
            if st.form_submit_button("Créer mon compte"):
                if not new_user.strip():
                    st.error("⚠️ Le nom d’utilisateur ne peut pas être vide.")
                elif new_pwd != confirm_pwd:
                    st.error("⚠️ Les mots de passe ne correspondent pas.")
                else:
                    if add_user(new_user.strip(), new_pwd):
                        # auto-login après inscription
                        st.session_state.user_id = verify_user(new_user.strip(), new_pwd)
                        st.success(f"✅ Compte '{new_user.strip()}' créé et connecté.")
                        st.experimental_rerun()
                    else:
                        st.error("❌ Ce nom d’utilisateur existe déjà.")

    st.markdown("---")
    st.write("### 🔍 Debug — Utilisateurs en base")
    st.write(fetch_all_users())
    st.stop()

# ---------------------------------------------------------------------
# 8) UTILISATEUR CONNECTÉ — MENU SECTIONS
# ---------------------------------------------------------------------
USER_ID = st.session_state.user_id
st.success(f"🎉 Bienvenue (user_id={USER_ID}) !")

# Navigation
sections = ["Accueil","Mes recettes","Planificateur","Liste de courses","Conseils & Astuces","Profil"]
if "section" not in st.session_state:
    st.session_state.section = "Accueil"
cols = st.columns(len(sections))
for i,sec in enumerate(sections):
    if cols[i].button(sec):
        st.session_state.section = sec
        st.experimental_rerun()
st.markdown("---")

# Pages
if st.session_state.section == "Accueil":
    st.header("🏠 Tableau de bord")
    st.write("… votre dashboard ici …")

elif st.session_state.section == "Mes recettes":
    st.header("📋 Mes recettes")
    st.write("… CRUD recettes ici …")

elif st.session_state.section == "Planificateur":
    st.header("📅 Planificateur")
    st.write("… votre planificateur ici …")

elif st.session_state.section == "Liste de courses":
    st.header("🛒 Liste de courses")
    st.write("… génération liste ici …")

elif st.session_state.section == "Conseils & Astuces":
    st.header("💡 Conseils & Astuces")
    st.write("… contenu astuces ici …")

else:
    st.header("👤 Profil")
    st.write("… gestion profil ici …")
