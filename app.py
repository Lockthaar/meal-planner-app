# ---------------------------------------------------------------------
# app.py – Batchist : Meal Planner & Batch Cooking (Streamlit Cloud)
# ---------------------------------------------------------------------

import sqlite3
import streamlit as st
import pandas as pd
import json
from collections import defaultdict
from typing import Optional
import io
from datetime import datetime
import time

# ---------------------------------------------------------------------
# 1) DATABASE INITIALIZATION
# ---------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    """
    Ouvre ou crée la base SQLite meal_planner.db.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """
    Vérifie / crée les tables users, recipes, mealplans (CREATE TABLE IF NOT EXISTS).
    Ne supprime jamais de tables existantes : on conserve les données entre redéploiements.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Table "users"
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
    conn.commit()

    # Table "recipes"
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
    conn.commit()

    # Table "mealplans"
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
    print("✅ init_db() exécuté (tables créées si nécessaire).")

# Appel immédiat (sera silencieux si les tables existent déjà)
init_db()

# ---------------------------------------------------------------------
# 2) FONCTIONS CRUD POUR SQLITE
# ---------------------------------------------------------------------
def add_user(username: str, password: str) -> bool:
    """
    Ajoute un nouvel utilisateur en base.
    Retourne True si OK, False si l’username existe déjà (IntegrityError) ou erreur SQLite.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users(username, password) VALUES(?, ?)",
            (username, password)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.OperationalError as e:
        st.error(f"⚠️ SQLite error dans add_user(): {e}")
        return False

def verify_user(username: str, password: str) -> Optional[int]:
    """
    Vérifie l’existence de (username, password). Si trouvé, retourne l’ID de l’utilisateur, sinon None.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM users WHERE username = ? AND password = ?",
            (username, password)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0]
        return None
    except sqlite3.OperationalError as e:
        st.error(f"⚠️ SQLite error dans verify_user(): {e}")
        return None

def get_user_profile(user_id: int) -> dict:
    """
    Récupère le profil (household_type, meals_per_day, num_children, num_adolescents, num_adults).
    """
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
    """
    Met à jour les colonnes profil de l’utilisateur (household_type, meals_per_day, etc.).
    """
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
    """
    Renvoie un DataFrame de toutes les recettes pour cet user_id.
    Colonnes : id, name, image_url, ingredients, instructions, extras_json.
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, image_url, ingredients, instructions, extras_json FROM recipes WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def insert_recipe(user_id: int, name: str, image_url: str, ingredients_json: str,
                  instructions: str, extras_json: str):
    """
    Ajoute une nouvelle recette pour l’utilisateur donné.
    """
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
    """
    Met à jour une recette existante identifiée par recipe_id.
    """
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
    """
    Supprime la recette dont l’ID est passé en paramètre.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    """
    Renvoie un DataFrame du planning (id, day, meal, recipe_name, timestamp) pour user_id.
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name, timestamp FROM mealplans WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
    """
    Remplace (DELETE puis INSERT) tout le planning pour user_id.
    Ajoute la date/heure d’insertion dans le champ timestamp.
    """
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
    """
    Transforme la chaîne JSON stockée dans 'ingredients' en liste de dicts 
    [{ "ingredient": ..., "quantity": ..., "unit": ... }, ...].
    """
    try:
        return json.loads(ing_str)
    except:
        return []

def parse_extras(extras_str: str) -> list:
    """
    Transforme la chaîne JSON stockée dans 'extras_json' en liste de dicts 
    [{ "category": ..., "item": ..., "quantity": ..., "unit": ... }, ...].
    """
    try:
        return json.loads(extras_str)
    except:
        return []

