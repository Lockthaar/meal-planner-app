# app.py

import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import hashlib

# --------------------------------------------------------------------------------
# CONFIGURATION GLOBALE DE LA PAGE
# --------------------------------------------------------------------------------

st.set_page_config(
    page_title="Batchist – Batch Cooking Simplifié",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --------------------------------------------------------------------------------
# CONSTANTES & URL D’IMAGES PAR DÉFAUT
# --------------------------------------------------------------------------------

# Bannière en haut de l’app (vous pouvez remplacer par n’importe quelle URL d’image libre de droits)
BANNER_URL = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1350&q=80"
DEFAULT_RECIPE_IMAGE = "https://images.unsplash.com/photo-1523986371872-9d3ba2e2f6e4?auto=format&fit=crop&w=800&q=80"

# Types de foyer pour le popup d’inscription
HOUSEHOLD_TYPES = {
    "solo": {
        "label": "Solo",
        "img": "https://img.icons8.com/fluency/96/000000/user-male-circle.png"
    },
    "couple": {
        "label": "Couple",
        "img": "https://img.icons8.com/fluency/96/000000/couple-with-heart.png"
    },
    "famille": {
        "label": "Famille",
        "img": "https://img.icons8.com/fluency/96/000000/family.png"
    }
}

# Chemin local (dans votre projet Streamlit Cloud) pour la base SQLite
DB_PATH = "meal_planner.db"

# --------------------------------------------------------------------------------
# UTILITAIRES POUR LA BASE DE DONNÉES
# --------------------------------------------------------------------------------

@st.cache_resource
def get_connection():
    """
    Renvoie une connexion SQLite (thread-safe) partagée pour toute la session Streamlit.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def initialize_database():
    """
    - Vérifie le schéma des tables 'users', 'recipes', 'mealplans' et 'extras'.
    - Si une table manque ou si son schéma est obsolète, on la (re)crée correctement.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # --- Table users ---
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='users'
    """)
    if cursor.fetchone() is None:
        # la table users n'existe pas → création
        cursor.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                household_type TEXT NOT NULL
            )
        """)
        conn.commit()
    else:
        # la table existe → vérifions ses colonnes
        cursor.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cursor.fetchall()]  # r[1] = nom de chaque colonne
        needed = {"id", "username", "password_hash", "household_type"}
        if not needed.issubset(set(cols)):
            # on supprime l’ancienne table et on la recrée
            cursor.execute("DROP TABLE IF EXISTS users")
            conn.commit()
            cursor.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    household_type TEXT NOT NULL
                )
            """)
            conn.commit()

    # --- Table recipes ---
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='recipes'
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
    else:
        # on considère qu’elle est correcte ; PAS de migration fine pour l’instant
        pass

    # --- Table ingredients (lié aux recipes) ---
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='ingredients'
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

    # --- Table mealplans ---
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='mealplans'
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
    else:
        pass

    # --- Table extras (compléments de courses) ---
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='extras'
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
    else:
        pass

# Appel immédiat pour créer/migrer les tables si besoin
initialize_database()

# --------------------------------------------------------------------------------
# HASHAGE DE MOT DE PASSE
# --------------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """
    Retourne le SHA-256 hex digest du mot de passe.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# --------------------------------------------------------------------------------
# FONCTIONS D’AUTHENTIFICATION / INSCRIPTION
# --------------------------------------------------------------------------------

