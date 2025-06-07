import streamlit as st
import json
from pathlib import Path

# ———————————————————————————
# Configuration
# ———————————————————————————
st.set_page_config(page_title="Batchist", layout="wide")

# Dossier persistant pour les JSON (recettes/extras/plans/profil)
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
RECIPES_FILE  = DATA_DIR / "recipes.json"
EXTRAS_FILE   = DATA_DIR / "extras.json"
PLANS_FILE    = DATA_DIR / "plans.json"
PROFILES_FILE = DATA_DIR / "profiles.json"

# Initialise les fichiers JSON vides
for f in [RECIPES_FILE, EXTRAS_FILE, PLANS_FILE, PROFILES_FILE]:
    if not f.exists():
        f.write_text("{}")

def load_json(path):
    return json.loads(path.read_text())

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

# ———————————————————————————
# Gestion en mémoire des utilisateurs
# ———————————————————————————
if "users" not in st.session_state:
    # Dict username → dict(password)
    st.session_state["users"] = {}

def register_user(username, password):
    """Retourne True si nouvel utilisateur créé."""
    users = st.session_state["users"]
    if username in users:
        return False
    users[username] = {"password": password}
    return True

def check_login(username, password):
    users = st.session_state["users"]
    return username in users and users[username]["password"] == password

def do_logout():
    for k in ("user",):
        if k in st.session_state: del st.session_state[k]
    st.experimental_rerun()

# ———————————————————————————
# Écran Connexion / Inscription
# ———————————————————————————
if "user" not in st.session_state:
    st.title("🔒 Connexion / Inscription")
    mode = st.radio("", ["Connexion", "Inscription"], horizontal=True)

    if mode == "Inscription":
        with st.form("form_reg"):
            nom = st.text_input("Nom d'utilisateur")
            mdp = st.text_input("Mot de passe", type="password")
            submit = st.form_submit_button("S'inscrire")
        if submit:
            if not nom or not mdp:
                st.error("Veuillez remplir les deux champs.")
            elif register_user(nom.strip(), mdp):
                st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
            else:
                st.error("Ce nom d'utilisateur existe déjà.")
        st.stop()

    # Mode Connexion
    with st.form("form_login"):
        nom = st.text_input("Nom d'utilisateur")
        mdp = st.text_input("Mot de passe", type="password")
        submit = st.form_submit_button("Se connecter")
    if submit:
        if check_login(nom.strip(), mdp):
            st.session_state.user = nom.strip()
            st.experimental_rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()

# ———————————————————————————
# Après connexion : menu principal
# ———————————————————————————
user = st.session_state.user
st.sidebar.write(f"👤 Connecté en tant que **{user}**")
menu = st.sidebar.radio(
    "Navigation",
    ["Accueil", "Mes recettes", "Extras", "Planificateur", "Liste de courses", "Conseils", "Profil", "Se déconnecter"]
)
if menu == "Se déconnecter":
    do_logout()

# ———————————————————————————
# Chargement / initialisation des données JSON
# ———————————————————————————
recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROFILES_FILE)

# Initialise structure utilisateur
for d in (recipes_db, extras_db, plans_db, profiles_db):
    d.setdefault(user, {})

# Pour recettes et extras on préfère une liste
if not isinstance(recipes_db[user], list):
    recipes_db[user] = []
if not isinstance(extras_db[user], list):
    extras_db[user] = []

# ———————————————————————————
# Pages
# ———————————————————————————

if menu == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur Batchist ! Sélectionnez une page à gauche.")

# — Mes recettes —
elif menu == "Mes recettes":
    st.title("📋 Mes recettes")

    # Formulaire d'ajout
    with st.expander("+ Ajouter une recette"):
        with st.form("add_recipe"):
            name  = st.text_input("Nom de la recette")
            instr = st.text_area("Instructions", height=100)
            img   = st.text_input("URL de l'image (placeholder OK)")

            # Dynamique : liste d'ingrédients
            if "ings" not in st.session_state:
                st.session_state.ings = [{"name":"", "qty":0.0, "unit":"g"}]
            cols = st.columns([4,1,1,1])
            cols[0].button("+ Ingrédient", on_click=lambda: st.session_state.ings.append({"name":"", "qty":0.0, "unit":"g"}))
            for i, ing in enumerate(st.session_state.ings):
                c0, c1, c2, c3 = st.columns([4,1,1,1])
                ing["name"] = c0.text_input(f"Ingrédient #{i+1}", value=ing["name"], key=f"name_{i}")
                ing["qty"]  = c1.number_input(f"Qté #{i+1}", value=ing["qty"], key=f"qty_{i}")
                ing["unit"] = c2.selectbox(f"Unité #{i+1}", ["g","kg","ml","l","pcs"], index=["g","kg","ml","l","pcs"].index(ing["unit"]), key=f"unit_{i}")
                if c3.button("🗑️", key=f"del_{i}"):
                    st.session_state.ings.pop(i)
                    st.experimental_rerun()

            sub = st.form_submit_button("Ajouter la recette")
        if sub:
            if not name.strip():
                st.error("Le nom de la recette est requis.")
            else:
                recipes_db[user].append({
                    "name": name.strip(),
                    "instr": instr,
                    "img": img,
                    "ings": st.session_state.ings.copy()
                })
                save_json(RECIPES_FILE, recipes_db)
                st.success("Recette ajoutée !")
                st.session_state.ings = [{"name":"", "qty":0.0, "unit":"g"}]
                st.experimental_rerun()

    st.write("---")

    # Affichage en deux colonnes
    cols = st.columns(2)
    for idx, rec in enumerate(recipes_db[user]):
        c = cols[idx % 2]
        if rec["img"]:
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        if c.button("Supprimer", key=f"delrec{idx}"):
            recipes_db[user].pop(idx)
            save_json(RECIPES_FILE, recipes_db)
            st.experimental_rerun()
        if c.button("Partager", key=f"sharerec{idx}"):
            st.info(f"Partage de « {rec['name']} »…")

