# app.py

# -*- coding: utf-8 -*-
import streamlit as st
import sqlite3
import pandas as pd
import json
from collections import defaultdict
from typing import Optional

# ----------------------------------------------------------------
# FONCTIONS DE GESTION DE LA BASE DE DONNÉES (SQLite)
# ----------------------------------------------------------------

DB_PATH = "meal_planner.db"

def get_connection():
    """Crée (si besoin) et retourne une connexion à la base SQLite."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """Crée les tables users, recipes, mealplans si elles n’existent pas."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table users : id, username, password (en clair pour l’exemple, 
    #              => à ne pas faire en production !)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # Table recipes : id, user_id, name, ingredients_JSON, instructions
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

    # Table mealplans : id, user_id, day, meal, recipe_name
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mealplans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day TEXT NOT NULL,
        meal TEXT NOT NULL,
        recipe_name TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

def add_user(username: str, password: str) -> bool:
    """
    Tente d’ajouter un nouvel utilisateur.
    Retourne True si succès, False si le username existe déjà.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users(username, password) VALUES(?, ?)",
            (username, password)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username: str, password: str) -> Optional[int]:
    """
    Vérifie que le couple (username, password) est valide.
    Si oui, retourne l’user_id. Sinon, retourne None.
    """
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

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère toutes les recettes pour cet user_id sous forme de DataFrame.
    Colonnes : ['id', 'name', 'ingredients', 'instructions']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def insert_recipe(user_id: int, name: str, ingredients_json: str, instructions: str):
    """Insère une nouvelle recette pour cet utilisateur."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes(user_id, name, ingredients, instructions) VALUES(?, ?, ?, ?)",
        (user_id, name, ingredients_json, instructions)
    )
    conn.commit()
    conn.close()

def delete_recipe(recipe_id: int):
    """Supprime la recette dont l’ID est recipe_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    """
    Récupère le planning de l’utilisateur sous forme de DataFrame.
    Colonnes : ['id', 'day', 'meal', 'recipe_name']
    """
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name FROM mealplans WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
    """
    Remplace (supprime + réinsère) tout le planning pour cet user_id.
    Pour simplifier, on efface d’abord tout, puis on réinsère.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM mealplans WHERE user_id = ?", (user_id,))
    conn.commit()
    for _, row in plan_df.iterrows():
        cursor.execute(
            "INSERT INTO mealplans(user_id, day, meal, recipe_name) VALUES(?, ?, ?, ?)",
            (user_id, row["Day"], row["Meal"], row["Recipe"])
        )
    conn.commit()
    conn.close()

# ----------------------------------------------------------------
# FONCTION UTILITAIRE : PARSAGE DES INGREDIENTS (JSON ↔ LISTE)
# ----------------------------------------------------------------
@st.cache_data
def parse_ingredients(ing_str: str):
    try:
        return json.loads(ing_str)
    except:
        return []

# ----------------------------------------------------------------
# INITIALISATION DE LA BASE (SI NÉCESSAIRE)
# ----------------------------------------------------------------
init_db()

# ----------------------------------------------------------------
# INTERFACE PRINCIPALE
# ----------------------------------------------------------------
st.set_page_config(page_title="Meal Planner", layout="wide")
st.title("🍴 Meal Planner Application")

# ----------------------------------------------------------------
# PARTIE AUTHENTIFICATION
# ----------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""

def show_login_page():
    """
    Affiche le formulaire de Connexion / Inscription.
    Si la connexion réussit, on met à jour st.session_state.user_id.
    """
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])

    # --- Onglet Connexion ---
    with tab1:
        st.write("### Connexion")
        login_user = st.text_input("Nom d'utilisateur", key="login_username")
        login_pwd  = st.text_input("Mot de passe", type="password", key="login_password")
        if st.button("Se connecter", key="login_button"):
            uid = verify_user(login_user, login_pwd)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = login_user
                st.success(f"Bienvenue, {login_user} ! Vous êtes connecté.")
                # On ne fait plus st.experimental_rerun() ici.
            else:
                st.error("Nom d’utilisateur ou mot de passe incorrect.")

    # --- Onglet Inscription ---
    with tab2:
        st.write("### Inscription")
        new_user = st.text_input("Choisissez un nom d'utilisateur", key="register_username")
        new_pwd  = st.text_input("Choisissez un mot de passe", type="password", key="register_password")
        confirm_pwd = st.text_input("Confirmez le mot de passe", type="password", key="register_confirm")
        if st.button("Créer mon compte", key="register_button"):
            if not new_user.strip():
                st.error("Le nom d’utilisateur ne peut pas être vide.")
            elif new_pwd != confirm_pwd:
                st.error("Les mots de passe ne correspondent pas.")
            else:
                ok = add_user(new_user.strip(), new_pwd)
                if ok:
                    st.success("Compte créé avec succès ! Vous pouvez maintenant vous connecter.")
                else:
                    st.error(f"Le nom d’utilisateur « {new_user} » existe déjà.")