def register_user(username: str, password: str, household_type: str) -> int | None:
    """
    Tente d’inscrire un nouvel utilisateur avec :
     - username UNIQUE
     - password_hash
     - household_type ∈ 'solo'|'couple'|'famille'
    → Renvoie l’id en base si OK, None si erreur (duplicate username ou SQL error).
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, household_type) VALUES (?, ?, ?)",
            (username.strip(), pwd_hash, household_type)
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    except sqlite3.OperationalError as e:
        st.error("❌ Erreur interne de la base lors de l’inscription.")
        st.write(f"_Détail technique : {e}_")
        return None

def login_user(username: str, password: str) -> int | None:
    """
    Recherche un utilisateur par username+hash(password).
    Renvoie l’id si trouvé, None sinon.
    """
    conn = get_connection()
    cursor = conn.cursor()
    pwd_hash = hash_password(password)

    try:
        cursor.execute(
            "SELECT id FROM users WHERE username = ? AND password_hash = ?",
            (username.strip(), pwd_hash)
        )
        res = cursor.fetchone()
        return res[0] if res else None
    except sqlite3.OperationalError as e:
        st.error("❌ Erreur interne de la base lors de la connexion.")
        st.write(f"_Détail technique : {e}_")
        return None

def get_user_household_type(user_id: int) -> str:
    """
    Renvoie le type de foyer ('solo'|'couple'|'famille') de l’utilisateur.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT household_type FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else "solo"

# --------------------------------------------------------------------------------
# SESSION STATE INITIALIZATION
# --------------------------------------------------------------------------------

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = ""

if "household_type" not in st.session_state:
    st.session_state.household_type = ""

if "show_household_popup" not in st.session_state:
    # Ce flag gère l’affichage du popup “type de foyer” après inscription
    st.session_state.show_household_popup = False

if "ingredients_buffer" not in st.session_state:
    # Buffer temporaire pour construire la liste d’ingrédients d’une recette
    st.session_state.ingredients_buffer = []

if "extras_buffer" not in st.session_state:
    # Buffer temporaire pour construire la liste “compléments de courses”
    st.session_state.extras_buffer = []

# --------------------------------------------------------------------------------
# PAGE DE CONNEXION / INSCRIPTION (ONGLETS)
# --------------------------------------------------------------------------------

