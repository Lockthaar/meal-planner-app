# ────────────────────────────────────────────────────────────────────────────────
#                     FICHIER : app.py (version complète)
# ────────────────────────────────────────────────────────────────────────────────

import streamlit as st
import sqlite3
import pandas as pd
import hashlib

# ────────────────────────────────────────────────────────────────────────────────
#   CONFIGURATION GÉNÉRALE DE LA PAGE (titre, icône, layout)
# ────────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Batchist - Votre batch cooking simplifié",
    page_icon="🍲",
    layout="wide",
)

# ────────────────────────────────────────────────────────────────────────────────
#   AFFICHAGE DE LA BANNIÈRE EN HAUT (image locale)
# ────────────────────────────────────────────────────────────────────────────────
# Placez votre image de bannière dans le même dossier que app.py ;
# par exemple "banner.jpg" ou "banner.png". Si le fichier s'appelle différemment,
# changez simplement le chemin ci-dessous.
#
# Exemple : si votre bannière s'appelle "banner.png" dans un sous-répertoire "assets",
# remplacez "banner.jpg" par "assets/banner.png".
#
try:
    st.image("banner.jpg", use_column_width=True)
except FileNotFoundError:
    # Si l'image n'est pas trouvée, on n'affiche rien et on continue
    pass

st.markdown("""
<h1 style="text-align:center; margin-top: -40px;">Batchist</h1>
<p style="text-align:center; color: #cccccc; font-size: 18px;">
    Vos recettes personnelles, votre batch cooking simplifié.
</p>
""", unsafe_allow_html=True)

st.write("---")  # Séparateur après la bannière

# ────────────────────────────────────────────────────────────────────────────────
#   CHEMIN VERS LA BASE DE DONNÉES (SQLite)
# ────────────────────────────────────────────────────────────────────────────────
DB_PATH = "meal_planner.db"

def get_connection():
    """
    Crée ou récupère la connexion thread-safe à la base SQLite.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """
    Initialise la base de données en créant les tables si elles n'existent pas.
    Tables créées :
      - users (id, username, password_hash)
      - recipes (id, user_id, name, ingredients, instructions)
      - mealplans (id, user_id, day, meal, recipe_name)
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

    # Table des plans de repas (pas de colonne timestamp ici)
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

# On initialise la base **avant tout autre appel** (pour éviter « no such table »)
init_db()

