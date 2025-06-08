# app.py
import streamlit as st
import json
import pandas as pd
from pathlib import Path

# ─── Helper JSON ──────────────────────────────────────────────────────
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
for fname in ("users.json","recipes.json","extras.json","plans.json","profiles.json"):
    (DATA_DIR/fname).write_text((DATA_DIR/fname).read_text() if (DATA_DIR/fname).exists() else "{}")

def load_json(fp):
    return json.loads(Path(fp).read_text() or "{}")

def save_json(fp, data):
    Path(fp).write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ─── Charger DB ──────────────────────────────────────────────────────
USERS_FILE    = DATA_DIR/"users.json"
RECIPES_FILE  = DATA_DIR/"recipes.json"
EXTRAS_FILE   = DATA_DIR/"extras.json"
PLANS_FILE    = DATA_DIR/"plans.json"
PROFILES_FILE = DATA_DIR/"profiles.json"

users_db    = load_json(USERS_FILE)
recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROFILES_FILE)

# ─── Fonctions Utilisateurs ──────────────────────────────────────────
def register_user(u,p):
    if u in users_db:
        return False
    users_db[u] = {"password":p}
    save_json(USERS_FILE, users_db)
    return True

def check_login(u,p):
    return u in users_db and users_db[u]["password"]==p

def do_logout():
    st.session_state.clear()
    st.experimental_rerun()

# ─── Configuration Streamlit ────────────────────────────────────────
st.set_page_config("Batchist","wide")
if "user" not in st.session_state:
    # Écran Login / Signup
    st.title("🔒 Connexion / Inscription")
    choice = st.radio("",["Connexion","Inscription"],horizontal=True)
    if choice=="Inscription":
        with st.form("form_reg", clear_on_submit=True):
            nu = st.text_input("Nom d'utilisateur")
            npw = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("S'inscrire")
        if ok:
            if not nu or not npw:
                st.error("Tous les champs sont requis.")
            elif register_user(nu.strip(),npw):
                st.success("Inscription OK : connectez-vous.")
            else:
                st.error("Nom déjà pris.")
        st.stop()
    else:
        with st.form("form_log", clear_on_submit=True):
            u = st.text_input("Nom d'utilisateur")
            p = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("Se connecter")
        if ok:
            if check_login(u.strip(),p):
                st.session_state.user = u.strip()
                st.experimental_rerun()
            else:
                st.error("Identifiants incorrects.")
        st.stop()

# ─── Préparer les données de l’utilisateur ───────────────────────────
user = st.session_state.user
for db, default in [
    (recipes_db,[]), (extras_db,[]), (plans_db,{}), (profiles_db,{})
]:
    db.setdefault(user, default)

# ─── Sidebar & Menu ─────────────────────────────────────────────────
st.sidebar.markdown(f"👤 **Connecté : {user}**")
page = st.sidebar.radio("Navigation",[
    "Accueil","Mes recettes","Extras",
    "Planificateur","Liste de courses",
    "Conseils","Profil","Se déconnecter"
])
if page=="Se déconnecter":
    do_logout()

# ─── ACCUEIL ─────────────────────────────────────────────────────────
if page=="Accueil":
    st.title("🏠 Batchist — Batch cooking simplifié")
    st.write("Bienvenue ! Choisissez un onglet dans la barre latérale.")