def show_login_page():
    """
    Affiche la page d’authentification (2 onglets : Connexion / Inscription).
    Si l’inscription aboutit, on affiche ensuite le popup “choix du foyer”.
    """
    st.title("🔒 Connexion / Inscription")
    tab_login, tab_register = st.tabs(["Connexion", "Inscription"])

    # --- Onglet Connexion ---
    with tab_login:
        st.subheader("Connexion")
        login_username = st.text_input("Nom d’utilisateur", key="login_username")
        login_password = st.text_input("Mot de passe", type="password", key="login_password")

        if st.button("Se connecter"):
            if login_username.strip() == "" or login_password.strip() == "":
                st.error("❌ Merci de remplir les deux champs.")
            else:
                user_id = login_user(login_username, login_password)
                if user_id:
                    st.success(f"✅ Bienvenue, **{login_username.strip()}** !")
                    st.session_state.user_id = user_id
                    st.session_state.username = login_username.strip()
                    st.session_state.household_type = get_user_household_type(user_id)
                    # Pas besoin de st.experimental_rerun() : st.stop() suffit
                else:
                    st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    # --- Onglet Inscription ---
    with tab_register:
        st.subheader("Inscription")
        reg_username = st.text_input("Choisissez un nom d’utilisateur", key="reg_username")
        reg_password = st.text_input("Choisissez un mot de passe", type="password", key="reg_password")
        reg_password_confirm = st.text_input("Confirmez le mot de passe", type="password", key="reg_password_confirm")

        if st.button("S'inscrire"):
            if reg_username.strip() == "" or reg_password.strip() == "" or reg_password_confirm.strip() == "":
                st.error("❌ Veuillez remplir tous les champs obligatoires.")
            elif reg_password != reg_password_confirm:
                st.error("❌ Les mots de passe ne correspondent pas.")
            else:
                # On marque qu’après inscription, on veut afficher le popup “type de foyer”
                st.session_state.show_household_popup = True
                # On crée d’abord un user “temp” avec household_type à “solo” par défaut (sera mis à jour dans le popup)
                new_id = register_user(reg_username, reg_password, "solo")
                if new_id:
                    st.success("✅ Inscription réussie ! Choisissez maintenant le type de votre foyer.")
                    st.session_state.user_id = new_id
                    st.session_state.username = reg_username.strip()
                    # Le popup s'affichera juste en-dessous
                else:
                    st.error("❌ Ce nom d’utilisateur existe déjà (ou une erreur est survenue).")

    # --- Popup “Choix du foyer” après inscription ---
    if st.session_state.show_household_popup and st.session_state.user_id is not None:
        # On affiche un conteneur “en mode modal” (fond translucide, etc.)
        popup = st.container()
        with popup:
            st.markdown(
                """
                <style>
                /* Overlay sombre */
                .modal-overlay {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background-color: rgba(0,0,0,0.6);
                    z-index: 99;
                }
                /* Conteneur central */
                .modal-content {
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%,-50%);
                    background-color: #1e1e1e;
                    padding: 2rem;
                    border-radius: 0.5rem;
                    max-width: 400px;
                    width: 90%;
                    z-index: 100;
                    color: #fff;
                }
                .close-btn {
                    position: absolute;
                    top: 0.5rem;
                    right: 0.5rem;
                    color: #ccc;
                    font-size: 1.2rem;
                    cursor: pointer;
                }
                .household-tile {
                    border: 2px solid #444;
                    border-radius: 0.5rem;
                    padding: 1rem;
                    text-align: center;
                    cursor: pointer;
                }
                .household-tile-selected {
                    border-color: #ffd700;
                    background-color: #333;
                }
                </style>
                <div class="modal-overlay"></div>
                <div class="modal-content">
                    <div class="close-btn" onclick="document.querySelectorAll('div.modal-overlay, div.modal-content').forEach(el => el.remove());">
                        ✕
                    </div>
                    <h3>Quel est votre type de foyer ?</h3>
                    <div style="display: flex; justify-content: space-around; margin-top: 1rem;">
                """,
                unsafe_allow_html=True
            )

            # Affichage des 3 tuiles (solo, couple, famille)
            cols = st.columns(3)
            idx = 0
            for key, info in HOUSEHOLD_TYPES.items():
                with cols[idx]:
                    # Chaque tuile est un “bouton caché” que l’on peut cliquer
                    if st.button("", key=f"tile_{key}"):
                        # Lorsqu'on clique, on met à jour le type de foyer en base
                        conn = get_connection()
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE users SET household_type = ? WHERE id = ?",
                            (key, st.session_state.user_id)
                        )
                        conn.commit()
                        st.session_state.household_type = key
                        # On masque ensuite le popup
                        st.session_state.show_household_popup = False
                        # On force la rerun pour masquer immédiatement
                        st.experimental_rerun()

                    # On dessine la tuile visuelle avec image+label
                    st.markdown(
                        f"""
                        <div class="household-tile">
                            <img src="{info['img']}" width="64"><br>
                            <span>{info['label']}</span>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                idx += 1

            st.markdown("</div></div>", unsafe_allow_html=True)

            # Note : le bouton “✕” en haut à droite est purement visuel (ferme le popup JS), 
            # mais ne met pas à jour la base. Si l’utilisateur ferme, il restera “solo” par défaut.

    # Puis on stoppe, car si utilisateur non connecté, on ne charge pas l’app principale
    st.stop()

# --------------------------------------------------------------------------------
# GESTION DES RECETTES + INGREDIENTS + EXTRA
# --------------------------------------------------------------------------------

def add_recipe_to_db(user_id: int, recipe_name: str, instructions: str, img_url: str,
                     ingredients: list[dict]):
    """
    Insère une nouvelle recette dans la table recipes, puis toutes ses lignes d'ingrédients.
    ingredients: list de dicts { "name": str, "quantity": float, "unit": str }
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes (user_id, recipe_name, instructions, image_url) VALUES (?, ?, ?, ?)",
        (user_id, recipe_name.strip(), instructions.strip(), img_url.strip())
    )
    conn.commit()
    rec_id = cursor.lastrowid

    # On insère chaque ingrédient lié
    for ingr in ingredients:
        cursor.execute(
            "INSERT INTO ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
            (rec_id, ingr["name"].strip(), ingr["quantity"], ingr["unit"].strip())
        )
    conn.commit()

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    """
    Renvoie un DataFrame avec les colonnes :
     ['id', 'recipe_name', 'instructions', 'image_url']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, recipe_name, instructions, image_url FROM recipes WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    return df

def get_ingredients_for_recipe(recipe_id: int) -> list[dict]:
    """
    Retourne la liste des ingrédients (dict) pour la recette donnée.
    Dict = { "name": str, "quantity": float, "unit": str }
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, quantity, unit FROM ingredients WHERE recipe_id = ?",
        (recipe_id,)
    )
    rows = cursor.fetchall()
    return [{"name": r[0], "quantity": r[1], "unit": r[2]} for r in rows]

