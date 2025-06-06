import streamlit as st
import sqlite3
import pandas as pd
import hashlib

# --- CONFIGURATION DE L'APPLICATION ---
st.set_page_config(page_title="Batchist", page_icon="🍲", layout="wide")

# --- INITIALISATION DE LA BASE DE DONNÉES ---
# Chemin vers la base SQLite
DB_PATH = "meal_planner.db"

def get_connection():
    """Retourne une connexion à la base SQLite."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """Création des tables si elles n'existent pas."""
    conn = get_connection()
    cursor = conn.cursor()
    # Table des utilisateurs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
    """)
    # Table des recettes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,
            instructions TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    # Table des plans de repas (sans timestamp pour simplifier)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            recipe_name TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    """)
    conn.commit()
    conn.close()

# On initialise la DB au démarrage
init_db()

# --- FONCTIONS UTILES ---
def hash_password(password):
    """Retourne le hash SHA-256 du mot de passe."""
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    """Enregistre un nouvel utilisateur si le nom n'existe pas."""
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username.strip(), password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def login_user(username, password):
    """Vérifie les identifiants et retourne l'id de l'utilisateur ou None."""
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    cursor.execute(
        "SELECT id FROM users WHERE username = ? AND password_hash = ?",
        (username.strip(), password_hash)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def get_user_recipes(user_id):
    """Retourne un DataFrame des recettes de l'utilisateur."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT name, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def add_recipe(user_id, name, ingredients, instructions):
    """Ajoute une nouvelle recette pour l'utilisateur."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes (user_id, name, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (user_id, name.strip(), ingredients.strip(), instructions.strip())
    )
    conn.commit()
    conn.close()