# Appel du login (ou affichage) 
show_login_page()

# Comme on a retiré le st.experimental_rerun(), il faut maintenant vérifier 
# ici si l’utilisateur est toujours non connecté. Si c’est le cas, on arrête.
if st.session_state.user_id is None:
    st.stop()

# ----------------------------------------------------------------
# À CE STADE, L’UTILISATEUR EST CONNECTÉ (user_id, username remplis)
# ----------------------------------------------------------------
st.sidebar.write(f"👤 Connecté en tant que **{st.session_state.username}**")
if st.sidebar.button("🔓 Se déconnecter"):
    # On réinitialise la session et on rafraîchit
    del st.session_state.user_id
    del st.session_state.username
    st.experimental_rerun()

# ----------------------------------------------------------------
# RAPPEL : USER_ID ACTUEL
# ----------------------------------------------------------------
USER_ID = st.session_state.user_id

# ----------------------------------------------------------------
# MENU DE NAVIGATION
# ----------------------------------------------------------------
section = st.sidebar.selectbox("Choisir une section", ["Recettes", "Planificateur", "Liste de courses", "Impression"])

# ----------------------------------------------------------------
# SECTION 1 : GESTION DES RECETTES
# ----------------------------------------------------------------
if section == "Recettes":
    st.header("📋 Mes recettes")

    st.write("**1. Ajouter une nouvelle recette**")
    with st.expander("🆕 Ajouter une nouvelle recette"):
        # Champ pour le nom de la recette
        name = st.text_input("Nom de la recette", key="new_name")

        # Gestion dynamique du nombre de lignes d’ingrédients
        st.write("**Ingrédients**")
        st.write("Pour ajouter une nouvelle ligne :")
        if st.button("➕ Ajouter une ligne d’ingrédient"):
            st.session_state.ing_count += 1

        # Construction du formulaire : ing_count lignes
        ingrédients_temp = []
        unités_dispo = ["mg", "g", "kg", "cl", "dl", "l", "pièce(s)"]

        # Affiche toutes les lignes d’ingrédients en fonction de ing_count
        for i in range(st.session_state.ing_count):
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                ingr_i = st.text_input(f"Ingrédient #{i+1}", key=f"ing_nom_{i}")
            with c2:
                qty_i = st.number_input(f"Quantité #{i+1}", min_value=0.0, format="%.2f", key=f"ing_qty_{i}")
            with c3:
                unit_i = st.selectbox(f"Unité #{i+1}", unités_dispo, key=f"ing_unit_{i}")
            ingrédients_temp.append((ingr_i, qty_i, unit_i))

        # Champ d’instructions
        instructions = st.text_area("Instructions", key="new_instructions")

        # Bouton pour enregistrer la recette
        if st.button("💾 Enregistrer la recette", key="save_recipe"):
            # Vérifie que le nom n’est pas vide ET qu’il n’existe pas déjà pour cet utilisateur
            df_recettes = get_recipes_for_user(USER_ID)
            if not name.strip():
                st.error("Le nom de la recette ne peut pas être vide.")
            elif name.strip() in df_recettes["name"].tolist():
                st.error(f"Vous avez déjà une recette appelée « {name.strip()} ».")
            else:
                # On filtre les lignes d’ingrédient où le nom est non vide et quantité > 0
                ingrédients_list = []
                for ingr_i, qty_i, unit_i in ingrédients_temp:
                    if ingr_i.strip() != "" and qty_i > 0:
                        ingrédients_list.append({
                            "ingredient": ingr_i.strip(),
                            "quantity": float(qty_i),
                            "unit": unit_i
                        })

                # Si aucun ingrédient valide, on signale une erreur
                if len(ingrédients_list) == 0:
                    st.error("Veuillez remplir au moins un ingrédient valide (nom non vide et quantité > 0).")
                else:
                    # Création du JSON des ingrédients
                    ing_json = json.dumps(ingrédients_list, ensure_ascii=False)

                    # Insertion en base
                    insert_recipe(USER_ID, name.strip(), ing_json, instructions.strip())
                    st.success(f"Recette « {name.strip()} » ajoutée.")

                    # Réinitialisation du formulaire (suppression des clés session_state)
                    if "new_name" in st.session_state:
                        del st.session_state["new_name"]
                    if "new_instructions" in st.session_state:
                        del st.session_state["new_instructions"]
                    for j in range(st.session_state.ing_count):
                        for field in (f"ing_nom_{j}", f"ing_qty_{j}", f"ing_unit_{j}"):
                            if field in st.session_state:
                                del st.session_state[field]
                    st.session_state.ing_count = 1

                    # Après avoir ajouté la recette, on relance simplement un "refresh" local 
                    # en appelant st.experimental_rerun() ici (uniquement pour afficher la nouvelle recette).
                    # Mais cette fois, comme on n’est plus dans la page de login, cela ne posera pas d’erreur.
                    st.experimental_rerun()

    st.markdown("---")
    st.write("**2. Liste des recettes existantes**")
    df_recettes = get_recipes_for_user(USER_ID)
    if df_recettes.empty:
        st.info("Vous n'avez aucune recette pour l'instant.")
    else:
        for idx, row in df_recettes.iterrows():
            col1, col2 = st.columns([8, 1])
            with col1:
                st.markdown(f"### {row['name']}")
                ingrédients = parse_ingredients(row["ingredients"])
                for ing in ingrédients:
                    st.write(f"- {ing['ingredient']}: {ing['quantity']} {ing['unit']}")
                st.write("**Instructions :**")
                st.write(row["instructions"])
            with col2:
                if st.button("🗑️ Supprimer", key=f"delete_recipe_{row['id']}"):
                    delete_recipe(row["id"])
                    st.success(f"Recette « {row['name']} » supprimée.")
                    st.experimental_rerun()
            st.markdown("---")

