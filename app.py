import streamlit as st
import sqlite3
import pandas as pd
import json

# ----------------------------------------------------------------
# BASE DE DONNÉES (SQLite embarquée)
# ----------------------------------------------------------------
DB_PATH = "meal_planner.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # utilisateurs
    cur.execute("""
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
    # recettes
    cur.execute("""
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            ingredients TEXT NOT NULL,  -- JSON list
            image_url TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    # extras (boissons, ménage, animaux…)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS extras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            items TEXT NOT NULL,  -- JSON list
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    # planificateur
    cur.execute("""
        CREATE TABLE IF NOT EXISTS planner (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            day_of_week TEXT NOT NULL,
            breakfast TEXT,
            lunch TEXT,
            dinner TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

def add_user(u, p):
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users(username,password) VALUES(?,?)",(u,p))
        conn.commit(); return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(u, p):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username=? AND password=?", (u,p))
    r = cur.fetchone(); conn.close()
    return r[0] if r else None

# fonctions pour CRUD recettes/extras/planner…
def get_recipes(uid):
    conn=get_connection(); df=pd.read_sql("SELECT * FROM recipes WHERE user_id=?",(conn,uid),params=(uid,))
    conn.close(); return df

def insert_recipe(uid,name,ing,image):
    conn=get_connection(); cur=conn.cursor()
    cur.execute("INSERT INTO recipes(user_id,name,ingredients,image_url) VALUES(?,?,?,?)",
                (uid,name,json.dumps(ing),image))
    conn.commit(); conn.close()

def get_extras(uid):
    conn=get_connection(); df=pd.read_sql("SELECT * FROM extras WHERE user_id=?",conn,params=(uid,))
    conn.close(); return df

def insert_extra(uid,items):
    conn=get_connection(); cur=conn.cursor()
    cur.execute("INSERT INTO extras(user_id,items) VALUES(?,?)",(uid,json.dumps(items)))
    conn.commit(); conn.close()

def get_planner(uid):
    conn=get_connection(); df=pd.read_sql("SELECT * FROM planner WHERE user_id=?",conn,params=(uid,))
    conn.close(); return df

def upsert_plan(uid,day,breakf,lunch,dinner):
    conn=get_connection(); cur=conn.cursor()
    cur.execute("""
      INSERT INTO planner(user_id,day_of_week,breakfast,lunch,dinner)
      VALUES(?,?,?,?,?)
      ON CONFLICT(user_id,day_of_week)
      DO UPDATE SET breakfast=excluded.breakfast,
                    lunch=excluded.lunch,
                    dinner=excluded.dinner
    """,(uid,day,breakf,lunch,dinner))
    conn.commit(); conn.close()

# initialisation DB
init_db()

# ----------------------------------------------------------------
# CONFIG + SIDEBAR NAVIGATION
# ----------------------------------------------------------------
st.set_page_config("Batchist", layout="wide")
if "user_id" not in st.session_state: st.session_state.user_id = None
if "onboard_step" not in st.session_state: st.session_state.onboard_step = 0

PAGES = ["Accueil","Mes recettes","Extras","Planificateur","Liste de courses","Conseils","Profil"]

def nav():
    st.session_state.page = st.radio("", PAGES, index=PAGES.index(st.session_state.get("page","Accueil")), horizontal=True)

# ----------------------------------------------------------------
# 1️⃣ Onboarding / Authentification
# ----------------------------------------------------------------
def login_page():
    st.title("🔒 Connexion / Inscription")
    tab1, tab2 = st.tabs(["Connexion","Inscription"])

    with tab1:
        u = st.text_input("Nom d'utilisateur", key="login_user")
        p = st.text_input("Mot de passe", type="password", key="login_pwd")
        if st.button("Se connecter"):
            uid=verify_user(u,p)
            if uid:
                st.session_state.user_id = uid
                st.session_state.page = "Accueil"
            else:
                st.error("Identifiant ou mot de passe incorrect.")

    with tab2:
        nu = st.text_input("Nom d'utilisateur souhaité", key="reg_user")
        npwd = st.text_input("Mot de passe", type="password", key="reg_pwd")
        cpwd=st.text_input("Confirmez mot de passe", type="password", key="reg_cpwd")
        if st.button("Créer mon compte"):
            if not nu.strip():
                st.error("Nom requis")
            elif npwd!=cpwd:
                st.error("Mots de passe différents")
            elif add_user(nu,npwd):
                st.success("Compte créé, connectez-vous.")
            else:
                st.error("Nom déjà pris.")

def onboarding():
    st.title("Bienvenue sur Batchist !")
    # étape 1 : foyer
    if st.session_state.onboard_step==0:
        st.subheader("1. Quel type de foyer ?")
        cols = st.columns(3)
        for i,typ in enumerate(["Solo","Couple","Famille"]):
            if cols[i].button(typ):
                st.session_state.foyer=typ
                st.session_state.onboard_step=1
                st.experimental_rerun()
    # étape 2 : quantités membres
    elif st.session_state.onboard_step==1:
        st.subheader("2. Combien de membres ?")
        ch=st.number_input("Enfants",0,10,0)
        te=st.number_input("Ados",0,10,0)
        ad=st.number_input("Adultes",1,10,1)
        if st.button("Valider"):
            st.session_state.num_children=ch
            st.session_state.num_teens=te
            st.session_state.num_adults=ad
            st.session_state.onboard_step=2
            st.experimental_rerun()
    # étape 3 : repas/jour
    elif st.session_state.onboard_step==2:
        st.subheader("3. Repas par jour ?")
        mpd=st.slider("",1,6,3)
        if st.button("Commencer"):
            st.session_state.meals_per_day=mpd
            # mise à jour BD
            conn=get_connection();cur=conn.cursor()
            cur.execute("UPDATE users SET household_type=?,num_children=?,num_teens=?,num_adults=?,meals_per_day=? WHERE id=?",
                        (st.session_state.foyer, st.session_state.num_children,
                         st.session_state.num_teens, st.session_state.num_adults,
                         st.session_state.meals_per_day, st.session_state.user_id))
            conn.commit();conn.close()
            st.session_state.onboard_step=3
            st.session_state.page="Accueil"
            st.experimental_rerun()

# ----------------------------------------------------------------
# 2️⃣ Pages de l’app après login + onboarding
# ----------------------------------------------------------------
def page_accueil():
    st.header("🏠 Tableau de bord")
    st.write(f"Bienvenue, **{st.session_state.user_id}** !")
    st.subheader("🧡 Top produits consommés ce mois")
    # placeholder graphique…

def page_recettes():
    st.header("📋 Mes recettes")
    # form ajout
    with st.form("frm_rec"):
        st.subheader("Ajouter une nouvelle recette")
        name=st.text_input("Nom de la recette")
        cols = st.columns([2,1,1])
        # ingrédients dynamiques
        if "ing_list" not in st.session_state:
            st.session_state.ing_list=[{"name":"","qty":0.0,"unit":"g"}]
        if st.form_submit_button("+ Ingrédient"):
            st.session_state.ing_list.append({"name":"","qty":0.0,"unit":"g"})
        for idx,ing in enumerate(st.session_state.ing_list):
            c0,c1,c2 = st.columns([2,1,1])
            ing["name"] = c0.text_input(f"Ingrédient #{idx+1}", value=ing["name"], key=f"n{idx}")
            ing["qty"]  = c1.number_input(f"Qté #{idx+1}", value=ing["qty"], key=f"q{idx}")
            ing["unit"] = c2.selectbox(f"Unité #{idx+1}",["mg","g","kg","ml","cl","l","u"], index=["mg","g","kg","ml","cl","l","u"].index(ing["unit"]), key=f"u{idx}")
        img_url=st.text_input("URL image (placeholder ok)", value="https://via.placeholder.com/150")
        if st.form_submit_button("Ajouter la recette"):
            insert_recipe(st.session_state.user_id, name, st.session_state.ing_list, img_url)
            st.success(f"Recette '{name}' ajoutée.")
            st.session_state.ing_list=[{"name":"","qty":0.0,"unit":"g"}]
            st.experimental_rerun()

    # affichage cartes recettes
    df = get_recipes(st.session_state.user_id)
    for _,row in df.iterrows():
        ing = json.loads(row["ingredients"])
        cols=st.columns([1,3,1])
        cols[0].image(row["image_url"], width=100)
        cols[1].markdown(f"#### {row['name']}")
        for i in ing:
            cols[1].write(f"- {i['name']}: {i['qty']} {i['unit']}")
        cdel = cols[2].button("🗑️ Supprimer", key=f"del{row['id']}")
        if cdel:
            conn=get_connection();cur=conn.cursor()
            cur.execute("DELETE FROM recipes WHERE id=?", (row["id"],))
            conn.commit();conn.close()
            st.experimental_rerun()
        cols[2].button("🔗 Partager", key=f"share{row['id']}")

def page_extras():
    st.header("📦 Mes extras")
    with st.form("frm_ext"):
        items = st.text_area("Liste d’extras (un par ligne: nom,quantité,unité)")
        if st.form_submit_button("Ajouter extras"):
            lst=[l.split(",") for l in items.split("\n") if l]
            insert_extra(st.session_state.user_id, lst)
            st.success("Extras ajoutés.")
            st.experimental_rerun()
    df = get_extras(st.session_state.user_id)
    for _,row in df.iterrows():
        items=json.loads(row["items"])
        st.write("—".join([f"{i[0]}: {i[1]} {i[2]}" for i in items]))

def page_planner():
    st.header("📅 Planificateur de la semaine")
    days=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    df=get_planner(st.session_state.user_id)
    for d in days:
        c=st.container(); c.subheader(d)
        b=l=d=""
        cols=c.columns(3)
        opt = [r["name"] for r in get_recipes(st.session_state.user_id).to_dict("records")]
        b = cols[0].selectbox("Petit-déj", [""]+opt, key=f"{d}_b")
        l = cols[1].selectbox("Déjeuner", [""]+opt, key=f"{d}_l")
        dnr = cols[2].selectbox("Dîner", [""]+opt, key=f"{d}_d")
        if cols[2].button("✔️", key=f"ok{d}"):
            upsert_plan(st.session_state.user_id, d, b, l, dnr)
            st.success(f"{d} enregistré.")

def page_list():
    st.header("🛒 Liste de courses")
    # regrouper ingrédients de recettes + extras
    recs = get_recipes(st.session_state.user_id)
    extras = get_extras(st.session_state.user_id)
    all_items=[]
    for _,r in recs.iterrows():
        for i in json.loads(r["ingredients"]): all_items.append((i["name"],i["qty"],i["unit"]))
    for _,e in extras.iterrows():
        for i in json.loads(e["items"]): all_items.append((i[0],float(i[1]),i[2]))
    df=pd.DataFrame(all_items,columns=["Nom","Qté","Unité"])
    df = df.groupby(["Nom","Unité"]).sum().reset_index()
    st.dataframe(df)
    st.button("🖨️ Imprimer", disabled=False)

def page_conseils():
    st.header("💡 Conseils & Astuces")
    tips = ["Batcher en gros","Congeler","Réutiliser les restes","Planifier le dimanche","Varier les épices"]
    for t in tips: st.write(f"- {t}")

def page_profil():
    st.header("👤 Profil")
    conn=get_connection();df=pd.read_sql("SELECT * FROM users WHERE id=?",conn,params=(st.session_state.user_id,))
    conn.close()
    user=df.iloc[0]
    st.write(f"- Foyer : {user['household_type']}")
    st.write(f"- Enfants : {user['num_children']}")
    st.write(f"- Ados : {user['num_teens']}")
    st.write(f"- Adultes : {user['num_adults']}")
    st.write(f"- Repas/jour : {user['meals_per_day']}")
    if st.button("Modifier"):
        st.session_state.onboard_step=1
        st.experimental_rerun()

# ----------------------------------------------------------------
# 🛠 Main
# ----------------------------------------------------------------
if st.session_state.user_id is None:
    login_page()
elif st.session_state.onboard_step<3:
    onboarding()
else:
    nav()
    if st.session_state.page=="Accueil":     page_accueil()
    if st.session_state.page=="Mes recettes": page_recettes()
    if st.session_state.page=="Extras":      page_extras()
    if st.session_state.page=="Planificateur":page_planner()
    if st.session_state.page=="Liste de courses": page_list()
    if st.session_state.page=="Conseils":     page_conseils()
    if st.session_state.page=="Profil":       page_profil()