def delete_recipe(recipe_id: int):
    """
    Supprime la recette et tous ses ingrédients associés.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ingredients WHERE recipe_id = ?", (recipe_id,))
    cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()

# --------------------------------------------------------------------------------
# GESTION DES COMPLÉMENTS (“EXTRAS”)
# --------------------------------------------------------------------------------

def add_extra_to_db(user_id: int, name: str, quantity: float, unit: str):
    """
    Ajoute un “complément de courses” indépendant (table extras).
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO extras (user_id, name, quantity, unit) VALUES (?, ?, ?, ?)",
        (user_id, name.strip(), quantity, unit.strip())
    )
    conn.commit()

def get_extras_for_user(user_id: int) -> list[dict]:
    """
    Renvoie la liste de compléments enregistrés pour cet utilisateur.
    Chaque élément = { "id": int, "name": str, "quantity": float, "unit": str }
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, quantity, unit FROM extras WHERE user_id = ?",
        (user_id,)
    )
    rows = cursor.fetchall()
    return [{"id": r[0], "name": r[1], "quantity": r[2], "unit": r[3]} for r in rows]

def delete_extra(extra_id: int):
    """
    Supprime un complément “extra” en base.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM extras WHERE id = ?", (extra_id,))
    conn.commit()

# --------------------------------------------------------------------------------
# GESTION DU MEALPLAN (planning) + LISTE DE COURSES
# --------------------------------------------------------------------------------

def upsert_mealplan(user_id: int, plan: list[dict]):
    """
    plan = liste de dicts [{"day": str, "meal": str, "recipe_id": int}, ...].
    On supprime l’ancien planning de la semaine, puis on insère chaque ligne.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for ligne in plan:
        cursor.execute(
            "INSERT INTO mealplans (user_id, day, meal, recipe_id, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, ligne["day"], ligne["meal"], ligne["recipe_id"], now_str)
        )
    conn.commit()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    """
    Renvoie le planning (DataFrame) avec colonnes :
    ['id', 'day', 'meal', 'recipe_id', 'timestamp'].
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_id, timestamp FROM mealplans WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    return df

# --------------------------------------------------------------------------------
# PAGE “PROFIL”
# --------------------------------------------------------------------------------

def show_profile_page():
    """
    Affiche la page Profil :
    - Nom d’utilisateur (immutable)
    - Type de foyer (affiché & possibilité de modifier via popup)
    - Bouton “Modifier le foyer” pour réafficher le popup
    """
    st.header("🧑‍💻 Profil")
    st.write(f"**Nom d’utilisateur :** {st.session_state.username}")
    ht = get_user_household_type(st.session_state.user_id)
    label = HOUSEHOLD_TYPES.get(ht, {"label": "Inconnu"})["label"]
    st.write(f"**Type de foyer :** {label.capitalize()}")
    if st.button("🖉 Modifier le foyer"):
        st.session_state.show_household_popup = True
        st.experimental_rerun()

# --------------------------------------------------------------------------------
# PAGE “MES RECETTES”
# --------------------------------------------------------------------------------

