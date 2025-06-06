# app.py

import sqlite3
import pandas as pd
import streamlit as st
from hashlib import sha256
from datetime import datetime

# ----------------------------
# CONFIGURATION GÉNÉRALE
# ----------------------------
st.set_page_config(
    page_title="Meal Planner",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DB_PATH = "mealplanner.db"


# ----------------------------
# FONCTIONS DE BASE DE DONNÉES
# ----------------------------
def get_connection():
    """
    Retourne une connexion sqlite3, en désactivant le thread check pour Streamlit.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


def init_db():
    """
    Crée TOUTES les tables nécessaires si elles n'existent pas déjà.
    """
    conn = get_connection()
    c = conn.cursor()

    # ------------------
    # TABLE users
    # ------------------
    # Ajout des colonnes pour stocker :
    #   - household_type (solo/couple/famille),
    #   - adultes, adolescents, enfants,
    #   - repas_par_semaine
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            household_type TEXT,
            adultes INTEGER,
            adolescents INTEGER,
            enfants INTEGER,
            repas_par_semaine INTEGER
        );
    """)

    # ------------------
    # TABLE recipes
    # ------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            recipe_name TEXT NOT NULL,
            description TEXT,
            image_url TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # ------------------
    # TABLE ingredients
    # ------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            FOREIGN KEY(recipe_id) REFERENCES recipes(id)
        );
    """)

    # ------------------
    # TABLE mealplans
    # ------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            meal TEXT NOT NULL,
            recipe_id INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(recipe_id) REFERENCES recipes(id)
        );
    """)

    # ------------------
    # TABLE grocery_items
    # ------------------
    c.execute("""
        CREATE TABLE IF NOT EXISTS grocery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


# Appel de l'initialisation de la base juste après les imports, avant tout affichage.
init_db()


# ----------------------------
# FONCTIONS D'AIDE : AUTHENTIFICATION
# ----------------------------
def hash_password(password: str) -> str:
    """
    Hache un mot de passe en SHA256 et retourne le hex digest.
    """
    return sha256(password.encode("utf-8")).hexdigest()


def register_user(username: str, password: str,
                  household_type: str, adultes: int,
                  adolescents: int, enfants: int,
                  repas_par_semaine: int) -> bool:
    """
    Enregistre un nouvel utilisateur dans la table users.
    Retourne True si succès, False si l'username existe déjà ou autre erreur.
    """
    pwd_hash = hash_password(password)
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, password_hash, household_type, adultes, adolescents, enfants, repas_par_semaine)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (
            username.strip(),
            pwd_hash,
            household_type,
            adultes,
            adolescents,
            enfants,
            repas_par_semaine
        ))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # username déjà existant
        conn.close()
        return False
    except Exception:
        conn.close()
        return False


def login_user(username: str, password: str):
    """
    Tente de connecter un utilisateur. Si succès, retourne son id, sinon None.
    """
    pwd_hash = hash_password(password)
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, household_type, adultes, adolescents, enfants, repas_par_semaine 
        FROM users 
        WHERE username = ? AND password_hash = ?;
    """, (username.strip(), pwd_hash))
    result = c.fetchone()
    conn.close()
    if result:
        # On renvoie aussi les infos de foyer
        return {
            "id": result[0],
            "household_type": result[1],
            "adultes": result[2],
            "adolescents": result[3],
            "enfants": result[4],
            "repas_par_semaine": result[5]
        }
    else:
        return None


