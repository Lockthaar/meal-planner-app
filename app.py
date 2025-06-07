import streamlit as st
import json
from pathlib import Path

# ———————————————————————————
# Helpers pour stocker en JSON
# ———————————————————————————
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))

USERS_FILE    = DATA_DIR / "users.json"
RECIPES_FILE  = DATA_DIR / "recipes.json"
EXTRAS_FILE   = DATA_DIR / "extras.json"
PLANS_FILE    = DATA_DIR / "plans.json"
PROFILES_FILE = DATA_DIR / "profiles.json"

# Crée les fichiers vides s’ils n’existent pas
for file in [USERS_FILE, RECIPES_FILE, EXTRAS_FILE, PLANS_FILE, PROFILES_FILE]:
    if not file.exists():
        file.write_text("{}")

def load_json(path):
    return json.loads(path.read_text())

def save_json(path, data):
    path.write_text(json.dumps(data, indent=2))

# ———————————————————————————
# Authentification
# ———————————————————————————
def register(username, password):
    users = load_json(USERS_FILE)
    if username in users:
        return False
    users[username] = {"password": password}
    save_json(USERS_FILE, users)
    return True

def login(username, password):
    users = load_json(USERS_FILE)
    return username in users and users[username]["password"] == password

def logout():
    for key in ["user", "edit_profile", "ing"]:
        st.session_state.pop(key, None)
    st.experimental_rerun()

# ———————————————————————————
# Setup de la page
# ———————————————————————————
st.set_page_config(page_title="Batchist", layout="wide")

# ———————————————————————————
# Écran Inscription / Connexion
# ———————————————————————————
if "user" not in st.session_state:
    st.title("🔒 Connexion / Inscription")
    mode = st.radio("", ["Connexion", "Inscription"], horizontal=True)

    if mode == "Inscription":
        with st.form("reg"):
            user = st.text_input("Nom d'utilisateur")
            pwd  = st.text_input("Mot de passe", type="password")
            ok   = st.form_submit_button("S'inscrire")
        if ok:
            if register(user, pwd):
                st.success("Compte créé ! Vous pouvez vous connecter.")
            else:
                st.error("Nom d'utilisateur déjà pris.")

    else:  # Connexion
        with st.form("login"):
            user = st.text_input("Nom d'utilisateur")
            pwd  = st.text_input("Mot de passe", type="password")
            ok   = st.form_submit_button("Se connecter")
        if ok:
            if login(user, pwd):
                st.session_state.user = user
                st.experimental_rerun()
            else:
                st.error("Identifiants incorrects.")
    st.stop()

# ———————————————————————————
# Après connexion : menu horizontal
# ———————————————————————————
st.markdown(f"### 🎉 Bienvenue, **{st.session_state.user}** !")
pages = [
    "Accueil",
    "Mes recettes",
    "Extras",
    "Planificateur",
    "Liste de courses",
    "Conseils",
    "Profil",
    "Se déconnecter"
]
choice = st.radio("", pages, horizontal=True)

if choice == "Se déconnecter":
    logout()

# ———————————————————————————
# Chargement des données utilisateur
# ———————————————————————————
user = st.session_state.user
recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROFILES_FILE)

# Initialise si vide
recipes_db .setdefault(user, [])
extras_db  .setdefault(user, [])
plans_db   .setdefault(user, {})
profiles_db.setdefault(user, {})

# ———————————————————————————
# Pages
# ———————————————————————————

if choice == "Accueil":
    st.title("🏠 Accueil")
    st.write("📊 Votre tableau de bord arrivera ici.")

elif choice == "Mes recettes":
    st.title("📋 Mes recettes")

    # Formulaire d'ajout
    with st.expander("+ Ajouter une recette", expanded=False):
        with st.form("add_recipe"):
            name  = st.text_input("Nom de la recette")
            instr = st.text_area("Instructions", height=120)
            img   = st.text_input("URL image (placeholder OK)")
            # Liste dynamique d'ingrédients
            if "ing" not in st.session_state:
                st.session_state.ing = [{"name":"", "qty":0.0, "unit":"g"}]
            cols = st.columns([4,1,1,1])
            cols[0].button("+ Ingrédient", on_click=lambda: st.session_state.ing.append({"name":"", "qty":0.0, "unit":"g"}))
            for i, ing in enumerate(st.session_state.ing):
                c0, c1, c2, c3 = st.columns([4,1,1,1])
                ing["name"] = c0.text_input(f"Ingrédient #{i+1}", value=ing["name"], key=f"name{i}")
                ing["qty"]  = c1.number_input(f"Qté #{i+1}", value=ing["qty"], key=f"qty{i}")
                ing["unit"] = c2.selectbox(f"Unité #{i+1}", ["g","kg","ml","l","pcs"], index=["g","kg","ml","l","pcs"].index(ing["unit"]), key=f"unit{i}")
                if c3.button("🗑️", key=f"del{i}"):
                    st.session_state.ing.pop(i)
                    st.experimental_rerun()
            ok = st.form_submit_button("Ajouter la recette")
        if ok and name:
            recipes_db[user].append({
                "name": name,
                "instr": instr,
                "img": img,
                "ings": st.session_state.ing.copy()
            })
            save_json(RECIPES_FILE, recipes_db)
            st.success("Recette ajoutée !")
            st.session_state.ing = [{"name":"", "qty":0.0, "unit":"g"}]
            st.experimental_rerun()

    st.write("---")

    # Affichage des recettes en 2 colonnes
    cols = st.columns(2)
    for i, rec in enumerate(recipes_db[user]):
        c = cols[i % 2]
        if rec["img"]:
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        if c.button("Supprimer", key=f"delrec{i}"):
            recipes_db[user].pop(i)
            save_json(RECIPES_FILE, recipes_db)
            st.experimental_rerun()
        if c.button("Partager", key=f"share{i}"):
            st.info(f"Partage de « {rec['name']} » sur les réseaux...")

