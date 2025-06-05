# app.py

import streamlit as st
import pandas as pd
import sqlite3
import json
from collections import defaultdict

# ----------------------------------------------------------------
# CONFIGURATION DE LA DB (SQLite)
# ----------------------------------------------------------------

# Chemin du fichier SQLite (il sera créé à la racine de votre app)
DB_PATH = "meal_planner.db"

def get_db_connection():
    """
    Ouvre (ou crée) la base SQLite, et renvoie une connexion.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initialise les tables si elles n'existent pas :
      - users(username UNIQUE, password)
      - recipes(user_id, name, ingredients (JSON), instructions)
      - mealplans(user_id, day, meal, recipe_name)
    """
    conn = get_db_connection()
    c = conn.cursor()
    # Table users
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT NOT NULL UNIQUE,
            password    TEXT NOT NULL
        )
    """)
    # Table recipes
    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            name          TEXT NOT NULL,
            ingredients   TEXT NOT NULL,  -- JSON string
            instructions  TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    # Table mealplans
    c.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            day         TEXT NOT NULL,
            meal        TEXT NOT NULL,
            recipe_name TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

# Appelle l'initialisation dès le démarrage
init_db()

# ----------------------------------------------------------------
# UTILITAIRES D'AUTHENTIFICATION
# ----------------------------------------------------------------

def register_user(username: str, password: str) -> (bool, str):
    """
    Tente de créer un nouvel utilisateur. 
    Renvoie (True, "") si OK, sinon (False, message_erreur).
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
        return True, ""
    except sqlite3.IntegrityError:
        return False, "Ce nom d’utilisateur existe déjà."
    finally:
        conn.close()