# ----------------------------------------------------------------
# SECTION 2 : PLANIFICATEUR DE LA SEMAINE
# ----------------------------------------------------------------
elif section == "Planificateur":
    st.header("📅 Planifier mes repas")

    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]

    st.write("Sélectionnez pour chaque jour le nom de la recette :")
    df_recettes = get_recipes_for_user(USER_ID)
    choix_recettes = [""] + df_recettes["name"].tolist()

    # On crée un petit formulaire
    with st.form(key="plan_form"):
        selections = []
        cols = st.columns(3)
        for i, day in enumerate(days):
            col = cols[0] if i < 3 else (cols[1] if i < 6 else cols[2])
            with col:
                st.subheader(day)
                for meal in meals:
                    recipe_choice = st.selectbox(f"{meal} :", choix_recettes, key=f"{day}_{meal}")
                    selections.append((day, meal, recipe_choice))

        submit = st.form_submit_button("💾 Enregistrer le plan")
        if submit:
            df_plan = pd.DataFrame(selections, columns=["Day", "Meal", "Recipe"])
            # On ne garde que les lignes où l’utilisateur a sélectionné une recette
            df_plan = df_plan[df_plan["Recipe"] != ""].reset_index(drop=True)
            upsert_mealplan(USER_ID, df_plan)
            st.success("Plan de la semaine enregistré.")
            st.experimental_rerun()

    st.markdown("**Plan actuel**")
    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Vous n’avez pas encore de plan pour cette semaine.")
    else:
        st.table(df_current_plan[["day", "meal", "recipe_name"]].rename(
            columns={"day": "Jour", "meal": "Repas", "recipe_name": "Recette"}
        ))

# ----------------------------------------------------------------
# SECTION 3 : GÉNÉRER LA LISTE DE COURSES
# ----------------------------------------------------------------
elif section == "Liste de courses":
    st.header("🛒 Liste de courses générée")

    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        for _, row in df_current_plan.iterrows():
            recette_name = row["recipe_name"]
            df_recettes = get_recipes_for_user(USER_ID)
            row_rec = df_recettes[df_recettes["name"] == recette_name]
            if not row_rec.empty:
                ing_list = parse_ingredients(row_rec.iloc[0]["ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    if total_ingredients[clé]["unit"] and total_ingredients[clé]["unit"] != unit:
                        st.warning(f"Unité différente pour '{clé}', vérifiez manuellement.")
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
        st.table(shopping_df)

# ----------------------------------------------------------------
# SECTION 4 : IMPRESSION DE LA LISTE DE COURSES
# ----------------------------------------------------------------
else:  # section == "Impression"
    st.header("🖨️ Liste de courses imprimable")

    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Planifiez d’abord vos repas pour obtenir la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        for _, row in df_current_plan.iterrows():
            recette_name = row["recipe_name"]
            df_recettes = get_recipes_for_user(USER_ID)
            row_rec = df_recettes[df_recettes["name"] == recette_name]
            if not row_rec.empty:
                ing_list = parse_ingredients(row_rec.iloc[0]["ingredients"])
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