# ----------------------------
# FONCTIONS D'AIDE : REQUÊTES UTILISATEUR
# ----------------------------
def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère tout le plan de repas pour un user donné.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, day, meal, recipe_id, timestamp 
            FROM mealplans 
            WHERE user_id = ?
            ORDER BY timestamp DESC;
            """,
            conn,
            params=(user_id,)
        )
    except Exception:
        st.error("❌ Impossible de récupérer le planning : la table ‘mealplans’ n’existe pas ou la requête SQL est incorrecte.")
        df = pd.DataFrame(columns=["id", "day", "meal", "recipe_id", "timestamp"])
    finally:
        conn.close()
    return df


def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère toutes les recettes d'un utilisateur.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, recipe_name, description, image_url 
            FROM recipes 
            WHERE user_id = ?
            ORDER BY recipe_name ASC;
            """,
            conn,
            params=(user_id,)
        )
    except Exception:
        st.error("❌ Impossible de récupérer vos recettes : la table ‘recipes’ n’existe pas ou la requête SQL est incorrecte.")
        df = pd.DataFrame(columns=["id", "recipe_name", "description", "image_url"])
    finally:
        conn.close()
    return df


def get_ingredients_for_recipe(recipe_id: int) -> pd.DataFrame:
    """
    Récupère les ingrédients d'une recette spécifique.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, name, quantity, unit 
            FROM ingredients 
            WHERE recipe_id = ?
            ORDER BY name ASC;
            """,
            conn,
            params=(recipe_id,)
        )
    except Exception:
        st.error("❌ Impossible de récupérer les ingrédients : la table ‘ingredients’ n’existe pas ou la requête SQL est incorrecte.")
        df = pd.DataFrame(columns=["id", "name", "quantity", "unit"])
    finally:
        conn.close()
    return df


def get_recipe_name(recipe_id: int) -> str:
    """
    Retourne le nom d'une recette depuis son ID.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT recipe_name FROM recipes WHERE id = ?;", (recipe_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else ""


def get_top_ingredients_for_user(user_id: int) -> pd.DataFrame:
    """
    Calcule le top 10 des ingrédients utilisés par l'utilisateur dans toutes ses recettes.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT i.name AS ingredient, SUM(i.quantity) AS total_quantite
            FROM ingredients i
            JOIN recipes r ON i.recipe_id = r.id
            WHERE r.user_id = ?
            GROUP BY i.name
            ORDER BY total_quantite DESC
            LIMIT 10;
            """,
            conn,
            params=(user_id,)
        )
    except Exception:
        st.error("❌ Impossible de récupérer le top ingrédients : vérifiez la table ‘ingredients’ et ‘recipes’.")
        df = pd.DataFrame(columns=["ingredient", "total_quantite"])
    finally:
        conn.close()
    return df


def get_grocery_items_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère les compléments de courses indépendants des recettes.
    """
    conn = get_connection()
    try:
        df = pd.read_sql_query(
            """
            SELECT id, item_name, quantity, unit 
            FROM grocery_items 
            WHERE user_id = ?
            ORDER BY item_name ASC;
            """,
            conn,
            params=(user_id,)
        )
    except Exception:
        st.error("❌ Impossible de récupérer la liste de courses : la table ‘grocery_items’ n’existe pas.")
        df = pd.DataFrame(columns=["id", "item_name", "quantity", "unit"])
    finally:
        conn.close()
    return df


# ----------------------------
# FONCTIONS D'ACTION : AJOUT / SUPPRESSION
# ----------------------------
def add_recipe(user_id: int, name: str, description: str, image_url: str) -> int:
    """
    Ajoute une nouvelle recette, retourne l'ID de la recette créée.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO recipes (user_id, recipe_name, description, image_url)
        VALUES (?, ?, ?, ?);
    """, (user_id, name.strip(), description.strip(), image_url.strip()))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def add_ingredient(recipe_id: int, name: str, qty: float, unit: str):
    """
    Ajoute un ingrédient à une recette donnée.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO ingredients (recipe_id, name, quantity, unit)
        VALUES (?, ?, ?, ?);
    """, (recipe_id, name.strip(), qty, unit))
    conn.commit()
    conn.close()


def delete_recipe(recipe_id: int):
    """
    Supprime une recette ET tous ses ingrédients associés.
    """
    conn = get_connection()
    c = conn.cursor()
    # On supprime d'abord les ingrédients
    c.execute("DELETE FROM ingredients WHERE recipe_id = ?;", (recipe_id,))
    # Puis la recette
    c.execute("DELETE FROM recipes WHERE id = ?;", (recipe_id,))
    conn.commit()
    conn.close()