def get_mealplan_for_user(user_id):
    """Retourne un DataFrame du planning de repas de l'utilisateur."""
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name FROM mealplans WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id, plan_df):
    """
    Insère ou remplace le planning de l'utilisateur.
    plan_df doit contenir colonnes ["Day", "Meal", "Recipe"].
    On supprime l'ancien plan complet et on insère le nouveau.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # Supprime ancien planning
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    # Insère nouveau planning
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans (user_id, day, meal, recipe_name) VALUES (?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"])
        )
    conn.commit()
    conn.close()

def generate_shopping_list(user_id):
    """
    Génère la liste de courses à partir du planning de l'utilisateur.
    On parcourt les recettes et on accumule les ingrédients.
    """
    plan_df = get_mealplan_for_user(user_id)
    if plan_df.empty:
        return pd.DataFrame(columns=["Ingredient", "Quantity"])
    conn = get_connection()
    cursor = conn.cursor()
    ingredients_list = []
    for recipe_name in plan_df["recipe_name"].unique():
        cursor.execute(
            "SELECT ingredients FROM recipes WHERE user_id = ? AND name = ?",
            (user_id, recipe_name)
        )
        row = cursor.fetchone()
        if row:
            texte_ingredients = row[0]
            lignes = texte_ingredients.split("\n")
            for ligne in lignes:
                if ligne.strip():
                    ingredients_list.append(ligne.strip())
    conn.close()
    if not ingredients_list:
        return pd.DataFrame(columns=["Ingredient", "Quantity"])
    df_ing = pd.DataFrame(ingredients_list, columns=["Ingredient"])
    df_count = df_ing.value_counts().reset_index(name="Quantity")
    df_count["Ingredient"] = df_count["Ingredient"].astype(str)
    return df_count

# --- GESTION DE L'AUTHENTIFICATION AVEC SESSION STATE ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = "login"  # ou "signup"

def show_login_page():
    """
    Affiche la page Connexion / Inscription.
    Renvoie True si la connexion a réussi (session_state.user_id est défini),
    False sinon.
    """
    st.title("🔒 Connexion / Inscription")
    # Basculer entre Connexion et Inscription
    col1, col2 = st.columns([1,1])
    with col1:
        if st.button("Connexion"):
            st.session_state.auth_mode = "login"
    with col2:
        if st.button("Inscription"):
            st.session_state.auth_mode = "signup"

    st.write("---")
    if st.session_state.auth_mode == "login":
        username = st.text_input("Nom d'utilisateur", key="login_username")
        password = st.text_input("Mot de passe", type="password", key="login_password")
        if st.button("Se connecter"):
            user_id = login_user(username, password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.username = username.strip()
                st.success(f"✅ Bienvenue, **{st.session_state.username}** !")
                return True
            else:
                st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")
                return False
        else:
            return False

    else:  # Mode Inscription
        new_username = st.text_input("Choisissez un nom d'utilisateur", key="signup_username")
        new_password = st.text_input("Choisissez un mot de passe", type="password", key="signup_password")
        confirm_password = st.text_input("Confirmez le mot de passe", type="password", key="signup_confirm")
        if st.button("S'inscrire"):
            if new_username.strip() == "" or new_password.strip() == "":
                st.error("❌ Veuillez renseigner un nom d'utilisateur et un mot de passe.")
                return False
            if new_password != confirm_password:
                st.error("❌ Les mots de passe ne correspondent pas.")
                return False
            user_id = register_user(new_username, new_password)
            if user_id:
                st.success("🟢 Inscription réussie ! Vous pouvez maintenant vous connecter.")
                st.session_state.auth_mode = "login"
                return False
            else:
                st.error("❌ Ce nom d'utilisateur est déjà pris.")
                return False
        else:
            return False

# --- PAGE PRINCIPALE APRÈS CONNEXION ---
def main_app():
    st.header("🏠 Tableau de bord")
    st.write(f"Bienvenue sur Batchist, **{st.session_state.username}** !")

    # Navigation latérale
    menu = ["Dashboard", "Planification", "Recettes", "Liste de courses", "Déconnexion"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Dashboard":
        st.subheader("Vos repas planifiés")
        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Vous n’avez pas encore planifié de repas.")
        else:
            st.dataframe(df_plan)

    elif choice == "Planification":
        st.subheader("🗓️ Planification Hebdomadaire")
        # Exemple de jours et repas
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        meals = ["Déjeuner", "Dîner"]
        # Récupérer la liste de recettes pour l'utilisateur
        df_recettes = get_user_recipes(st.session_state.user_id)
        listes_recettes = df_recettes["name"].tolist()
        listes_recettes.insert(0, "")  # Option vide

        selections = []
        with st.form("plan_form"):
            for day in days:
                cols = st.columns(len(meals))
                for i, meal in enumerate(meals):
                    with cols[i]:
                        key = f"{day}_{meal}"
                        choix = st.selectbox(f"{day} - {meal}", listes_recettes, key=key)
                        selections.append({"Day": day, "Meal": meal, "Recipe": choix})
            submitted = st.form_submit_button("💾 Enregistrer le planning")
            if submitted:
                df_plan = pd.DataFrame(selections)
                df_plan = df_plan[df_plan["Recipe"] != ""].reset_index(drop=True)
                upsert_mealplan(st.session_state.user_id, df_plan)
                st.success("✅ Planning de la semaine enregistré.")

    elif choice == "Recettes":
        st.subheader("📖 Mes recettes")
        st.write("Ajouter une nouvelle recette")
        with st.form("recipe_form"):
            name = st.text_input("Nom de la recette")
            ingredients = st.text_area("Ingrédients (une ligne par ingrédient)")
            instructions = st.text_area("Instructions")
            add_submitted = st.form_submit_button("➕ Ajouter la recette")
            if add_submitted:
                if name.strip() == "" or ingredients.strip() == "" or instructions.strip() == "":
                    st.error("❌ Tous les champs sont obligatoires.")
                else:
                    add_recipe(st.session_state.user_id, name, ingredients, instructions)
                    st.success("✅ Recette ajoutée avec succès.")

        st.write("### Vos recettes existantes")
        df_recettes = get_user_recipes(st.session_state.user_id)
        if df_recettes.empty:
            st.info("Vous n’avez pas encore ajouté de recettes.")
        else:
            st.dataframe(df_recettes)

    elif choice == "Liste de courses":
        st.subheader("🛒 Liste de courses générée")
        df_shopping = generate_shopping_list(st.session_state.user_id)
        if df_shopping.empty:
            st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
        else:
            st.dataframe(df_shopping)

    else:  # Déconnexion
        if st.button("Se déconnecter"):
            for key in ["user_id", "username", "auth_mode"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("Vous avez été déconnecté.")
            st.experimental_rerun  # Force le rerun pour revenir à la page de login

# --- ROUTE PRINCIPALE ---
logged_in = False
if st.session_state.user_id is None:
    # Si pas encore connecté, on affiche la page login/inscription
    logged_in = show_login_page()
    if not logged_in:
        st.stop()  # On arrête ici tant que l'utilisateur n'est pas authentifié

# Si on arrive ici, l'utilisateur est connecté : on affiche le reste de l'app
main_app()
