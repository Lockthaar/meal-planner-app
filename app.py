import streamlit as st
import json
from pathlib import Path

# ————————————————————————————
# Configuration page
# ————————————————————————————
st.set_page_config(page_title="Batchist", layout="wide")

# ————————————————————————————
# Répertoire de données + fichiers JSON
# ————————————————————————————
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
for fname in ("users.json", "recipes.json", "extras.json", "plans.json", "profiles.json"):
    fp = DATA_DIR / fname
    if not fp.exists():
        fp.write_text("{}")

def load_json(fp: Path):
    return json.loads(fp.read_text() or "{}")

def save_json(fp: Path, data):
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False))

USERS_FILE    = DATA_DIR / "users.json"
RECIPES_FILE  = DATA_DIR / "recipes.json"
EXTRAS_FILE   = DATA_DIR / "extras.json"
PLANS_FILE    = DATA_DIR / "plans.json"
PROFILES_FILE = DATA_DIR / "profiles.json"

users_db    = load_json(USERS_FILE)
recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROFILES_FILE)

# ————————————————————————————
# Gestion utilisateurs persistée
# ————————————————————————————
def register_user(u, p):
    if u in users_db:
        return False
    users_db[u] = {"password": p}
    save_json(USERS_FILE, users_db)
    return True

def check_login(u, p):
    return u in users_db and users_db[u]["password"] == p

def logout():
    if "user" in st.session_state:
        del st.session_state.user
    st.experimental_rerun()

# ————————————————————————————
# Login / Signup
# ————————————————————————————
if "user" not in st.session_state:
    st.title("🔒 Connexion / Inscription")
    choice = st.radio("", ["Connexion", "Inscription"], horizontal=True)
    if choice == "Inscription":
        with st.form("form_reg", clear_on_submit=True):
            new_u = st.text_input("Nom d'utilisateur")
            new_p = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("S'inscrire")
        if ok:
            if not new_u or not new_p:
                st.error("Tous les champs sont requis.")
            elif register_user(new_u.strip(), new_p):
                st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
            else:
                st.error("Nom d'utilisateur déjà pris.")
        st.stop()
    else:
        with st.form("form_log", clear_on_submit=True):
            u = st.text_input("Nom d'utilisateur")
            p = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("Se connecter")
        if ok:
            if check_login(u.strip(), p):
                st.session_state.user = u.strip()
                st.experimental_rerun()
            else:
                st.error("Identifiants incorrects.")
        st.stop()

# ————————————————————————————
# Préparation des bases de l’utilisateur
# ————————————————————————————
user = st.session_state.user
for db in (recipes_db, extras_db, plans_db, profiles_db):
    db.setdefault(user, [] if db is recipes_db or db is extras_db else {})

# ————————————————————————————
# Barre latérale
# ————————————————————————————
st.sidebar.markdown(f"👤 **Connecté en tant que {user}**")
page = st.sidebar.radio("Navigation", [
    "Accueil", "Mes recettes", "Extras",
    "Planificateur", "Liste de courses",
    "Conseils", "Profil", "Se déconnecter"
])
if page == "Se déconnecter":
    logout()

# ————————————————————————————
# Accueil
# ————————————————————————————
if page == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur **Batchist**, votre batch cooking simplifié !")

# ————————————————————————————
# Mes recettes
# ————————————————————————————
elif page == "Mes recettes":
    st.title("📋 Mes recettes")
    tmp = st.session_state.setdefault("tmp_ings", [{"name":"", "qty":0.0, "unit":"g"}])
    show = st.session_state.setdefault("show_rec_form", False)
    edit_idx = st.session_state.get("edit_idx", None)

    # + Ajouter une recette
    if st.button("+ Ajouter une recette"):
        st.session_state.show_rec_form = not show
        st.session_state.edit_idx = None

    # Bouton + Ingrédient (hors form)
    if show and edit_idx is None:
        if st.button("+ Ingrédient"):
            tmp.append({"name":"", "qty":0.0, "unit":"g"})

    # Formulaire d'ajout ou d'édition
    if show:
        mode = "Modifier" if edit_idx is not None else "Nouvelle"
        st.subheader(f"{mode} recette")
        with st.form("recipe_form", clear_on_submit=False):
            name = st.text_input("Nom de la recette",
                                 value= recipes_db[user][edit_idx]["name"] if edit_idx is not None else "")
            instr = st.text_area("Instructions",
                                 value= recipes_db[user][edit_idx]["instr"] if edit_idx is not None else "",
                                 height=100)
            img = st.text_input("URL de l'image (placeholder OK)",
                                value= recipes_db[user][edit_idx]["img"] if edit_idx is not None else "")
            # Ingrédients dynamiques
            cols = st.columns([3,1,1,1])
            for i, ing in enumerate(tmp):
                c0,c1,c2,c3 = cols
                ing["name"] = c0.text_input(f"Ingrédient #{i+1}", value=ing["name"], key=f"n_{i}")
                ing["qty"]  = c1.number_input("", value=ing["qty"], key=f"q_{i}")
                ing["unit"] = c2.selectbox("", ["g","kg","ml","l","pcs"],
                                          index=["g","kg","ml","l","pcs"].index(ing["unit"]), key=f"u_{i}")
                if c3.button("🗑️", key=f"d_{i}"):
                    tmp.pop(i)
                    st.experimental_rerun()

            submit = st.form_submit_button("Enregistrer")

        if submit:
            if not name.strip():
                st.error("Le nom est requis.")
            else:
                entry = {"name":name.strip(), "instr":instr, "img":img, "ings":tmp.copy()}
                if edit_idx is None:
                    recipes_db[user].append(entry)
                    st.success("Recette ajoutée !")
                else:
                    recipes_db[user][edit_idx] = entry
                    st.success("Recette mise à jour !")
                    st.session_state.edit_idx = None
                save_json(RECIPES_FILE, recipes_db)
                st.session_state.tmp_ings = [{"name":"", "qty":0.0, "unit":"g"}]
                st.session_state.show_rec_form = False
                st.experimental_rerun()

    st.markdown("---")
    # Affichage des cartes
    cols = st.columns(2)
    for idx, rec in enumerate(recipes_db[user]):
        c = cols[idx%2]
        if rec["img"]:
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        btn1, btn2, btn3 = c.columns([1,1,1])
        if btn1.button("✏️ Modifier", key=f"m_{idx}"):
            st.session_state.show_rec_form = True
            st.session_state.edit_idx = idx
            st.session_state.tmp_ings = rec["ings"].copy()
            st.experimental_rerun()
        if btn2.button("🗑️ Supprimer", key=f"x_{idx}"):
            recipes_db[user].pop(idx)
            save_json(RECIPES_FILE, recipes_db)
            st.experimental_rerun()
        if btn3.button("🔗 Partager", key=f"s_{idx}"):
            st.info(f"Partager « {rec['name']} »…")