def add_grocery_item(user_id: int, name: str, qty: float, unit: str):
    """
    Ajoute un complément de course pour l’utilisateur.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO grocery_items (user_id, item_name, quantity, unit)
        VALUES (?, ?, ?, ?);
    """, (user_id, name.strip(), qty, unit))
    conn.commit()
    conn.close()


def delete_grocery_item(item_id: int):
    """
    Supprime un complément de course.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM grocery_items WHERE id = ?;", (item_id,))
    conn.commit()
    conn.close()


# ----------------------------
# INITIALISATION DES VARIABLES DE SESSION
# ----------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = ""

# Infos de foyer (après inscription ou login):
for key in ["household_type", "adultes", "adolescents", "enfants", "repas_par_semaine"]:
    if key not in st.session_state:
        st.session_state[key] = None

# Pour piloter le pop-up d'inscription en plusieurs étapes
if "registration_phase" not in st.session_state:
    st.session_state.registration_phase = 1

# Pour stocker temporairement dans le modal d'inscription
for key in ["reg_username", "reg_password", "reg_confirm_password",
            "reg_household_type", "reg_adultes", "reg_adolescents",
            "reg_enfants", "reg_repas_par_semaine"]:
    if key not in st.session_state:
        st.session_state[key] = None


# ----------------------------
# FONCTION : PAGE DE LOGIN / INSCRIPTION
# ----------------------------
def show_login_registration():
    """
    Affiche le formulaire de connexion ou d'inscription.
    Utilise un st.beta_container (st.container) pour regrouper les deux onglets.
    """
    st.title("🔒 Connexion / Inscription")

    # On crée 2 onglets : Connexion | Inscription
    tabs = st.tabs(["Connexion", "Inscription"])

    # --------------------
    # ONGLET CONNEXION
    # --------------------
    with tabs[0]:
        st.subheader("Connexion")
        login_username = st.text_input("Nom d'utilisateur", key="login_username")
        login_password = st.text_input("Mot de passe", type="password", key="login_password")
        if st.button("Se connecter"):
            if not login_username or not login_password:
                st.error("Veuillez remplir les deux champs.")
            else:
                user_data = login_user(login_username, login_password)
                if user_data:
                    # On enregistre dans session_state
                    st.session_state.logged_in = True
                    st.session_state.user_id = user_data["id"]
                    st.session_state.username = login_username.strip()
                    st.session_state.household_type = user_data["household_type"]
                    st.session_state.adultes = user_data["adultes"]
                    st.session_state.adolescents = user_data["adolescents"]
                    st.session_state.enfants = user_data["enfants"]
                    st.session_state.repas_par_semaine = user_data["repas_par_semaine"]
                    st.success("Succès ! Vous êtes connecté.")
                    st.experimental_rerun()
                else:
                    st.error("Identifiants incorrects.")

    # --------------------
    # ONGLET INSCRIPTION
    # --------------------
    with tabs[1]:
        st.subheader("Inscription")
        # Champs initiaux : username / password / confirm password
        st.session_state.reg_username = st.text_input("Choisissez un nom d'utilisateur", key="reg_username")
        st.session_state.reg_password = st.text_input("Choisissez un mot de passe", type="password", key="reg_password")
        st.session_state.reg_confirm_password = st.text_input("Confirmez le mot de passe", type="password", key="reg_confirm_password")

        if st.button("Continuer l'inscription"):
            # Validation basique
            if not st.session_state.reg_username or not st.session_state.reg_password or not st.session_state.reg_confirm_password:
                st.error("Remplissez tous les champs obligatoires.")
            elif st.session_state.reg_password != st.session_state.reg_confirm_password:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                # On ouvre un modal pour les étapes suivantes
                with st.modal("Quel est votre type de foyer ?") as modal:
                    modal.write("Veuillez répondre aux 3 questions pour terminer l'inscription.")
                    # On gère la progression via st.session_state.registration_phase
                    if st.session_state.registration_phase == 1:
                        st.markdown("### 1) Sélectionnez votre type de foyer")
                        col1, col2, col3 = st.columns(3)
                        # URL d'images en ligne (exemple)
                        url_solo = "https://i.imgur.com/3ZQ3ZDt.png"        # image solo
                        url_couple = "https://i.imgur.com/6zK8DuQ.png"      # image couple
                        url_famille = "https://i.imgur.com/dp0N3Jf.png"    # image famille

                        with col1:
                            st.image(url_solo, caption="Solo", use_column_width=True)
                            if st.button("Solo"):
                                st.session_state.reg_household_type = "Solo"
                                st.session_state.registration_phase = 2
                                st.experimental_rerun()

                        with col2:
                            st.image(url_couple, caption="Couple", use_column_width=True)
                            if st.button("Couple"):
                                st.session_state.reg_household_type = "Couple"
                                st.session_state.registration_phase = 2
                                st.experimental_rerun()

                        with col3:
                            st.image(url_famille, caption="Famille", use_column_width=True)
                            if st.button("Famille"):
                                st.session_state.reg_household_type = "Famille"
                                st.session_state.registration_phase = 2
                                st.experimental_rerun()

                    elif st.session_state.registration_phase == 2:
                        st.markdown("### 2) Combien de personnes dans le foyer ?")
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.session_state.reg_adultes = st.number_input("Adultes", min_value=0, max_value=10, value=1, step=1, key="reg_adultes")
                        with col2:
                            st.session_state.reg_adolescents = st.number_input("Adolescents (13-17 ans)", min_value=0, max_value=10, value=0, step=1, key="reg_adolescents")
                        with col3:
                            st.session_state.reg_enfants = st.number_input("Enfants (<13 ans)", min_value=0, max_value=10, value=0, step=1, key="reg_enfants")
                        if st.button("Suivant"):
                            # On vérifie qu'au moins une personne existe (évitons 0 total)
                            total_personnes = st.session_state.reg_adultes + st.session_state.reg_adolescents + st.session_state.reg_enfants
                            if total_personnes == 0:
                                st.error("Votre foyer doit contenir au moins une personne.")
                            else:
                                st.session_state.registration_phase = 3
                                st.experimental_rerun()

                    elif st.session_state.registration_phase == 3:
                        st.markdown("### 3) Combien de repas par semaine prévoyez-vous ?")
                        st.session_state.reg_repas_par_semaine = st.number_input(
                            "Repas par semaine", min_value=1, max_value=50, value=7, step=1, key="reg_repas_par_semaine"
                        )
                        if st.button("Terminer l'inscription"):
                            # On tente d'enregistrer l'utilisateur
                            success = register_user(
                                username=st.session_state.reg_username,
                                password=st.session_state.reg_password,
                                household_type=st.session_state.reg_household_type,
                                adultes=st.session_state.reg_adultes,
                                adolescents=st.session_state.reg_adolescents,
                                enfants=st.session_state.reg_enfants,
                                repas_par_semaine=st.session_state.reg_repas_par_semaine
                            )
                            if success:
                                st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
                                # On remet la phase à 1 pour une prochaine inscription éventuelle
                                st.session_state.registration_phase = 1
                                modal.empty()
                            else:
                                st.error("Ce nom d'utilisateur est déjà pris ou une erreur est survenue.")
                                # On reste en phase 3 pour réessayer
    # Fin de show_login_registration


# ----------------------------
# FONCTION : HEADER / BANNIÈRE
# ----------------------------
def show_banner():
    """
    Affiche une bannière image en haut de l'application.
    """
    banner_url = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?ixlib=rb-4.0.3&auto=format&fit=crop&w=1350&q=80"
    st.image(banner_url, use_container_width=True)
    st.markdown("---")


# ----------------------------
# FONCTION : MENU DE NAVIGATION (TOP NAV BAR)
# ----------------------------
def main_navigation():
    """
    Retourne le nom de la page choisie par l'utilisateur via st.tabs (top navigation).
    """
    tabs = st.tabs([
        "🏠 Tableau de bord",
        "📝 Mes recettes",
        "🛒 Liste de courses",
        "👤 Profil",
        "🚪 Se déconnecter",
    ])
    return tabs


# ----------------------------
# PAGE : TABLEAU DE BORD
# ----------------------------
def show_dashboard_page():
    st.header("🏠 Tableau de bord")

    # 1) Afficher un résumé du foyer
    st.subheader("Votre foyer")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Type", st.session_state.household_type or "–")
    with col2:
        n_total = (st.session_state.adultes or 0) + (st.session_state.adolescents or 0) + (st.session_state.enfants or 0)
        st.metric("Nombre total de personnes", n_total)
    with col3:
        st.metric("Repas/semaine", st.session_state.repas_par_semaine or "–")

    st.markdown("---")

    # 2) Afficher le plan de repas (tableau)
    st.subheader("Votre plan de repas")
    df_plan = get_mealplan_for_user(st.session_state.user_id)
    if df_plan.empty:
        st.info("Vous n’avez pas encore de planning de repas.")
    else:
        # On cherche à montrer le nom de la recette à la place de recipe_id
        df_plan["Recette"] = df_plan["recipe_id"].apply(get_recipe_name)
        df_plan_display = df_plan[["day", "meal", "Recette", "timestamp"]].copy()
        df_plan_display = df_plan_display.rename(columns={
            "day": "Jour",
            "meal": "Repas",
            "Recette": "Recette sélectionnée",
            "timestamp": "Planifié le"
        })
        st.dataframe(df_plan_display, use_container_width=True)

    st.markdown("---")

    # 3) Top 10 ingrédients
    st.subheader("Top 10 des ingrédients utilisés")
    df_top = get_top_ingredients_for_user(st.session_state.user_id)
    if df_top.empty:
        st.info("Aucun ingrédient à afficher pour le moment.")
    else:
        df_top = df_top.set_index("ingredient")
        st.bar_chart(df_top["total_quantite"])

    st.markdown("---")

    # 4) Section formulaire rapide : ajouter un planning (exemple générique)
    st.subheader("Ajouter un repas au planning")
    with st.form("form_add_meal"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            day = st.selectbox("Jour", ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"], key="plan_day")
        with col2:
            meal = st.selectbox("Repas", ["Petit-déjeuner", "Déjeuner", "Dîner"], key="plan_meal")
        with col3:
            # On propose toutes les recettes de l'utilisateur
            df_rec = get_recipes_for_user(st.session_state.user_id)
            rec_names = df_rec["recipe_name"].tolist()
            selected_recipe_name = st.selectbox("Recette", ["–"] + rec_names, key="plan_recipe")
        with col4:
            submitted = st.form_submit_button("Ajouter au planning")
        if submitted:
            if selected_recipe_name == "–":
                st.error("Veuillez choisir une recette valide.")
            else:
                # Récupérer l'ID de la recette choisie
                recipe_row = df_rec[df_rec["recipe_name"] == selected_recipe_name]
                if not recipe_row.empty:
                    recipe_id = int(recipe_row["id"].iloc[0])
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO mealplans (user_id, day, meal, recipe_id)
                        VALUES (?, ?, ?, ?);
                    """, (st.session_state.user_id, day, meal, recipe_id))
                    conn.commit()
                    conn.close()
                    st.success(f"Le repas '{selected_recipe_name}' a été ajouté au planning.")
                    st.experimental_rerun()
                else:
                    st.error("Erreur interne : recette introuvable.")

    st.markdown("---")


