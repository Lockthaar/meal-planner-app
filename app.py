# app.py

import os
import sqlite3
import streamlit as st
import pandas as pd
import json
from collections import defaultdict
from typing import Optional
import io
from datetime import datetime, timedelta

# -------------------------------------------------------------------------------
# 1) DÉLETION OPTIONNELLE D'UNE ANCIENNE BASE (POUR DEBUG)
# -------------------------------------------------------------------------------
# Si vous rencontrez toujours une erreur "no such table: users", supprimez le fichier meal_planner.db existant
# en décommentant la ligne suivante (ou faites-le manuellement à la racine de votre projet) :

# if os.path.exists("meal_planner.db"):
#     os.remove("meal_planner.db")

# -------------------------------------------------------------------------------
# 2) DÉFINITION DU CHEMIN DE LA BASE ET DES FONCTIONS D’INIT / CONNEXION
# -------------------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    """
    Ouvre une connexion vers le fichier SQLite meal_planner.db
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """
    1) Crée les tables users, recipes, mealplans si elles n’existent pas.
    2) Ajoute les colonnes manquantes (profil, image_url, extras_json) le cas échéant.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 2.1) Table users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    conn.commit()

    # Vérifier/ajouter colonnes profil si manquantes
    cursor.execute("PRAGMA table_info(users)")
    cols_users = [col[1] for col in cursor.fetchall()]
    if "household_type" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN household_type TEXT")
    if "meals_per_day" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN meals_per_day INTEGER")
    if "num_children" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN num_children INTEGER")
    if "num_adolescents" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN num_adolescents INTEGER")
    if "num_adults" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN num_adults INTEGER")
    conn.commit()

    # 2.2) Table recipes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    cursor.execute("PRAGMA table_info(recipes)")
    cols_rec = [col[1] for col in cursor.fetchall()]
    if "image_url" not in cols_rec:
        cursor.execute("ALTER TABLE recipes ADD COLUMN image_url TEXT")
    if "extras_json" not in cols_rec:
        cursor.execute("ALTER TABLE recipes ADD COLUMN extras_json TEXT")
    conn.commit()

    # 2.3) Table mealplans
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            recipe_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()

    conn.close()
    # Afficher un log dans la console pour vérifier que l'init est passée
    print("✅ init_db() exécuté – tables (users, recipes, mealplans) OK")

# APPEL IMMÉDIAT À init_db(), avant toute logique Streamlit
init_db()

# -------------------------------------------------------------------------------
# 3) FONCTIONS DE GESTION DES DONNÉES (CRUD)
# -------------------------------------------------------------------------------
def add_user(username: str, password: str) -> bool:
    """
    Ajoute un nouvel utilisateur dans la table users.
    Retourne True si OK, False si le username existe déjà ou erreur SQLite.
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
        # Username déjà existant : UNIQUE contraint
        return False
    except sqlite3.OperationalError as e:
        st.error(f"⚠️ SQLite error dans add_user(): {e}")
        return False

def verify_user(username: str, password: str) -> Optional[int]:
    """
    Vérifie que (username,password) existe dans la table users.
    Si oui, renvoie l’id. Sinon, renvoie None.
    En cas d’erreur SQLite, affiche st.error(...) et renvoie None.
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
    Retourne le profil (household_type, meals_per_day, num_children, num_adolescents, num_adults) de l’utilisateur.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT household_type, meals_per_day, num_children, num_adolescents, num_adults FROM users WHERE id = ?",
        (user_id,)
    )
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
    Met à jour le profil dans la table users pour l’id donné.
    profile doit contenir : household_type, meals_per_day, num_children, num_adolescents, num_adults
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
    Renvoie un DataFrame des recettes (id, name, image_url, ingredients, instructions, extras_json)
    pour l’utilisateur spécifié.
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
    Insère une nouvelle recette pour l’utilisateur user_id.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes(user_id, name, image_url, ingredients, instructions, extras_json) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (user_id, name, image_url, ingredients_json, instructions, extras_json)
    )
    conn.commit()
    conn.close()

def update_recipe(recipe_id: int, name: str, image_url: str, ingredients_json: str,
                  instructions: str, extras_json: str):
    """
    Met à jour une recette existante via son ID.
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
    Supprime la recette dont l’id est passé en paramètre.
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
    Remplace (supprime + réinsère) tout le planning pour user_id.
    Ajoute un champ timestamp pour chaque ligne.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans(user_id, day, meal, recipe_name, timestamp) VALUES(?, ?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"], now_str)
        )
    conn.commit()
    conn.close()