def show_recipes_page():
    """
    Contient :
    - Formulaire d’ajout de RECETTE (nom, instructions, image_url, ingrédients individuellement)
    - Liste des recettes existantes sous forme de cartes (image, nom, fiche ingrédients, fiche instructions, boutons “Supprimer” et “Partager”)
    - Section “Compléments de courses” (ajout ligne par ligne, et listing)
    """
    st.header("📖 Mes recettes")

    # --- SECTION AJOUT DE RECETTE ---
    st.subheader("➕ Ajouter une nouvelle recette")

    with st.form("recipe_form", clear_on_submit=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            rec_name = st.text_input("Nom de la recette", key="form_rec_name")
            rec_instructions = st.text_area("Instructions", key="form_rec_instructions")
        with col2:
            rec_image_url = st.text_input(
                "URL de l’image (optionnel)", 
                placeholder=DEFAULT_RECIPE_IMAGE, 
                key="form_rec_img"
            )
            st.caption("Exemple: URL Unsplash libre de droits")
        st.markdown("---")

        # Saisie “ingrédients” individuellement avec quantité & unité
        st.write("Ajoutez vos ingrédients :")

        # Tableau pour visualiser les ingrédients en cours de saisie
        ingr_df = pd.DataFrame(st.session_state.ingredients_buffer)
        if not ingr_df.empty:
            st.dataframe(ingr_df[["name", "quantity", "unit"]])

        # Champs pour saisir un ingrédient
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            ingr_name = st.text_input("Nom ingrédient", key="form_ingr_name")
        with c2:
            ingr_qty = st.number_input("Quantité", min_value=0.0, format="%.2f", key="form_ingr_qty")
        with c3:
            ingr_unit = st.text_input("Unité (ex: g, ml, etc.)", key="form_ingr_unit")

        if st.button("➕ Ajouter l’ingrédient"):
            if ingr_name.strip() == "" or ingr_qty <= 0 or ingr_unit.strip() == "":
                st.error("❌ Merci de remplir tous les champs de l’ingrédient.")
            else:
                st.session_state.ingredients_buffer.append({
                    "name": ingr_name.strip(),
                    "quantity": ingr_qty,
                    "unit": ingr_unit.strip()
                })
                # On reset les champs de saisie ingrédient en redémarrant le form
                st.experimental_rerun()

        st.markdown("---")
        if st.form_submit_button("Enregistrer la recette"):
            # Validation
            if rec_name.strip() == "" or rec_instructions.strip() == "":
                st.error("❌ Veuillez au moins donner un nom et des instructions.")
            elif len(st.session_state.ingredients_buffer) == 0:
                st.error("❌ Veuillez ajouter au moins un ingrédient.")
            else:
                # On utilise l’URL entrée ou le DEFAULT si vide
                img_url = rec_image_url.strip() if rec_image_url.strip() != "" else DEFAULT_RECIPE_IMAGE
                add_recipe_to_db(
                    st.session_state.user_id,
                    rec_name,
                    rec_instructions,
                    img_url,
                    st.session_state.ingredients_buffer
                )
                st.success("✅ Recette ajoutée !")
                # On vide le buffer d’ingrédients pour la prochaine recette
                st.session_state.ingredients_buffer = []
                st.experimental_rerun()

    st.markdown("---")

    # --- SECTION COMPLÉMENTS DE COURSES ---
    st.subheader("📝 Compléments de courses pour la maison")

    with st.form("extras_form", clear_on_submit=True):
        e1, e2, e3 = st.columns([2, 1, 1])
        with e1:
            extra_name = st.text_input("Nom ingrédient", key="form_extra_name")
        with e2:
            extra_qty = st.number_input("Quantité", min_value=0.0, format="%.2f", key="form_extra_qty")
        with e3:
            extra_unit = st.text_input("Unité (ex: g, ml, etc.)", key="form_extra_unit")

        if st.form_submit_button("Ajouter aux compléments"):
            if extra_name.strip() == "" or extra_qty <= 0 or extra_unit.strip() == "":
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

    # Afficher la liste des “extras” existants
    extras = get_extras_for_user(st.session_state.user_id)
    if extras:
        st.write("### Vos compléments existants :")
        df_extras = pd.DataFrame(extras)
        df_extras_display = df_extras[["name", "quantity", "unit"]].rename(
            columns={"name":"Ingrédient", "quantity":"Quantité", "unit":"Unité"}
        )
        st.dataframe(df_extras_display)

        # Boutons “supprimer” pour chaque extra
        for row in extras:
            col_a, col_b, col_c, col_d = st.columns([3,1,1,1])
            with col_a:
                st.write(f"- {row['name']} ({row['quantity']} {row['unit']})")
            with col_b:
                if st.button("❌ Supprimer", key=f"del_extra_{row['id']}"):
                    delete_extra(row["id"])
                    st.success("🗑️ Complément supprimé.")
                    st.experimental_rerun()
    else:
        st.info("Vous n’avez pas encore ajouté de compléments.")

    st.markdown("---")

    # --- SECTION DES FICHES-RECETTES EXISTANTES ---
    st.subheader("📚 Vos recettes enregistrées")

    df_recipes = get_recipes_for_user(st.session_state.user_id)
    if df_recipes.empty:
        st.info("Vous n’avez pas encore ajouté de recette.")
    else:
        # Pour chaque recette, on affiche une carte
        for idx, rec in df_recipes.iterrows():
            rec_id = rec["id"]
            name = rec["recipe_name"]
            instr = rec["instructions"]
            img_url = rec["image_url"] if rec["image_url"] else DEFAULT_RECIPE_IMAGE
            ingredients_list = get_ingredients_for_recipe(rec_id)

            st.markdown("---")
            card_cols = st.columns([1, 2, 1])
            with card_cols[0]:
                st.image(img_url, use_column_width=True, caption=name)
            with card_cols[1]:
                st.markdown(f"#### {name}")
                st.write("**Ingrédients :**")
                for ingr in ingredients_list:
                    st.write(f"- {ingr['name']} : {ingr['quantity']} {ingr['unit']}")
                st.write("**Instructions :**")
                st.write(instr)
            with card_cols[2]:
                if st.button("❌ Supprimer", key=f"del_rec_{rec_id}"):
                    delete_recipe(rec_id)
                    st.success("🗑️ Recette supprimée.")
                    st.experimental_rerun()

                # Simulation d’un bouton “Partager” via un simple partage Twitter
                tweet_text = f"Découvrez ma recette « {name} » sur Batchist ! 🍽️"
                tweet_url = f"https://twitter.com/intent/tweet?text={tweet_text.replace(' ', '%20')}"
                st.markdown(f"[🐦 Partager sur Twitter]({tweet_url})", unsafe_allow_html=True)

# --------------------------------------------------------------------------------
# PAGE “TABLEAU DE BORD”
# --------------------------------------------------------------------------------

def show_dashboard_page():
    """
    Affiche : 
    - Récapitulatif du planning (dernier planning enregistré) 
    - Possibilité de générer le planning de la semaine (en combinant jour / repas / recette).
    """
    st.header("🏠 Tableau de bord")

    # Récupérer le planning existant
    df_plan = get_mealplan_for_user(st.session_state.user_id)
    if df_plan.empty:
        st.info("Vous n’avez pas encore planifié de repas pour cette semaine.")
    else:
        # On montre les 5 dernières lignes (ordre chrono)
        st.write("### Vos derniers repas planifiés :")
        display = df_plan.copy()
        display["recipe_name"] = display["recipe_id"].apply(lambda rid: get_recipe_name(rid))
        st.dataframe(display[["day", "meal", "recipe_name", "timestamp"]].sort_values(
            by="timestamp", ascending=False
        ).head(5))

    st.markdown("---")
    st.write("### 📅 Planifier vos repas pour la semaine")

    # Construction d’un planning: 7 jours × 3 repas (Petit-déj, Déjeuner, Dîner)
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]
    df_recettes = get_recipes_for_user(st.session_state.user_id)

    # On prépare un DataFrame vide pour stocker ce qu’on choisit
    planning_buffer = []

    with st.form("plan_form"):
        for d in days:
            st.markdown(f"**{d}**")
            cols = st.columns(len(meals))
            for idx, m in enumerate(meals):
                with cols[idx]:
                    key_name = f"select_{d}_{m}"
                    if df_recettes.empty:
                        st.write("Pas de recette")
                    else:
                        choix = st.selectbox(
                            f"{m}",
                            options=[""] + df_recettes["recipe_name"].tolist(),
                            key=key_name
                        )
                        if choix != "":
                            # On cherche l’id de la recette correspondante
                            rid = df_recettes[df_recettes["recipe_name"] == choix]["id"].iloc[0]
                            planning_buffer.append({
                                "day": d,
                                "meal": m,
                                "recipe_id": int(rid)
                            })
        if st.form_submit_button("💾 Enregistrer mon planning"):
            if not planning_buffer:
                st.error("❌ Veuillez sélectionner au moins une recette.")
            else:
                upsert_mealplan(st.session_state.user_id, planning_buffer)
                st.success("✅ Planning enregistré !")
                st.experimental_rerun()