# ----------------------------
# PAGE : MES RECETTES
# ----------------------------
def show_recipes_page():
    st.header("📝 Mes recettes")

    # 1) FORMULAIRE D'AJOUT DE RECETTE
    st.subheader("Ajouter une nouvelle recette")
    with st.expander("Cliquez pour ajouter une recette"):
        with st.form("form_add_recipe"):
            name = st.text_input("Nom de la recette", key="new_recipe_name")
            description = st.text_area("Description", key="new_recipe_desc")
            image_url = st.text_input("URL de l'image (optionnel)", key="new_recipe_image")

            # Gestion dynamique de la liste d'ingrédients
            if "new_ingredients" not in st.session_state:
                st.session_state.new_ingredients = []

            st.markdown("**Ingrédients**")
            cols = st.columns(4)
            with cols[0]:
                ingr_name = st.text_input("Nom ingrédient", key="new_ingr_name")
            with cols[1]:
                ingr_qty = st.number_input("Quantité", min_value=0.0, step=0.1, format="%.2f", key="new_ingr_qty")
            with cols[2]:
                unit = st.selectbox("Unité", ["g", "kg", "ml", "l", "unité(s)"], key="new_ingr_unit")
            with cols[3]:
                if st.button("➕ Ajouter ingrédient"):
                    if ingr_name and ingr_qty > 0:
                        st.session_state.new_ingredients.append({
                            "name": ingr_name.strip(),
                            "quantity": ingr_qty,
                            "unit": unit
                        })
                    else:
                        st.warning(" renseignez un nom et une quantité > 0")

            # Affichage de la liste d'ingrédients ajoutés
            if st.session_state.new_ingredients:
                df_temp = pd.DataFrame(st.session_state.new_ingredients)
                st.table(df_temp)

            submitted = st.form_submit_button("Enregistrer la recette")
            if submitted:
                if not name:
                    st.error("Le nom de la recette est requis.")
                else:
                    # On ajoute la recette
                    new_id = add_recipe(st.session_state.user_id, name, description, image_url)
                    # Puis on ajoute tous les ingrédients
                    for ing in st.session_state.new_ingredients:
                        add_ingredient(new_id, ing["name"], ing["quantity"], ing["unit"])
                    # Réinitialiser la liste d'ingrédients
                    st.session_state.new_ingredients = []
                    st.success(f"Recette '{name}' enregistrée !")
                    st.experimental_rerun()

    st.markdown("---")

    # 2) AFFICHAGE DES RECETTES EXISTANTES
    st.subheader("Vos recettes enregistrées")
    df_rec = get_recipes_for_user(st.session_state.user_id)
    if df_rec.empty:
        st.info("Vous n’avez aucune recette pour le moment.")
    else:
        for idx, row in df_rec.iterrows():
            with st.container():
                cols = st.columns([2, 4, 1, 1])
                with cols[0]:
                    if row["image_url"]:
                        st.image(row["image_url"], use_column_width=True)
                    else:
                        # Placeholder si pas d'image
                        st.image("https://via.placeholder.com/150", use_column_width=True)

                with cols[1]:
                    st.markdown(f"### {row['recipe_name']}")
                    st.write(row["description"] or "_Pas de description_")

                    # Liste des ingrédients
                    df_ing = get_ingredients_for_recipe(int(row["id"]))
                    if not df_ing.empty:
                        st.write("**Ingrédients :**")
                        for _, ing in df_ing.iterrows():
                            st.write(f"- {ing['name']} : {ing['quantity']} {ing['unit']}")

                with cols[2]:
                    # Bouton de suppression
                    if st.button("🗑️ Supprimer", key=f"del_rec_{row['id']}"):
                        delete_recipe(int(row["id"]))
                        st.success("Recette supprimée.")
                        st.experimental_rerun()

                with cols[3]:
                    # Bouton de partage social — exemple Twitter
                    tweet_text = f"Découvrez ma recette « {row['recipe_name']} » !"
                    tweet_url = "https://twitter.com/intent/tweet?text=" + tweet_text.replace(" ", "%20")
                    st.markdown(f"[Partager 🐦]({tweet_url})", unsafe_allow_html=True)

            st.markdown("---")


