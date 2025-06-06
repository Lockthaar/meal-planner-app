# app.py

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib

# --------------------------------------------------------------------------------
# CONFIGURATION DE LA PAGE
# --------------------------------------------------------------------------------

st.set_page_config(
    page_title="Batchist - Batch Cooking Simplifié",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --------------------------------------------------------------------------------
# BANNIÈRE (IMAGE EN LIGNE)
# --------------------------------------------------------------------------------

# Exemple d’URL d’image hébergée. Vous pouvez changer pour toute URL d’image libre de droits.
BANNER_URL = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1350&q=80"
st.image(BANNER_URL, use_container_width=True)

# --------------------------------------------------------------------------------
# CHEMIN VERS LA BASE DE DONNÉES SQLITE
# --------------------------------------------------------------------------------

DB_PATH = "meal_planner.db"

@st.cache_resource
def get_connection():
    """
    Retourne une connexion SQLite3 unique pour toute la session.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def initialize_database():
    """
    Crée les tables de base si elles n'existent pas.
    Ensuite, si la table 'users' existe déjà mais n'a pas la colonne 'household_name',
    on ajoute automatiquement cette colonne.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # 1) Création des tables si elles n'existent pas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
            -- NOTE : la colonne household_name sera ajoutée ensuite si nécessaire
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recipe_name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT NOT NULL,
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

    # 2) Vérification / ajout de la colonne 'household_name' dans 'users' si elle n'existe pas
    # On récupère la liste des colonnes actuelles de 'users'
    cursor.execute("PRAGMA table_info(users)")
    cols = [col_info[1] for col_info in cursor.fetchall()]  # col_info[1] = nom de la colonne
    if "household_name" not in cols:
        # On ajoute la colonne
        cursor.execute("ALTER TABLE users ADD COLUMN household_name TEXT")
        conn.commit()

# Appel immédiat à l'initialisation (avant tout accès à la base)
initialize_database()

# --------------------------------------------------------------------------------
# UTILITAIRES DE SÉCURITÉ (HASH DE MOT DE PASSE)
# --------------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Retourne le hachage SHA-256 du mot de passe.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# --------------------------------------------------------------------------------
# FONCTIONS D'AUTHENTIFICATION
# --------------------------------------------------------------------------------

def login_user(username: str, password: str):
    """
    Vérifie si l'utilisateur existe en base. 
    Compare username et hash du mot de passe. Si correct, retourne l'ID utilisateur, sinon None.
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
        st.error("❌ Erreur interne de la base de données lors de la connexion.")
        st.write(f"_Détail technique : {e}_")
        return None

def register_user(username: str, password: str, household_name: str):
    """
    Inscrit un nouvel utilisateur en base. 
    Retourne l'ID généré ou None si le username existe déjà.
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, household_name) VALUES (?, ?, ?)",
            (username.strip(), pwd_hash, household_name.strip())
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        # Contrainte UNIQUE violée (username déjà existant)
        return None
    except sqlite3.OperationalError as e:
        # Par sécurité, on affiche l'erreur technique si autre problème
        st.error("❌ Erreur interne de la base lors de l'inscription.")
        st.write(f"_Détail technique : {e}_")
        return None

# --------------------------------------------------------------------------------
# INITIALISATION DES VARIABLES DE SESSION
# --------------------------------------------------------------------------------

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 1
if "household_name" not in st.session_state:
    st.session_state.household_name = ""

# --------------------------------------------------------------------------------
# PAGE DE CONNEXION / INSCRIPTION
# --------------------------------------------------------------------------------

def show_login_page():
    """
    Affiche la page d'authentification avec deux onglets : Connexion et Inscription.
    """
    st.title("🔒 Connexion / Inscription")
    tab_login, tab_register = st.tabs(["Connexion", "Inscription"])

    # ---- ONGLET CONNEXION ----
    with tab_login:
        st.subheader("Connexion")
        login_username = st.text_input("Nom d’utilisateur", key="login_username")
        login_password = st.text_input("Mot de passe", type="password", key="login_password")

        if st.button("Se connecter"):
            if login_username.strip() == "" or login_password.strip() == "":
                st.error("❌ Veuillez remplir tous les champs.")
            else:
                user_id = login_user(login_username, login_password)
                if user_id:
                    st.success(f"✅ Bienvenue, **{login_username.strip()}** !")
                    st.session_state.user_id = user_id
                    st.session_state.username = login_username.strip()
                    # On ne force pas st.experimental_rerun() : le script se termine avec st.stop() plus bas,
                    # puis redémarre automatiquement (session_state.user_id n'est plus None)
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    # ---- ONGLET INSCRIPTION ----
    with tab_register:
        st.subheader("Inscription")
        reg_username = st.text_input("Choisissez un nom d’utilisateur", key="reg_username")
        reg_password = st.text_input("Choisissez un mot de passe", type="password", key="reg_password")
        reg_password_confirm = st.text_input("Confirmez le mot de passe", type="password", key="reg_password_confirm")
        reg_household = st.text_input("Nom du foyer (optionnel)", key="reg_household")

        if st.button("S'inscrire"):
            if reg_username.strip() == "" or reg_password.strip() == "" or reg_password_confirm.strip() == "":
                st.error("❌ Veuillez remplir tous les champs obligatoires.")
            elif reg_password != reg_password_confirm:
                st.error("❌ Les mots de passe ne correspondent pas.")
            else:
                new_user_id = register_user(reg_username, reg_password, reg_household)
                if new_user_id:
                    st.success(f"✅ Inscription réussie. Vous pouvez maintenant vous connecter, **{reg_username.strip()}**.")
                    # L'utilisateur reste sur l'onglet Inscription. 
                    # S'il clique ensuite sur "Connexion", il pourra se logguer.
                else:
                    st.error("❌ Ce nom d’utilisateur existe déjà.")

