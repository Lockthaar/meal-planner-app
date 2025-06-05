# app.py

import streamlit as st
import sqlite3
import pandas as pd
import json
from collections import defaultdict
from typing import Optional
import io

# ----------------------------------------------------------------
# 1) SET_PAGE_CONFIG (TOUJOURS EN TÊTE) ET CSS POUR LE STYLE
# ----------------------------------------------------------------
st.set_page_config(
    page_title="🍽️ Meal Planner",
    page_icon="🍴",
    layout="wide",
)

# Petit CSS pour masquer le menu Streamlit et le footer, 
# et pour ajuster l’apparence des titres et expandeurs.
st.markdown(
    """
    <style>
        /* Masquer le menu hamburger en haut à droite */
        # MainMenu {visibility: hidden;}
        /* Masquer le footer “Made with Streamlit” */
        footer {visibility: hidden;}
        /* Changer la police et la couleur des headers */
        h1, .st-b {font-family: 'Arial', sans-serif; color: #FFA500;}
        /* Style pour les expanders (bordure, ombre légère) */
        .streamlit-expanderHeader {
            font-size: 1.1rem;
            font-weight: 600;
        }
        .css-1outpf7 {
            border: 1px solid #ddd;
            border-radius: 5px;
            box-shadow: 1px 1px 3px rgba(0,0,0,0.05);
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------------------------------------------
# 2) TITRE PRINCIPAL + LOGO (SI VOUS AVEZ UNE IMAGE, CHANGEZ LE LIEN)
# ----------------------------------------------------------------
st.markdown(
    """
    <div style="display: flex; align-items: center; gap:10px;">
        <img src="https://img.icons8.com/fluency/48/000000/cutlery.png" width="48">
        <h1 style="margin: 0;">🍴 Meal Planner Application</h1>
    </div>
    <p style="font-size:1rem; color:#555; margin-top: -5px;">
        Organisez vos repas, gérez vos recettes et générez votre liste de courses en un clin d’œil !
    </p>
    <hr>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------
# 3) BASE DE DONNÉES SQLITE (COMPTES, RECETTES, PLANNINGS)
# ----------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    """Crée (si besoin) et retourne une connexion à la base SQLite."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    """Crée les tables users, recipes et mealplans si elles n’existent pas."""
    conn = get_connection()
    cursor = conn.cursor()

    # Table users : id, username, password (en clair pour l’exemple — à ne pas faire en prod)
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
    Pour simplifier, on efface d’abord tout, puis on réinsère toutes les lignes.
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

# Fonction de parsage JSON ↔ liste d’ingrédients
@st.cache_data
def parse_ingredients(ing_str: str):
    try:
        return json.loads(ing_str)
    except:
        return []

# Initialise la base (création des tables si nécessaire)
init_db()

# ----------------------------------------------------------------
# 4) AUTHENTIFICATION : GESTION DE LA CONNEXION / INSCRIPTION
# ----------------------------------------------------------------
# On stocke user_id et username dans session_state pour “session login”
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""

# Initialisation du compteur de lignes d’ingrédients (recettes)
if "ing_count" not in st.session_state:
    st.session_state.ing_count = 1

def show_login_page():
    """
    Affiche le formulaire de Connexion / Inscription.
    Si la connexion réussit, on met à jour st.session_state.user_id.
    """
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["🔐 Connexion", "✍️ Inscription"])

    # --- Onglet Connexion ---
    with tab1:
        st.write("Connectez-vous pour accéder à vos recettes et plannings.")
        login_user = st.text_input("Nom d'utilisateur", key="login_username", placeholder="Ex. : mon_login")
        login_pwd  = st.text_input("Mot de passe", type="password", key="login_password", placeholder="••••••••")
        if st.button("Se connecter", key="login_button", use_container_width=True):
            uid = verify_user(login_user.strip(), login_pwd)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = login_user.strip()
                st.success(f"Bienvenue, **{login_user.strip()}** ! Vous êtes connecté.")
                # On ne force plus le rerun ici, on laisse le script continuer naturellement
            else:
                st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

    # --- Onglet Inscription ---
    with tab2:
        st.write("Créez votre compte pour commencer à enregistrer vos recettes.")
        new_user = st.text_input("Nom d'utilisateur souhaité", key="register_username", placeholder="Ex. : mon_profil")
        new_pwd  = st.text_input("Mot de passe", type="password", key="register_password", placeholder="••••••••")
        confirm_pwd = st.text_input("Confirmez le mot de passe", type="password", key="register_confirm", placeholder="••••••••")
        if st.button("Créer mon compte", key="register_button", use_container_width=True):
            if not new_user.strip():
                st.error("❌ Le nom d’utilisateur ne peut pas être vide.")
            elif new_pwd != confirm_pwd:
                st.error("❌ Les mots de passe ne correspondent pas.")
            else:
                ok = add_user(new_user.strip(), new_pwd)
                if ok:
                    st.success("✅ Compte créé avec succès ! Vous pouvez maintenant vous connecter.")
                else:
                    st.error(f"❌ Le nom d’utilisateur « {new_user.strip()} » existe déjà.")