# ----------------------------
# PAGE : LISTE DE COURSES
# ----------------------------
def show_shopping_list_page():
    st.header("🛒 Liste de courses")

    # 1) Ajout d'un complément de course indépendant
    st.subheader("Ajouter un complément de course")
    with st.form("form_add_grocery"):
        name = st.text_input("Nom de l'article", key="new_item_name")
        qty = st.number_input("Quantité", min_value=0.0, step=0.1, format="%.2f", key="new_item_qty")
        unit = st.selectbox("Unité", ["g", "kg", "ml", "l", "unité(s)"], key="new_item_unit")
        submitted = st.form_submit_button("Ajouter à la liste")
        if submitted:
            if not name or qty <= 0:
                st.error("Nom et quantité (>0) requis.")
            else:
                add_grocery_item(st.session_state.user_id, name, qty, unit)
                st.success(f"'{name}' ajouté à votre liste.")
                st.experimental_rerun()

    st.markdown("---")

    # 2) Affichage des compléments de course
    st.subheader("Vos compléments de courses")
    df_groc = get_grocery_items_for_user(st.session_state.user_id)
    if df_groc.empty:
        st.info("Aucun complément de course ajouté.")
    else:
        for idx, row in df_groc.iterrows():
            col1, col2, col3 = st.columns([4, 1, 1])
            with col1:
                st.write(f"- {row['item_name']} : {row['quantity']} {row['unit']}")
            with col2:
                if st.button("🗑️ Supprimer", key=f"del_item_{row['id']}"):
                    delete_grocery_item(int(row["id"]))
                    st.success("Article supprimé.")
                    st.experimental_rerun()

    st.markdown("---")


