# app.py

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime

# --------------------------------------------------------------------------------
# CONFIGURATION ET INITIALISATION
# --------------------------------------------------------------------------------

# Titre de l'application
st.set_page_config(
    page_title="Batchist - Batch Cooking Simplifié",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# -------------------------------------------------------------------------------
# BANNIÈRE (IMAGE EN LIGNE)
# -------------------------------------------------------------------------------
# Comme vous n'avez pas de dossier local pour les images, on utilise un URL
# direct vers une image hébergée en ligne. Ici, j'ai choisi une image libre
# provenant d'Unsplash (photo de plats cuisinés) pour servir de bannière.
BANNER_URL = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1350&q=80"

# Affichage de la banniѐre en largeur totale
st.image(BANNER_URL, use_container_width=True)

# -------------------------------------------------------------------------------
# BASE DE DONNÉES SQLITE
# -------------------------------------------------------------------------------

DB_PATH = "meal_planner.db"

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    # Table users (id, username, password_hash, household_name)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            household_name TEXT
        )
        """
    )

    # Table recipes (id, user_id, recipe_name, ingredients, instructions)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recipe_name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    # Table mealplans (ajout de la colonne timestamp pour suivre la date d'ajout)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            recipe_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()

# Assurez-vous d'initialiser la base au démarrage
initialize_database()

# -------------------------------------------------------------------------------
# UTILITAIRES DE SÉCURITÉ (HASH DE MOT DE PASSE)
# -------------------------------------------------------------------------------

import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# -------------------------------------------------------------------------------
# FONCTIONS D'AUTHENTIFICATION
# -------------------------------------------------------------------------------

def login_user(username: str, password: str):
    """
    Vérifie si l'utilisateur existe et si le mot de passe hash correspond.
    Renvoie l'ID utilisateur si connexion réussie, None sinon.
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    cursor.execute(
        "SELECT id FROM users WHERE username = ? AND password_hash = ?",
        (username.strip(), pwd_hash),
    )
    row = cursor.fetchone()
    return row[0] if row else None

