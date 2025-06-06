import streamlit as st
import sqlite3
import pandas as pd
import hashlib

# -------------------------------------------------------------------
# CONFIGURATION DE L'APPLICATION
# -------------------------------------------------------------------
st.set_page_config(
    page_title="Batchist",
    page_icon="🍲",
    layout="wide",
)

# -------------------------------------------------------------------
# INITIALISATION DE LA BASE DE DONNÉES (SQLite)
# -------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    """
    Retourne une connexion thread-safe à la base SQLite.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """
    Crée les tables si elles n'existent pas encore :
      - users
      - recipes
      - mealplans (sans colonne timestamp pour éviter toute erreur)
    """
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
    # Table des plans de repas (sans timestamp)
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

# Initialise la base au chargement du script
init_db()

# -------------------------------------------------------------------
# FONCTIONS AUXILIAIRES (Hashage, CRUD Utilisateurs, Recettes, Planning)
# -------------------------------------------------------------------
def hash_password(password: str) -> str:
    """
    Retourne le hash SHA-256 d'une chaîne de caractères.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str):
    """
    Tente d'enregistrer un utilisateur.
    - Renvoie l'user_id si l'inscription réussit.
    - Renvoie None si le nom d'utilisateur existe déjà.
    """
    username_clean = username.strip()
    if username_clean == "" or password.strip() == "":
        return None
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username_clean, pwd_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def login_user(username: str, password: str):
    """
    Tente de connecter un utilisateur.
    - Renvoie l'user_id si mot de passe OK.
    - Renvoie None sinon.
    """
    username_clean = username.strip()
    pwd_hash = hash_password(password)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM users WHERE username = ? AND password_hash = ?",
        (username_clean, pwd_hash)
    )
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return None

def get_user_recipes(user_id: int) -> pd.DataFrame:
    """
    Renvoie un DataFrame des recettes (name, ingredients, instructions)
    associées à l'user_id.
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT name, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def add_recipe(user_id: int, name: str, ingredients: str, instructions: str):
    """
    Ajoute une recette pour l'utilisateur.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes (user_id, name, ingredients, instructions) VALUES (?, ?, ?, ?)",
        (user_id, name.strip(), ingredients.strip(), instructions.strip())
    )
    conn.commit()
    conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    """
    Renvoie un DataFrame du planning de repas pour user_id.
    Colonnes : ['id', 'day', 'meal', 'recipe_name']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name FROM mealplans WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
    """
    Met à jour entièrement le planning de l'utilisateur :
    - Supprime tous les enregistrements existants pour user_id.
    - Réinsère chaque ligne de plan_df (colonnes 'Day', 'Meal', 'Recipe').
    """
    conn = get_connection()
    cursor = conn.cursor()
    # Supprime l'ancien planning
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    # Insère le nouveau planning
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans (user_id, day, meal, recipe_name) VALUES (?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"])
        )
    conn.commit()
    conn.close()

def generate_shopping_list(user_id: int) -> pd.DataFrame:
    """
    Génère un DataFrame de la liste de courses à partir du planning :
    - Récupère toutes les recettes planifiées pour user_id.
    - Pour chaque recette, récupère le texte 'ingredients'.
    - Sépare chaque ligne d'ingrédient, puis fait un comptage (value_counts).
    - Retourne un DataFrame à deux colonnes : ['Ingredient', 'Quantity'].
    """
    plan_df = get_mealplan_for_user(user_id)
    if plan_df.empty:
        return pd.DataFrame(columns=["Ingredient", "Quantity"])

    conn = get_connection()
    cursor = conn.cursor()
    all_ingredients = []
    # Pour chaque recette planifiée, on cherche les ingrédients
    for recipe_name in plan_df["recipe_name"].unique():
        cursor.execute(
            "SELECT ingredients FROM recipes WHERE user_id = ? AND name = ?",
            (user_id, recipe_name)
        )
        row = cursor.fetchone()
        if row:
            texte = row[0]
            # Chaque ligne non vide devient un ingrédient distinct
            for line in texte.split("\n"):
                if line.strip():
                    all_ingredients.append(line.strip())
    conn.close()

    if not all_ingredients:
        return pd.DataFrame(columns=["Ingredient", "Quantity"])

    df_ing = pd.DataFrame(all_ingredients, columns=["Ingredient"])
    df_count = df_ing.value_counts().reset_index(name="Quantity")
    df_count["Ingredient"] = df_count["Ingredient"].astype(str)
    return df_count

# -------------------------------------------------------------------
# GESTION DU STATE STREAMLIT (SESSION_STATE)
# -------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"  # ou "signup"