# ----------------------------
# PAGE : PROFIL
# ----------------------------
def show_profile_page():
    st.header("👤 Profil")
    st.subheader("Informations de votre compte")

    # Récupérer les données actuelles
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT username, household_type, adultes, adolescents, enfants, repas_par_semaine
        FROM users
        WHERE id = ?;
    """, (st.session_state.user_id,))
    result = c.fetchone()
    conn.close()

    if result:
        current_username = result[0]
        current_household = result[1] or ""
        current_adultes = result[2] or 0
        current_adolescents = result[3] or 0
        current_enfants = result[4] or 0
        current_repas = result[5] or 0

        st.markdown(f"**Nom d'utilisateur :** {current_username}")
        st.markdown(f"**Type de foyer :** {current_household}")
        st.markdown(f"**Adultes :** {current_adultes}")
        st.markdown(f"**Adolescents :** {current_adolescents}")
        st.markdown(f"**Enfants :** {current_enfants}")
        st.markdown(f"**Repas/semaine :** {current_repas}")

        st.markdown("---")

        # Changer de mot de passe
        st.subheader("Changer le mot de passe")
        old_pwd = st.text_input("Ancien mot de passe", type="password", key="old_pwd")
        new_pwd = st.text_input("Nouveau mot de passe", type="password", key="new_pwd")
        confirm_new_pwd = st.text_input("Confirmez le nouveau mot de passe", type="password", key="confirm_new_pwd")
        if st.button("Mettre à jour le mot de passe"):
            if not old_pwd or not new_pwd or not confirm_new_pwd:
                st.error("Remplissez tous les champs.")
            elif new_pwd != confirm_new_pwd:
                st.error("Les nouveaux mots de passe ne correspondent pas.")
            else:
                # Vérification de l'ancien mot de passe
                conn = get_connection()
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE id = ?;", (st.session_state.user_id,))
                stored_hash = c.fetchone()[0]
                conn.close()
                if hash_password(old_pwd) != stored_hash:
                    st.error("L'ancien mot de passe est incorrect.")
                else:
                    # On met à jour
                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        UPDATE users
                        SET password_hash = ?
                        WHERE id = ?;
                    """, (hash_password(new_pwd), st.session_state.user_id))
                    conn.commit()
                    conn.close()
                    st.success("Mot de passe mis à jour avec succès.")

        st.markdown("---")

        # Mettre à jour les informations de foyer
        st.subheader("Mettre à jour votre foyer")
        with st.form("form_update_foyer"):
            new_household = st.selectbox("Type de foyer", ["Solo", "Couple", "Famille"], index=["Solo", "Couple", "Famille"].index(current_household) if current_household in ["Solo", "Couple", "Famille"] else 0)
            new_adultes = st.number_input("Adultes", min_value=0, max_value=10, value=current_adultes, step=1, key="upd_adultes")
            new_adolescents = st.number_input("Adolescents", min_value=0, max_value=10, value=current_adolescents, step=1, key="upd_adolescents")
            new_enfants = st.number_input("Enfants", min_value=0, max_value=10, value=current_enfants, step=1, key="upd_enfants")
            new_repas = st.number_input("Repas par semaine", min_value=1, max_value=50, value=current_repas, step=1, key="upd_repas")
            submitted = st.form_submit_button("Mettre à jour le foyer")
            if submitted:
                conn = get_connection()
                c = conn.cursor()
                c.execute("""
                    UPDATE users
                    SET household_type = ?, adultes = ?, adolescents = ?, enfants = ?, repas_par_semaine = ?
                    WHERE id = ?;
                """, (new_household, new_adultes, new_adolescents, new_enfants, new_repas, st.session_state.user_id))
                conn.commit()
                conn.close()
                st.success("Informations de foyer mises à jour.")
                # On met à jour le session_state
                st.session_state.household_type = new_household
                st.session_state.adultes = new_adultes
                st.session_state.adolescents = new_adolescents
                st.session_state.enfants = new_enfants
                st.session_state.repas_par_semaine = new_repas
    else:
        st.error("Impossible de récupérer les informations du profil.")