def register_user(username: str, password: str, household_name: str):
    """
    Inscrit un nouvel utilisateur. Renvoie l'ID utilisateur créé.
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    cursor.execute(
        "INSERT INTO users (username, password_hash, household_name) VALUES (?, ?, ?)",
        (username.strip(), pwd_hash, household_name.strip()),
    )
    conn.commit()
    return cursor.lastrowid

# -------------------------------------------------------------------------------
# INITIALISATION DES VARIABLES DE SESSION
# -------------------------------------------------------------------------------

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 1
if "household_name" not in st.session_state:
    st.session_state.household_name = ""

# -------------------------------------------------------------------------------
# PAGE DE CONNEXION / INSCRIPTION
# -------------------------------------------------------------------------------

def show_login_page():
    st.title("🔒 Connexion / Inscription")
    tab_login, tab_register = st.tabs(["Connexion", "Inscription"])

    with tab_login:
        st.subheader("Connexion")
        login_username = st.text_input("Nom d'utilisateur", key="login_username")
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
                    # Pas besoin de relancer le script ; le reste du code s'exécutera naturellement.
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    with tab_register:
        st.subheader("Inscription")
        reg_username = st.text_input("Choisissez un nom d'utilisateur", key="reg_username")
        reg_password = st.text_input("Choisissez un mot de passe", type="password", key="reg_password")
        reg_password_confirm = st.text_input("Confirmez le mot de passe", type="password", key="reg_password_confirm")
        reg_household = st.text_input("Nom du foyer (optionnel)", key="reg_household")

        if st.button("S'inscrire"):
            if reg_username.strip() == "" or reg_password.strip() == "" or reg_password_confirm.strip() == "":
                st.error("❌ Veuillez remplir tous les champs obligatoires.")
            elif reg_password != reg_password_confirm:
                st.error("❌ Les mots de passe ne correspondent pas.")
            else:
                # Tenter d'inscrire l'utilisateur
                try:
                    new_user_id = register_user(reg_username, reg_password, reg_household)
                    st.success(f"✅ Inscription réussie. Vous pouvez maintenant vous connecter, **{reg_username.strip()}**.")
                    # On redirige vers l'onglet connexion en remettant à jour la session_state
                    # Aucun st.experimental_rerun() requis ; l'onglet "Connexion" apparaîtra au prochain affichage.
                    st.session_state.onboard_step = 1
                except sqlite3.IntegrityError:
                    st.error("❌ Ce nom d’utilisateur existe déjà. Veuillez en choisir un autre.")

# -------------------------------------------------------------------------------
# FONCTIONS DE GESTION DES RECETTES ET PLANNING
# -------------------------------------------------------------------------------

def add_recipe(user_id: int, recipe_name: str, ingredients: str, instructions: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes (user_id, recipe_name, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (user_id, recipe_name.strip(), ingredients.strip(), instructions.strip()),
    )
    conn.commit()

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, recipe_name, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn,
        params=(user_id,),
    )
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
    conn = get_connection()
    cursor = conn.cursor()
    # On supprime l'ancien planning pour remplacer par le nouveau
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans (user_id, day, meal, recipe_name, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"], now_str),
        )
    conn.commit()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name, timestamp FROM mealplans WHERE user_id = ?",
        conn,
        params=(user_id,),
    )
    return df

# -------------------------------------------------------------------------------
# CONTENU PRINCIPAL DE L'APPLICATION (APRÈS AUTHENTIFICATION)
# -------------------------------------------------------------------------------

def main_app():
    st.sidebar.title(f"👋 Bonjour, {st.session_state.username} !")
    menu = st.sidebar.radio("Navigation", ["🏠 Tableau de bord", "📖 Mes recettes", "🛒 Liste de courses", "🔓 Se déconnecter"])

    if menu == "🏠 Tableau de bord":
        st.header("🏠 Tableau de bord")
        st.markdown("Vos repas préférés du mois dernier :")

        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Vous n’avez pas encore planifié de repas.")
        else:
            # Affiche un tableau avec les derniers repas planifiés
            st.dataframe(df_plan[["day", "meal", "recipe_name", "timestamp"]])

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

    elif menu == "🛒 Liste de courses":
        st.header("🛒 Liste de courses générée")
        st.markdown("La liste est compilée automatiquement depuis votre planning :")

        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
        else:
            # On génère la liste de courses en fusionnant les ingrédients de chaque recette
            conn = get_connection()
            ingredients_list = []
            for recipe in df_plan["recipe_name"].unique():
                df_rec = pd.read_sql_query(
                    "SELECT ingredients FROM recipes WHERE user_id = ? AND recipe_name = ?",
                    conn,
                    params=(st.session_state.user_id, recipe),
                )
                if not df_rec.empty:
                    ingr_str = df_rec.iloc[0]["ingredients"]
                    ing_list = [i.strip() for i in ingr_str.split(",")]
                    ingredients_list.extend(ing_list)

            if ingredients_list:
                df_shop = pd.DataFrame(pd.Series(ingredients_list).value_counts(), columns=["Quantité Approx."])
                df_shop.reset_index(inplace=True)
                df_shop.columns = ["Ingrédient", "Quantité Approx."]
                st.dataframe(df_shop)
            else:
                st.info("Il n’y a pas d’ingrédients à afficher.")

    elif menu == "🔓 Se déconnecter":
        # Réinitialiser la session
        for key in ["user_id", "username", "onboard_step", "household_name"]:
            if key in st.session_state:
                del st.session_state[key]
        st.experimental_rerun()  # restart pour revenir à la page de connexion

# -------------------------------------------------------------------------------
# LOGIQUE PRINCIPALE
# -------------------------------------------------------------------------------

# Si l’utilisateur n’est pas connecté, on affiche le login/inscription
if st.session_state.user_id is None:
    show_login_page()
    st.stop()

# Sinon, on affiche l’application principale
main_app()
