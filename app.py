import streamlit as st
import sqlite3
import json
from typing import List, Dict

# ----------------------------
# CONST & DB INITIALIZATION
# ----------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            ingredients TEXT,       -- JSON list of {name, qty, unit}
            instructions TEXT,
            image_url TEXT,
            is_extra INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS mealplans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            day TEXT,
            meal_time TEXT,
            recipe_id INTEGER,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(recipe_id) REFERENCES recipes(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ----------------------------
# UTIL FUNCTIONS
# ----------------------------
def add_user(u,p):
    conn=get_connection(); c=conn.cursor()
    try:
        c.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(u,p):
    conn=get_connection(); c=conn.cursor()
    c.execute("SELECT id FROM users WHERE username=? AND password=?", (u,p))
    row=c.fetchone(); conn.close()
    return row[0] if row else None

def get_recipes(user_id, extra=False):
    conn=get_connection(); c=conn.cursor()
    c.execute("SELECT id,name,ingredients,image_url FROM recipes WHERE user_id=? AND is_extra=?", (user_id,1 if extra else 0))
    rows=c.fetchall(); conn.close()
    return [{"id":r[0],"name":r[1],"ings":json.loads(r[2]),"img":r[3]} for r in rows]

def insert_recipe(user_id,name,ings,instr,img_url,extra=False):
    conn=get_connection(); c=conn.cursor()
    c.execute("""
        INSERT INTO recipes(user_id,name,ingredients,instructions,image_url,is_extra)
        VALUES(?,?,?,?,?,?)
    """,(user_id,name,json.dumps(ings),instr,img_url,1 if extra else 0))
    conn.commit(); conn.close()

def delete_recipe(rid):
    conn=get_connection(); c=conn.cursor()
    c.execute("DELETE FROM recipes WHERE id=?", (rid,))
    conn.commit(); conn.close()

def upsert_mealplan(user_id,day,meal_time,recipe_id):
    conn=get_connection(); c=conn.cursor()
    c.execute("""
        INSERT INTO mealplans(user_id,day,meal_time,recipe_id)
        VALUES(?,?,?,?)
        ON CONFLICT(user_id,day,meal_time) DO UPDATE SET recipe_id=excluded.recipe_id
    """,(user_id,day,meal_time,recipe_id))
    conn.commit(); conn.close()

def get_plan(user_id):
    conn=get_connection(); c=conn.cursor()
    c.execute("SELECT day,meal_time,recipe_id FROM mealplans WHERE user_id=?", (user_id,))
    rows=c.fetchall(); conn.close()
    plan = {d:{"Petit-déj":None,"Déjeuner":None,"Dîner":None} for d in 
            ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]}
    for d,m,r in rows: plan[d][m]=r
    return plan

# ----------------------------
# SESSION STATE INIT
# ----------------------------
st.set_page_config(page_title="Batchist", layout="wide")
if "user_id" not in st.session_state: st.session_state.user_id = None
if "username" not in st.session_state: st.session_state.username = ""
if "onboard_done" not in st.session_state: st.session_state.onboard_done = False

# ----------------------------
# AUTH (Inscription / Login)
# ----------------------------
def show_auth():
    st.title("🔒 Connexion / Inscription")
    tab1,tab2 = st.tabs(["Connexion","Inscription"])
    with tab1:
        u = st.text_input("Nom d’utilisateur", key="login_user")
        p = st.text_input("Mot de passe", type="password", key="login_pwd")
        if st.button("Se connecter"):
            uid = verify_user(u,p)
            if uid:
                st.session_state.user_id = uid
                st.session_state.username = u
                st.success(f"Bienvenue, {u} !")
            else:
                st.error("Identifiants incorrects.")
    with tab2:
        u2 = st.text_input("Choisissez un nom d’utilisateur", key="reg_user")
        p2 = st.text_input("Choisissez mot de passe", type="password", key="reg_pwd")
        p3 = st.text_input("Confirmez mot de passe", type="password", key="reg_pwd2")
        if st.button("Créer mon compte"):
            if not u2.strip():
                st.error("Nom requis.")
            elif p2!=p3:
                st.error("Mots de passe ne correspondent pas.")
            else:
                ok=add_user(u2.strip(),p2)
                if ok: st.success("Compte créé, connectez-vous.")
                else: st.error("Nom déjà pris.")

if st.session_state.user_id is None:
    show_auth()
    st.stop()

# ----------------------------
# ONBOARDING
# ----------------------------
if not st.session_state.onboard_done:
    st.title("Bienvenue sur Batchist !")
    t = st.radio("Comment vivez-vous ?", ["Solo","Couple","Famille"], key="household_type")
    ch = st.number_input("Nombre d’enfants", min_value=0, step=1, key="num_children")
    te = st.number_input("Nombre d’adolescents", min_value=0, step=1, key="num_teens")
    ad = st.number_input("Nombre d’adultes", min_value=1, step=1, key="num_adults")
    mpd = st.slider("Repas par jour ?", 1,6,3, key="meals_per_day")
    if st.button("Commencer"):
        conn=get_connection(); c=conn.cursor()
        c.execute("""
            UPDATE users SET household_type=?,num_children=?,num_teens=?,num_adults=?,meals_per_day=?
            WHERE id=?
        """,(t,ch,te,ad,mpd,st.session_state.user_id))
        conn.commit(); conn.close()
        st.session_state.onboard_done = True
        st.experimental_rerun()