# Affiche d’abord la page de login/inscription
show_login_page()

# Tant que l’utilisateur n’est pas connecté, on stoppe le reste
if st.session_state.user_id is None:
    st.stop()

# ----------------------------------------------------------------
# 5) L’UTILISATEUR EST CONNECTÉ : on affiche le reste de l’application
# ----------------------------------------------------------------
USER_ID = st.session_state.user_id

# Barre latérale : infos utilisateur + déconnexion + navigation
with st.sidebar:
    st.markdown("---")
    st.write(f"👤 **Connecté en tant que : {st.session_state.username}**")
    if st.button("🔓 Se déconnecter", use_container_width=True):
        # On vide la session et on recharge la page pour revenir au login
        del st.session_state.user_id
        del st.session_state.username
        st.experimental_rerun()
    st.markdown("---")
    st.write("🗂️ **Navigation :**")
    section = st.radio(
        label="Aller à…",
        options=["Mes recettes", "Planificateur", "Liste de courses", "Impression"],
        index=0
    )
    st.markdown("---")
    st.info(
        """
        💡 Astuces :  
        - Créez d’abord vos recettes,  
        - Puis planifiez la semaine,  
        - Et générez la liste de courses automatiquement !
        """
    )

# ----------------------------------------------------------------
# FONCTIONNALITÉS PAR SECTION
# ----------------------------------------------------------------

# Section “Mes recettes”
if section == "Mes recettes":
    st.header("📋 Mes recettes")
    st.markdown("Ajoutez, consultez ou supprimez vos recettes personnelles.")

    # 5.1 – Formulaire d’ajout de recette
    with st.expander("➕ Ajouter une nouvelle recette", expanded=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            name = st.text_input("Nom de la recette", key="new_name", placeholder="Ex. : Poulet au curry")
        with col2:
            # Permet d’ajouter dynamiquement plusieurs lignes d’ingrédients
            st.write("**Lignes d’ingrédients :**")
            if st.button("➕ Ajouter une ligne", key="add_ing", use_container_width=True):
                st.session_state.ing_count += 1

        # Affiche les lignes en fonction de ing_count
        ingrédients_temp = []
        unités_dispo = ["mg", "g", "kg", "cl", "dl", "l", "pièce(s)"]

        for i in range(st.session_state.ing_count):
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                ingr_i = st.text_input(f"Ingrédient #{i+1}", key=f"ing_nom_{i}", placeholder="Ex. : Farine")
            with c2:
                qty_i = st.number_input(f"Quantité #{i+1}", min_value=0.0, format="%.2f", key=f"ing_qty_{i}")
            with c3:
                unit_i = st.selectbox(f"Unité #{i+1}", unités_dispo, key=f"ing_unit_{i}")
            ingrédients_temp.append((ingr_i, qty_i, unit_i))

        instructions = st.text_area("Instructions (facultatif)", key="new_instructions", placeholder="Décrivez ici la préparation…")

        if st.button("💾 Enregistrer la recette", key="save_recipe", use_container_width=True):
            df_recettes = get_recipes_for_user(USER_ID)
            if not name.strip():
                st.error("❌ Le nom de la recette ne peut pas être vide.")
            elif name.strip() in df_recettes["name"].tolist():
                st.error(f"❌ Vous avez déjà une recette appelée « {name.strip()} ».")
            else:
                # Filtrage des ingrédients valides (nom non vide + qty > 0)
                ingrédients_list = []
                for ingr_i, qty_i, unit_i in ingrédients_temp:
                    if ingr_i.strip() != "" and qty_i > 0:
                        ingrédients_list.append({
                            "ingredient": ingr_i.strip(),
                            "quantity": float(qty_i),
                            "unit": unit_i
                        })

                if len(ingrédients_list) == 0:
                    st.error("❌ Veuillez remplir au moins un ingrédient valide (nom + quantité > 0).")
                else:
                    ing_json = json.dumps(ingrédients_list, ensure_ascii=False)
                    insert_recipe(USER_ID, name.strip(), ing_json, instructions.strip())
                    st.success(f"✅ Recette « {name.strip()} » ajoutée avec succès.")

                    # Réinitialisation du formulaire
                    if "new_name" in st.session_state:
                        del st.session_state["new_name"]
                    if "new_instructions" in st.session_state:
                        del st.session_state["new_instructions"]
                    for j in range(st.session_state.ing_count):
                        for field in (f"ing_nom_{j}", f"ing_qty_{j}", f"ing_unit_{j}"):
                            if field in st.session_state:
                                del st.session_state[field]
                    st.session_state.ing_count = 1

                    st.experimental_rerun()

    st.markdown("---")

    # 5.2 – Affichage des recettes existantes en expanders individuels
    df_recettes = get_recipes_for_user(USER_ID)
    if df_recettes.empty:
        st.info("Vous n’avez (encore) aucune recette enregistrée. Utilisez le formulaire ci-dessus pour en ajouter !")
    else:
        st.markdown("### 📖 Liste de vos recettes")
        for _, row in df_recettes.iterrows():
            with st.expander(f"📝 {row['name']}", expanded=False):
                colon1, colon2 = st.columns([3, 1])
                with colon1:
                    st.markdown("**Ingrédients :**")
                    for ing in parse_ingredients(row["ingredients"]):
                        st.write(f"- {ing['ingredient']}: {ing['quantity']} {ing['unit']}")
                    st.markdown("**Instructions :**")
                    st.write(row["instructions"] or "_Aucune instruction précisée._")
                with colon2:
                    if st.button("🗑️ Supprimer la recette", key=f"delete_recipe_{row['id']}", use_container_width=True):
                        delete_recipe(row["id"])
                        st.success(f"❌ Recette « {row['name']} » supprimée.")
                        st.experimental_rerun()
                st.markdown("---")

# Section “Planificateur”
elif section == "Planificateur":
    st.header("📅 Planifier mes repas")
    st.markdown("Choisissez une recette pour chaque jour, pour chaque type de repas.")

    df_recettes = get_recipes_for_user(USER_ID)
    choix_recettes = [""] + df_recettes["name"].tolist()

    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]

    with st.form(key="plan_form", clear_on_submit=False):
        cols = st.columns(3)
        selections = []
        for i, day in enumerate(days):
            col = cols[0] if i < 3 else (cols[1] if i < 6 else cols[2])
            with col:
                st.subheader(f"🗓 {day}")
                for meal in meals:
                    recipe_choice = st.selectbox(f"{meal} :", choix_recettes, key=f"{day}_{meal}")
                    selections.append((day, meal, recipe_choice))

        if st.form_submit_button("💾 Enregistrer le planning", use_container_width=True):
            df_plan = pd.DataFrame(selections, columns=["Day", "Meal", "Recipe"])
            df_plan = df_plan[df_plan["Recipe"] != ""].reset_index(drop=True)
            upsert_mealplan(USER_ID, df_plan)
            st.success("✅ Planning de la semaine enregistré.")
            st.experimental_rerun()

    st.markdown("---")
    st.write("### 🏠 Votre planning actuel")
    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Vous n’avez pas encore de planning. Utilisez le formulaire ci-dessus pour en créer un.")
    else:
        st.table(
            df_current_plan[["day", "meal", "recipe_name"]].rename(
                columns={"day": "Jour", "meal": "Repas", "recipe_name": "Recette"}
            )
        )