@st.cache_data
def parse_ingredients(ing_str: str) -> list:
    """
    Convertit la chaîne JSON stockée sous 'ingredients' en liste de dicts.
    """
    try:
        return json.loads(ing_str)
    except:
        return []

@st.cache_data
def parse_extras(extras_str: str) -> list:
    """
    Convertit la chaîne JSON stockée sous 'extras_json' en liste de dicts.
    """
    try:
        return json.loads(extras_str)
    except:
        return []

# -------------------------------------------------------------------------------
# 4) CSS GLOBAL POUR NAVBAR + HERO + MODALES
# -------------------------------------------------------------------------------
st.set_page_config(
    page_title="Batchist: Meal Planner & Batch Cooking",
    page_icon="🥘",
    layout="wide",
)
st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        * { font-family: 'Poppins', sans-serif !important; }
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }

        .header {
            position: fixed; top: 0; left: 0; width: 100%;
            background: #ffffffcc; backdrop-filter: blur(10px);
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); z-index: 1000;
        }
        .header-content {
            max-width: 1200px; margin: 0 auto; padding: 10px 20px;
            display: flex; align-items: center; justify-content: space-between;
        }
        .header-logo img { width: 40px; height: 40px; }
        .nav-item { margin-left: 20px; font-weight: 500; cursor: pointer; color: #333; }
        .nav-item:hover { color: #FFA500; }

        .streamlit-container { padding-top: 100px !important; }

        .hero {
            position: relative; width: 100%; height: 300px;
            background: url('https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80') no-repeat center center / cover;
            margin-bottom: 40px; color: white;
        }
        .hero-overlay {
            position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.4);
        }
        .hero-text {
            position: relative; z-index: 1;
            text-align: center; top: 50%; transform: translateY(-50%);
        }
        .hero-text h1 { font-size: 3rem; margin-bottom: 10px; }
        .hero-text p { font-size: 1.2rem; opacity: 0.9; }

        /* MODAL */
        .modal-background {
            position: fixed; top: 0; left: 0;
            width: 100%; height: 100%;
            background-color: rgba(0,0,0,0.5); z-index: 1001;
        }
        .modal-content {
            position: fixed; top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            background: white; padding: 30px; border-radius: 8px;
            max-width: 450px; width: 90%; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.2); z-index: 1002;
        }
        .modal-title {
            font-size: 1.3rem; font-weight: 700; margin-bottom: 20px;
            color: #333; text-align: center;
        }
        .modal-close {
            position: absolute; top: 10px; right: 15px;
            font-size: 1.2rem; font-weight: 700; color: #666; cursor: pointer;
        }
        .modal-close:hover { color: #333; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------------------
# 5) NAVBAR + HERO (HTML/CSS)
# -------------------------------------------------------------------------------
# NAVBAR
st.markdown(
    """
    <div class="header">
      <div class="header-content">
        <div class="header-logo">
          <img src="https://img.icons8.com/fluency/48/000000/cutlery.png" alt="logo">
          <span style="font-size:1.5rem; font-weight:700; color:#333;">Batchist</span>
        </div>
        <div>
          <span class="nav-item" onclick="window.location.hash='#home'">Accueil</span>
          <span class="nav-item" onclick="window.location.hash='#recipes'">Recettes</span>
          <span class="nav-item" onclick="window.location.hash='#planner'">Planificateur</span>
          <span class="nav-item" onclick="window.location.hash='#shopping'">Liste de courses</span>
          <span class="nav-item" onclick="window.location.hash='#tips'">Conseils</span>
          <span class="nav-item" onclick="window.location.hash='#profile'">Profil</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# HERO
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

# -------------------------------------------------------------------------------
# 6) AUTHENTIFICATION + ONBOARDING
# -------------------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 0  # 0 : non connecté, 1 : onboarding foyer, 2 : onboarding repas, 3 : onboardé
if "household_type" not in st.session_state:
    st.session_state.household_type = None
if "meals_per_day" not in st.session_state:
    st.session_state.meals_per_day = None

def show_login_page():
    """
    Formulaire Connexion / Inscription, chacun dans un st.form pour capturer le submit-button.
    """
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["🔐 Connexion", "✍️ Inscription"])

    # ---------- Onglet Connexion ----------
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
                    if not profile.get("household_type") or not profile.get("meals_per_day"):
                        st.session_state.onboard_step = 1
                    else:
                        st.session_state.onboard_step = 3
                    st.experimental_rerun()
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    # ---------- Onglet Inscription ----------
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

# Tant que user_id est None, on affiche la page login et on stoppe (aucune autre requête n’est lancée)
if st.session_state.user_id is None:
    show_login_page()
    st.stop()

# -------------------------------------------------------------------------------
# 6.1) ONBOARDING POP-UPS (étapes 1 & 2)
# -------------------------------------------------------------------------------
if st.session_state.onboard_step == 1:
    # Pop-up “Comment vivez-vous ?”
    st.markdown('<div class="modal-background"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="modal-content">
          <div class="modal-close" onclick="window._closeOnboarding()" title="Fermer">✕</div>
          <div class="modal-title">Comment vivez-vous ?</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    # JS pour injecter closeOnboarding dans l’URL puis reload
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
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3, gap="small")
    with col1:
        if st.button("Solo", key="btn_solo", use_container_width=True):
            st.session_state.household_type = "Solo"
            st.session_state.onboard_step = 2
            st.experimental_rerun()
        st.markdown(
            '<div style="text-align:center; margin-top:5px;">'
            '<img src="https://img.icons8.com/dusk/100/000000/user.png" alt="solo"/></div>',
            unsafe_allow_html=True
        )
    with col2:
        if st.button("Couple", key="btn_couple", use_container_width=True):
            st.session_state.household_type = "Couple"
            st.session_state.onboard_step = 2
            st.experimental_rerun()
        st.markdown(
            '<div style="text-align:center; margin-top:5px;">'
            '<img src="https://img.icons8.com/dusk/100/000000/couple.png" alt="couple"/></div>',
            unsafe_allow_html=True
        )
    with col3:
        if st.button("Famille", key="btn_family", use_container_width=True):
            st.session_state.household_type = "Famille"
            st.session_state.onboard_step = 2
            st.experimental_rerun()
        st.markdown(
            '<div style="text-align:center; margin-top:5px;">'
            '<img src="https://img.icons8.com/dusk/100/000000/family.png" alt="famille"/></div>',
            unsafe_allow_html=True
        )

    # Si l’utilisateur clique sur la croix (closeOnboarding=1), on passe à l’appli
    if st.experimental_get_query_params().get("closeOnboarding"):
        st.session_state.onboard_step = 3
        st.experimental_set_query_params()
        st.experimental_rerun()
    st.stop()

if st.session_state.onboard_step == 2:
    # Pop-up “Combien de repas par jour ?”
    st.markdown('<div class="modal-background"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="modal-content">
          <div class="modal-close" onclick="window._closeOnboarding()" title="Fermer">✕</div>
          <div class="modal-title">Combien de repas par jour préparez-vous ?</div>
        </div>
        """,
        unsafe_allow_html=True,
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
        unsafe_allow_html=True,
    )

    meals_input = st.number_input(
        "Nombre de repas / jour :", 
        min_value=1, max_value=10, step=1, 
        value=3, key="meals_input"
    )
    if st.button("Valider", key="btn_set_meals", use_container_width=True):
        st.session_state.meals_per_day = meals_input
        if st.session_state.household_type == "Solo":
            num_adults, num_adolescents, num_children = 1, 0, 0
        elif st.session_state.household_type == "Couple":
            num_adults, num_adolescents, num_children = 2, 0, 0
        else:
            num_adults, num_adolescents, num_children = 2, 0, 0

        update_user_profile(
            st.session_state.user_id,
            {
                "household_type": st.session_state.household_type,
                "meals_per_day": st.session_state.meals_per_day,
                "num_children": num_children,
                "num_adolescents": num_adolescents,
                "num_adults": num_adults
            }
        )
        st.session_state.onboard_step = 3
        st.experimental_rerun()

    if st.experimental_get_query_params().get("closeOnboarding"):
        st.session_state.onboard_step = 3
        st.experimental_set_query_params()
        st.experimental_rerun()
    st.stop()

# -------------------------------------------------------------------------------
# 7) UTILISATEUR CONNECTÉ & ONBOARDÉ : AFFICHAGE DU CONTENU PRINCIPAL
# -------------------------------------------------------------------------------
USER_ID = st.session_state.user_id

with st.sidebar:
    st.markdown("---")
    st.write(f"👤 **Utilisateur : {st.session_state.username}**")
    profile = get_user_profile(USER_ID)
    st.write(f"🏠 Foyer : {profile.get('household_type', '–')}")
    st.write(f"🍽️ Repas/jour : {profile.get('meals_per_day', '–')}")
    if st.button("🔓 Se déconnecter", use_container_width=True):
        for key in ["user_id","username","onboard_step","household_type","meals_per_day"]:
            if key in st.session_state:
                del st.session_state[key]
        st.experimental_rerun()
    st.markdown("---")
    st.write("🗂️ **Navigation :**")
    section = st.radio(
        label="Aller à…",
        options=["Accueil", "Mes recettes", "Planificateur", "Liste de courses", "Conseils & Astuces", "Profil"],
        index=0
    )
    st.markdown("---")
    st.info(
        """
        💡 Commencez par créer vos recettes,  
        planifiez vos repas et générez votre liste de courses !
        """
    )

# -------------------------------------------------------------------------------
# 8) LAYOUT PAR SECTION
# -------------------------------------------------------------------------------
# — Accueil (Dashboard)
if section == "Accueil":
    st.markdown('<div id="home"></div>', unsafe_allow_html=True)
    st.header("🏠 Tableau de bord")
    st.markdown("Vos repas préférés du mois dernier")

    df_plan = get_mealplan_for_user(USER_ID)
    if df_plan.empty:
        st.info("Vous n’avez pas encore planifié de repas.")
    else:
        now = datetime.now()
        one_month_ago = now - timedelta(days=30)
        df_plan["timestamp"] = pd.to_datetime(df_plan["timestamp"])
        df_last_month = df_plan[df_plan["timestamp"] >= one_month_ago]
        if df_last_month.empty:
            st.info("Aucun repas planifié au cours du mois précédent.")
        else:
            favorites = df_last_month["recipe_name"].value_counts().head(6)
            cols = st.columns(3, gap="medium")
            idx = 0
            for recipe_name, count in favorites.items():
                df_rec = get_recipes_for_user(USER_ID)
                img_url = df_rec[df_rec["name"] == recipe_name]["image_url"]
                if not img_url.empty and img_url.values[0]:
                    img = img_url.values[0]
                else:
                    img = "https://via.placeholder.com/300x180.png?text=No+Image"
                with cols[idx % 3]:
                    st.markdown(
                        f"""
                        <div class="favorite-card">
                          <img src="{img}" alt="{recipe_name}">
                          <div class="favorite-card-body">
                            <div class="favorite-card-title">{recipe_name}</div>
                            <div style="font-size:0.9rem; color:#555;">Planifié {count} fois</div>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                idx += 1

# — Mes recettes
elif section == "Mes recettes":
    st.markdown('<div id="recipes"></div>', unsafe_allow_html=True)
    st.header("📋 Mes recettes")
    st.markdown("Ajoutez, consultez, modifiez ou supprimez vos recettes personnelles.")

    df_recettes = get_recipes_for_user(USER_ID)
    all_names = df_recettes["name"].tolist()

    with st.expander("➕ Ajouter / Modifier une recette", expanded=True):
        choice = st.selectbox(
            "Sélectionnez une recette à modifier (ou laissez vide pour nouvelle)",
            options=[""] + all_names
        )

        if choice:
            rec_row = df_recettes[df_recettes["name"] == choice].iloc[0]
            recipe_id = rec_row["id"]
            default_name = rec_row["name"]
            default_image = rec_row["image_url"] or ""
            default_ing = parse_ingredients(rec_row["ingredients"])
            default_instr = rec_row["instructions"] or ""
            default_extras = parse_extras(rec_row["extras_json"] or "[]")
        else:
            recipe_id = None
            default_name = ""
            default_image = ""
            default_ing = []
            default_instr = ""
            default_extras = []

        name = st.text_input("Nom de la recette", value=default_name, placeholder="Ex. : Gratin de légumes")
        image_url = st.text_input("URL de l’image (optionnelle)", value=default_image, placeholder="Ex. : https://…/mon_image.jpg")
        instructions = st.text_area("Instructions (facultatif)", value=default_instr, placeholder="Décrivez ici la préparation…")

        st.markdown("**Ingrédients**")
        ing_mode = st.radio("Mode d’ajout des ingrédients", ("Saisie manuelle", "Importer depuis texte"), index=0, horizontal=True)
        ingrédients_list = []
        if ing_mode == "Saisie manuelle":
            count_default = len(default_ing) if default_ing else 1
            if "ing_count" not in st.session_state:
                st.session_state.ing_count = count_default
            if st.button("➕ Ajouter une ligne", key="add_ing_manu"):
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
                    un = st.selectbox(f"Unité #{i+1}", ["mg","g","kg","cl","dl","l","pièce(s)"], key=f"ing_unit_{i}", index=["mg","g","kg","cl","dl","l","pièce(s)"].index(unit_i) if unit_i in ["mg","g","kg","cl","dl","l","pièce(s)"] else 1)
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
                    for ingr_i, qty_i, unit_i in ingrédients_list:
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
                    ["Boissons", "Maison", "Plantes", "Animaux"],
                    key=f"extra_cat_{j}",
                    index=["Boissons","Maison","Plantes","Animaux"].index(cat_default) if cat_default in ["Boissons","Maison","Plantes","Animaux"] else 0
                )
            with dcol2:
                item = st.text_input(f"Article #{j+1}", key=f"extra_item_{j}", value=item_default)
            with dcol3:
                qty_extra = st.number_input(f"Quantité #{j+1}", min_value=0.0, format="%.2f", key=f"extra_qty_{j}", value=qty_extra_default)
            with dcol4:
                unit_extra = st.selectbox(f"Unité #{j+1}", ["mg","g","kg","cl","dl","l","pièce(s)"], key=f"extra_unit_{j}", index=["mg","g","kg","cl","dl","l","pièce(s)"].index(unit_extra_default) if unit_extra_default in ["mg","g","kg","cl","dl","l","pièce(s)"] else 1)
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
                st.error("❌ Vous devez renseigner au moins un ingrédient.")
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
                # Réinitialiser le formulaire
                for key in ["new_name", "new_image_url", "new_instructions", "ing_count", "extra_count", "import_ing_text"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.experimental_rerun()

    st.markdown("---")

    # Affichage des recettes en cards
    df_recettes = get_recipes_for_user(USER_ID)
    if df_recettes.empty:
        st.info("Vous n’avez (encore) aucune recette enregistrée.")
    else:
        st.markdown("### 📖 Vos recettes")
        cards_per_row = 3
        for i in range(0, len(df_recettes), cards_per_row):
            cols = st.columns(cards_per_row, gap="medium")
            for idx, col in enumerate(cols):
                if i + idx < len(df_recettes):
                    row = df_recettes.iloc[i + idx]
                    recipe_id = row["id"]
                    recipe_name = row["name"]
                    image_url = row["image_url"] or "https://via.placeholder.com/300x180.png?text=Pas+d%27image"
                    ingrédients = parse_ingredients(row["ingredients"])
                    instructions_text = row["instructions"] or "Aucune instruction précisée."
                    with col:
                        st.markdown(
                            f"""
                            <div class="recipe-card">
                              <img src="{image_url}" alt="{recipe_name}">
                              <div class="recipe-card-body">
                                <div class="recipe-card-title">{recipe_name}</div>
                                <div style="font-size:0.9rem; color:#555; margin-top:5px;">
                                    Ingrédients : {', '.join([ing['ingredient'] for ing in ingrédients][:3])}...
                                </div>
                                <div class="recipe-card-buttons">
                                    <button onclick="alert('Affichage détails non implémenté')">Voir</button>
                                    <button onclick="alert('Pour modifier : réouvrez ce module et sélectionnez la recette')">Modifier</button>
                                </div>
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

# — Planificateur
elif section == "Planificateur":
    st.markdown('<div id="planner"></div>', unsafe_allow_html=True)
    st.header("📅 Planifier mes repas")
    st.markdown("Choisissez une recette pour chaque jour et chaque repas.")

    df_recettes = get_recipes_for_user(USER_ID)
    choix_recettes = [""] + df_recettes["name"].tolist()

    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]

    with st.form(key="plan_form", clear_on_submit=False):
        cols = st.columns(3)
        selections = []
        for i, day in enumerate(days):
            col = cols[0] if i < 3 else (cols[1] if i < 6 else cols[2])
            with col:
                st.subheader(f"🗓 {day}")
                for meal in meals:
                    recipe_choice = st.selectbox(
                        f"{meal} :",
                        choix_recettes,
                        key=f"{day}_{meal}"
                    )
                    selections.append((day, meal, recipe_choice))

        if st.form_submit_button("💾 Enregistrer le planning", use_container_width=True):
            df_plan = pd.DataFrame(selections, columns=["Day", "Meal", "Recipe"])
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
            df_current_plan[["day", "meal", "recipe_name"]].rename(
                columns={"day": "Jour", "meal": "Repas", "recipe_name": "Recette"}
            )
        )

