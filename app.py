import streamlit as st
import json
from pathlib import Path

# ————————————————————————————————————————————————
#   Wrapper “re-run” robuste
# ————————————————————————————————————————————————
def do_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        pass

# ————————————————————————————————————————————————
#   Configuration de la page
# ————————————————————————————————————————————————
st.set_page_config(
    page_title="Batchist — Batch cooking simplifié",
    layout="wide",
)

# ————————————————————————————————————————————————
#   Bannière en haut
# ————————————————————————————————————————————————
st.markdown(
    """
    <div style="display:flex;align-items:center;gap:10px">
      <h1>🍽️ Batchist — Batch cooking simplifié</h1>
    </div>
    <hr>
    """,
    unsafe_allow_html=True,
)

# ————————————————————————————————————————————————
#   Répertoire de données & JSON
# ————————————————————————————————————————————————
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE   = DATA_DIR / "users.json"
RECIPES_FILE = DATA_DIR / "recipes.json"
EXTRAS_FILE  = DATA_DIR / "extras.json"
PLANS_FILE   = DATA_DIR / "plans.json"
PROF_FILE    = DATA_DIR / "profiles.json"

for fp in (USERS_FILE, RECIPES_FILE, EXTRAS_FILE, PLANS_FILE, PROF_FILE):
    if not fp.exists():
        fp.write_text("{}")

def load_json(fp: Path):
    return json.loads(fp.read_text())

def save_json(fp: Path, data):
    fp.write_text(json.dumps(data, indent=2))


# ————————————————————————————————————————————————
#   Gestion persistante des utilisateurs
# ————————————————————————————————————————————————
users_db = load_json(USERS_FILE)

def register_user(username, pwd):
    username = username.strip()
    if not username or not pwd or username in users_db:
        return False
    users_db[username] = {"password": pwd}
    save_json(USERS_FILE, users_db)
    return True

def check_login(username, pwd):
    username = username.strip()
    return username in users_db and users_db[username]["password"] == pwd

def do_logout():
    if "user" in st.session_state:
        del st.session_state.user
    do_rerun()


# ————————————————————————————————————————————————
#   Écran Connexion / Inscription
# ————————————————————————————————————————————————
if "user" not in st.session_state:
    choice = st.radio("", ["Connexion", "Inscription"], horizontal=True)

    if choice == "Inscription":
        st.subheader("📝 Inscription")
        with st.form("reg", clear_on_submit=True):
            new_u = st.text_input("Nom d'utilisateur")
            new_p = st.text_input("Mot de passe", type="password")
            ok   = st.form_submit_button("S'inscrire")
        if ok:
            if register_user(new_u, new_p):
                st.success("Inscription réussie ! Connectez-vous.")
            else:
                st.error("Nom indisponible ou champs vides.")
        st.stop()

    st.subheader("🔐 Connexion")
    with st.form("login", clear_on_submit=False):
        u = st.text_input("Nom d'utilisateur")
        p = st.text_input("Mot de passe", type="password")
        ok = st.form_submit_button("Se connecter")
    if ok:
        if check_login(u, p):
            st.session_state.user = u.strip()
            do_rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()


# ————————————————————————————————————————————————
#   Sidebar & navigation
# ————————————————————————————————————————————————
user = st.session_state.user
st.sidebar.markdown(f"👤 **Connecté en tant que {user}**")
page = st.sidebar.radio("Navigation", [
    "Accueil", "Mes recettes", "Extras",
    "Planificateur", "Liste de courses",
    "Conseils", "Profil", "Se déconnecter"
])
if page == "Se déconnecter":
    do_logout()


# ————————————————————————————————————————————————
#   Chargement des autres données
# ————————————————————————————————————————————————
recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROF_FILE)

for db in (recipes_db, extras_db, plans_db, profiles_db):
    default = [] if db in (recipes_db, extras_db) else {}
    db.setdefault(user, default)

recipes_db[user] = recipes_db[user] or []
extras_db[user]  = extras_db[user]  or []


# ————————————————————————————————————————————————
#   Page Accueil
# ————————————————————————————————————————————————
if page == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur **Batchist** ! Choisissez une section dans le menu.")