# Fonction utilitaire pour obtenir le nom d’une recette depuis son ID
def get_recipe_name(recipe_id: int) -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT recipe_name FROM recipes WHERE id = ?", (recipe_id,))
    row = cursor.fetchone()
    return row[0] if row else "Inconnue"

# --------------------------------------------------------------------------------
# PAGE “LISTE DE COURSES”
# --------------------------------------------------------------------------------

def show_shopping_list_page():
    """
    Construit et affiche la liste de courses en combinant :
    - Tous les ingrédients liés aux recettes planifiées
    - Tous les compléments “extras”
    """
    st.header("🛒 Liste de courses générée")

    df_plan = get_mealplan_for_user(st.session_state.user_id)
    if df_plan.empty:
        st.info("Planifiez vos repas dans le Tableau de bord avant de générer la liste.")
        return

    # 1) Récupérer tous les ingrédients des recettes planifiées
    conn = get_connection()
    ingr_list = []
    for rid in df_plan["recipe_id"].unique():
        rec_ingr = get_ingredients_for_recipe(rid)
        ingr_list.extend(rec_ingr)

    # 2) Récupérer tous les “extras”
    extras = get_extras_for_user(st.session_state.user_id)

    # On combine ingrédients + extras dans un seul DataFrame pour compter les quantités globales
    combi = []
    for ingr in ingr_list:
        combi.append((ingr["name"], ingr["quantity"], ingr["unit"]))
    for ex in extras:
        combi.append((ex["name"], ex["quantity"], ex["unit"]))

    if not combi:
        st.info("Aucun ingrédient à afficher.")
        return

    # Création d’un DataFrame intermédiaire pour calculer la somme par (name, unit)
    dfc = pd.DataFrame(combi, columns=["name", "quantity", "unit"])
    df_summary = dfc.groupby(["name", "unit"], as_index=False).sum()
    df_summary.columns = ["Ingrédient", "Unité", "Quantité approximative"]

    st.dataframe(df_summary)