# ----------------------------
# MAIN NAV
# ----------------------------
st.sidebar.title(f"👋 {st.session_state.username}")
page = st.sidebar.radio("Aller à", [
    "Accueil","Mes recettes","Extras","Planificateur","Liste de courses","Conseils","Profil"
])

# ----------------------------
# PAGES
# ----------------------------
if page=="Accueil":
    st.header("🏠 Tableau de bord")
    st.write("**Recettes favorites** / **Tendances du mois** / **Astuces rapides** … (placeholder)")

elif page in ("Mes recettes","Extras"):
    is_extra = (page=="Extras")
    st.header("📝 " + page)
    # Formulaire d'ajout
    with st.expander("➕ Ajouter une recette" + (" (extra)" if is_extra else "")):
        name = st.text_input("Nom de la recette", key="rname")
        instr = st.text_area("Instructions", key="rinstr")
        img = st.text_input("URL image (placeholder OK)", value="https://via.placeholder.com/150", key="rimg")
        # ingrédients dynamiques
        if "ings" not in st.session_state: st.session_state.ings = []
        if st.button("+ Ajouter un ingrédient"):
            st.session_state.ings.append({"name":"","qty":0.0,"unit":"g"})
        for idx,ing in enumerate(st.session_state.ings):
            cols = st.columns([4,2,2,1])
            ing["name"] = cols[0].text_input(f"Ingrédient #{idx+1}", value=ing["name"], key=f"name{idx}")
            ing["qty"]  = cols[1].number_input(f"Qté #{idx+1}", value=ing["qty"], key=f"qty{idx}")
            ing["unit"] = cols[2].selectbox(f"Unité #{idx+1}", ["g","kg","ml","l","pcs"], index=["g","kg","ml","l","pcs"].index(ing["unit"]), key=f"unit{idx}")
            if cols[3].button("🗑", key=f"del{idx}"):
                st.session_state.ings.pop(idx)
                st.experimental_rerun()
        if st.button("Ajouter la recette", key="addrec"):
            insert_recipe(st.session_state.user_id, name, st.session_state.ings, instr, img, extra=is_extra)
            st.success(f"Recette « {name} » ajoutée !")
            st.session_state.ings = []
    # Affichage des cartes
    recs = get_recipes(st.session_state.user_id, extra=is_extra)
    cols = st.columns(3)
    for i,r in enumerate(recs):
        c = cols[i%3]
        with c:
            st.image(r["img"], use_column_width=True)
            st.subheader(r["name"])
            for ing in r["ings"]:
                st.write(f"- {ing['name']} : {ing['qty']} {ing['unit']}")
            btns = st.columns([1,1])
            if btns[0].button("🗑 Supprimer", key=f"delr{r['id']}"):
                delete_recipe(r["id"]); st.experimental_rerun()
            if btns[1].button("🔗 Partager", key=f"sharer{r['id']}"):
                st.info("Lien copié ! (placeholder)")

elif page=="Planificateur":
    st.header("📅 Planificateur de la semaine")
    plan = get_plan(st.session_state.user_id)
    days = list(plan.keys())
    cols = st.columns(7)
    for idx,day in enumerate(days):
        with cols[idx]:
            st.subheader(day)
            for meal in ["Petit-déj","Déjeuner","Dîner"]:
                sel = st.selectbox(meal, ["—"] + [r["name"] for r in get_recipes(st.session_state.user_id)], 
                                   index=0, key=f"{day}_{meal}")
                if sel!="—":
                    # find id
                    rid = next((r["id"] for r in get_recipes(st.session_state.user_id) if r["name"]==sel), None)
                    upsert_mealplan(st.session_state.user_id, day, meal, rid)

elif page=="Liste de courses":
    st.header("🛒 Liste de courses")
    # on récupère tous les ingrédients des recettes planifiées + extras
    plan = get_plan(st.session_state.user_id)
    needed = []
    for day_info in plan.values():
        for rid in day_info.values():
            if rid:
                rec = next(r for r in get_recipes(st.session_state.user_id) if r["id"]==rid)
                needed += rec["ings"]
    # agregation
    agg: Dict[str, Dict[str,float]] = {}
    for ing in needed:
        k = ing["name"]+"|"+ing["unit"]
        agg.setdefault(k,{"name":ing["name"],"unit":ing["unit"],"qty":0})
        agg[k]["qty"] += ing["qty"]
    for v in agg.values():
        st.write(f"- {v['name']} : {v['qty']} {v['unit']}")

elif page=="Conseils":
    st.header("💡 Conseils & astuces")
    st.write("— Batch cooking : préparer en grande quantité…")  # placeholder

elif page=="Profil":
    st.header("👤 Profil")
    conn=get_connection(); c=conn.cursor()
    c.execute("SELECT household_type,num_children,num_teens,num_adults,meals_per_day FROM users WHERE id=?",
              (st.session_state.user_id,))
    t,ch,te,ad,mpd = c.fetchone(); conn.close()
    st.write(f"- Foyer : {t}")
    st.write(f"- Enfants : {ch}")
    st.write(f"- Ados : {te}")
    st.write(f"- Adultes : {ad}")
    st.write(f"- Repas par jour : {mpd}")
    if st.button("Modifier profil"):
        st.session_state.onboard_done = False
        st.experimental_rerun()