# ---------------------------------------------------------------------
# 3) CONFIGURATION GLOBALE STREAMLIT (CSS + PAGE CONFIG)
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Batchist: Meal Planner & Batch Cooking",
    page_icon="🥘",
    layout="wide"
)
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Poppins', sans-serif !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        /* NAVBAR FIXE EN HAUT */
        .header {
            position: fixed;
            top: 0; left: 0;
            width: 100%;
            background: #ffffffcc;
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 1000;
        }
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-logo img { width: 36px; height: 36px; margin-right: 8px; vertical-align: middle; }
        .header-logo span { font-size: 1.5rem; font-weight: 700; color: #333; vertical-align: middle; }
        .nav-item {
            margin-left: 20px;
            font-weight: 500;
            cursor: pointer;
            color: #333;
            font-size: 1rem;
        }
        .nav-item:hover { color: #FFA500; }

        /* Evite que le contenu soit caché par la navbar */
        .streamlit-container { padding-top: 80px !important; }

        /* HERO (BANNIÈRE) */
        .hero {
            position: relative;
            width: 100%;
            height: 280px;
            background: url('https://images.unsplash.com/photo-1565895405132-ac3e0ffb5e15?auto=format&fit=crop&w=1200&q=80') no-repeat center center / cover;
            margin-bottom: 32px;
            color: white;
        }
        .hero-overlay {
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.4);
        }
        .hero-text {
            position: relative; z-index: 1;
            text-align: center; top: 50%; transform: translateY(-50%);
        }
        .hero-text h1 { font-size: 3rem; margin-bottom: 8px; }
        .hero-text p { font-size: 1.2rem; opacity: 0.9; }

        /* MODALE (POP-UP ONBOARDING) */
        .modal-background {
            position: fixed; top: 0; left: 0;
            width: 100%; height: 100%;
            background-color: rgba(0,0,0,0.5);
            z-index: 1001;
        }
        .modal-content {
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background: white; padding: 30px; border-radius: 8px;
            max-width: 400px; width: 90%;
            box-shadow: 0 4px 20px rgba(0,0,0,0.2);
            z-index: 1002;
        }
        .modal-title {
            font-size: 1.3rem; font-weight: 700; margin-bottom: 20px;
            color: #333; text-align: center;
        }
        .modal-close {
            position: absolute; top: 10px; right: 15px;
            font-size: 1.2rem; font-weight: 700; color: #666;
            cursor: pointer;
        }
        .modal-close:hover { color: #333; }

        /* Style des boutons de carte recette */
        .btn-share, .btn-delete {
            padding: 5px 10px;
            border: none;
            border-radius: 4px;
            color: white;
            font-size: 0.9rem;
            cursor: pointer;
        }
        .btn-share { background-color: #FFA500; margin-right: 8px; }
        .btn-delete { background-color: #D32F2F; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# 4) BARRE DE NAVIGATION HTML + HERO
# ---------------------------------------------------------------------
st.markdown(
    """
    <div class="header">
      <div class="header-content">
        <div class="header-logo">
          <img src="https://img.icons8.com/fluency/48/000000/cutlery.png" alt="logo">
          <span>Batchist</span>
        </div>
        <div>
          <span class="nav-item" onclick="window.location.hash='#home'">Accueil</span>
          <span class="nav-item" onclick="window.location.hash='#recipes'">Recettes</span>
          <span class="nav-item" onclick="window.location.hash='#planner'">Planificateur</span>
          <span class="nav-item" onclick="window.location.hash='#shopping'">Liste de courses</span>
          <span class="nav-item" onclick="window.location.hash='#tips'">Conseils</span>
          <span class="nav-item" onclick="window.location.hash='#profile'">Profil</span>
        </div>
        <div id="clock" style="font-size:0.95rem; color:#333;"></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Hero (bannière)
st.markdown(
    """
    <div id="home" class="hero">
      <div class="hero-overlay"></div>
      <div class="hero-text">
        <h1>Batchist</h1>
        <p>Vos recettes personnelles, votre batch cooking simplifié.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Script JavaScript pour afficher l’heure en temps réel
st.markdown(
    """
    <script>
    function updateClock() {
        const now = new Date();
        let h = now.getHours();
        let m = now.getMinutes();
        let s = now.getSeconds();
        if (h<10) h='0'+h;
        if (m<10) m='0'+m;
        if (s<10) s='0'+s;
        document.getElementById('clock').innerText = `🕒 ${h}:${m}:${s}`;
    }
    setInterval(updateClock, 1000);
    updateClock();
    </script>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------
# 5) AUTHENTIFICATION + ONBOARDING POP-UPS
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
    """
    Affiche la page Connexion / Inscription tant que l’utilisateur n’est pas connecté.
    """
    st.markdown('<div id="home"></div>', unsafe_allow_html=True)
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["🔐 Connexion", "✍️ Inscription"])

    # Onglet Connexion
    with tab1:
        st.write("Connectez-vous pour accéder à Batchist.")
        with st.form(key="login_form"):
            login_user = st.text_input("Nom d'utilisateur", key="login_username", placeholder="Ex. : utilisateur123")
            login_pwd  = st.text_input("Mot de passe", type="password", key="login_password", placeholder="••••••••")
            login_submit = st.form_submit_button("Se connecter", use_container_width=True)
            if login_submit:
                uid = verify_user(login_user.strip(), login_pwd)
                if uid:
                    st.session_state.user_id = uid
                    st.session_state.username = login_user.strip()
                    st.success(f"Bienvenue, **{login_user.strip()}** !")
                    profile = get_user_profile(uid)
                    # Si l’utilisateur n’a pas encore de profil complet, on déclenche l’onboarding
                    if not profile.get("household_type") or not profile.get("meals_per_day"):
                        st.session_state.onboard_step = 1
                    else:
                        st.session_state.onboard_step = 3
                    st.experimental_rerun()
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    # Onglet Inscription
    with tab2:
        st.write("Créez votre compte pour commencer.")
        with st.form(key="register_form"):
            new_user = st.text_input("Nom d'utilisateur souhaité", key="register_username", placeholder="Ex. : mon_profil")
            new_pwd  = st.text_input("Mot de passe", type="password", key="register_password", placeholder="••••••••")
            confirm_pwd = st.text_input("Confirmez le mot de passe", type="password", key="register_confirm", placeholder="••••••••")
            register_submit = st.form_submit_button("Créer mon compte", use_container_width=True)
            if register_submit:
                if not new_user.strip():
                    st.error("❌ Le nom d’utilisateur ne peut pas être vide.")
                elif new_pwd != confirm_pwd:
                    st.error("❌ Les mots de passe ne correspondent pas.")
                else:
                    ok = add_user(new_user.strip(), new_pwd)
                    if ok:
                        st.success("✅ Compte créé. Vous pouvez maintenant vous connecter.")
                    else:
                        st.error(f"❌ Le nom d’utilisateur « {new_user.strip()} » existe déjà ou erreur SQLite.")

# Tant que l’utilisateur n’est pas connecté, on n’avance pas plus loin
if st.session_state.user_id is None:
    show_login_page()
    st.stop()

# ---------------------------------------------------------------------
# 5.1) ONBOARDING – Étape 1 : « Comment vivez-vous ? »
# ---------------------------------------------------------------------
if st.session_state.onboard_step == 1:
    st.markdown('<div class="modal-background"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="modal-content">
          <div class="modal-close" onclick="window._closeOnboarding()" title="Fermer">✕</div>
          <div class="modal-title">Comment vivez-vous ?</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <script>
        window._closeOnboarding = function() {
            const url = new URL(window.location);
            url.searchParams.set("closeOnboarding", "1");
            window.history.replaceState(null, null, url.toString());
            window.location.reload();
        }
        </script>
        """,
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        if st.button("Solo", key="btn_solo", use_container_width=True):
            st.session_state.household_type = "Solo"
            st.session_state.onboard_step = 2
            st.experimental_rerun()
        st.markdown(
            '<div style="text-align:center; margin-top:8px;">'
            '<img src="https://img.icons8.com/dusk/100/000000/user.png" alt="solo"/></div>',
            unsafe_allow_html=True
        )
    with col2:
        if st.button("Couple", key="btn_couple", use_container_width=True):
            st.session_state.household_type = "Couple"
            st.session_state.onboard_step = 2
            st.experimental_rerun()
        st.markdown(
            '<div style="text-align:center; margin-top:8px;">'
            '<img src="https://img.icons8.com/dusk/100/000000/couple.png" alt="couple"/></div>',
            unsafe_allow_html=True
        )
    with col3:
        if st.button("Famille", key="btn_family", use_container_width=True):
            st.session_state.household_type = "Famille"
            st.session_state.onboard_step = 2
            st.experimental_rerun()
        st.markdown(
            '<div style="text-align:center; margin-top:8px;">'
            '<img src="https://img.icons8.com/dusk/100/000000/family.png" alt="famille"/></div>',
            unsafe_allow_html=True
        )

    # Si l’utilisateur clique sur la croix, on passe à la fin de l’onboarding (skip)
    if st.experimental_get_query_params().get("closeOnboarding"):
        st.session_state.onboard_step = 3
        st.experimental_set_query_params()
        st.experimental_rerun()

    st.stop()

# ---------------------------------------------------------------------
# 5.2) ONBOARDING – Étape 2 : « Combien de repas par jour ? »
# ---------------------------------------------------------------------
if st.session_state.onboard_step == 2:
    st.markdown('<div class="modal-background"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="modal-content">
          <div class="modal-close" onclick="window._closeOnboarding()" title="Fermer">✕</div>
          <div class="modal-title">Combien de repas par jour préparez-vous ?</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        """
        <script>
        window._closeOnboarding = function() {
            const url = new URL(window.location);
            url.searchParams.set("closeOnboarding", "1");
            window.history.replaceState(null, null, url.toString());
            window.location.reload();
        }
        </script>
        """,
        unsafe_allow_html=True
    )

    meals_input = st.number_input(
        "Nombre de repas / jour :",
        min_value=1, max_value=10, step=1, value=3, key="meals_input"
    )
    if st.button("Valider", key="btn_set_meals", use_container_width=True):
        st.session_state.meals_per_day = meals_input
        # Par défaut : Solo → 1 adulte ; Couple → 2 adultes ; Famille → 2 adultes
        if st.session_state.household_type == "Solo":
            na, nadol, nenf = 1, 0, 0
        elif st.session_state.household_type == "Couple":
            na, nadol, nenf = 2, 0, 0
        else:
            na, nadol, nenf = 2, 0, 0

        update_user_profile(
            st.session_state.user_id,
            {
                "household_type": st.session_state.household_type,
                "meals_per_day": st.session_state.meals_per_day,
                "num_children": nenf,
                "num_adolescents": nadol,
                "num_adults": na
            }
        )
        st.session_state.onboard_step = 3
        st.experimental_rerun()

    if st.experimental_get_query_params().get("closeOnboarding"):
        st.session_state.onboard_step = 3
        st.experimental_set_query_params()
        st.experimental_rerun()

    st.stop()

# ---------------------------------------------------------------------
# 6) UTILISATEUR CONNECTÉ & ONBOARDÉ → AFFICHAGE DU CONTENU PRINCIPAL
# ---------------------------------------------------------------------
USER_ID = st.session_state.user_id

# Récupère une première fois le profil pour avoir household_type & meals_per_day
profile = get_user_profile(USER_ID)

# ---------------------------------------------------------------------
# 6.1) MENU DE NAVIGATION (raccourcis en haut, au-dessus du contenu)
# ---------------------------------------------------------------------
# On « lit » window.location.hash pour démarrer sur la section correcte
# mais on propose aussi un menu Streamlit classique sous forme de radio.
hash_sel = st.experimental_get_query_params().get("selected")
# Si on a un hash (#recipes, #planner, etc.), on l’interprète
if st.experimental_get_query_params().get("selected") is None:
    # Par défaut → Accueil
    st.experimental_set_query_params(selected="Accueil")
    current_section = "Accueil"
else:
    current_section = st.experimental_get_query_params()["selected"][0]

# Barre horizontale de navigation (fallback en cas de click direct sur onglet)
cols_menu = st.columns(6, gap="small")
menu_items = ["Accueil","Mes recettes","Planificateur","Liste de courses","Conseils & Astuces","Profil"]
for idx, item in enumerate(menu_items):
    style = "font-weight:600; color:#FFA500;" if item == current_section else "color:#333;"
    if cols_menu[idx].button(item, key=f"nav_{item}", help=f"Aller à {item}", args=None):
        st.experimental_set_query_params(selected=item)
        st.experimental_rerun()

st.markdown("---")

# ---------------------------------------------------------------------
# 7) PAGE : Accueil (Dashboard + Favoris + Astuces)
# ---------------------------------------------------------------------
if current_section == "Accueil":
    st.markdown('<div id="home"></div>', unsafe_allow_html=True)
    st.header("🏠 Tableau de bord")
    st.markdown("**Vos recettes favorites du mois dernier** & **Astuces rapides**")
    st.markdown("")

    # 7.1) SECTION FAVORIS
    df_plan = get_mealplan_for_user(USER_ID)
    if df_plan.empty:
        st.info("Vous n’avez pas encore planifié de repas.")
    else:
        # Filtre le mois passé
        now = datetime.now()
        one_month_ago = now.replace(day=1)  # début du mois en cours → pour simplifier, on prend tous depuis début du mois
        df_plan["timestamp"] = pd.to_datetime(df_plan["timestamp"])
        df_last_month = df_plan[df_plan["timestamp"] >= one_month_ago]
        if df_last_month.empty:
            st.info("Aucun repas planifié ce mois-ci.")
        else:
            favorites = df_last_month["recipe_name"].value_counts().head(6)
            st.subheader("💖 Recettes les plus planifiées ce mois")
            cols_fav = st.columns(3, gap="large")
            df_recettes = get_recipes_for_user(USER_ID)
            idx = 0
            for recipe_name, count in favorites.items():
                img_row = df_recettes[df_recettes["name"] == recipe_name]["image_url"]
                img = img_row.values[0] if (not img_row.empty and img_row.values[0]) else "https://via.placeholder.com/300x180.png?text=No+Image"
                with cols_fav[idx % 3]:
                    st.markdown(
                        f"""
                        <div style="border:1px solid #ddd; border-radius:8px; overflow:hidden; margin-bottom:20px;">
                          <img src="{img}" alt="{recipe_name}" style="width:100%; height:160px; object-fit:cover;">
                          <div style="padding:8px;">
                            <div style="font-weight:600; font-size:1.1rem;">{recipe_name}</div>
                            <div style="font-size:0.9rem; color:#555; margin-top:4px;">
                              Planifiée {count} fois
                            </div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                idx += 1

    st.markdown("---")

    # 7.2) ASTUCES RAPIDES
    st.subheader("💡 Astuces rapides pour votre batch cooking")
    st.markdown("""
    - **Planifiez à l’avance** : sélectionnez 3 à 5 recettes que vous pouvez préparer en grandes quantités.  
    - **Optimisez les ingrédients** : achetez en vrac riz, pâtes, légumineuses, conservez en portions hermétiques.  
    - **Variez vos assaisonnements** : base de protéines (poulet, tofu, œufs) : curry, teriyaki, épices mexicaines selon la journée.  
    - **Congélation intelligente** : congelez en Portions individuelles pour décongeler rapidement.  
    - **Nettoyage au fur et à mesure** : pendant que vos plats mijotent, profitez pour laver et ranger.  
    - **Impliquer la famille** : attribuez des tâches simples (laver légumes, mélanger) pour rendre le batch cooking ludique.  
    """)

# ---------------------------------------------------------------------
# 8) PAGE : Mes recettes (création, édition, suppression, cartes, partage)
# ---------------------------------------------------------------------
elif current_section == "Mes recettes":
    st.markdown('<div id="recipes"></div>', unsafe_allow_html=True)
    st.header("📋 Mes recettes")
    st.markdown("Ajoutez, modifiez ou supprimez vos recettes personnelles.")

    df_recettes = get_recipes_for_user(USER_ID)
    all_names = df_recettes["name"].tolist()

    with st.expander("➕ Ajouter / Modifier une recette", expanded=True):
        # Choix de la recette à modifier (ou vide pour nouvelle)
        choice = st.selectbox(
            "Sélectionnez une recette à modifier (ou laissez vide pour nouvelle)",
            options=[""] + all_names
        )

        # Si on modifie, on récupère les valeurs par défaut
        if choice:
            row = df_recettes[df_recettes["name"] == choice].iloc[0]
            recipe_id = row["id"]
            default_name = row["name"]
            default_image = row["image_url"] or ""
            default_ing = parse_ingredients(row["ingredients"])
            default_instr = row["instructions"] or ""
            default_extras = parse_extras(row["extras_json"] or "[]")
        else:
            recipe_id = None
            default_name = ""
            default_image = ""
            default_ing = []
            default_instr = ""
            default_extras = []

        # Formulaire de la recette
        name = st.text_input("Nom de la recette", value=default_name, placeholder="Ex. : Gratin de légumes")
        image_url = st.text_input("URL de l’image (optionnelle)", value=default_image, placeholder="Ex. : https://…/image.jpg")
        instructions = st.text_area("Instructions (facultatif)", value=default_instr, placeholder="Décrivez la préparation…")

        st.markdown("**Ingrédients**")
        ing_mode = st.radio("Mode d’ajout des ingrédients", ("Saisie manuelle", "Importer depuis texte"), index=0, horizontal=True)
        ingrédients_list = []

        if ing_mode == "Saisie manuelle":
            # Nombre de lignes à afficher
            if "ing_count" not in st.session_state:
                st.session_state.ing_count = len(default_ing) if default_ing else 1
            if st.button("➕ Ajouter une ligne", key="add_ing"):
                st.session_state.ing_count += 1

            for i in range(st.session_state.ing_count):
                ingr_i = default_ing[i]["ingredient"] if i < len(default_ing) else ""
                qty_i = default_ing[i]["quantity"] if i < len(default_ing) else 0.0
                unit_i = default_ing[i]["unit"] if i < len(default_ing) else "g"
                c1, c2, c3 = st.columns([4, 2, 2])
                with c1:
                    nm = st.text_input(f"Ingrédient #{i+1}", key=f"ing_nom_{i}", value=ingr_i, placeholder="Ex. : Farine")
                with c2:
                    qt = st.number_input(f"Quantité #{i+1}", min_value=0.0, format="%.2f", key=f"ing_qty_{i}", value=qty_i)
                with c3:
                    un = st.selectbox(
                        f"Unité #{i+1}",
                        ["mg","g","kg","cl","dl","l","pièce(s)"],
                        key=f"ing_unit_{i}",
                        index=["mg","g","kg","cl","dl","l","pièce(s)"].index(unit_i) if unit_i in ["mg","g","kg","cl","dl","l","pièce(s)"] else 1
                    )
                ingrédients_list.append((nm, qt, un))

        else:
            raw_text = st.text_area(
                "Copiez/collez votre liste d’ingrédients (Nom, quantité, unité)",
                value="\n".join([f"{ing['ingredient']}, {ing['quantity']}, {ing['unit']}" for ing in default_ing]) if default_ing else "",
                key="import_ing_text"
            )
            if raw_text:
                lignes = raw_text.strip().split("\n")
                for line in lignes:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) == 3:
                        ingr, qty, unit = parts
                        try:
                            qty_val = float(qty)
                        except:
                            qty_val = 0.0
                        if ingr and qty_val > 0:
                            ingrédients_list.append((ingr, qty_val, unit))
                st.markdown("**Aperçu des ingrédients importés :**")
                if ingrédients_list:
                    for (ingr_i, qty_i, unit_i) in ingrédients_list:
                        st.write(f"- {ingr_i}: {qty_i} {unit_i}")
                else:
                    st.warning("Aucun ingrédient valide détecté.")

        st.markdown("**Extras** (Boissons, Maison, Plantes, Animaux)")
        extras_list = []
        if "extra_count" not in st.session_state:
            st.session_state.extra_count = len(default_extras) if default_extras else 1
        if st.button("➕ Ajouter un extra", key="add_extra"):
            st.session_state.extra_count += 1

        for j in range(st.session_state.extra_count):
            cat_default = default_extras[j]["category"] if j < len(default_extras) else "Boissons"
            item_default = default_extras[j]["item"] if j < len(default_extras) else ""
            qty_extra_default = default_extras[j]["quantity"] if j < len(default_extras) else 0.0
            unit_extra_default = default_extras[j]["unit"] if j < len(default_extras) else "g"
            dcol1, dcol2, dcol3, dcol4 = st.columns([3, 3, 2, 2])
            with dcol1:
                category = st.selectbox(
                    f"Catégorie #{j+1}",
                    ["Boissons","Maison","Plantes","Animaux"],
                    key=f"extra_cat_{j}",
                    index=["Boissons","Maison","Plantes","Animaux"].index(cat_default) if cat_default in ["Boissons","Maison","Plantes","Animaux"] else 0
                )
            with dcol2:
                item = st.text_input(f"Article #{j+1}", key=f"extra_item_{j}", value=item_default)
            with dcol3:
                qty_extra = st.number_input(f"Quantité #{j+1}", min_value=0.0, format="%.2f", key=f"extra_qty_{j}", value=qty_extra_default)
            with dcol4:
                unit_extra = st.selectbox(
                    f"Unité #{j+1}",
                    ["mg","g","kg","cl","dl","l","pièce(s)"],
                    key=f"extra_unit_{j}",
                    index=["mg","g","kg","cl","dl","l","pièce(s)"].index(unit_extra_default) if unit_extra_default in ["mg","g","kg","cl","dl","l","pièce(s)"] else 1
                )
            extras_list.append({
                "category": category,
                "item": item,
                "quantity": float(qty_extra),
                "unit": unit_extra
            })

        if st.button("💾 Enregistrer la recette", key="save_recipe", use_container_width=True):
            if not name.strip():
                st.error("❌ Le nom de la recette ne peut pas être vide.")
            elif not ingrédients_list:
                st.error("❌ Vous devez ajouter au moins un ingrédient.")
            else:
                ing_json = json.dumps([
                    {"ingredient": nm.strip(), "quantity": float(qt), "unit": un.strip()}
                    for nm, qt, un in ingrédients_list if nm.strip() and qt > 0 and un.strip()
                ], ensure_ascii=False)
                extras_json = json.dumps([e for e in extras_list if e["item"].strip() and e["quantity"] > 0], ensure_ascii=False)
                if recipe_id:
                    update_recipe(recipe_id, name.strip(), image_url.strip(), ing_json, instructions.strip(), extras_json)
                    st.success(f"✅ Recette « {name.strip()} » mise à jour.")
                else:
                    insert_recipe(USER_ID, name.strip(), image_url.strip(), ing_json, instructions.strip(), extras_json)
                    st.success(f"✅ Recette « {name.strip()} » ajoutée.")
                # Réinitialiser les compteurs d’ingrédients extras
                for key in ["ing_count", "extra_count", "import_ing_text"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun()

    st.markdown("---")

    # Affichage des recettes sous forme de cartes
    df_recettes = get_recipes_for_user(USER_ID)
    if df_recettes.empty:
        st.info("Vous n’avez (encore) aucune recette.")
    else:
        st.subheader("📖 Vos recettes")
        cards_per_row = 3
        for i in range(0, len(df_recettes), cards_per_row):
            cols = st.columns(cards_per_row, gap="medium")
            for idx, col in enumerate(cols):
                if i + idx < len(df_recettes):
                    row = df_recettes.iloc[i + idx]
                    rec_id = row["id"]
                    rec_name = row["name"]
                    rec_img = row["image_url"] or "https://via.placeholder.com/300x180.png?text=Pas+d%27image"
                    ingrédients = parse_ingredients(row["ingredients"])
                    with col:
                        st.markdown(
                            f"""
                            <div style="border:1px solid #ddd; border-radius:8px; overflow:hidden; margin-bottom:20px;">
                              <img src="{rec_img}" alt="{rec_name}" style="width:100%; height:160px; object-fit:cover;">
                              <div style="padding:10px;">
                                <div style="font-weight:600; font-size:1.1rem;">{rec_name}</div>
                                <div style="font-size:0.9rem; color:#555; margin-top:5px;">
                                  Ingrédients : {', '.join([ing['ingredient'] for ing in ingrédients][:3])}...
                                </div>
                                <div style="margin-top:10px;">
                                  <button class="btn-share" onclick="alert('Fonctionnalité partagée non implémentée')">Partager</button>
                                  <button class="btn-delete" onclick="window._deleteRecipe({rec_id})">Supprimer</button>
                                </div>
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
        # JS pour supprimer la recette directement depuis la carte
        st.markdown(
            """
            <script>
            window._deleteRecipe = function(recipe_id) {
                const params = new URLSearchParams(window.location.search);
                params.set("deleteRec", recipe_id);
                window.history.replaceState(null, null, "?" + params.toString());
                window.location.reload();
            }
            </script>
            """,
            unsafe_allow_html=True
        )
        # Si query param "deleteRec" est présent, on supprime la recette
        delete_param = st.experimental_get_query_params().get("deleteRec")
        if delete_param:
            try:
                rec_to_delete = int(delete_param[0])
                delete_recipe(rec_to_delete)
                # Nettoyage du param
                st.experimental_set_query_params({})
                st.success("✅ Recette supprimée.")
                st.experimental_rerun()
            except:
                pass

# ---------------------------------------------------------------------
# 9) PAGE : Planificateur (sélection jour/repas/recette)
# ---------------------------------------------------------------------
elif current_section == "Planificateur":
    st.markdown('<div id="planner"></div>', unsafe_allow_html=True)
    st.header("📅 Planifier mes repas")
    st.markdown("Choisissez une recette pour chaque jour et chaque repas.")

    df_recettes = get_recipes_for_user(USER_ID)
    choix_recettes = [""] + df_recettes["name"].tolist()

    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    meals = ["Petit-déjeuner","Déjeuner","Dîner"]

    with st.form(key="plan_form", clear_on_submit=False):
        cols = st.columns(3, gap="large")
        selections = []
        for i, day in enumerate(days):
            col = cols[0] if i < 3 else (cols[1] if i < 6 else cols[2])
            with col:
                st.subheader(f"🗓 {day}")
                for meal in meals:
                    key_name = f"{day}_{meal}"
                    # Valeur par défaut = ce qui est déjà planifié (si existant)
                    existing = get_mealplan_for_user(USER_ID)
                    default_choice = ""
                    if not existing.empty:
                        filt = existing[
                            (existing["day"] == day) & (existing["meal"] == meal)
                        ]
                        if not filt.empty:
                            default_choice = filt.iloc[0]["recipe_name"]
                    recipe_choice = st.selectbox(
                        f"{meal} :",
                        choix_recettes,
                        key=key_name,
                        index=choix_recettes.index(default_choice) if default_choice in choix_recettes else 0
                    )
                    selections.append((day, meal, recipe_choice))

        if st.form_submit_button("💾 Enregistrer le planning", use_container_width=True):
            df_plan = pd.DataFrame(selections, columns=["Day","Meal","Recipe"])
            df_plan = df_plan[df_plan["Recipe"] != ""].reset_index(drop=True)
            upsert_mealplan(USER_ID, df_plan)
            st.success("✅ Planning de la semaine enregistré.")
            st.experimental_rerun()

    st.markdown("---")
    st.write("### 🏠 Votre planning actuel")
    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Vous n’avez pas encore de planning.")
    else:
        st.table(
            df_current_plan[["day","meal","recipe_name"]].rename(
                columns={"day":"Jour","meal":"Repas","recipe_name":"Recette"}
            )
        )

# ---------------------------------------------------------------------
# 10) PAGE : Liste de courses (automatique + téléchargeable)
# ---------------------------------------------------------------------
elif current_section == "Liste de courses":
    st.markdown('<div id="shopping"></div>', unsafe_allow_html=True)
    st.header("🛒 Liste de courses générée")
    st.markdown("La liste est compilée automatiquement depuis votre planning et vos extras.")

    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Planifiez d’abord vos repas pour générer la liste.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        df_recettes = get_recipes_for_user(USER_ID)

        # Parcours des recettes planifiées
        for _, row_plan in df_current_plan.iterrows():
            recette_name = row_plan["recipe_name"]
            row_rec = df_recettes[df_recettes["name"] == recette_name]
            if not row_rec.empty:
                ing_list = parse_ingredients(row_rec.iloc[0]["ingredients"])
                for ing in ing_list:
                    key = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    if total_ingredients[key]["unit"] and total_ingredients[key]["unit"] != unit:
                        st.warning(f"⚠️ Unité différente pour « {key} » ; vérifiez manuellement.")
                    total_ingredients[key]["quantity"] += qty
                    total_ingredients[key]["unit"] = unit

        # Ajout des extras de TOUTES les recettes
        for _, row_rec in df_recettes.iterrows():
            extras = parse_extras(row_rec["extras_json"] or "[]")
            for e in extras:
                cat = e["category"]
                item = e["item"]
                key = f"{cat} : {item}"
                qty = e["quantity"]
                unit = e["unit"]
                if total_ingredients[key]["unit"] and total_ingredients[key]["unit"] != unit:
                    st.warning(f"⚠️ Unité différente pour « {key} » ; vérifiez manuellement.")
                total_ingredients[key]["quantity"] += qty
                total_ingredients[key]["unit"] = unit

        shopping_data = [
            {"Ingrédient / Extra": ing, "Quantité": vals["quantity"], "Unité": vals["unit"]}
            for ing, vals in total_ingredients.items()
        ]
        shopping_df = pd.DataFrame(shopping_data)

        st.table(shopping_df)

        # Télécharger la liste au format CSV
        towrite = io.StringIO()
        shopping_df.to_csv(towrite, index=False, sep=";")
        towrite.seek(0)
        st.download_button(
            label="⤓ Télécharger la liste en CSV",
            data=towrite,
            file_name="liste_de_courses.csv",
            mime="text/csv",
        )

# ---------------------------------------------------------------------
# 11) PAGE : Conseils & Astuces (texte statique)
# ---------------------------------------------------------------------
elif current_section == "Conseils & Astuces":
    st.markdown('<div id="tips"></div>', unsafe_allow_html=True)
    st.header("💡 Conseils & Astuces sur le Batch Cooking")
    st.markdown("""
    **Bienvenue dans la section Astuces !**  
    Découvrez des conseils pour optimiser votre batch cooking et gagner du temps tout en mangeant sain :

    1. **Planifiez vos menus à l’avance** :  
       Choisissez 3 à 5 recettes que vous pouvez préparer en une seule session.  
    2. **Cuisinez des bases polyvalentes** :  
       Préparez du riz, du quinoa ou des légumineuses en grande quantité pour accompagner plusieurs plats toute la semaine.  
    3. **Congélation intelligente** :  
       Portionnez vos repas en boîtes hermétiques afin de congeler au plus vite.  
    4. **Optimisez vos ingrédients frais** :  
       Coupez et rangez vos légumes dans des sachets hermétiques pour gagner du temps chaque jour.  
    5. **Variez les assaisonnements** :  
       Une même base protéinée (poulet, tofu, œufs) peut devenir curry, teriyaki ou épicée selon votre envie.  
    6. **Nettoyage au fur et à mesure** :  
       Pendant que vos plats cuisent, profitez-en pour laver et ranger vos ustensiles.  
    7. **Impliquer toute la famille** :  
       Attribuez des tâches simples (laver légumes, mélanger) pour rendre le batch cooking ludique.  
    8. **Utilisez des boîtes réutilisables** :  
       Privilégiez des boîtes hermétiques et étiquetez-les (date, contenu) pour éviter le gaspillage.  
    9. **Réinventez vos restes** :  
       Transformez vos restes en lunch box (salades composées, wraps, omelettes).  
    10. **Planifiez vos collations** :  
       Pensez à préparer des fruits coupés, des barres de céréales maison, ou des yaourts à emporter.  

    > Bon batch cooking !  
    """)

# ---------------------------------------------------------------------
# 12) PAGE : Profil (modifier foyer, composition, repas/jour)
# ---------------------------------------------------------------------
else:  # current_section == "Profil"
    st.markdown('<div id="profile"></div>', unsafe_allow_html=True)
    st.header("👤 Profil utilisateur")
    st.markdown("Modifiez vos informations de foyer et vos préférences de repas.")

    # Valeurs par défaut extraites de la base
    profile = get_user_profile(USER_ID)
    household_default = profile.get("household_type") or "Solo"
    meals_default = profile.get("meals_per_day") or 3
    children_default = profile.get("num_children") or 0
    adolescents_default = profile.get("num_adolescents") or 0
    adults_default = profile.get("num_adults") or (1 if household_default == "Solo" else (2 if household_default == "Couple" else 2))

    st.subheader("Type de foyer")
    household = st.selectbox(
        "Vous êtes :",
        options=["Solo","Couple","Famille"],
        index=["Solo","Couple","Famille"].index(household_default) if household_default in ["Solo","Couple","Famille"] else 0
    )

    st.subheader("Nombre de repas par jour")
    meals_per_day = st.number_input("Repas/jour :", min_value=1, max_value=10, step=1, value=meals_default, key="profile_meals")

    if household == "Famille":
        st.subheader("Composition de la famille")
        colA, colB, colC = st.columns(3)
        with colA:
            num_adults = st.number_input("Adultes :", min_value=0, max_value=10, step=1, value=adults_default if household_default == "Famille" else 0, key="profile_adults")
        with colB:
            num_adolescents = st.number_input("Adolescents :", min_value=0, max_value=10, step=1, value=adolescents_default if household_default == "Famille" else 0, key="profile_adolescents")
        with colC:
            num_children = st.number_input("Enfants :", min_value=0, max_value=10, step=1, value=children_default if household_default == "Famille" else 0, key="profile_children")
    else:
        num_adults = 1 if household == "Solo" else 2
        num_adolescents = 0
        num_children = 0

    if st.button("💾 Mettre à jour le profil", use_container_width=True):
        update_user_profile(
            USER_ID,
            {
                "household_type": household,
                "meals_per_day": meals_per_day,
                "num_children": num_children,
                "num_adolescents": num_adolescents,
                "num_adults": num_adults
            }
        )
        st.success("✅ Profil mis à jour.")
        st.experimental_rerun()