# ————————————————————————————————————————————————
#   Page Mes recettes (réécrite SANS st.form pour ingrédients)
# ————————————————————————————————————————————————
elif page == "Mes recettes":
    st.title("📋 Mes recettes")

    # Initialisation du form state
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
        st.session_state.ings      = [{"name":"", "qty":0.0, "unit":"g"}]
        st.session_state.tmp_name  = ""
        st.session_state.tmp_instr = ""
        st.session_state.tmp_img   = ""

    # Bouton pour afficher/masquer le formulaire
    if st.button("➕ Ajouter une recette"):
        st.session_state.show_form = not st.session_state.show_form

    if st.session_state.show_form:
        st.subheader("Nouvelle recette")
        # Champs de base
        st.session_state.tmp_name  = st.text_input(
            "Nom de la recette", value=st.session_state.tmp_name
        )
        st.session_state.tmp_instr = st.text_area(
            "Instructions", value=st.session_state.tmp_instr, height=100
        )
        st.session_state.tmp_img   = st.text_input(
            "URL de l'image (placeholder OK)", value=st.session_state.tmp_img
        )

        col1, col2 = st.columns(2)
        # ← Partie ingrédients
        with col1:
            if st.button("➕ Ingrédient"):
                st.session_state.ings.append({"name":"", "qty":0.0, "unit":"g"})
                do_rerun()

            for i, ing in enumerate(st.session_state.ings):
                c0, c1, c2, c3 = st.columns([3,1,1,1])
                ing["name"] = c0.text_input(
                    f"Ingrédient #{i+1}",
                    value=ing["name"],
                    key=f"name_{i}"
                )
                ing["qty"] = c1.number_input(
                    "", value=ing["qty"], key=f"qty_{i}"
                )
                ing["unit"] = c2.selectbox(
                    "", ["g","kg","ml","l","pcs"],
                    index=["g","kg","ml","l","pcs"].index(ing["unit"]),
                    key=f"unit_{i}"
                )
                if c3.button("🗑️", key=f"del_{i}"):
                    st.session_state.ings.pop(i)
                    do_rerun()

        # → Aperçu
        with col2:
            st.markdown("**Aperçu des ingrédients**")
            for ing in st.session_state.ings:
                st.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")

        # Bouton final pour sauvegarder
        if st.button("💾 Ajouter la recette"):
            if not st.session_state.tmp_name.strip():
                st.error("Le nom est requis.")
            else:
                recipes_db[user].append({
                    "name": st.session_state.tmp_name.strip(),
                    "instr": st.session_state.tmp_instr,
                    "img":   st.session_state.tmp_img,
                    "ings":  st.session_state.ings.copy()
                })
                save_json(RECIPES_FILE, recipes_db)
                st.success("Recette ajoutée !")
                # Réinitialisation
                st.session_state.ings      = [{"name":"", "qty":0.0, "unit":"g"}]
                st.session_state.tmp_name  = ""
                st.session_state.tmp_instr = ""
                st.session_state.tmp_img   = ""
                st.session_state.show_form = False
                do_rerun()

    st.write("---")
    # Affichage existant
    cols = st.columns(2)
    for idx, rec in enumerate(recipes_db[user]):
        c = cols[idx % 2]
        if rec.get("img"):
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        if c.button("🗑️ Supprimer", key=f"dr{idx}"):
            recipes_db[user].pop(idx)
            save_json(RECIPES_FILE, recipes_db)
            do_rerun()
        if c.button("🔗 Partager", key=f"sr{idx}"):
            st.info(f"Partage de « {rec['name']} »…")

# ————————————————————————————————————————————————
#   Page Extras
# ————————————————————————————————————————————————
elif page == "Extras":
    st.title("➕ Extras")
    with st.expander("➕ Ajouter un extra"):
        with st.form("add_extra", clear_on_submit=True):
            nom  = st.text_input("Produit")
            qty  = st.number_input("Quantité")
            unit = st.selectbox("Unité", ["g","kg","ml","l","pcs"])
            ok   = st.form_submit_button("Ajouter")
        if ok and nom.strip():
            extras_db[user].append({"name":nom.strip(),"qty":qty,"unit":unit})
            save_json(EXTRAS_FILE, extras_db)
            st.success("Extra ajouté !")
            do_rerun()

    st.write("---")
    for i, ex in enumerate(extras_db[user]):
        c0,c1,c2,c3 = st.columns([4,1,1,1])
        c0.write(ex["name"]); c1.write(ex["qty"]); c2.write(ex["unit"])
        if c3.button("🗑️", key=f"dx{i}"):
            extras_db[user].pop(i)
            save_json(EXTRAS_FILE, extras_db)
            do_rerun()


# ————————————————————————————————————————————————
#   Page Planificateur
# ————————————————————————————————————————————————
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
                key   = f"{day}_{m}"
                choix = [""] + [r["name"] for r in recipes_db[user]]
                plans_db[user].setdefault(key, "")
                plans_db[user][key] = st.selectbox("", choix,
                                                   index=choix.index(plans_db[user][key]),
                                                   key=key)
    if st.button("💾 Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")


# ————————————————————————————————————————————————
#   Page Liste de courses
# ————————————————————————————————————————————————
elif page == "Liste de courses":
    st.title("🛒 Liste de courses")
    shop = {}
    for recname in plans_db[user].values():
        if not recname: continue
        rec = next((r for r in recipes_db[user] if r["name"]==recname), None)
        if rec:
            for ing in rec["ings"]:
                k = (ing["name"], ing["unit"])
                shop[k] = shop.get(k,0) + ing["qty"]
    for ex in extras_db[user]:
        k = (ex["name"], ex["unit"])
        shop[k] = shop.get(k,0) + ex["qty"]

    for (n,u),q in shop.items():
        st.write(f"- {n}: {q} {u}")

    csv = "Produit,Quantité,Unité\n" + "\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("⬇️ Télécharger CSV", csv, file_name="liste_courses.csv")


# ————————————————————————————————————————————————
#   Page Conseils
# ————————————————————————————————————————————————
elif page == "Conseils":
    st.title("💡 Conseils & Astuces")
    for tip in [
        "Planifiez vos repas à l'avance.",
        "Variez les couleurs dans vos assiettes.",
        "Préparez des portions à congeler.",
        "Utilisez des herbes fraîches pour relever vos plats."
    ]:
        st.info(tip)


# ————————————————————————————————————————————————
#   Page Profil
# ————————————————————————————————————————————————
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
            ok= st.form_submit_button("Valider")
        if ok:
            profiles_db[user] = {
                "household":h,"children":c,
                "teens":t,    "adults":a,
                "meals_per_day":m
            }
            save_json(PROF_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_prof = False
            do_rerun()