# — Extras —
elif menu == "Extras":
    st.title("➕ Extras")
    with st.expander("+ Ajouter un extra"):
        with st.form("add_extra"):
            e0, e1, e2 = st.columns([4,1,1])
            nom = e0.text_input("Produit")
            qty = e1.number_input("Quantité")
            unit = e2.selectbox("Unité", ["g","kg","ml","l","pcs"])
            ok = st.form_submit_button("Ajouter")
        if ok and nom.strip():
            extras_db[user].append({"name":nom.strip(),"qty":qty,"unit":unit})
            save_json(EXTRAS_FILE, extras_db)
            st.success("Extra ajouté !")
            st.experimental_rerun()
    st.write("---")
    for i, ex in enumerate(extras_db[user]):
        c0, c1, c2, c3 = st.columns([4,1,1,1])
        c0.write(ex["name"])
        c1.write(ex["qty"])
        c2.write(ex["unit"])
        if c3.button("🗑️", key=f"delx{i}"):
            extras_db[user].pop(i)
            save_json(EXTRAS_FILE, extras_db)
            st.experimental_rerun()

# — Planificateur —
elif menu == "Planificateur":
    st.title("📅 Planificateur de la semaine")

    # Récupère profil (nb repas/jour)
    prof = profiles_db[user] or {}
    mpd = prof.get("meals_per_day", 3)

    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    cols = st.columns(7)
    for di, day in enumerate(days):
        with cols[di]:
            st.subheader(day)
            for m in range(mpd):
                key = f"{day}_{m}"
                choix = [""] + [r["name"] for r in recipes_db[user]]
                plans_db[user].setdefault(key, "")
                plans_db[user][key] = st.selectbox(f"Repas {m+1}", choix, index=choix.index(plans_db[user][key]), key=key)

    if st.button("Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")

# — Liste de courses —
elif menu == "Liste de courses":
    st.title("🛒 Liste de courses")
    plan = plans_db[user]
    shop = {}
    # Recettes planifiées
    for key, recname in plan.items():
        if not recname: continue
        rec = next((r for r in recipes_db[user] if r["name"]==recname), None)
        if rec:
            for ing in rec["ings"]:
                k = (ing["name"], ing["unit"])
                shop[k] = shop.get(k, 0) + ing["qty"]
    # Extras
    for ex in extras_db[user]:
        k = (ex["name"], ex["unit"])
        shop[k] = shop.get(k, 0) + ex["qty"]

    for (n,u),q in shop.items():
        st.write(f"- {n}: {q} {u}")

    # CSV
    csv = "Produit,Quantité,Unité\n" + "\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("Télécharger CSV", csv, file_name="liste_courses.csv")

# — Conseils —
elif menu == "Conseils":
    st.title("💡 Conseils & Astuces")
    astuces = [
        "Planifiez vos courses à l'avance.",
        "Variez les couleurs dans vos assiettes.",
        "Préparez des portions à congeler.",
        "Utilisez des herbes fraîches pour relever vos plats."
    ]
    for a in astuces:
        st.info(a)

# — Profil —
elif menu == "Profil":
    st.title("👤 Profil")

    prof = profiles_db[user] or {
        "household":"Solo","children":0,"teens":0,"adults":1,"meals_per_day":3
    }
    st.write(f"- Foyer : {prof['household']}")
    st.write(f"- Enfants : {prof['children']}")
    st.write(f"- Ados : {prof['teens']}")
    st.write(f"- Adultes : {prof['adults']}")
    st.write(f"- Repas/jour : {prof['meals_per_day']}")

    if st.button("Modifier le profil"):
        st.session_state["edit_prof"] = True

    if st.session_state.get("edit_prof", False):
        with st.form("form_prof"):
            h  = st.selectbox("Type de foyer", ["Solo","Couple","Famille"], index=["Solo","Couple","Famille"].index(prof["household"]))
            c  = st.number_input("Enfants", prof["children"], 0, 10)
            t  = st.number_input("Adolescents", prof["teens"], 0, 10)
            a  = st.number_input("Adultes", prof["adults"], 1, 10)
            m  = st.slider("Repas par jour", 1, 6, prof["meals_per_day"])
            ok = st.form_submit_button("Valider")
        if ok:
            profiles_db[user] = {
                "household": h,
                "children":  c,
                "teens":     t,
                "adults":    a,
                "meals_per_day": m
            }
            save_json(PROFILES_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state["edit_prof"] = False
            st.experimental_rerun()