def check_credentials(username: str, password: str) -> (bool, int):
    """
    Vérifie si le couple (username, password) existe. 
    Si oui, renvoie (True, user_id). Sinon, (False, None).
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id FROM users WHERE username = ? AND password = ?",
        (username, password)
    )
    row = c.fetchone()
    conn.close()
    if row:
        return True, row["id"]
    else:
        return False, None

# ----------------------------------------------------------------
# SESSION STATE: initialisation des clés
# ----------------------------------------------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# ----------------------------------------------------------------
# FONCTION UTILITAIRE DE PARSAGE DES INGREDIENTS
# ----------------------------------------------------------------
@st.cache_data
def parse_ingredients(ing_str: str):
    """
    Convertit la chaîne JSON enregistrée dans 'ingredients' en liste de dict.
    """
    try:
        return json.loads(ing_str)
    except:
        return []

# ----------------------------------------------------------------
# PAGE DE CONNEXION / INSCRIPTION
# ----------------------------------------------------------------
def show_login_page():
    st.title("🔒 Connexion / Inscription")

    tab1, tab2 = st.tabs(["Connexion", "Inscription"])

    # --- Onglet Connexion ---
    with tab1:
        st.subheader("Se connecter")
        login_username = st.text_input("Nom d’utilisateur", key="login_user")
        login_password = st.text_input("Mot de passe", type="password", key="login_pass")
        if st.button("🔑 Se connecter"):
            ok, user_id = check_credentials(login_username, login_password)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username = login_username
                st.session_state.user_id = user_id
                st.success(f"Connecté en tant que '{login_username}'.")
                st.experimental_rerun()
            else:
                st.error("Nom d’utilisateur ou mot de passe incorrect.")

    # --- Onglet Inscription ---
    with tab2:
        st.subheader("Créer un nouveau compte")
        new_username = st.text_input("Choisir un nom d’utilisateur", key="reg_user")
        new_password = st.text_input("Choisir un mot de passe", type="password", key="reg_pass")
        new_password2 = st.text_input("Confirmez le mot de passe", type="password", key="reg_pass2")
        if st.button("📝 S’inscrire"):
            if not new_username.strip():
                st.error("Le nom d’utilisateur ne peut pas être vide.")
            elif new_password != new_password2:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                ok, msg = register_user(new_username, new_password)
                if ok:
                    st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
                else:
                    st.error(msg)

# ----------------------------------------------------------------
# SI NON CONNECTÉ → AFFICHER LA PAGE DE LOGIN
# ----------------------------------------------------------------
if not st.session_state.logged_in:
    show_login_page()
    st.stop()  # on ne va pas plus loin tant que l'utilisateur n'est pas connecté

# ----------------------------------------------------------------
# ICI : UTILISATEUR CONNECTÉ
# ----------------------------------------------------------------
st.sidebar.write(f"👤 Connecté en tant que **{st.session_state.username}**")
if st.sidebar.button("🚪 Se déconnecter"):
    # Réinitialise le session_state pertinent puis reload
    for key in ["logged_in", "username", "user_id"]:
        if key in st.session_state:
            del st.session_state[key]
    st.experimental_rerun()

# ----------------------------------------------------------------
# À PARTIR D’ICI, TOUT EST PROTÉGÉ PAR CONNEXION
# ----------------------------------------------------------------

conn = get_db_connection()
c = conn.cursor()

# ----------------------------------------------------------------
# SECTION RECETTES (AJOUT / AFFICHAGE / SUPPRESSION)
# ----------------------------------------------------------------
def add_recipe_to_db(user_id: int, name: str, ingredients: list, instructions: str):
    """
    Ajoute la recette pour l’utilisateur donné dans la table 'recipes'.
    'ingredients' doit être une liste de dicts {ingredient, quantity, unit}.
    """
    ing_json = json.dumps(ingredients, ensure_ascii=False)
    c.execute("""
        INSERT INTO recipes (user_id, name, ingredients, instructions)
        VALUES (?, ?, ?, ?)
    """, (user_id, name, ing_json, instructions))
    conn.commit()

def get_user_recipes_df(user_id: int) -> pd.DataFrame:
    """
    Récupère toutes les recettes de l'utilisateur sous forme de DataFrame.
    Colonnes : ['id', 'name', 'ingredients', 'instructions'].
    """
    c.execute("""
        SELECT id, name, ingredients, instructions
        FROM recipes
        WHERE user_id = ?
        ORDER BY name COLLATE NOCASE
    """, (user_id,))
    rows = c.fetchall()
    data = []
    for r in rows:
        data.append({
            "id": r["id"],
            "name": r["name"],
            "ingredients": r["ingredients"],
            "instructions": r["instructions"]
        })
    return pd.DataFrame(data)

def delete_recipe_from_db(recipe_id: int):
    c.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()

# ----------------------------------------------------------------
# SECTION MEALPLANNER (AJOUT / AFFICHAGE)
# ----------------------------------------------------------------
def save_mealplan_to_db(user_id: int, df_plan: pd.DataFrame):
    """
    Sauvegarde le DataFrame du planning (colonnes ['day','meal','recipe_name'])
    dans la table 'mealplans' après avoir effacé l’ancien planning pour cet user.
    """
    # Supprime l’ancien planning
    c.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    # Insère chaque ligne
    for _, row in df_plan.iterrows():
        c.execute("""
            INSERT INTO mealplans (user_id, day, meal, recipe_name)
            VALUES (?, ?, ?, ?)
        """, (user_id, row["day"], row["meal"], row["recipe_name"]))
    conn.commit()

def get_user_mealplan_df(user_id: int) -> pd.DataFrame:
    """
    Récupère le planning actuel de l’utilisateur sous forme de DataFrame.
    Colonnes : ['day','meal','recipe_name'].
    """
    c.execute("""
        SELECT day, meal, recipe_name
        FROM mealplans
        WHERE user_id = ?
        ORDER BY 
          CASE day 
            WHEN 'Lundi' THEN 1
            WHEN 'Mardi' THEN 2
            WHEN 'Mercredi' THEN 3
            WHEN 'Jeudi' THEN 4
            WHEN 'Vendredi' THEN 5
            WHEN 'Samedi' THEN 6
            WHEN 'Dimanche' THEN 7
          END,
          CASE meal
            WHEN 'Petit-déjeuner' THEN 1
            WHEN 'Déjeuner' THEN 2
            WHEN 'Dîner' THEN 3
          END
    """, (user_id,))
    rows = c.fetchall()
    data = []
    for r in rows:
        data.append({
            "day": r["day"],
            "meal": r["meal"],
            "recipe_name": r["recipe_name"]
        })
    return pd.DataFrame(data)

def delete_user_mealplan(user_id: int):
    c.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()

# ----------------------------------------------------------------
# AFFICHAGE DE L’APPLICATION APRÈS CONNEXION
# ----------------------------------------------------------------

st.title("🍽️ Meal Planner Application")
st.sidebar.markdown("---")
section = st.sidebar.selectbox("Choisir une section", ["Recettes", "Planificateur", "Liste de courses", "Impression"])


# ----------------------------------------------------------------
# SECTION 1 : RECETTES
# ----------------------------------------------------------------
if section == "Recettes":
    st.header("📖 Ajouter / Voir / Supprimer vos recettes")

    # Récupère le DataFrame des recettes de l’utilisateur
    recipes_df = get_user_recipes_df(st.session_state.user_id)

    # 1. FORMULAIRE D’AJOUT
    st.subheader("1. Ajouter une nouvelle recette")
    with st.expander("🆕 Ajouter une nouvelle recette"):
        name = st.text_input("Nom de la recette", key="new_name")
        st.write("**Ingrédients**")
        st.write("Pour ajouter une ligne :", "➕ Ajouter une ligne d’ingrédient")

        # Compteur d’ingrédients en session
        if "ing_count" not in st.session_state:
            st.session_state.ing_count = 1

        if st.button("➕ Ajouter une ligne d’ingrédient", key="add_ing_line"):
            st.session_state.ing_count += 1

        ingrédients_temp = []
        unités_dispo = ["mg", "g", "kg", "cl", "dl", "l", "pièce(s)"]

        for i in range(st.session_state.ing_count):
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                ingr_i = st.text_input(f"Ingrédient #{i+1}", key=f"ing_nom_{i}")
            with c2:
                qty_i = st.number_input(f"Quantité #{i+1}", min_value=0.0, format="%.2f", key=f"ing_qty_{i}")
            with c3:
                unit_i = st.selectbox(f"Unité #{i+1}", unités_dispo, key=f"ing_unit_{i}")
            ingrédients_temp.append((ingr_i, qty_i, unit_i))

        instructions = st.text_area("Instructions", key="new_instructions")

        if st.button("💾 Enregistrer la recette", key="save_recipe"):
            # Validation basique
            if not name.strip():
                st.error("Le nom de la recette ne peut pas être vide.")
            elif name in recipes_df["name"].tolist():
                st.error(f"Une recette '{name}' existe déjà.")
            else:
                # Filtre ingrédients
                ingrédients_list = []
                for ingr_i, qty_i, unit_i in ingrédients_temp:
                    if ingr_i.strip() != "" and qty_i > 0:
                        ingrédients_list.append({
                            "ingredient": ingr_i.strip(),
                            "quantity": float(qty_i),
                            "unit": unit_i
                        })

                if len(ingrédients_list) == 0:
                    st.error("Remplissez au moins un ingrédient valide.")
                else:
                    add_recipe_to_db(
                        st.session_state.user_id,
                        name.strip(),
                        ingrédients_list,
                        instructions.strip()
                    )
                    st.success(f"Recette '{name}' ajoutée.")

                    # Réinitialisation du formulaire : supprime les clés de session
                    to_del = ["new_name", "new_instructions", "ing_count"]
                    for key in list(st.session_state.keys()):
                        if key in to_del or key.startswith("ing_nom_") or key.startswith("ing_qty_") or key.startswith("ing_unit_"):
                            del st.session_state[key]

    st.markdown("---")
    # 2. LISTE DES RECETTES EXISTANTES
    st.subheader("2. Vos recettes existantes")
    recipes_df = get_user_recipes_df(st.session_state.user_id)  # recharge après potentiels ajouts
    if recipes_df.empty:
        st.info("Vous n’avez pas encore de recette.")
    else:
        for idx, row in recipes_df.iterrows():
            col1, col2 = st.columns([8, 1])
            with col1:
                st.markdown(f"### {row['name']}")
                ing_list = parse_ingredients(row["ingredients"])
                for ing in ing_list:
                    st.write(f"- {ing['ingredient']}: {ing['quantity']} {ing['unit']}")
                st.write("**Instructions :**")
                st.write(row["instructions"])
            with col2:
                if st.button("🗑️ Supprimer", key=f"del_rec_{row['id']}"):
                    delete_recipe_from_db(row["id"])
                    st.experimental_rerun()
            st.markdown("---")


# ----------------------------------------------------------------
# SECTION 2 : PLANIFICATEUR DE LA SEMAINE
# ----------------------------------------------------------------
elif section == "Planificateur":
    st.header("🗓️ Planifier vos repas de la semaine")

    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]

    # Récupère l’ancien planning, si existant
    old_plan_df = get_user_mealplan_df(st.session_state.user_id)

    with st.form(key="plan_form"):
        cols = st.columns(3)
        selections = []
        for i, day in enumerate(days):
            col = cols[0] if i < 3 else (cols[1] if i < 6 else cols[2])
            with col:
                st.subheader(day)
                for meal in meals:
                    # On pré-remplit la selectbox si le plan existait
                    default_choice = ""
                    if not old_plan_df.empty:
                        match = old_plan_df[
                            (old_plan_df["day"] == day) & (old_plan_df["meal"] == meal)
                        ]
                        if len(match) == 1:
                            default_choice = match.iloc[0]["recipe_name"]

                    recette_choices = [""] + get_user_recipes_df(st.session_state.user_id)["name"].tolist()
                    recipe_choice = st.selectbox(
                        f"{meal} :",
                        options=recette_choices,
                        index=recette_choices.index(default_choice) if default_choice in recette_choices else 0,
                        key=f"{day}_{meal}"
                    )
                    selections.append((day, meal, recipe_choice))

        if st.form_submit_button("💾 Enregistrer le plan"):
            df_new = pd.DataFrame(selections, columns=["day", "meal", "recipe_name"])
            df_new = df_new[df_new["recipe_name"] != ""].reset_index(drop=True)
            # On remplace totalement l’ancien planning
            save_mealplan_to_db(st.session_state.user_id, df_new)
            st.success("Plan de la semaine enregistré.")
            # On peut rafraîchir pour voir immédiatement la table
            st.experimental_rerun()

    st.markdown("**Plan actuel**")
    updated_plan = get_user_mealplan_df(st.session_state.user_id)
    if updated_plan.empty:
        st.info("Aucun plan enregistré.")
    else:
        st.table(updated_plan)


# ----------------------------------------------------------------
# SECTION 3 : LISTE DE COURSES
# ----------------------------------------------------------------
elif section == "Liste de courses":
    st.header("🛒 Liste de courses générée")

    plan_df = get_user_mealplan_df(st.session_state.user_id)
    if plan_df.empty:
        st.info("Veuillez d’abord planifier vos repas.")
    else:
        # Agrégation des ingrédients pour chaque recette planifiée
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        recipes_df = get_user_recipes_df(st.session_state.user_id)
        for rec_name in plan_df["recipe_name"]:
            match = recipes_df[recipes_df["name"] == rec_name]
            if not match.empty:
                ing_list = parse_ingredients(match.iloc[0]["ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    if total_ingredients[clé]["unit"] and total_ingredients[clé]["unit"] != unit:
                        st.warning(f"Unité différente pour '{clé}', vérifiez manuellement.")
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        # Construction du DataFrame de la liste de courses
        shopping_data = []
        for ing, vals in total_ingredients.items():
            shopping_data.append({
                "Ingrédient": ing,
                "Quantité": vals["quantity"],
                "Unité": vals["unit"]
            })
        shopping_df = pd.DataFrame(shopping_data)
        st.table(shopping_df)


# ----------------------------------------------------------------
# SECTION 4 : IMPRESSION DE LA LISTE DE COURSES
# ----------------------------------------------------------------
else:  # section == "Impression"
    st.header("🖨️ Liste de courses imprimable")

    plan_df = get_user_mealplan_df(st.session_state.user_id)
    if plan_df.empty:
        st.info("Planifiez vos repas pour obtenir la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        recipes_df = get_user_recipes_df(st.session_state.user_id)
        for rec_name in plan_df["recipe_name"]:
            match = recipes_df[recipes_df["name"] == rec_name]
            if not match.empty:
                ing_list = parse_ingredients(match.iloc[0]["ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        shopping_data = []
        for ing, vals in total_ingredients.items():
            shopping_data.append({
                "Ingrédient": ing,
                "Quantité": vals["quantity"],
                "Unité": vals["unit"]
            })
        shopping_df = pd.DataFrame(shopping_data)

        st.markdown("---")
        st.write("## Liste de courses à imprimer")
        st.table(shopping_df)
