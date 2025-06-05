# app.py

import streamlit as st
import sqlite3
import pandas as pd
import json
from collections import defaultdict
from typing import Optional
import io

# -------------------------------------------------------------------------------
# 1) CONFIGURATION GLOBALE (police, titre, favicon, CSS “global” pour navbar + cards)
# -------------------------------------------------------------------------------
st.set_page_config(
    page_title="🍽️ Meal Planner",
    page_icon="🍴",
    layout="wide",
)

# On injecte un peu de CSS pour :
#  - charger une Google Font moderne (“Poppins”)
#  - masquer le menu Streamlit par défaut et le footer
#  - créer une navbar fixe en haut
#  - styliser les cards des recettes
#  - ajouter des comportements responsive

st.markdown(
    """
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            font-family: 'Poppins', sans-serif;
        }
        /* Masquer le menu hamburger et le footer “Made with Streamlit” */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}

        /* NAVBAR FIXE EN HAUT */
        .header {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            background: #ffffffcc; /* semi-transparent */
            backdrop-filter: blur(10px);
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 1000;
        }
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 10px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-logo {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header-logo img {
            width: 40px;
            height: 40px;
        }
        .nav-item {
            margin-left: 20px;
            font-weight: 500;
            cursor: pointer;
            color: #333;
        }
        .nav-item:hover {
            color: #FFA500;
        }

        /* Adjust the top padding so that content isn't hidden behind the navbar */
        .streamlit-container {
            padding-top: 80px !important;
        }

        /* HERO SECTION */
        .hero {
            position: relative;
            width: 100%;
            height: 300px;
            background: url('https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80') no-repeat center center / cover;
            margin-bottom: 40px;
            color: white;
        }
        .hero-overlay {
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.4);
        }
        .hero-text {
            position: relative;
            z-index: 1;
            text-align: center;
            top: 50%;
            transform: translateY(-50%);
        }
        .hero-text h1 {
            font-size: 3rem;
            margin-bottom: 10px;
        }
        .hero-text p {
            font-size: 1.2rem;
            opacity: 0.9;
        }

        /* CARDS POUR LES RECETTES */
        .recipe-card {
            border: 1px solid #eee;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .recipe-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        .recipe-card img {
            width: 100%;
            height: 160px;
            object-fit: cover;
        }
        .recipe-card-body {
            padding: 15px;
        }
        .recipe-card-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }
        .recipe-card-buttons {
            margin-top: 10px;
            display: flex;
            justify-content: space-between;
        }
        .recipe-card-buttons button {
            background: #FFA500;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .recipe-card-buttons button:hover {
            background: #ff9800;
        }

        /* STYLE DES EXPANDERS */
        .streamlit-expanderHeader {
            font-size: 1.1rem;
            font-weight: 600;
        }
        .css-1outpf7 {
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 1px 1px 3px rgba(0,0,0,0.05);
        }

        /* SMALL SCREEN ADJUST */
        @media (max-width: 768px) {
            .hero h1 {
                font-size: 2rem !important;
            }
            .hero p {
                font-size: 1rem !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------------------
# 2) STRUCTURE DE LA PAGE
#   - NAVBAR FIXE en haut
#   - HERO (image en background avec titre / description)
#   - CONTENU en dessous (Recettes, Planificateur, Liste de courses, Impression)
# -------------------------------------------------------------------------------

# 2.1) NAVBAR (header fixe)
st.markdown(
    """
    <div class="header">
      <div class="header-content">
        <div class="header-logo">
          <img src="https://img.icons8.com/fluency/48/000000/cutlery.png" alt="logo">
          <span style="font-size:1.5rem; font-weight:700; color:#333;">Meal Planner</span>
        </div>
        <div>
          <span class="nav-item" onclick="window.location.hash='#home'">Accueil</span>
          <span class="nav-item" onclick="window.location.hash='#recipes'">Recettes</span>
          <span class="nav-item" onclick="window.location.hash='#planner'">Planificateur</span>
          <span class="nav-item" onclick="window.location.hash='#shopping'">Liste de courses</span>
          <span class="nav-item" onclick="window.location.hash='#print'">Impression</span>
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 2.2) HERO SECTION
st.markdown(
    """
    <div id="home" class="hero">
      <div class="hero-overlay"></div>
      <div class="hero-text">
        <h1>Planifiez vos repas en quelques clics</h1>
        <p>Créez vos recettes, organisez votre planning et générez votre liste de courses automatiquement.</p>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------------------------------------------------------------
# 3) BASE DE DONNÉES SQLITE (COMPTES, RECETTES, PLANNINGS) – inchangé
# -------------------------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        image_url TEXT,
        ingredients TEXT NOT NULL,
        instructions TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)
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
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, name, image_url, ingredients, instructions FROM recipes WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def insert_recipe(user_id: int, name: str, image_url: str, ingredients_json: str, instructions: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO recipes(user_id, name, image_url, ingredients, instructions) VALUES(?, ?, ?, ?, ?)",
        (user_id, name, image_url, ingredients_json, instructions)
    )
    conn.commit()
    conn.close()

def delete_recipe(recipe_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    conn.commit()
    conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT id, day, meal, recipe_name FROM mealplans WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df

def upsert_mealplan(user_id: int, plan_df: pd.DataFrame):
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

@st.cache_data
def parse_ingredients(ing_str: str):
    try:
        return json.loads(ing_str)
    except:
        return []

init_db()

# -------------------------------------------------------------------------------
# 4) AUTHENTIFICATION : CONNEXION / INSCRIPTION (MASQUÉE LORSQU’ON EST CONNECTÉ)
# -------------------------------------------------------------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "username" not in st.session_state:
    st.session_state.username = ""

# Initialisation du compteur de lignes (recettes)
if "ing_count" not in st.session_state:
    st.session_state.ing_count = 1

def show_login_page():
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["🔐 Connexion", "✍️ Inscription"])

    with tab1:
        st.write("Connectez-vous pour accéder à vos recettes et plannings.")
        login_user = st.text_input("Nom d'utilisateur", key="login_username", placeholder="Ex. : utilisateur123")
        login_pwd  = st.text_input("Mot de passe", type="password", key="login_password", placeholder="••••••••")
        if st.button("Se connecter", key="login_button", use_container_width=True):
            uid = verify_user(login_user.strip(), login_pwd)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = login_user.strip()
                st.success(f"Bienvenue, **{login_user.strip()}** ! Vous êtes connecté.")
            else:
                st.error("❌ Nom d’utilisateur ou mot de passe incorrect.")

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

# Si l’utilisateur n’est pas connecté, on affiche uniquement Connexion/Inscription
if st.session_state.user_id is None:
    show_login_page()
    st.stop()

# -------------------------------------------------------------------------------
# 5) L’UTILISATEUR EST CONNECTÉ : AFFICHAGE DU CONTENU PRINCIPAL
# -------------------------------------------------------------------------------
USER_ID = st.session_state.user_id

# Barre latérale : infos utilisateur + déconnexion + navigation
with st.sidebar:
    st.markdown("---")
    st.write(f"👤 **Connecté : {st.session_state.username}**")
    if st.button("🔓 Se déconnecter", use_container_width=True):
        del st.session_state.user_id
        del st.session_state.username
        st.experimental_rerun()
    st.markdown("---")
    st.write("🗂️ **Navigation :**")
    section = st.radio(
        label="Aller à…",
        options=["Mes recettes", "Planificateur", "Liste de courses", "Impression"],
        index=0,
        horizontal=False
    )
    st.markdown("---")
    st.info(
        """
        💡 Astuces :  
        - Commencez par ajouter vos recettes,  
        - Puis planifiez vos repas,  
        - Et générez votre liste de courses !
        """
    )

# -------------------------------------------------------------------------------
# 6) LAYOUT PAR SECTION
# -------------------------------------------------------------------------------

# SECTION “Mes recettes”
if section == "Mes recettes":
    st.header("📋 Mes recettes")
    st.markdown("Ajoutez, consultez, modifiez ou supprimez vos recettes personnelles.")

    # 6.1 – Formulaire d’ajout de recette (deux modes)
    with st.expander("➕ Ajouter une nouvelle recette", expanded=True):
        st.markdown("**Mode d’ajout :**")
        mode = st.radio(
            label="Sélectionnez le mode d’ajout",
            options=["Saisie manuelle", "Importer depuis texte"],
            index=0,
            horizontal=True
        )

        name = st.text_input("Nom de la recette", key="new_name", placeholder="Ex. : Poulet au curry")

        image_url = st.text_input(
            "URL de l’image (optionnelle)", 
            key="new_image_url", 
            placeholder="Ex. : https://…/mon_image.jpg"
        )

        ingrédients_list = []
        unités_dispo = ["mg", "g", "kg", "cl", "dl", "l", "pièce(s)"]

        if mode == "Saisie manuelle":
            col1, col2 = st.columns([2, 1])
            with col2:
                st.write("**Lignes d’ingrédients**")
                if st.button("➕ Ajouter une ligne", key="add_ing"):
                    st.session_state.ing_count += 1

            ingrédients_temp = []
            for i in range(st.session_state.ing_count):
                c1, c2, c3 = st.columns([4, 2, 2])
                with c1:
                    ingr_i = st.text_input(f"Ingrédient #{i+1}", key=f"ing_nom_{i}", placeholder="Ex. : Farine")
                with c2:
                    qty_i = st.number_input(f"Quantité #{i+1}", min_value=0.0, format="%.2f", key=f"ing_qty_{i}")
                with c3:
                    unit_i = st.selectbox(f"Unité #{i+1}", unités_dispo, key=f"ing_unit_{i}")
                ingrédients_temp.append((ingr_i, qty_i, unit_i))
            ingrédients_list = ingrédients_temp

        else:
            raw_text = st.text_area(
                "Copiez/collez votre liste d’ingrédients",
                key="import_textarea",
                placeholder="Format :\nTomates, 200, g\nPâtes, 300, g\nFromage, 100, g"
            )
            if raw_text:
                lignes = raw_text.strip().split("\n")
                for line in lignes:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) == 3:
                        ingr, qty, unit = parts
                        try:
                            qty_val = float(qty)
                        except:
                            qty_val = 0.0
                        if ingr and qty_val > 0:
                            ingrédients_list.append((ingr, qty_val, unit))
                st.markdown("**Aperçu des ingrédients ajoutés :**")
                if ingrédients_list:
                    for ingr_i, qty_i, unit_i in ingrédients_list:
                        st.write(f"- {ingr_i}: {qty_i} {unit_i}")
                else:
                    st.warning("Aucun ingrédient valide détecté dans le texte.")

        instructions = st.text_area(
            "Instructions (facultatif)",
            key="new_instructions",
            placeholder="Décrivez ici la préparation…"
        )

        if st.button("💾 Enregistrer la recette", key="save_recipe", use_container_width=True):
            df_recettes = get_recipes_for_user(USER_ID)
            if not name.strip():
                st.error("❌ Le nom de la recette ne peut pas être vide.")
            elif name.strip() in df_recettes["name"].tolist():
                st.error(f"❌ Vous avez déjà une recette appelée « {name.strip()} ».")
            else:
                # Construction JSON des ingrédients
                ing_json_list = []
                for ingr_i, qty_i, unit_i in ingrédients_list:
                    if ingr_i.strip() and qty_i > 0 and unit_i.strip():
                        ing_json_list.append({
                            "ingredient": ingr_i.strip(),
                            "quantity": float(qty_i),
                            "unit": unit_i.strip()
                        })

                if len(ing_json_list) == 0:
                    st.error("❌ Veuillez renseigner au moins un ingrédient valide.")
                else:
                    ing_json_str = json.dumps(ing_json_list, ensure_ascii=False)
                    insert_recipe(
                        USER_ID,
                        name.strip(),
                        image_url.strip(),
                        ing_json_str,
                        instructions.strip()
                    )
                    st.success(f"✅ Recette « {name.strip()} » ajoutée avec succès.")

                    # Réinitialisation du formulaire
                    if "new_name" in st.session_state:
                        del st.session_state["new_name"]
                    if mode == "Saisie manuelle":
                        if "ing_count" in st.session_state:
                            del st.session_state["ing_count"]
                        st.session_state.ing_count = 1
                        for j in range(0, 10):
                            for field in (f"ing_nom_{j}", f"ing_qty_{j}", f"ing_unit_{j}"):
                                if field in st.session_state:
                                    del st.session_state[field]
                    else:
                        if "import_textarea" in st.session_state:
                            del st.session_state["import_textarea"]
                    if "new_instructions" in st.session_state:
                        del st.session_state["new_instructions"]
                    if "new_image_url" in st.session_state:
                        del st.session_state["new_image_url"]

                    st.experimental_rerun()

    st.markdown("---")

    # 6.2 – Affichage des recettes sous forme de CARDS (grid)
    df_recettes = get_recipes_for_user(USER_ID)
    if df_recettes.empty:
        st.info("Vous n’avez (encore) aucune recette enregistrée. Utilisez le formulaire ci-dessus pour en ajouter !")
    else:
        st.markdown("### 📖 Vos recettes")
        # On affiche 3 cards par ligne (responsive)
        cards_per_row = 3
        for i in range(0, len(df_recettes), cards_per_row):
            cols = st.columns(cards_per_row, gap="medium")
            for idx, col in enumerate(cols):
                if i + idx < len(df_recettes):
                    row = df_recettes.iloc[i + idx]
                    recipe_id = row["id"]
                    recipe_name = row["name"]
                    image_url = row["image_url"] or "https://via.placeholder.com/300x180.png?text=Pas+d'image"
                    ingrédients = parse_ingredients(row["ingredients"])
                    instructions_txt = row["instructions"] or "Aucune instruction précisée."

                    with col:
                        st.markdown(
                            f"""
                            <div class="recipe-card">
                              <img src="{image_url}" alt="{recipe_name}">
                              <div class="recipe-card-body">
                                <div class="recipe-card-title">{recipe_name}</div>
                                <div style="font-size:0.9rem; color:#555; margin-top:5px;">
                                    {', '.join([ing['ingredient'] for ing in ingrédients][:5])}...
                                </div>
                                <div class="recipe-card-buttons">
                                    <button onclick="window.location.hash='#'">Voir</button>
                                    <button onclick="window.location.hash='#'">Modifier</button>
                                </div>
                              </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

# SECTION “Planificateur”
elif section == "Planificateur":
    st.header("📅 Planifier mes repas")
    st.markdown("Choisissez une recette pour chaque jour et chaque repas.")

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
                    recipe_choice = st.selectbox(
                        f"{meal} :",
                        choix_recettes,
                        key=f"{day}_{meal}"
                    )
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

# SECTION “Liste de courses”
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

        # Tableau stylisé
        st.table(shopping_df)

        # Bouton téléchargement CSV
        towrite = io.StringIO()
        shopping_df.to_csv(towrite, index=False, sep=";")
        towrite.seek(0)
        st.download_button(
            label="⤓ Télécharger la liste en CSV",
            data=towrite,
            file_name="liste_de_courses.csv",
            mime="text/csv",
        )

# SECTION “Impression”
else:  # section == "Impression"
    st.header("🖨️ Liste de courses imprimable")
    st.markdown("Affichez la liste ci-dessous et utilisez votre navigateur pour imprimer (Ctrl+P / ⌘+P).")

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