# --------------------------------------------------------------------------------
# “MENU” + NAVIGATION PRINCIPALE
# --------------------------------------------------------------------------------

def main_app():
    """
    Barre latérale + navigation :
    - 🏠 Tableau de bord
    - 📖 Mes recettes
    - 🛒 Liste de courses
    - 🧑‍💻 Profil
    - 🔓 Se déconnecter
    """
    st.sidebar.title(f"👋 Bonjour, {st.session_state.username}!")

    choix = st.sidebar.radio(
        "Navigation",
        ["🏠 Tableau de bord", "📖 Mes recettes", "🛒 Liste de courses", "🧑‍💻 Profil", "🔓 Se déconnecter"]
    )

    if choix == "🏠 Tableau de bord":
        show_dashboard_page()
    elif choix == "📖 Mes recettes":
        show_recipes_page()
    elif choix == "🛒 Liste de courses":
        show_shopping_list_page()
    elif choix == "🧑‍💻 Profil":
        show_profile_page()
    elif choix == "🔓 Se déconnecter":
        # On supprime les clés essentielles de session pour forcer le login
        for k in ["user_id", "username", "household_type", "show_household_popup"]:
            if k in st.session_state:
                del st.session_state[k]
        st.experimental_rerun()

# --------------------------------------------------------------------------------
# DÉROULEMENT PRINCIPAL DU SCRIPT
# --------------------------------------------------------------------------------

# Afficher la bannière en haut (URL)
st.image(BANNER_URL, use_container_width=True)

# Si non authentifié → page connexion/inscription
if st.session_state.user_id is None:
    show_login_page()
    st.stop()

# Sinon → afficher l’app complète
main_app()
