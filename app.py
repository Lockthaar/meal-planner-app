# app.py

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib
import matplotlib.pyplot as plt

# ---------------------------------------------
# CONFIGURATION GLOBALE DE LA PAGE
# ---------------------------------------------
st.set_page_config(
    page_title="Batchist – Batch Cooking 2.0",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ---------------------------------------------
# CONSTANTES & URL D’IMAGES PAR DÉFAUT
# ---------------------------------------------
BANNER_URL = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1350&q=80"
DEFAULT_RECIPE_IMAGE = "https://images.unsplash.com/photo-1523986371872-9d3ba2e2f6e4?auto=format&fit=crop&w=800&q=80"

# Images pour les tuiles de type de foyer
HOUSEHOLD_TYPES = {
    "solo": {
        "label": "Solo",
        "img": "https://img.icons8.com/fluency/96/ffd700/user-male-circle.png"
    },
    "couple": {
        "label": "Couple",
        "img": "https://img.icons8.com/fluency/96/ffd700/couple-with-heart.png"
    },
    "famille": {
        "label": "Famille",
        "img": "https://img.icons8.com/fluency/96/ffd700/family.png"
    }
}

DB_PATH = "meal_planner.db"

# ---------------------------------------------
# UTILITAIRES POUR LA BASE DE DONNÉES
# ---------------------------------------------
@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def initialize_database():
    """
    Crée / migre les tables suivantes :
     - users (avec colonnes : username, password_hash, household_type, children_count, adolescents_count, adults_count, meals_per_week)
     - recipes
     - ingredients
     - mealplans
     - extras
    """
    conn = get_connection()
    cursor = conn.cursor()

    # --- TABLE users ---
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='users'
    """)
    if cursor.fetchone() is None:
        # création initiale
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                household_type TEXT NOT NULL,
                children_count INTEGER NOT NULL DEFAULT 0,
                adolescents_count INTEGER NOT NULL DEFAULT 0,
                adults_count INTEGER NOT NULL DEFAULT 0,
                meals_per_week INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    else:
        # vérifier si toutes les colonnes sont présentes
        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        needed_cols = {
            "id", "username", "password_hash", "household_type",
            "children_count", "adolescents_count", "adults_count", "meals_per_week"
        }
        if not needed_cols.issubset(existing_cols):
            # suppression + recréation
            cursor.execute("DROP TABLE IF EXISTS users")
            conn.commit()
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    household_type TEXT NOT NULL,
                    children_count INTEGER NOT NULL DEFAULT 0,
                    adolescents_count INTEGER NOT NULL DEFAULT 0,
                    adults_count INTEGER NOT NULL DEFAULT 0,
                    meals_per_week INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.commit()

    # --- TABLE recipes ---
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='recipes'
    """)
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                recipe_name TEXT NOT NULL,
                instructions TEXT NOT NULL,
                image_url TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

    # --- TABLE ingredients ---
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='ingredients'
    """)
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id)
            )
        """)
        conn.commit()

    # --- TABLE mealplans ---
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='mealplans'
    """)
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE mealplans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                day TEXT NOT NULL,
                meal TEXT NOT NULL,
                recipe_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (recipe_id) REFERENCES recipes(id)
            )
        """)
        conn.commit()

    # --- TABLE extras ---
    cursor.execute("""
        SELECT name FROM sqlite_master WHERE type='table' AND name='extras'
    """)
    if cursor.fetchone() is None:
        cursor.execute("""
            CREATE TABLE extras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        conn.commit()

# Initialisation / migration à chaque exécution
initialize_database()

# ---------------------------------------------
# HASHAGE DE MOT DE PASSE
# ---------------------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# ---------------------------------------------
# AUTHENTIFICATION / INSCRIPTION
# ---------------------------------------------
def register_user(username: str, password: str) -> int | None:
    """
    Crée un user avec username + sha256(password).
    household_type = 'solo' par défaut, et counts = 0 par défaut.
    Renvoie l'ID si OK, None en cas de duplicata ou d'erreur SQL.
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    try:
        cursor.execute(
            """INSERT INTO users 
               (username, password_hash, household_type, children_count, adolescents_count, adults_count, meals_per_week)
               VALUES (?, ?, 'solo', 0, 0, 0, 0)""",
            (username.strip(), pwd_hash)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    except sqlite3.OperationalError as e:
        st.error("❌ Erreur interne lors de l’inscription.")
        st.write(f"_Détail technique : {e}_")
        return None

def login_user(username: str, password: str) -> int | None:
    """
    Retourne l’ID de l’utilisateur si username + sha256(password) sont corrects, sinon None.
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    try:
        cursor.execute(
            "SELECT id FROM users WHERE username = ? AND password_hash = ?",
            (username.strip(), pwd_hash)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError as e:
        st.error("❌ Erreur interne lors de la connexion.")
        st.write(f"_Détail technique : {e}_")
        return None

def get_user_profile(user_id: int) -> dict:
    """
    Renvoie un dict avec toutes les infos stockées dans users pour user_id.
    { username, household_type, children_count, adolescents_count, adults_count, meals_per_week }
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT username, household_type, children_count, adolescents_count, adults_count, meals_per_week
        FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    if not row:
        return {}
    return {
        "username": row[0],
        "household_type": row[1],
        "children_count": row[2],
        "adolescents_count": row[3],
        "adults_count": row[4],
        "meals_per_week": row[5]
    }

def update_user_profile(user_id: int,
                        household_type: str = None,
                        children: int | None = None,
                        adolescents: int | None = None,
                        adults: int | None = None,
                        meals_per_week: int | None = None):
    """
    Met à jour les champs fournis pour l’utilisateur.
    """
    conn = get_connection()
    cursor = conn.cursor()

    updates = []
    params = []
    if household_type is not None:
        updates.append("household_type = ?")
        params.append(household_type)
    if children is not None:
        updates.append("children_count = ?")
        params.append(children)
    if adolescents is not None:
        updates.append("adolescents_count = ?")
        params.append(adolescents)
    if adults is not None:
        updates.append("adults_count = ?")
        params.append(adults)
    if meals_per_week is not None:
        updates.append("meals_per_week = ?")
        params.append(meals_per_week)

    if updates:
        clause = ", ".join(updates)
        params.append(user_id)
        cursor.execute(f"UPDATE users SET {clause} WHERE id = ?", tuple(params))
        conn.commit()

# ---------------------------------------------
# SESSION STATE INITIALIZATION
# ---------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = ""

if "show_household_modal" not in st.session_state:
    st.session_state.show_household_modal = False

if "modal_step" not in st.session_state:
    st.session_state.modal_step = 1

# Buffer pour les recettes / ingrédients (identique à avant)
if "ingredients_buffer" not in st.session_state:
    st.session_state.ingredients_buffer = []

if "extras_buffer" not in st.session_state:
    st.session_state.extras_buffer = []

# Buffers temporaires pour récupérer les valeurs du modal (avant commit en base)
if "tmp_household_type" not in st.session_state:
    st.session_state.tmp_household_type = "solo"
if "tmp_children" not in st.session_state:
    st.session_state.tmp_children = 0
if "tmp_adolescents" not in st.session_state:
    st.session_state.tmp_adolescents = 0
if "tmp_adults" not in st.session_state:
    st.session_state.tmp_adults = 0
if "tmp_meals" not in st.session_state:
    st.session_state.tmp_meals = 0

# ---------------------------------------------
# FONCTION D’AFFICHAGE DE LA PAGE DE LOGIN / INSCRIPTION
# ---------------------------------------------
def show_login_page():
    """
    Affiche un écran à onglets : [Connexion] [Inscription].
    Après inscription réussie, déclenche l’ouverture du modal en 3 étapes.
    """
    st.title("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])

    with tab1:
        st.subheader("🔐 Connexion")
        login_user_input = st.text_input("Nom d’utilisateur", key="login_usr")
        login_pwd_input  = st.text_input("Mot de passe", type="password", key="login_pwd")
        if st.button("Se connecter"):
            if not login_user_input.strip() or not login_pwd_input.strip():
                st.error("❌ Merci de remplir tous les champs.")
            else:
                uid = login_user(login_user_input, login_pwd_input)
                if uid:
                    st.success(f"✅ Bienvenue, **{login_user_input.strip()}** !")
                    st.session_state.user_id = uid
                    st.session_state.username = login_user_input.strip()
                    st.experimental_rerun()
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    with tab2:
        st.subheader("📝 Inscription")
        reg_user_input = st.text_input("Choisissez un nom d’utilisateur", key="reg_usr")
        reg_pwd_input  = st.text_input("Choisissez un mot de passe", type="password", key="reg_pwd")
        reg_pwd_conf   = st.text_input("Confirmez le mot de passe", type="password", key="reg_pwd_conf")
        if st.button("S’inscrire"):
            if (not reg_user_input.strip()
                or not reg_pwd_input.strip()
                or not reg_pwd_conf.strip()):
                st.error("❌ Merci de remplir tous les champs.")
            elif reg_pwd_input != reg_pwd_conf:
                st.error("❌ Les mots de passe ne correspondent pas.")
            else:
                new_id = register_user(reg_user_input, reg_pwd_input)
                if new_id:
                    st.success("✅ Inscription réussie ! Veuillez compléter votre profil.")
                    # Initialiser le modal de profil
                    st.session_state.user_id = new_id
                    st.session_state.username = reg_user_input.strip()
                    st.session_state.show_household_modal = True
                    st.session_state.modal_step = 1
                    st.experimental_rerun()
                else:
                    st.error("❌ Ce nom d’utilisateur existe déjà !")

    st.stop()

# ---------------------------------------------
# FONCTION D’AFFICHAGE DU MODAL “PROFIL EN 3 ÉTAPES”
# ---------------------------------------------
def show_household_modal():
    """
    Ouvre une fenêtre modale (Streamlit 1.18+) en 3 étapes :
     1) Choix du type de foyer (solo, couple, famille)
     2) Nombre d’enfants, adolescents, adultes
     3) Nombre de repas par semaine

    À la validation de l’étape 3, on write en base et on ferme le modal.
    """
    with st.modal("Complétez votre profil", clear_on_close=False):
        st.markdown("<h3 style='color: white;'>Votre profil de foyer</h3>", unsafe_allow_html=True)
        st.write("Veuillez saisir quelques informations pour personnaliser votre expérience.")

        step = st.session_state.modal_step

        if step == 1:
            st.markdown("#### 1️⃣ Choisissez votre type de foyer")
            cols = st.columns(3, gap="small")
            idx = 0
            for key, info in HOUSEHOLD_TYPES.items():
                with cols[idx]:
                    # Si cette tuile est sélectionnée, on ajoute un contour doré
                    border_style = (
                        "border: 3px solid #ffd700; background-color: #333;"
                        if st.session_state.tmp_household_type == key
                        else "border: 2px solid #444; background-color: #222;"
                    )
                    if st.button("", key=f"choose_{key}"):
                        st.session_state.tmp_household_type = key

                    st.markdown(
                        f"""
                        <div style="{border_style}; border-radius: 8px; padding: 12px; text-align: center;">
                            <img src="{info['img']}" width="64"/><br>
                            <span style="color: white; font-weight: bold;">{info['label']}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                idx += 1

            if st.button("Suivant ➡️"):
                st.session_state.modal_step = 2
                st.experimental_rerun()

        elif step == 2:
            st.markdown("#### 2️⃣ Combien de personnes dans votre foyer ?")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.session_state.tmp_children = st.number_input(
                    "Enfants", 
                    min_value=0, max_value=20, step=1,
                    value=st.session_state.tmp_children,
                    key="in_children"
                )
            with c2:
                st.session_state.tmp_adolescents = st.number_input(
                    "Adolescents", 
                    min_value=0, max_value=20, step=1,
                    value=st.session_state.tmp_adolescents,
                    key="in_adolescents"
                )
            with c3:
                st.session_state.tmp_adults = st.number_input(
                    "Adultes",
                    min_value=0, max_value=20, step=1,
                    value=st.session_state.tmp_adults,
                    key="in_adults"
                )
            st.markdown(" ")
            if st.button("⏪ Retour"):
                st.session_state.modal_step = 1
                st.experimental_rerun()
            st.write(" ")
            if st.button("Suivant ➡️"):
                st.session_state.modal_step = 3
                st.experimental_rerun()

        elif step == 3:
            st.markdown("#### 3️⃣ Combien de repas par semaine ?")
            st.session_state.tmp_meals = st.number_input(
                "Repas hebdomadaires",
                min_value=1, max_value=50, step=1,
                value=st.session_state.tmp_meals,
                key="in_meals"
            )
            st.markdown(" ")
            row = st.columns(3)
            with row[0]:
                if st.button("⏪ Retour"):
                    st.session_state.modal_step = 2
                    st.experimental_rerun()
            with row[2]:
                if st.button("✅ Valider"):
                    # On commit en base toutes ces valeurs
                    update_user_profile(
                        st.session_state.user_id,
                        household_type=st.session_state.tmp_household_type,
                        children=st.session_state.tmp_children,
                        adolescents=st.session_state.tmp_adolescents,
                        adults=st.session_state.tmp_adults,
                        meals_per_week=st.session_state.tmp_meals
                    )
                    st.success("🎉 Profil enregistré !")
                    # On ferme le modal et on revient à l'app principale
                    st.session_state.show_household_modal = False
                    st.session_state.modal_step = 1
                    st.experimental_rerun()

        # Lorsque l’utilisateur clique sur la croix “✕”, st.modal la gère automatiquement en fermant la fenêtre.
        # Nous n’avons pas besoin d’un bouton explicite “fermer”.

# ---------------------------------------------
# GESTION DES RECETTES + INGREDIENTS + EXTRAS
# ---------------------------------------------
def add_recipe_to_db(user_id: int, recipe_name: str, instructions: str, img_url: str,
                     ingredients: list[dict]):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes (user_id, recipe_name, instructions, image_url) VALUES (?, ?, ?, ?)",
        (user_id, recipe_name.strip(), instructions.strip(), img_url.strip())
    )
    conn.commit()
    rec_id = cursor.lastrowid
    for ingr in ingredients:
        cursor.execute(
            "INSERT INTO ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
            (rec_id, ingr["name"].strip(), ingr["quantity"], ingr["unit"].strip())
        )
    conn.commit()

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, recipe_name, instructions, image_url FROM recipes WHERE user_id = ?",
        conn, params=(user_id,)
    )
    return df

def get_ingredients_for_recipe(recipe_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name, quantity, unit FROM ingredients WHERE recipe_id = ?", (recipe_id,))
    rows = cur.fetchall()
    return [{"name": r[0], "quantity": r[1], "unit": r[2]} for r in rows]

def delete_recipe(recipe_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
    cur.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()

def add_extra_to_db(user_id: int, name: str, quantity: float, unit: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO extras (user_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
        (user_id, name.strip(), quantity, unit.strip())
    )
    conn.commit()

def get_extras_for_user(user_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, quantity, unit FROM extras WHERE user_id = ?", (user_id,))
    rows = cur.fetchall()
    return [{"id": r[0], "name": r[1], "quantity": r[2], "unit": r[3]} for r in rows]

def delete_extra(extra_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM extras WHERE id = ?", (extra_id,))
    conn.commit()

# ---------------------------------------------
# GESTION DU MEALPLAN (PLANNING) + LISTE DE COURSES
# ---------------------------------------------
def upsert_mealplan(user_id: int, plan: list[dict]):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for ligne in plan:
        cur.execute(
            """INSERT INTO mealplans (user_id, day, meal, recipe_id, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, ligne["day"], ligne["meal"], ligne["recipe_id"], now_str)
        )
    conn.commit()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_id, timestamp FROM mealplans WHERE user_id = ?",
        conn, params=(user_id,)
    )
    return df

def get_recipe_name(recipe_id: int) -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT recipe_name FROM recipes WHERE id = ?", (recipe_id,))
    r = cur.fetchone()
    return r[0] if r else "Inconnue"

# ---------------------------------------------
# PAGE “TABLEAU DE BORD”
# ---------------------------------------------
def show_dashboard_page():
    st.markdown("<h2 style='color: white;'>🏠 Tableau de bord</h2>", unsafe_allow_html=True)

    # 1) Afficher les derniers repas planifiés
    df_plan = get_mealplan_for_user(st.session_state.user_id)
    if df_plan.empty:
        st.info("Vous n’avez pas encore planifié de repas pour cette semaine.")
    else:
        st.write("#### Vos dernières planifications")
        df_disp = df_plan.copy()
        df_disp["Recette"] = df_disp["recipe_id"].apply(lambda rid: get_recipe_name(rid))
        st.dataframe(
            df_disp[["day", "meal", "Recette", "timestamp"]]
            .sort_values(by="timestamp", ascending=False)
            .reset_index(drop=True),
            use_container_width=True
        )

    st.markdown("---")

    # 2) Breakdown Top 10 ingrédients (toutes recettes confondues)
    st.write("#### 📊 Top 10 des ingrédients utilisés")
    # Récupérer et agréger depuis la table ingredients
    conn = get_connection()
    query = """
        SELECT name, SUM(quantity) as total_qty
        FROM ingredients
        WHERE recipe_id IN (SELECT id FROM recipes WHERE user_id = ?)
        GROUP BY name
        ORDER BY total_qty DESC
        LIMIT 10
    """
    df_top = pd.read_sql_query(query, conn, params=(st.session_state.user_id,))

    if df_top.empty:
        st.info("Aucune recette enregistrée → aucun ingrédient à afficher.")
    else:
        # Utilisation de Matplotlib pour un graphique simple à barres
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.barh(df_top["name"], df_top["total_qty"])
        ax.invert_yaxis()
        ax.set_xlabel("Quantité totale")
        ax.set_ylabel("Ingrédient")
        ax.set_title("Top 10 des ingrédients")
        st.pyplot(fig)

    st.markdown("---")

    # 3) Formulaire de planification hebdomadaire
    st.write("#### 📅 Planifier vos repas pour la semaine")
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]
    df_recs = get_recipes_for_user(st.session_state.user_id)

    planning_buffer = []
    with st.form("form_plan"):
        for d in days:
            st.markdown(f"**{d}**")
            cols = st.columns(len(meals))
            for idx, m in enumerate(meals):
                with cols[idx]:
                    keyname = f"sel_{d}_{m}"
                    if df_recs.empty:
                        st.write("Pas de recette")
                    else:
                        choix = st.selectbox(
                            f"{m}",
                            [""] + df_recs["recipe_name"].tolist(),
                            key=keyname
                        )
                        if choix:
                            rid = int(df_recs[df_recs["recipe_name"] == choix]["id"].iloc[0])
                            planning_buffer.append({"day": d, "meal": m, "recipe_id": rid})
        if st.form_submit_button("💾 Enregistrer le planning"):
            if not planning_buffer:
                st.error("❌ Veuillez sélectionner au moins une recette.")
            else:
                upsert_mealplan(st.session_state.user_id, planning_buffer)
                st.success("✅ Planning enregistré !")
                st.experimental_rerun()

# ---------------------------------------------
# PAGE “MES RECETTES”
# ---------------------------------------------
def show_recipes_page():
    st.markdown("<h2 style='color: white;'>📖 Mes recettes</h2>", unsafe_allow_html=True)

    # --- AJOUT DE RECETTE ---
    st.subheader("➕ Ajouter une nouvelle recette")
    with st.form("form_recette", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            rec_name = st.text_input("Nom de la recette", key="inp_rec_name")
            rec_instructions = st.text_area("Instructions détaillées", key="inp_rec_inst")
        with col2:
            rec_img = st.text_input(
                "URL de l’image (optionnel)",
                placeholder=DEFAULT_RECIPE_IMAGE,
                key="inp_rec_img"
            )
            st.caption("Si vide : image par défaut sous license Unsplash")
        st.markdown("---")

        st.write("**1) Ajoutez vos ingrédients un à un :**")
        # Afficher le buffer
        if st.session_state.ingredients_buffer:
            df_buf = pd.DataFrame(st.session_state.ingredients_buffer)
            st.dataframe(df_buf[["name", "quantity", "unit"]], use_container_width=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            name_ingr = st.text_input("Nom ingrédient", key="ingr_name")
        with c2:
            qty_ingr = st.number_input("Quantité", min_value=0.0, format="%.2f", key="ingr_qty")
        with c3:
            unit_ingr = st.text_input("Unité (ex : g, ml, etc.)", key="ingr_unit")

        if st.button("➕ Ajouter l’ingrédient"):
            if not name_ingr.strip() or qty_ingr <= 0 or not unit_ingr.strip():
                st.error("❌ Merci de remplir tous les champs de l’ingrédient.")
            else:
                st.session_state.ingredients_buffer.append({
                    "name": name_ingr.strip(),
                    "quantity": qty_ingr,
                    "unit": unit_ingr.strip()
                })
                st.experimental_rerun()

        st.markdown("---")
        if st.form_submit_button("💾 Enregistrer la recette"):
            if not rec_name.strip() or not rec_instructions.strip():
                st.error("❌ Merci de saisir un nom et des instructions.")
            elif len(st.session_state.ingredients_buffer) == 0:
                st.error("❌ Merci d’ajouter au moins un ingrédient.")
            else:
                final_img = rec_img.strip() if rec_img.strip() else DEFAULT_RECIPE_IMAGE
                add_recipe_to_db(
                    st.session_state.user_id,
                    rec_name,
                    rec_instructions,
                    final_img,
                    st.session_state.ingredients_buffer
                )
                st.success("✅ Recette ajoutée !")
                st.session_state.ingredients_buffer = []
                st.experimental_rerun()

    st.markdown("---")

    # --- COMPLÉMENTS DE COURSES ---
    st.subheader("📝 Compléments de courses (Maison)")
    with st.form("form_extras", clear_on_submit=True):
        e1, e2, e3 = st.columns([2, 1, 1])
        with e1:
            extra_name = st.text_input("Nom ingrédient", key="extra_name")
        with e2:
            extra_qty = st.number_input("Quantité", min_value=0.0, format="%.2f", key="extra_qty")
        with e3:
            extra_unit = st.text_input("Unité", key="extra_unit")

        if st.form_submit_button("➕ Ajouter aux compléments"):
            if not extra_name.strip() or extra_qty <= 0 or not extra_unit.strip():
                st.error("❌ Merci de remplir tous les champs du complément.")
            else:
                add_extra_to_db(
                    st.session_state.user_id,
                    extra_name,
                    extra_qty,
                    extra_unit
                )
                st.success("✅ Complément ajouté !")
                st.experimental_rerun()

    extras = get_extras_for_user(st.session_state.user_id)
    if extras:
        st.write("#### Vos compléments existants")
        for ex in extras:
            col_a, col_b, col_c, col_d = st.columns([3, 1, 1, 1])
            with col_a:
                st.write(f"- {ex['name']} : {ex['quantity']} {ex['unit']}")
            with col_b:
                if st.button("❌ Supprimer", key=f"del_ext_{ex['id']}"):
                    delete_extra(ex["id"])
                    st.success("🗑️ Complément supprimé.")
                    st.experimental_rerun()
    else:
        st.info("Vous n’avez pas de compléments pour le moment.")

    st.markdown("---")

    # --- FICHES-RECETTES EXISTANTES ---
    st.subheader("📚 Fiches de vos recettes")
    df_recs = get_recipes_for_user(st.session_state.user_id)
    if df_recs.empty:
        st.info("Vous n’avez pas encore ajouté de recette.")
    else:
        for idx, row in df_recs.iterrows():
            rid = row["id"]
            name = row["recipe_name"]
            inst = row["instructions"]
            img_url = row["image_url"] if row["image_url"] else DEFAULT_RECIPE_IMAGE
            ingr_list = get_ingredients_for_recipe(rid)

            st.markdown("---")
            card_cols = st.columns([1, 2, 1])
            with card_cols[0]:
                st.image(img_url, width=180, caption=name)
            with card_cols[1]:
                st.markdown(f"##### {name}")
                st.write("**Ingrédients :**")
                for ingr in ingr_list:
                    st.write(f"- {ingr['name']} : {ingr['quantity']} {ingr['unit']}")
                st.write("**Instructions :**")
                st.write(inst)
            with card_cols[2]:
                if st.button("❌ Supprimer", key=f"del_rec_{rid}"):
                    delete_recipe(rid)
                    st.success("🗑️ Recette supprimée.")
                    st.experimental_rerun()

                # Bouton “Partager” → lien vers Twitter pour partager du texte basique
                tweet = f"Découvrez ma recette « {name} » sur Batchist !"
                tweet_url = (
                    "https://twitter.com/intent/tweet?"
                    + f"text={tweet.replace(' ', '%20')}"
                )
                st.markdown(f"[🐦 Partager sur Twitter]({tweet_url})", unsafe_allow_html=True)

# ---------------------------------------------
# PAGE “LISTE DE COURSES”
# ---------------------------------------------
def show_shopping_list_page():
    st.markdown("<h2 style='color: white;'>🛒 Liste de courses</h2>", unsafe_allow_html=True)

    df_plan = get_mealplan_for_user(st.session_state.user_id)
    if df_plan.empty:
        st.info("Planifiez vos repas dans le Tableau de bord pour générer la liste.")
        return

    # 1) Ingrédients des recettes planifiées
    conn = get_connection()
    ingr_records = []
    for rid in df_plan["recipe_id"].unique():
        ingredients = get_ingredients_for_recipe(rid)
        for ingr in ingredients:
            ingr_records.append((ingr["name"], ingr["quantity"], ingr["unit"]))

    # 2) Compléments “extras”
    extras = get_extras_for_user(st.session_state.user_id)
    for ex in extras:
        ingr_records.append((ex["name"], ex["quantity"], ex["unit"]))

    if not ingr_records:
        st.info("Aucun ingrédient à afficher.")
        return

    df_all = pd.DataFrame(ingr_records, columns=["name", "quantity", "unit"])
    df_sum = (
        df_all.groupby(["name", "unit"], as_index=False)
        .sum()
        .rename(columns={"name": "Ingrédient", "unit": "Unité", "quantity": "Quantité approximative"})
    )
    st.dataframe(df_sum, use_container_width=True)

# ---------------------------------------------
# PAGE “PROFIL”
# ---------------------------------------------
def show_profile_page():
    profil = get_user_profile(st.session_state.user_id)
    st.markdown("<h2 style='color: white;'>🧑‍💻 Mon profil</h2>", unsafe_allow_html=True)
    st.write(f"**Nom d’utilisateur :** {profil['username']}")
    ht_label = HOUSEHOLD_TYPES.get(profil['household_type'], {"label": "Inconnu"})["label"]
    st.write(f"**Type de foyer :** {ht_label}")
    st.write(f"**Enfants :** {profil['children_count']}")
    st.write(f"**Adolescents :** {profil['adolescents_count']}")
    st.write(f"**Adultes :** {profil['adults_count']}")
    st.write(f"**Repas / semaine :** {profil['meals_per_week']}")

    if st.button("🖉 Modifier mon profil"):
        st.session_state.show_household_modal = True
        st.session_state.modal_step = 1
        st.experimental_rerun()

# ---------------------------------------------
# MENU DE NAVIGATION PRINCIPALE (TABS)
# ---------------------------------------------
def main_app():
    # Affichage de la bannière en haut
    st.image(BANNER_URL, use_column_width=True)

    # Onglets horizontaux
    tabs = st.tabs(["🏠 Tableau de bord", "📖 Mes recettes", "🛒 Liste de courses", "🧑‍💻 Profil", "🔓 Se déconnecter"])

    # Tableau de bord
    with tabs[0]:
        show_dashboard_page()

    # Mes recettes
    with tabs[1]:
        show_recipes_page()

    # Liste de courses
    with tabs[2]:
        show_shopping_list_page()

    # Profil
    with tabs[3]:
        show_profile_page()

    # Déconnexion
    with tabs[4]:
        if st.button("🔓 Se déconnecter"):
            for key in [
                "user_id", "username", "show_household_modal",
                "modal_step", "tmp_household_type", "tmp_children",
                "tmp_adolescents", "tmp_adults", "tmp_meals"
            ]:
                if key in st.session_state:
                    del st.session_state[key]
            st.experimental_rerun()

# ---------------------------------------------
# DÉROULEMENT PRINCIPAL
# ---------------------------------------------
# Si l’utilisateur n’est pas connecté : page de login/inscription
if st.session_state.user_id is None:
    show_login_page()

# Si, juste après l’inscription, il faut compléter le profil :
if st.session_state.show_household_modal:
    show_household_modal()
    st.stop()

# Sinon : afficher l’application principale
main_app()