# ----------------------------
# FONCTION : DÉCONNEXION
# ----------------------------
def do_logout():
    """
    Déconnecte l'utilisateur en réinitialisant session_state.
    """
    for key in ["logged_in", "user_id", "username",
                "household_type", "adultes", "adolescents", "enfants", "repas_par_semaine"]:
        st.session_state[key] = None if key != "logged_in" else False
    st.success("Vous êtes déconnecté.")
    st.experimental_rerun()


# ----------------------------
# CORPS PRINCIPAL DE L'APPLICATION
# ----------------------------
def main_app():
    # Affichage de la bannière
    show_banner()

    # Menu de navigation (onglets en haut)
    tab_objects = main_navigation()

    # On parcourt chaque onglet et on affiche la page correspondante s'il est sélectionné
    if st.experimental_get_query_params().get("page", [None])[0] == "logout":
        do_logout()
        return

    # Détection de l'onglet actif
    if "active_tab" not in st.session_state:
        st.session_state.active_tab = 0

    for i, tobj in enumerate(tab_objects):
        if tobj:
            if st.session_state.active_tab == i:
                with st.container():
                    if i == 0:
                        show_dashboard_page()
                    elif i == 1:
                        show_recipes_page()
                    elif i == 2:
                        show_shopping_list_page()
                    elif i == 3:
                        show_profile_page()
                    elif i == 4:
                        do_logout()

    # Mise à jour de l'onglet actif au clic
    # (L'API st.tabs n'offre pas directement de callback, donc on simule
    # en utilisant query_params ou un bouton masqué.)

    # En fait, on peut utiliser st.experimental_set_query_params pour changer de page à la déconnexion,
    # mais pour les onglets, on se contente de stocker active_tab dans session_state
    # et Streamlit gère l'affichage. Si vous souhaitez une logique plus complexe,
    # on peut remplacer st.tabs par st.radio horizontal + st.empty() pour afficher dynamiquement.


# ----------------------------
# POINT D'ENTRÉE
# ----------------------------
def run():
    if not st.session_state.logged_in:
        show_login_registration()
    else:
        main_app()


if __name__ == "__main__":
    run()