# ————————————————————————————
# Extras
# ————————————————————————————
elif page == "Extras":
    st.title("➕ Extras")
    with st.expander("+ Ajouter un extra"):
        with st.form("extra_form", clear_on_submit=True):
            nom  = st.text_input("Produit")
            qty  = st.number_input("Quantité", min_value=0.0)
            unit = st.selectbox("Unité", ["g","kg","ml","l","pcs"])
            ok   = st.form_submit_button("Ajouter")
        if ok and nom.strip():
            extras_db[user].append({"name":nom.strip(),"qty":qty,"unit":unit})
            save_json(EXTRAS_FILE, extras_db)
            st.success("Extra ajouté !")
            st.experimental_rerun()
    st.markdown("---")
    for i, ex in enumerate(extras_db[user]):
        c0,c1,c2,c3 = st.columns([4,1,1,1])
        c0.write(ex["name"]); c1.write(ex["qty"]); c2.write(ex["unit"])
        if c3.button("🗑️", key=f"del_ex{i}"):
            extras_db[user].pop(i)
            save_json(EXTRAS_FILE, extras_db)
            st.experimental_rerun()

# ————————————————————————————
# Planificateur
# ————————————————————————————
elif page == "Planificateur":
    st.title("📅 Planificateur de la semaine")
    prof = profiles_db[user] or {}
    mpd  = prof.get("meals_per_day", 3)
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    cols = st.columns(7)
    for d, day in enumerate(days):
        with cols[d]:
            st.subheader(day)
            for m in range(mpd):
                key = f"{day}_{m}"
                choix = [""] + [r["name"] for r in recipes_db[user]]
                val = plans_db[user].get(key, "")
                plans_db[user][key] = st.selectbox("", choix, index=choix.index(val), key=key)
    if st.button("Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")

# ————————————————————————————
# Liste de courses
# ————————————————————————————
elif page == "Liste de courses":
    st.title("🛒 Liste de courses")
    shop = {}
    for key, recname in plans_db[user].items():
        if not recname: continue
        rec = next((r for r in recipes_db[user] if r["name"]==recname), None)
        if rec:
            for ing in rec["ings"]:
                k = (ing["name"], ing["unit"])
                shop[k] = shop.get(k, 0) + ing["qty"]
    for ex in extras_db[user]:
        k = (ex["name"], ex["unit"])
        shop[k] = shop.get(k, 0) + ex["qty"]
    for (n,u),q in shop.items():
        st.write(f"- {n}: {q} {u}")
    csv = "Produit,Quantité,Unité\n" + "\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("📥 Télécharger CSV", csv, file_name="liste_courses.csv")

# ————————————————————————————
# Conseils & Astuces
# ————————————————————————————
elif page == "Conseils":
    st.title("💡 Conseils & Astuces")
    for tip in [
        "Planifiez vos repas à l'avance.",
        "Variez les couleurs dans vos assiettes.",
        "Préparez des portions à congeler.",
        "Utilisez des herbes fraîches pour relever vos plats."
    ]:
        st.info(tip)

# ————————————————————————————
# Profil
# ————————————————————————————
elif page == "Profil":
    st.title("👤 Profil")
    prof = profiles_db[user] or {
        "household":"Solo","children":0,"teens":0,"adults":1,"meals_per_day":3
    }
    st.write(f"- Foyer      : {prof['household']}")
    st.write(f"- Enfants    : {prof['children']}")
    st.write(f"- Ados       : {prof['teens']}")
    st.write(f"- Adultes    : {prof['adults']}")
    st.write(f"- Repas/jour : {prof['meals_per_day']}")
    if st.button("✏️ Modifier le profil"):
        st.session_state.edit_prof = True
    if st.session_state.get("edit_prof", False):
        with st.form("form_prof", clear_on_submit=True):
            h = st.selectbox("Type de foyer", ["Solo","Couple","Famille"],
                             index=["Solo","Couple","Famille"].index(prof["household"]))
            c = st.number_input("Enfants", prof["children"], 0, 10)
            t = st.number_input("Ados", prof["teens"], 0, 10)
            a = st.number_input("Adultes", prof["adults"], 1, 20)
            m = st.slider("Repas par jour", 1, 6, prof["meals_per_day"])
            ok = st.form_submit_button("Valider")
        if ok:
            profiles_db[user] = {"household":h, "children":c,
                                 "teens":t, "adults":a,
                                 "meals_per_day":m}
            save_json(PROFILES_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_prof = False
            st.experimental_rerun()