elif choice == "Extras":
    st.title("➕ Extras")
    with st.expander("+ Ajouter un extra", expanded=False):
        with st.form("add_extra"):
            e0, e1, e2 = st.columns([4,1,1])
            name = e0.text_input("Produit")
            qty  = e1.number_input("Qté")
            unit = e2.selectbox("Unité", ["g","kg","ml","l","pcs"])
            ok   = st.form_submit_button("Ajouter")
        if ok and name:
            extras_db[user].append({"name":name,"qty":qty,"unit":unit})
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

elif choice == "Planificateur":
    st.title("📅 Planificateur de la semaine")
    prof = profiles_db[user] or {"meals_per_day": 3}
    mpd = prof["meals_per_day"]
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    cols = st.columns(7)
    for idx, day in enumerate(days):
        with cols[idx]:
            st.subheader(day)
            for m in range(mpd):
                key = f"{day}_{m}"
                opts = [""] + [r["name"] for r in recipes_db[user]]
                plans_db[user][key] = st.selectbox(f"Repas {m+1}", opts, key=key)
    if st.button("Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")

elif choice == "Liste de courses":
    st.title("🛒 Liste de courses")
    plan = plans_db[user]
    shop = {}
    # ingrédients des recettes du plan
    for key, recname in plan.items():
        if not recname: continue
        rec = next((r for r in recipes_db[user] if r["name"]==recname), None)
        if rec:
            for ing in rec["ings"]:
                k = (ing["name"], ing["unit"])
                shop[k] = shop.get(k, 0) + ing["qty"]
    # extras
    for ex in extras_db[user]:
        k = (ex["name"], ex["unit"])
        shop[k] = shop.get(k, 0) + ex["qty"]
    for (n,u),q in shop.items():
        st.write(f"- {n}: {q} {u}")
    # CSV
    csv = "Produit,Qté,Unité\\n" + "\\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("Télécharger CSV", data=csv, file_name="courses.csv")

elif choice == "Conseils":
    st.title("💡 Conseils & Astuces")
    tips = [
        "Planifiez vos repas le week-end pour gagner du temps.",
        "Variez les protéines (viande, poisson, végétal).",
        "Congelez une partie pour plus tard.",
        "Ajoutez herbes & épices pour relever vos plats."
    ]
    for t in tips:
        st.info(t)

elif choice == "Profil":
    st.title("👤 Profil")
    prof = profiles_db[user] or {"household":"Solo","children":0,"teens":0,"adults":1,"meals_per_day":3}
    st.write(f"- Foyer : {prof['household']}")
    st.write(f"- Enfants : {prof['children']}")
    st.write(f"- Ados : {prof['teens']}")
    st.write(f"- Adultes : {prof['adults']}")
    st.write(f"- Repas/jour : {prof['meals_per_day']}")
    if st.button("Modifier profil"):
        st.session_state.edit_profile = True
    if st.session_state.get("edit_profile", False):
        with st.form("profile_form"):
            h  = st.selectbox("Type de foyer", ["Solo","Couple","Famille"], index=["Solo","Couple","Famille"].index(prof["household"]))
            ch = st.number_input("Enfants", prof["children"], 0, 10)
            te = st.number_input("Adolescents", prof["teens"], 0, 10)
            ad = st.number_input("Adultes", prof["adults"], 1, 10)
            mp = st.slider("Repas par jour", 1, 6, prof["meals_per_day"])
            ok = st.form_submit_button("Valider")
        if ok:
            profiles_db[user] = {"household":h,"children":ch,"teens":te,"adults":ad,"meals_per_day":mp}
            save_json(PROFILES_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_profile = False
            st.experimental_rerun()