# Section “Liste de courses”
elif section == "Liste de courses":
    st.header("🛒 Liste de courses générée")
    st.markdown("La liste est automatiquement compilée d’après votre planning.")

    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Planifiez d’abord vos repas pour générer la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        df_recettes = get_recipes_for_user(USER_ID)
        for _, row_plan in df_current_plan.iterrows():
            recette_name = row_plan["recipe_name"]
            row_rec = df_recettes[df_recettes["name"] == recette_name]
            if not row_rec.empty:
                ing_list = parse_ingredients(row_rec.iloc[0]["ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    if total_ingredients[clé]["unit"] and total_ingredients[clé]["unit"] != unit:
                        st.warning(f"⚠️ Unité différente pour « {clé} », vérifiez manuellement.")
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        shopping_data = [
            {"Ingrédient": ing, "Quantité": vals["quantity"], "Unité": vals["unit"]}
            for ing, vals in total_ingredients.items()
        ]
        shopping_df = pd.DataFrame(shopping_data)

        st.table(shopping_df)

        # Ajout d’un bouton pour télécharger la liste en CSV
        towrite = io.StringIO()
        shopping_df.to_csv(towrite, index=False, sep=";")
        towrite.seek(0)
        st.download_button(
            label="⤓ Télécharger la liste en CSV",
            data=towrite,
            file_name="liste_de_courses.csv",
            mime="text/csv",
        )

# Section “Impression”
else:  # section == "Impression"
    st.header("🖨️ Liste de courses imprimable")
    st.markdown("Affichez simplement la liste, puis imprimez la page (Ctrl+P / Cmd+P).")

    df_current_plan = get_mealplan_for_user(USER_ID)
    if df_current_plan.empty:
        st.info("Planifiez d’abord vos repas pour obtenir la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        df_recettes = get_recipes_for_user(USER_ID)
        for _, row_plan in df_current_plan.iterrows():
            recette_name = row_plan["recipe_name"]
            row_rec = df_recettes[df_recettes["name"] == recette_name]
            if not row_rec.empty:
                ing_list = parse_ingredients(row_rec.iloc[0]["ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        shopping_data = [
            {"Ingrédient": ing, "Quantité": vals["quantity"], "Unité": vals["unit"]}
            for ing, vals in total_ingredients.items()
        ]
        shopping_df = pd.DataFrame(shopping_data)

        st.markdown("---")
        st.write("## 📝 Liste de courses")
        st.table(shopping_df)

        st.markdown(
            """
            <div style="text-align:center; margin-top:20px;">
                <i>Appuyez sur <b>Ctrl+P</b> (Windows) ou <b>⌘+P</b> (Mac) pour imprimer cette page.</i>
            </div>
            """,
            unsafe_allow_html=True
        )
