import os
import sqlite3
import streamlit as st
import pandas as pd
import json
from typing import Optional

# ----------------------------------------------------------------
# Supprime la base existante (uniquement en phase de dev)
# ----------------------------------------------------------------
DB_PATH = "meal_planner.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

# ----------------------------------------------------------------
# INITIALISATION DE LA BASE (SI NÉCESSAIRE)
# ----------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    # Utilisateurs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        household_type TEXT,
        num_children INTEGER,
        num_teens INTEGER,
        num_adults INTEGER,
        meals_per_day INTEGER
    )
    """)

    # Recettes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS recipes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        ingredients TEXT NOT NULL,      -- JSON list of {name, qty, unit}
        instructions TEXT,
        image_url TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Extras (boissons, ménage, animaux…)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        qty REAL,
        unit TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    # Plan de la semaine
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mealplans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        day TEXT NOT NULL,      -- Lundi, Mardi…
        meal TEXT NOT NULL,     -- petit-déj / déjeuner / dîner
        recipe_name TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ----------------------------------------------------------------
# FONCTIONS UTILITAIRES / CRUD
# ----------------------------------------------------------------
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def add_user(username: str, password: str) -> bool:
    conn = get_connection(); c = conn.cursor()
    try:
        c.execute("INSERT INTO users(username,password) VALUES(?,?)", (username, password))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username: str, password: str) -> Optional[int]:
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
    row = c.fetchone(); conn.close()
    return row[0] if row else None

def insert_recipe(user_id: int, name: str, ingredients: list, instructions: str, image_url: str):
    conn = get_connection(); c = conn.cursor()
    c.execute(
        "INSERT INTO recipes(user_id,name,ingredients,instructions,image_url) VALUES(?,?,?,?,?)",
        (user_id, name, json.dumps(ingredients), instructions, image_url)
    )
    conn.commit(); conn.close()

def get_recipes_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection(); df = pd.read_sql_query(
        "SELECT * FROM recipes WHERE user_id=?", conn, params=(user_id,)
    )
    conn.close()
    if not df.empty:
        df["ingredients"] = df["ingredients"].apply(json.loads)
    return df

def delete_recipe(recipe_id: int):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM recipes WHERE id=?", (recipe_id,))
    conn.commit(); conn.close()

def insert_extra(user_id: int, name: str, qty: float, unit: str):
    conn = get_connection(); c = conn.cursor()
    c.execute(
        "INSERT INTO extras(user_id,name,qty,unit) VALUES(?,?,?,?)",
        (user_id, name, qty, unit)
    )
    conn.commit(); conn.close()

def get_extras_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection(); df = pd.read_sql_query(
        "SELECT * FROM extras WHERE user_id=?", conn, params=(user_id,)
    )
    conn.close()
    return df

def delete_extra(extra_id: int):
    conn = get_connection(); c = conn.cursor()
    c.execute("DELETE FROM extras WHERE id=?", (extra_id,))
    conn.commit(); conn.close()

def upsert_mealplan(user_id: int, day: str, meal: str, recipe_name: str):
    conn = get_connection(); c = conn.cursor()
    # on supprime l'ancien si existant
    c.execute(
        "DELETE FROM mealplans WHERE user_id=? AND day=? AND meal=?",
        (user_id, day, meal)
    )
    c.execute(
        "INSERT INTO mealplans(user_id,day,meal,recipe_name) VALUES(?,?,?,?)",
        (user_id, day, meal, recipe_name)
    )
    conn.commit(); conn.close()

def get_mealplan_for_user(user_id: int) -> pd.DataFrame:
    conn = get_connection(); df = pd.read_sql_query(
        "SELECT * FROM mealplans WHERE user_id=?", conn, params=(user_id,)
    )
    conn.close()
    return df

# ----------------------------------------------------------------
# UI
# ----------------------------------------------------------------
st.set_page_config(page_title="Batchist", layout="wide")
st.title("🍽️ Batchist — Batch cooking simplifié")

# Session state init
for key, val in {
    "user_id": None,
    "username": "",
    "onboard_step": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

def show_login():
    st.subheader("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["Connexion", "Inscription"])
    with tab1:
        u = st.text_input("Nom d’utilisateur", key="login_u")
        p = st.text_input("Mot de passe", type="password", key="login_p")
        if st.button("Se connecter", key="btn_login"):
            uid = verify_user(u.strip(), p)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = u.strip()
                st.success(f"Bienvenue, {u.strip()} !")
                st.experimental_rerun()
            else:
                st.error("Identifiants incorrects.")
    with tab2:
        nu = st.text_input("Choisissez un nom", key="reg_u")
        npw = st.text_input("Mot de passe", type="password", key="reg_p")
        cpw = st.text_input("Confirmez", type="password", key="reg_cp")
        if st.button("Créer mon compte", key="btn_reg"):
            if not nu.strip():
                st.error("Nom vide.")
            elif npw != cpw:
                st.error("Mots de passe différents.")
            else:
                ok = add_user(nu.strip(), npw)
                if ok:
                    st.success("Compte créé, connectez-vous.")
                else:
                    st.error("Ce nom existe déjà.")

show_login()
if st.session_state.user_id is None:
    st.stop()

# Navigation horizontale
page = st.radio(
    "", ["Accueil", "Mes recettes", "Extras", "Planificateur", "Liste de courses", "Conseils", "Profil"],
    horizontal=True
)

# --- Accueil ---
def page_accueil():
    st.header("📊 Tableau de bord")
    st.markdown("- Vos recettes les plus planifiées le mois dernier…")
    st.markdown("- Astuces du mois : …")

# --- Mes recettes ---
def page_recettes():
    st.header("📋 Mes recettes")
    # Formulaire d’ajout
    with st.expander("➕ Ajouter une nouvelle recette", expanded=True):
        mode = st.radio("Mode d’ajout", ["Manuel", "Importer"], horizontal=True)
        name = st.text_input("Nom de la recette")
        # ingrédients dynamiques
        if "ing_items" not in st.session_state:
            st.session_state.ing_items = [{"name":"", "qty":0.0, "unit":"g"}]
        if st.button("➕ Ajouter un ingrédient"):
            st.session_state.ing_items.append({"name":"", "qty":0.0, "unit":"g"})
            st.experimental_rerun()
        cols = st.columns((3,1,1))
        for i, item in enumerate(st.session_state.ing_items):
            cols[0].text_input(f"Ingrédient #{i+1}", key=f"i_name_{i}")
            cols[1].number_input(f"Qté #{i+1}", key=f"i_qty_{i}", format="%.2f")
            cols[2].selectbox(f"Unité #{i+1}", ["mg","g","kg","ml","cl","l"], key=f"i_unit_{i}")
        instr = st.text_area("Instructions")
        imgurl = st.text_input("URL image (placeholder OK)")
        if st.button("Ajouter la recette"):
            # collecte
            inks = []
            for i in range(len(st.session_state.ing_items)):
                inks.append({
                    "name": st.session_state[f"i_name_{i}"],
                    "qty": st.session_state[f"i_qty_{i}"],
                    "unit": st.session_state[f"i_unit_{i}"]
                })
            insert_recipe(st.session_state.user_id, name, inks, instr, imgurl)
            st.success(f"Recette “{name}” ajoutée !")
            del st.session_state["ing_items"]
            st.experimental_rerun()
    # Listing
    df = get_recipes_for_user(st.session_state.user_id)
    for _, r in df.iterrows():
        st.image(r["image_url"] or "https://via.placeholder.com/150", width=150)
        st.subheader(r["name"])
        st.write("• “" + r["instructions"] + "”")
        ing_list = r["ingredients"]
        st.write("Ingrédients :")
        for ing in ing_list:
            st.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        c1, c2 = st.columns(2)
        if c1.button("❌ Supprimer", key=f"del_r_{r['id']}"):
            delete_recipe(r["id"]); st.experimental_rerun()
        if c2.button("🔗 Partager", key=f"share_r_{r['id']}"):
            st.info("Lien à implémenter…")

# --- Extras ---
def page_extras():
    st.header("🥤 Extras (boissons, ménage…)")
    with st.expander("➕ Ajouter un extra", expanded=True):
        ename = st.text_input("Nom de l’extra")
        eqty = st.number_input("Quantité", format="%.2f", key="ext_qty")
        eunit = st.selectbox("Unité", ["mg","g","kg","ml","cl","l"], key="ext_unit")
        if st.button("Ajouter l’extra"):
            insert_extra(st.session_state.user_id, ename, eqty, eunit)
            st.success(f"“{ename}” ajouté !")
            st.experimental_rerun()
    df = get_extras_for_user(st.session_state.user_id)
    for _, e in df.iterrows():
        st.write(f"- {e['name']}: {e['qty']} {e['unit']}  ", end="")
        if st.button("❌", key=f"del_e_{e['id']}"):
            delete_extra(e["id"]); st.experimental_rerun()

# --- Planificateur ---
def page_planif():
    st.header("📅 Planificateur de la semaine")
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    for day in days:
        with st.container():
            st.markdown(f"### {day}")
            cols = st.columns(3)
            for meal in ["Petit-déj","Déjeuner","Dîner"]:
                cols[["Petit-déj","Déjeuner","Dîner"].index(meal)].selectbox(
                    meal,
                    [""] + list(get_recipes_for_user(st.session_state.user_id)["name"]),
                    key=f"{day}_{meal}"
                )
            if st.button(f"Sauvegarder {day}"):
                for meal in ["Petit-déj","Déjeuner","Dîner"]:
                    recipe = st.session_state[f"{day}_{meal}"]
                    if recipe:
                        upsert_mealplan(st.session_state.user_id, day, meal, recipe)
                st.success(f"{day} enregistré !")

# --- Liste de courses ---
def page_courses():
    st.header("🛒 Liste de courses")
    # On regroupe ingrédients + extras
    mp = get_mealplan_for_user(st.session_state.user_id)
    recipes = get_recipes_for_user(st.session_state.user_id)
    shop = {}
    for _, row in mp.iterrows():
        rec = recipes[recipes["name"]==row["recipe_name"]].iloc[0]
        for ing in rec["ingredients"]:
            key = (ing["name"], ing["unit"])
            shop[key] = shop.get(key,0) + ing["qty"]
    extras = get_extras_for_user(st.session_state.user_id)
    for _, e in extras.iterrows():
        key = (e["name"], e["unit"])
        shop[key] = shop.get(key,0) + e["qty"]

    for (name,unit), qty in shop.items():
        st.write(f"- {name}: {qty} {unit}")
    if st.button("🖨️ Imprimer"):
        st.info("Fonction à intégrer…")

# --- Conseils & astuces ---
def page_conseils():
    st.header("💡 Conseils & Astuces")
    st.markdown("- Organisez vos batchs par types d’ingrédients…")
    st.markdown("- Congelez ce qui se garde longtemps…")

# --- Profil utilisateur ---
def page_profil():
    st.header("👤 Profil")
    conn = get_connection(); c = conn.cursor()
    c.execute("SELECT household_type,num_children,num_teens,num_adults,meals_per_day FROM users WHERE id=?", (st.session_state.user_id,))
    row = c.fetchone(); conn.close()
    st.write(f"- Type de foyer : {row[0] or '—'}")
    st.write(f"- Enfants : {row[1] or 0}")
    st.write(f"- Adolescents : {row[2] or 0}")
    st.write(f"- Adultes : {row[3] or 0}")
    st.write(f"- Repas/jour : {row[4] or 0}")
    if st.button("✏️ Modifier le profil"):
        st.session_state.onboard_step = 1
        st.experimental_rerun()

    # onboarding modals
    if st.session_state.onboard_step >= 1:
        # Étape foyer
        foy = st.radio("1) Comment vivez-vous ?", ["Solo","Couple","Famille"], key="foyer")
        if st.button("Suivant", key="btn_foyer"):
            st.session_state.onboard_step = 2
            conn = get_connection(); c = conn.cursor()
            c.execute(
                "UPDATE users SET household_type=? WHERE id=?",
                (st.session_state.foyer, st.session_state.user_id)
            )
            conn.commit(); conn.close()
            st.experimental_rerun()
    if st.session_state.onboard_step >= 2:
        # Étape composition
        nc = st.number_input("Nombre d’enfants", min_value=0, key="num_children")
        nt = st.number_input("Nombre d’ados", min_value=0, key="num_teens")
        na = st.number_input("Nombre d’adultes", min_value=1, key="num_adults")
        if st.button("Suivant", key="btn_comp"):
            st.session_state.onboard_step = 3
            conn = get_connection(); c = conn.cursor()
            c.execute(
                "UPDATE users SET num_children=?,num_teens=?,num_adults=? WHERE id=?",
                (st.session_state.num_children, st.session_state.num_teens,
                 st.session_state.num_adults, st.session_state.user_id)
            )
            conn.commit(); conn.close()
            st.experimental_rerun()
    if st.session_state.onboard_step >= 3:
        mpd = st.slider("Repas par jour ?", 1, 6, key="meals_per_day")
        if st.button("Terminer", key="btn_mpd"):
            conn = get_connection(); c = conn.cursor()
            c.execute(
                "UPDATE users SET meals_per_day=? WHERE id=?",
                (st.session_state.meals_per_day, st.session_state.user_id)
            )
            conn.commit(); conn.close()
            st.session_state.onboard_step = 0
            st.success("Profil mis à jour !")
            st.experimental_rerun()

# Dispatch pages
if page == "Accueil":
    page_accueil()
elif page == "Mes recettes":
    page_recettes()
elif page == "Extras":
    page_extras()
elif page == "Planificateur":
    page_planif()
elif page == "Liste de courses":
    page_courses()
elif page == "Conseils":
    page_conseils()
elif page == "Profil":
    page_profil()