# -------------------------------------------------------------------
# PAGE DE CONNEXION / INSCRIPTION
# -------------------------------------------------------------------
def show_login_page() -> bool:
    """
    Affiche la page '🔒 Connexion / Inscription'. 
    - Si la connexion réussit, on stocke user_id et username, 
      on affiche un message de bienvenue, et on retourne True. 
    - Sinon, on reste sur la page login/inscription, on retourne False.
    """
    st.title("🔒 Connexion / Inscription")

    # Choix entre Connexion ou Inscription
    col_conn, col_sign = st.columns([1, 1])
    with col_conn:
        if st.button("Connexion"):
            st.session_state.auth_mode = "login"
    with col_sign:
        if st.button("Inscription"):
            st.session_state.auth_mode = "signup"

    st.write("---")

    if st.session_state.auth_mode == "login":
        login_username = st.text_input("Nom d'utilisateur", key="login_username")
        login_password = st.text_input("Mot de passe", type="password", key="login_password")
        if st.button("Se connecter"):
            user_id = login_user(login_username, login_password)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.username = login_username.strip()
                st.success(f"✅ Bienvenue, **{st.session_state.username}** !")
                return True
            else:
                st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")
                return False
        else:
            return False

    else:
        # Mode Inscription
        signup_username = st.text_input("Choisissez un nom d'utilisateur", key="signup_username")
        signup_password = st.text_input("Choisissez un mot de passe", type="password", key="signup_password")
        signup_confirm = st.text_input("Confirmez le mot de passe", type="password", key="signup_confirm")
        if st.button("S'inscrire"):
            if signup_username.strip() == "" or signup_password.strip() == "":
                st.error("❌ Veuillez renseigner un nom d'utilisateur et un mot de passe.")
                return False
            if signup_password != signup_confirm:
                st.error("❌ Les mots de passe ne correspondent pas.")
                return False
            user_id = register_user(signup_username, signup_password)
            if user_id:
                st.success("🟢 Inscription réussie ! Vous pouvez maintenant vous connecter.")
                st.session_state.auth_mode = "login"
                return False
            else:
                st.error("❌ Ce nom d'utilisateur est déjà pris.")
                return False
        else:
            return False

# -------------------------------------------------------------------
# PAGE PRINCIPALE APRÈS CONNEXION
# -------------------------------------------------------------------
def main_app():
    """
    Affiche l'interface principale une fois l'utilisateur connecté.
    Sidebar de navigation + panels correspondants.
    """
    st.header("🏠 Tableau de bord")
    st.write(f"Bienvenue sur **Batchist**, **{st.session_state.username}** !")

    # ── Barre latérale ─────────────────────────────────────────────────────────────────
    menu = ["Dashboard", "Planification", "Recettes", "Liste de courses", "Déconnexion"]
    choice = st.sidebar.selectbox("Navigation", menu)

    # ── Onglet "Dashboard" ───────────────────────────────────────────────────────────────
    if choice == "Dashboard":
        st.subheader("Vos repas planifiés")
        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Vous n’avez pas encore planifié de repas.")
        else:
            st.dataframe(df_plan)

    # ── Onglet "Planification" ───────────────────────────────────────────────────────────
    elif choice == "Planification":
        st.subheader("🗓️ Planification Hebdomadaire")
        days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        meals = ["Déjeuner", "Dîner"]

        # Récupère la liste des recettes existantes pour l'user
        df_recettes = get_user_recipes(st.session_state.user_id)
        recettes_list = df_recettes["name"].tolist()
        # Ajoute une option vide en début
        recettes_list.insert(0, "")

        selections = []
        with st.form("form_plan"):
            for day in days:
                cols = st.columns(len(meals))
                for i, meal in enumerate(meals):
                    with cols[i]:
                        key_name = f"{day}_{meal}"
                        choix = st.selectbox(f"{day} - {meal}", recettes_list, key=key_name)
                        selections.append({"Day": day, "Meal": meal, "Recipe": choix})
            submitted = st.form_submit_button("💾 Enregistrer le planning")
            if submitted:
                # On garde seulement les lignes où Recipe != ""
                df_plan = pd.DataFrame(selections)
                df_plan = df_plan[df_plan["Recipe"] != ""].reset_index(drop=True)
                upsert_mealplan(st.session_state.user_id, df_plan)
                st.success("✅ Planning de la semaine enregistré.")

    # ── Onglet "Recettes" ────────────────────────────────────────────────────────────────
    elif choice == "Recettes":
        st.subheader("📖 Mes recettes")

        # Formulaire d'ajout de recette
        with st.form("form_recipe"):
            name = st.text_input("Nom de la recette", key="rec_name")
            ingredients = st.text_area("Ingrédients (une ligne par ingrédient)", key="rec_ingredients")
            instructions = st.text_area("Instructions", key="rec_instructions")
            add_sub = st.form_submit_button("➕ Ajouter la recette")
            if add_sub:
                if name.strip() == "" or ingredients.strip() == "" or instructions.strip() == "":
                    st.error("❌ Tous les champs sont obligatoires.")
                else:
                    add_recipe(
                        st.session_state.user_id,
                        name,
                        ingredients,
                        instructions
                    )
                    st.success("✅ Recette ajoutée avec succès.")

        st.write("### Vos recettes existantes")
        df_recettes = get_user_recipes(st.session_state.user_id)
        if df_recettes.empty:
            st.info("Vous n’avez pas encore ajouté de recettes.")
        else:
            st.dataframe(df_recettes)

    # ── Onglet "Liste de courses" ────────────────────────────────────────────────────────
    elif choice == "Liste de courses":
        st.subheader("🛒 Liste de courses générée")
        df_shopping = generate_shopping_list(st.session_state.user_id)
        if df_shopping.empty:
            st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
        else:
            st.dataframe(df_shopping)

    # ── Onglet "Déconnexion" ──────────────────────────────────────────────────────────────
    else:  # Déconnexion
        if st.button("Se déconnecter"):
            # On vide le session_state
            for key in ["user_id", "username", "auth_mode"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.success("Vous avez été déconnecté.")
            st.stop()  # Le script se recharge et repasse automatiquement sur la page de login

# -------------------------------------------------------------------
# ROUTE PRINCIPALE DU SCRIPT
# -------------------------------------------------------------------
# Si l'utilisateur n'est pas encore connecté, on affiche la page login/inscription
if st.session_state.user_id is None:
    logged_in = show_login_page()
    if not logged_in:
        st.stop()  # On interrompt l'exécution ici pour rester sur le login

# Si on arrive ici, c'est que l'utilisateur est connecté -> on affiche l'app principale
main_app()