# --------------------------------------------------------------------------------
# FONCTIONS DE GESTION DES RECETTES ET DU PLANNING
# --------------------------------------------------------------------------------

def add_recipe(user_id: int, recipe_name: str, ingredients: str, instructions: str):
    """
    Ajoute une recette pour l'utilisateur donné.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes (user_id, recipe_name, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (user_id, recipe_name.strip(), ingredients.strip(), instructions.strip())
    )
    conn.commit()

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère toutes les recettes de l'utilisateur sous forme de DataFrame.
    Colonnes : ['id', 'recipe_name', 'ingredients', 'instructions']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, recipe_name, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
    """
    Supprime l'ancien planning et insère le nouveau (avec timestamp commun).
    plan_df doit contenir les colonnes ["Day", "Meal", "Recipe"].
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Supprimer l'ancien planning
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans (user_id, day, meal, recipe_name, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"], now_str)
        )
    conn.commit()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère le planning de l'utilisateur sous forme de DataFrame.
    Colonnes : ['id', 'day', 'meal', 'recipe_name', 'timestamp']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name, timestamp FROM mealplans WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    return df

# --------------------------------------------------------------------------------
# CONTENU PRINCIPAL DE L'APPLICATION (APRÈS AUTHENTIFICATION)
# --------------------------------------------------------------------------------

def main_app():
    """
    Affiche le menu latéral et les différentes pages :
    - Tableau de bord
    - Mes recettes
    - Liste de courses
    - Se déconnecter
    """
    st.sidebar.title(f"👋 Bonjour, {st.session_state.username} !")
    menu = st.sidebar.radio(
        "Navigation",
        ["🏠 Tableau de bord", "📖 Mes recettes", "🛒 Liste de courses", "🔓 Se déconnecter"]
    )

    # ---- TABLEAU DE BORD ----
    if menu == "🏠 Tableau de bord":
        st.header("🏠 Tableau de bord")
        st.markdown("Vos repas planifiés (derniers ajouts) :")

        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Vous n’avez pas encore planifié de repas.")
        else:
            st.dataframe(df_plan[["day", "meal", "recipe_name", "timestamp"]])

    # ---- MES RECETTES ----
    elif menu == "📖 Mes recettes":
        st.header("📖 Mes recettes")
        st.markdown("Ajoutez une nouvelle recette :")
        with st.form("recipe_form", clear_on_submit=True):
            rec_name = st.text_input("Nom de la recette")
            rec_ingredients = st.text_area("Ingrédients (séparés par des virgules)")
            rec_instructions = st.text_area("Instructions")
            if st.form_submit_button("➕ Ajouter la recette"):
                if rec_name.strip() == "" or rec_ingredients.strip() == "" or rec_instructions.strip() == "":
                    st.error("❌ Tous les champs sont obligatoires.")
                else:
                    add_recipe(st.session_state.user_id, rec_name, rec_ingredients, rec_instructions)
                    st.success("✅ Recette ajoutée.")

        st.markdown("---")
        st.markdown("Vos recettes enregistrées :")
        df_rec = get_recipes_for_user(st.session_state.user_id)
        if df_rec.empty:
            st.info("Vous n’avez pas encore ajouté de recette.")
        else:
            st.dataframe(df_rec[["recipe_name", "ingredients", "instructions"]])

    # ---- LISTE DE COURSES ----
    elif menu == "🛒 Liste de courses":
        st.header("🛒 Liste de courses générée")
        st.markdown("La liste est compilée automatiquement depuis votre planning de la semaine :")

        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
        else:
            # Récupère les ingrédients de chaque recette planifiée
            conn = get_connection()
            ingredients_list = []
            for recipe in df_plan["recipe_name"].unique():
                df_rec = pd.read_sql_query(
                    "SELECT ingredients FROM recipes WHERE user_id = ? AND recipe_name = ?",
                    conn,
                    params=(st.session_state.user_id, recipe)
                )
                if not df_rec.empty:
                    ingr_str = df_rec.iloc[0]["ingredients"]
                    ing_list = [i.strip() for i in ingr_str.split(",") if i.strip() != ""]
                    ingredients_list.extend(ing_list)

            if ingredients_list:
                df_shop = pd.DataFrame(pd.Series(ingredients_list).value_counts(), columns=["Quantité Approx."])
                df_shop.reset_index(inplace=True)
                df_shop.columns = ["Ingrédient", "Quantité Approx."]
                st.dataframe(df_shop)
            else:
                st.info("Il n’y a pas d’ingrédients à afficher pour l’instant.")

    # ---- SE DÉCONNECTER ----
    elif menu == "🔓 Se déconnecter":
        for key in ["user_id", "username", "onboard_step", "household_name"]:
            if key in st.session_state:
                del st.session_state[key]
        st.experimental_rerun()

# --------------------------------------------------------------------------------
# LOGIQUE PRINCIPALE
# --------------------------------------------------------------------------------

if st.session_state.user_id is None:
    show_login_page()
    st.stop()

main_app()