# — Liste de courses
elif section == "Liste de courses":
    st.markdown('<div id="shopping"></div>', unsafe_allow_html=True)
    st.header("🛒 Liste de courses générée")
    st.markdown("La liste est compilée automatiquement depuis votre planning.")

    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        df_recettes = get_recipes_for_user(USER_ID)
        for _, row_plan in df_current_plan.iterrows():
            recette_name = row_plan["recipe_name"]
            row_rec = df_recettes[df_recettes["name"] == recette_name]
            if not row_rec.empty:
                ing_list = parse_ingredients(row_rec.iloc[0]["ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    if total_ingredients[clé]["unit"] and total_ingredients[clé]["unit"] != unit:
                        st.warning(f"⚠️ Unité différente pour « {clé} », vérifiez manuellement.")
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        shopping_data = [
            {"Ingrédient": ing, "Quantité": vals["quantity"], "Unité": vals["unit"]}
            for ing, vals in total_ingredients.items()
        ]
        shopping_df = pd.DataFrame(shopping_data)

        st.table(shopping_df)

        # Télécharger CSV
        towrite = io.StringIO()
        shopping_df.to_csv(towrite, index=False, sep=";")
        towrite.seek(0)
        st.download_button(
            label="⤓ Télécharger la liste en CSV",
            data=towrite,
            file_name="liste_de_courses.csv",
            mime="text/csv",
        )

# — Conseils & Astuces
elif section == "Conseils & Astuces":
    st.markdown('<div id="tips"></div>', unsafe_allow_html=True)
    st.header("💡 Conseils & Astuces sur le Batch Cooking")
    st.markdown("""
    **Bienvenue dans la page Astuces !**  
    Découvrez des conseils pour optimiser votre batch cooking, économiser du temps et cuisiner des plats savoureux :
    
    1. **Planifiez vos menus à l'avance** :  
       Sélectionnez 2 à 3 recettes par semaine que vous pouvez préparer en grandes quantités.  
    2. **Utilisez des contenants hermétiques** :  
       Investissez dans des boîtes de conservation réutilisables et étiquetez-les pour éviter la confusion.  
    3. **Cuisinez des aliments polyvalents** :  
       Préparez des légumineuses, du riz ou du quinoa en grande quantité pour accompagner plusieurs plats.  
    4. **Congélation intelligente** :  
       Séparez vos plats en portions individuelles avant de congeler pour décongeler rapidement une seule portion.  
    5. **Optimisez vos ingrédients frais** :  
       Coupez et stockez vos légumes en avance dans des sacs hermétiques ; les herbes fraîches se conservent plus longtemps si elles sont légèrement humides et bien emballées.  
    6. **Variez les assaisonnements** :  
       Préparez une base de protéines (poulet, tofu, œufs) et assaisonnez-la différemment chaque jour (curry, teriyaki, épices mexicaines).  
    7. **Surveillez les dates de péremption** :  
       Utilisez un auto-collant pour indiquer la date de préparation.  
    8. **Impliquer toute la famille** :  
       Si vous cuisinez pour une famille, attribuez des tâches simples aux enfants (mélanger, laver les légumes), cela rend l’activité ludique.  
    9. **Réinventez vos restes** :  
       Transformez les restes du dîner en lunch box le lendemain (salades composées, wraps, omelettes).  
    10. **Nettoyage au fur et à mesure** :  
       Pendant que les ingrédients cuisent, profitez des temps de pause pour nettoyer les surfaces et ustensiles utilisés.  

    Bon batch cooking !
    """)

# — Profil
else:  # section == "Profil"
    st.markdown('<div id="profile"></div>', unsafe_allow_html=True)
    st.header("👤 Profil utilisateur")
    st.markdown("Modifiez vos informations de foyer et d’usage de l’application.")

    profile = get_user_profile(USER_ID)
    household_default = profile.get("household_type") or "Solo"
    meals_default = profile.get("meals_per_day") or 3
    children_default = profile.get("num_children") or 0
    adolescents_default = profile.get("num_adolescents") or 0
    adults_default = profile.get("num_adults") or (1 if household_default == "Solo" else (2 if household_default == "Couple" else 2))

    st.subheader("Type de foyer")
    household = st.selectbox(
        "Vous êtes :",
        options=["Solo", "Couple", "Famille"],
        index=["Solo","Couple","Famille"].index(household_default) if household_default in ["Solo","Couple","Famille"] else 0
    )

    st.subheader("Nombre de repas par jour")
    meals_per_day = st.number_input("Repas/jour :", min_value=1, max_value=10, step=1, value=meals_default)

    if household == "Famille":
        st.subheader("Composition de la famille")
        colA, colB, colC = st.columns(3)
        with colA:
            num_adults = st.number_input("Adultes :", min_value=0, max_value=10, step=1, value=adults_default if household_default == "Famille" else 0)
        with colB:
            num_adolescents = st.number_input("Adolescents :", min_value=0, max_value=10, step=1, value=adolescents_default if household_default == "Famille" else 0)
        with colC:
            num_children = st.number_input("Enfants :", min_value=0, max_value=10, step=1, value=children_default if household_default == "Famille" else 0)
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