# ─── MES RECETTES ────────────────────────────────────────────────────
elif page=="Mes recettes":
    st.title("📋 Mes recettes")
    # Toggle formulaire
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    if st.button("+ Ajouter une recette"):
        st.session_state.show_form = not st.session_state.show_form

    if st.session_state.show_form:
        st.subheader("➕ Nouvelle recette")
        with st.form("frm_recipe", clear_on_submit=True):
            name  = st.text_input("Nom de la recette")
            instr = st.text_area("Instructions", height=100)
            img   = st.text_input("URL de l'image (placeholder OK)")
            # Table interactive des ingrédients
            df = pd.DataFrame(st.session_state.get("tmp_ings",[]),
                              columns=["name","qty","unit"])
            out = st.experimental_data_editor(
                df, num_rows="dynamic", use_container_width=True
            )
            # Soumettre
            ok = st.form_submit_button("Enregistrer la recette")
            if ok:
                if not name.strip():
                    st.error("Le nom est obligatoire.")
                else:
                    recipes_db[user].append({
                        "name":name.strip(),
                        "instr":instr,
                        "img":img,
                        "ings": out.to_dict("records")
                    })
                    save_json(RECIPES_FILE, recipes_db)
                    st.success("Recette ajoutée !")
                    # Réinit
                    st.session_state.tmp_ings = []
                    st.session_state.show_form = False
                    st.experimental_rerun()

    st.markdown("---")
    # Affichage cartes 2 colonnes
    cols = st.columns(2)
    for i, rec in enumerate(recipes_db[user]):
        c = cols[i%2]
        if rec["img"]:
            c.image(rec["img"],width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        m,s,p = c.columns([1,1,1])
        if m.button("✏️ Modifier", key=f"m_{i}"):
            # Précharger en session
            st.session_state.tmp_ings = rec["ings"]
            st.session_state.show_form = True
            # On supprime l’ancienne carte pour réécrire
            recipes_db[user].pop(i)
            save_json(RECIPES_FILE, recipes_db)
            st.experimental_rerun()
        if s.button("🗑️ Supprimer", key=f"x_{i}"):
            recipes_db[user].pop(i)
            save_json(RECIPES_FILE, recipes_db)
            st.experimental_rerun()
        if p.button("🔗 Partager", key=f"sh_{i}"):
            st.info(f"Partage de « {rec['name']} »…")

# ─── EXTRAS ───────────────────────────────────────────────────────────
elif page=="Extras":
    st.title("➕ Extras (produits ménagers, boissons, etc.)")
    with st.expander("+ Ajouter un extra"):
        with st.form("frm_extra", clear_on_submit=True):
            nom  = st.text_input("Produit")
            qty  = st.number_input("Quantité", min_value=0.0)
            unit = st.selectbox("Unité", ["g","kg","ml","l","pcs"])
            ok   = st.form_submit_button("Ajouter")
            if ok and nom.strip():
                extras_db[user].append({"name":nom,"qty":qty,"unit":unit})
                save_json(EXTRAS_FILE, extras_db)
                st.success("Extra ajouté !")
                st.experimental_rerun()

    st.markdown("---")
    for j, ex in enumerate(extras_db[user]):
        c0,c1,c2,c3 = st.columns([4,1,1,1])
        c0.write(ex["name"]); c1.write(ex["qty"]); c2.write(ex["unit"])
        if c3.button("🗑️", key=f"del_{j}"):
            extras_db[user].pop(j)
            save_json(EXTRAS_FILE, extras_db)
            st.experimental_rerun()

# ─── PLANIFICATEUR ──────────────────────────────────────────────────
elif page=="Planificateur":
    st.title("📅 Planificateur de la semaine")
    prof = profiles_db[user] or {"meals_per_day":3}
    mpd = prof["meals_per_day"]
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    cols = st.columns(7)
    for d, day in enumerate(days):
        with cols[d]:
            st.subheader(day)
            for m in range(mpd):
                key = f"{day}_{m}"
                choix = [""] + [r["name"] for r in recipes_db[user]]
                val = plans_db[user].get(key,"")
                plans_db[user][key] = st.selectbox("", choix, index=choix.index(val), key=key)
    if st.button("💾 Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")

# ─── LISTE DE COURSES ────────────────────────────────────────────────
elif page=="Liste de courses":
    st.title("🛒 Liste de courses")
    shop = {}
    # recettes plan
    for recn in plans_db[user].values():
        if not recn: continue
        rec = next((r for r in recipes_db[user] if r["name"]==recn),None)
        if rec:
            for ing in rec["ings"]:
                k=(ing["name"],ing["unit"])
                shop[k]=shop.get(k,0)+ing["qty"]
    # extras
    for ex in extras_db[user]:
        k=(ex["name"],ex["unit"])
        shop[k]=shop.get(k,0)+ex["qty"]
    for (n,u),q in shop.items():
        st.write(f"- {n}: {q} {u}")
    csv = "Produit,Quantité,Unité\n" + "\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("📥 Télécharger CSV", csv, file_name="courses.csv")

# ─── CONSEILS ────────────────────────────────────────────────────────
elif page=="Conseils":
    st.title("💡 Conseils & Astuces")
    for tip in [
        "Planifiez vos repas à l'avance.",
        "Variez les couleurs dans votre assiettes.",
        "Préparez des portions à congeler.",
        "Utilisez des herbes fraîches pour relever vos plats."
    ]:
        st.info(tip)

# ─── PROFIL ─────────────────────────────────────────────────────────
elif page=="Profil":
    st.title("👤 Profil")
    prof = profiles_db[user] or {
        "household":"Solo","children":0,
        "teens":0,"adults":1,"meals_per_day":3
    }
    st.write(f"- Foyer      : {prof['household']}")
    st.write(f"- Enfants    : {prof['children']}")
    st.write(f"- Ados       : {prof['teens']}")
    st.write(f"- Adultes    : {prof['adults']}")
    st.write(f"- Repas/jour : {prof['meals_per_day']}")
    if st.button("✏️ Modifier le profil"):
        st.session_state.edit_prof = True

    if st.session_state.get("edit_prof",False):
        with st.form("frm_prof", clear_on_submit=True):
            h = st.selectbox("Type de foyer", ["Solo","Couple","Famille"],
                             index=["Solo","Couple","Famille"].index(prof["household"]))
            c = st.number_input("Enfants", prof["children"], 0, 10)
            t = st.number_input("Ados", prof["teens"], 0, 10)
            a = st.number_input("Adultes", prof["adults"], 1, 20)
            m = st.slider("Repas par jour", 1, 6, prof["meals_per_day"])
            ok=st.form_submit_button("Valider")
        if ok:
            profiles_db[user] = {
                "household":h,"children":c,
                "teens":t,"adults":a,
                "meals_per_day":m
            }
            save_json(PROFILES_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_prof=False
            st.experimental_rerun()