# ────────────────────────────────────────────────────────────────────────────────
#   FONCTIONS D'AIDE (hash, CRUD utilisateur, CRUD recette, CRUD planning)
# ────────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    Retourne le hash SHA-256 d'une chaîne de caractères.
    """
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username: str, password: str) -> int | None:
    """
    Enregistre un nouvel utilisateur. 
    - Renvoie user_id si l'inscription réussit. 
    - Renvoie None si l'utilisateur existe déjà ou données invalides.
    """
    username_clean = username.strip()
    password_clean = password.strip()
    if not username_clean or not password_clean:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password_clean)
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username_clean, pwd_hash)
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        # Nom d'utilisateur déjà pris
        conn.close()
        return None

def login_user(username: str, password: str) -> int | None:
    """
    Tente de connecter un utilisateur :
    - Renvoie user_id si OK.
    - Sinon renvoie None.
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
    Retourne un DataFrame des recettes de l'utilisateur :
    Colonnes = ['name', 'ingredients', 'instructions']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT name, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def add_recipe(user_id: int, name: str, ingredients: str, instructions: str) -> None:
    """
    Ajoute une nouvelle recette pour l'utilisateur.
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
    Retourne un DataFrame du planning de repas pour l'utilisateur.
    Colonnes = ['id', 'day', 'meal', 'recipe_name']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name FROM mealplans WHERE user_id = ?",
        conn, params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame) -> None:
    """
    Met à jour (ou insère) le planning de repas de l'utilisateur :
    - Supprime d'abord tout le planning existant pour user_id.
    - Réinsère toutes les lignes contenues dans plan_df.
      plan_df doit contenir les colonnes 'Day', 'Meal', 'Recipe'.
    """
    conn = get_connection()
    cursor = conn.cursor()
    # On efface l'ancien planning
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    # On insère chaque ligne du nouveau planning
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans (user_id, day, meal, recipe_name) VALUES (?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"])
        )
    conn.commit()
    conn.close()

def generate_shopping_list(user_id: int) -> pd.DataFrame:
    """
    Génère la liste de courses sous forme de DataFrame :
    - À partir du planning, on récupère toutes les recettes planifiées.
    - On extrait leurs listes d'ingrédients (lignes séparées).
    - On compte chaque ingrédient pour avoir la "quantité".
    Renvoie un DataFrame ['Ingredient', 'Quantity'].
    """
    plan_df = get_mealplan_for_user(user_id)
    if plan_df.empty:
        return pd.DataFrame(columns=["Ingredient", "Quantity"])

    conn = get_connection()
    cursor = conn.cursor()
    all_ingredients = []

    # Parcours de chaque recette planifiée
    for recipe_name in plan_df["recipe_name"].unique():
        cursor.execute(
            "SELECT ingredients FROM recipes WHERE user_id = ? AND name = ?",
            (user_id, recipe_name)
        )
        row = cursor.fetchone()
        if row:
            texte_ingredients = row[0]
            # Séparer chaque ligne non vide en ingrédient distinct
            for line in texte_ingredients.split("\n"):
                if line.strip():
                    all_ingredients.append(line.strip())
    conn.close()

    if not all_ingredients:
        return pd.DataFrame(columns=["Ingredient", "Quantity"])

    df_ing = pd.DataFrame(all_ingredients, columns=["Ingredient"])
    # On compte la fréquence d'apparition de chaque ingrédient
    df_count = df_ing.value_counts().reset_index(name="Quantity")
    df_count["Ingredient"] = df_count["Ingredient"].astype(str)
    return df_count

# ────────────────────────────────────────────────────────────────────────────────
#       INITIALISATION DU SESSION_STATE POUR GARDER L'ÉTAT ENTRE LES RUNS
# ────────────────────────────────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = ""

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"  # ou "signup"

# ────────────────────────────────────────────────────────────────────────────────
#                  FONCTION D'AFFICHAGE DE LA PAGE LOGIN / SIGNUP
# ────────────────────────────────────────────────────────────────────────────────
def show_login_page() -> bool:
    """
    Affiche la page Connexion / Inscription.
    - Si la connexion réussit, remplit st.session_state.user_id et .username, puis renvoie True.
    - Sinon, reste sur la page login/inscription et renvoie False.
    """
    st.title("🔒 Connexion / Inscription")
    st.write("Connectez-vous pour accéder à Batchist.")

    # Boutons pour basculer entre "Connexion" et "Inscription"
    colL, colR = st.columns([1, 1])
    with colL:
        if st.button("Connexion"):
            st.session_state.auth_mode = "login"
    with colR:
        if st.button("Inscription"):
            st.session_state.auth_mode = "signup"

    st.write("---")

    if st.session_state.auth_mode == "login":
        # ------------------ FORMULAIRE DE CONNEXION ------------------
        login_username = st.text_input("Nom d'utilisateur", key="login_username")
        login_password = st.text_input("Mot de passe", type="password", key="login_password")
        if st.button("Se connecter"):
            user_id = login_user(login_username, login_password)
            if user_id:
                # Authentification OK
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
        # ------------------ FORMULAIRE D'INSCRIPTION ------------------
        signup_username = st.text_input("Choisissez un nom d'utilisateur", key="signup_username")
        signup_password = st.text_input("Choisissez un mot de passe", type="password", key="signup_password")
        signup_confirm  = st.text_input("Confirmez le mot de passe", type="password", key="signup_confirm")
        if st.button("S'inscrire"):
            if not signup_username.strip() or not signup_password.strip():
                st.error("❌ Veuillez renseigner un nom d'utilisateur et un mot de passe.")
                return False
            if signup_password != signup_confirm:
                st.error("❌ Les mots de passe ne correspondent pas.")
                return False

            new_id = register_user(signup_username, signup_password)
            if new_id:
                st.success("🟢 Inscription réussie ! Vous pouvez maintenant vous connecter.")
                # On repasse en mode 'login' pour que l'utilisateur puisse se connecter ensuite
                st.session_state.auth_mode = "login"
                return False
            else:
                st.error("❌ Ce nom d'utilisateur est déjà pris.")
                return False
        else:
            return False

# ────────────────────────────────────────────────────────────────────────────────
#               FONCTION PRINCIPALE DE L'APPLICATION APRÈS LOGIN
# ────────────────────────────────────────────────────────────────────────────────
def main_app():
    """
    Affiche l’interface principale (une fois l'utilisateur connecté).
    Contient la Sidebar de navigation et les différents onglets.
    """
    st.header("🏠 Tableau de bord")
    st.write(f"Bienvenue sur **Batchist**, **{st.session_state.username}** !")

    # ─── Barre latérale de navigation ─────────────────────────────────
    menu = ["Dashboard", "Planification", "Recettes", "Liste de courses", "Déconnexion"]
    choice = st.sidebar.selectbox("Navigation", menu)

    # ─── Onglet "Dashboard" ────────────────────────────────────────────
    if choice == "Dashboard":
        st.subheader("Vos repas planifiés")
        df_plan = get_mealplan_for_user(st.session_state.user_id)
        if df_plan.empty:
            st.info("Vous n’avez pas encore planifié de repas.")
        else:
            st.dataframe(df_plan, use_container_width=True)

    # ─── Onglet "Planification" ────────────────────────────────────────
    elif choice == "Planification":
        st.subheader("🗓️ Planification Hebdomadaire")
        days  = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        meals = ["Déjeuner", "Dîner"]

        # On récupère la liste des recettes de l'utilisateur
        df_recettes = get_user_recipes(st.session_state.user_id)
        recettes_list = df_recettes["name"].tolist()
        recettes_list.insert(0, "")  # Ajoute une option vide au début

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
                df_plan = pd.DataFrame(selections)
                df_plan = df_plan[df_plan["Recipe"] != ""].reset_index(drop=True)
                upsert_mealplan(st.session_state.user_id, df_plan)
                st.success("✅ Planning de la semaine enregistré.")

    # ─── Onglet "Recettes" ─────────────────────────────────────────────
    elif choice == "Recettes":
        st.subheader("📖 Mes recettes")

        # Formulaire d'ajout de recette
        with st.form("form_recipe"):
            name         = st.text_input("Nom de la recette", key="rec_name")
            ingredients  = st.text_area("Ingrédients (une ligne par ingrédient)", key="rec_ingredients")
            instructions = st.text_area("Instructions", key="rec_instructions")
            add_sub = st.form_submit_button("➕ Ajouter la recette")
            if add_sub:
                if not name.strip() or not ingredients.strip() or not instructions.strip():
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
            st.dataframe(df_recettes, use_container_width=True)

    # ─── Onglet "Liste de courses" ─────────────────────────────────────
    elif choice == "Liste de courses":
        st.subheader("🛒 Liste de courses générée")
        df_shopping = generate_shopping_list(st.session_state.user_id)
        if df_shopping.empty:
            st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
        else:
            st.dataframe(df_shopping, use_container_width=True)

    # ─── Onglet "Déconnexion" ───────────────────────────────────────────
    else:  # Déconnexion
        if st.button("Se déconnecter"):
            # On supprime les clés du session_state pour déconnecter l'utilisateur
            for k in ["user_id", "username", "auth_mode"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.success("Vous avez été déconnecté.")
            st.stop()  # On arrête ici ; Streamlit rechargera la page et reviendra au login

# ────────────────────────────────────────────────────────────────────────────────
#                          BOUCLE PRINCIPALE D'EXECUTION
# ────────────────────────────────────────────────────────────────────────────────
if st.session_state.user_id is None:
    # Tant que l'utilisateur n'est pas connecté, on affiche la page login
    logged_in = show_login_page()
    if not logged_in:
        st.stop()  # On reste sur la page login tant que l'utilisateur n'est pas connecté

# Si on atteint ce point, c'est que user_id est désormais renseigné => on affiche l'app principale
main_app()
