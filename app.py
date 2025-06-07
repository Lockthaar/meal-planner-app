import streamlit as st
import json
from pathlib import Path

# ————————————————————————————————————————————————
#   Fonction robuste pour “re-run” sans planter
# ————————————————————————————————————————————————
def do_rerun():
    try:
        st.experimental_rerun()
    except Exception:
        st.stop()

# ————————————————————————————————————————————————
#   Configuration de la page
# ————————————————————————————————————————————————
st.set_page_config(page_title="Batchist", layout="wide")

# ————————————————————————————————————————————————
#   Dossier de données + création des JSON vides si besoin
# ————————————————————————————————————————————————
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
for fname in ("recipes.json", "extras.json", "plans.json", "profiles.json"):
    fp = DATA_DIR / fname
    if not fp.exists():
        fp.write_text("{}")

def load_json(fp: Path):
    return json.loads(fp.read_text())

def save_json(fp: Path, data):
    fp.write_text(json.dumps(data, indent=2))

# ————————————————————————————————————————————————
#   Gestion simplifiée des utilisateurs (EN MÉMOIRE uniquement)
# ————————————————————————————————————————————————
if "users" not in st.session_state:
    st.session_state["users"] = {}

def register_user(u, p):
    if u in st.session_state["users"]:
        return False
    st.session_state["users"][u] = {"password": p}
    return True

def check_login(u, p):
    return u in st.session_state["users"] and st.session_state["users"][u]["password"] == p

def do_logout():
    del st.session_state.user
    do_rerun()

# ————————————————————————————————————————————————
#   Écran Connexion / Inscription
# ————————————————————————————————————————————————
if "user" not in st.session_state:
    st.title("🔒 Connexion / Inscription")
    choice = st.radio("", ["Connexion", "Inscription"], horizontal=True)

    if choice == "Inscription":
        with st.form("form_reg", clear_on_submit=True):
            new_u = st.text_input("Nom d'utilisateur")
            new_p = st.text_input("Mot de passe", type="password")
            sub = st.form_submit_button("S'inscrire")
        if sub:
            if not new_u or not new_p:
                st.error("Tous les champs sont requis.")
            elif register_user(new_u.strip(), new_p):
                st.success("Inscription réussie ! Connectez-vous.")
            else:
                st.error("Nom d'utilisateur déjà pris.")
        st.stop()

    # Connexion
    with st.form("form_log", clear_on_submit=False):
        u = st.text_input("Nom d'utilisateur")
        p = st.text_input("Mot de passe", type="password")
        sub = st.form_submit_button("Se connecter")
    if sub:
        if check_login(u.strip(), p):
            st.session_state.user = u.strip()
            do_rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()

# ————————————————————————————————————————————————
#   Sidebar & Navigation
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
#   Chargement des bases JSON
# ————————————————————————————————————————————————
RECIPES_FILE  = DATA_DIR / "recipes.json"
EXTRAS_FILE   = DATA_DIR / "extras.json"
PLANS_FILE    = DATA_DIR / "plans.json"
PROFILES_FILE = DATA_DIR / "profiles.json"

recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROFILES_FILE)

# S’assurer que chaque user a ses clés
for db in (recipes_db, extras_db, plans_db, profiles_db):
    db.setdefault(user, {})

# Convertir en liste si vide
recipes_db[user] = recipes_db[user] or []
extras_db[user]  = extras_db[user]  or []

# ————————————————————————————————————————————————
#   Accueil
# ————————————————————————————————————————————————
if page == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur **Batchist**, votre batch cooking simplifié ! Sélectionnez une section.")

# ————————————————————————————————————————————————
#   Mes recettes
# ————————————————————————————————————————————————
elif page == "Mes recettes":
    st.title("📋 Mes recettes")

    # INITIALISATION DU STATE
    st.session_state.setdefault("show_form", False)
    st.session_state.setdefault("ings", [{"name":"", "qty":0.0, "unit":"g"}])

    # BOUTON POUR AFFICHER/CACHER LE FORMULAIRE
    if st.button("+ Ajouter une recette"):
        st.session_state.show_form = not st.session_state.show_form

    # SI ON A DEMANDÉ LE FORMULAIRE :
    if st.session_state.show_form:

        # ON PLACE TOUT DANS UN EXPANDER
        with st.expander("📝 Nouveau formulaire de recette", expanded=True):

            # CHAMPS PRINCIPAUX
            name  = st.text_input("Nom de la recette", key="rec_name")
            instr = st.text_area("Instructions", height=100, key="rec_instr")
            img   = st.text_input("URL de l'image (placeholder OK)", key="rec_img")

            st.markdown("**Ingrédients**")

            # BOUTON + ING
            if st.button("➕ Ajouter un ingrédient", key="add_ing"):
                st.session_state.ings.append({"name":"", "qty":0.0, "unit":"g"})
                do_rerun()

            # AFFICHAGE DES LIGNES D'INGRÉDIENTS
            for i, ing in enumerate(st.session_state.ings):
                c0, c1, c2, c3 = st.columns([4,1,1,1])
                ing["name"] = c0.text_input(f"Ingrédient #{i+1}", value=ing["name"], key=f"name_{i}")
                ing["qty"]  = c1.number_input(f"", value=ing["qty"], format="%.2f", key=f"qty_{i}")
                ing["unit"] = c2.selectbox("", ["g","kg","ml","l","pcs"],
                                          index=["g","kg","ml","l","pcs"].index(ing["unit"]),
                                          key=f"unit_{i}")
                if c3.button("🗑️", key=f"del_{i}"):
                    st.session_state.ings.pop(i)
                    do_rerun()

            st.write("---")

            # BOUTON FINAL POUR AJOUTER LA RECETTE
            if st.button("✅ Ajouter la recette", key="submit_recipe"):
                if not name.strip():
                    st.error("Le nom de la recette est requis.")
                else:
                    # Sauvegarde
                    recipes_db[user].append({
                        "name": name.strip(),
                        "instr": instr,
                        "img" : img,
                        "ings": st.session_state.ings.copy()
                    })
                    save_json(RECIPES_FILE, recipes_db)
                    st.success("Recette ajoutée !")
                    # RESET
                    st.session_state.ings = [{"name":"", "qty":0.0, "unit":"g"}]
                    st.session_state.show_form = False
                    do_rerun()

    st.write("---")

    # AFFICHAGE DES RECETTES EXISTANTES
    cols = st.columns(2)
    for idx, rec in enumerate(recipes_db[user]):
        c = cols[idx % 2]
        if rec["img"]:
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        if c.button("🗑️ Supprimer", key=f"delrec{idx}"):
            recipes_db[user].pop(idx)
            save_json(RECIPES_FILE, recipes_db)
            do_rerun()
        if c.button("🔗 Partager", key=f"sharerec{idx}"):
            st.info(f"Partage de « {rec['name']} »…")

# ————————————————————————————————————————————————
#   Extras
# ————————————————————————————————————————————————
elif page == "Extras":
    st.title("➕ Extras")
    with st.expander("+ Ajouter un extra"):
        nom  = st.text_input("Produit", key="extra_name")
        qty  = st.number_input("Quantité", key="extra_qty")
        unit = st.selectbox("Unité", ["g","kg","ml","l","pcs"], key="extra_unit")
        if st.button("✅ Ajouter", key="add_extra"):
            if nom.strip():
                extras_db[user].append({"name":nom.strip(),"qty":qty,"unit":unit})
                save_json(EXTRAS_FILE, extras_db)
                st.success("Extra ajouté !")
                do_rerun()

    st.write("---")
    for i, ex in enumerate(extras_db[user]):
        c0,c1,c2,c3 = st.columns([4,1,1,1])
        c0.write(ex["name"])
        c1.write(ex["qty"])
        c2.write(ex["unit"])
        if c3.button("🗑️", key=f"delx{i}"):
            extras_db[user].pop(i)
            save_json(EXTRAS_FILE, extras_db)
            do_rerun()

# ————————————————————————————————————————————————
#   Planificateur
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
                key = f"{day}_{m}"
                choix = [""] + [r["name"] for r in recipes_db[user]]
                plans_db[user].setdefault(key, "")
                plans_db[user][key] = st.selectbox("", choix,
                                                   index=choix.index(plans_db[user][key]),
                                                   key=key)
    if st.button("💾 Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")

# ————————————————————————————————————————————————
#   Liste de courses
# ————————————————————————————————————————————————
elif page == "Liste de courses":
    st.title("🛒 Liste de courses")
    shop = {}
    # Ingrédients du plan
    for key, recname in plans_db[user].items():
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

    csv = "Produit,Quantité,Unité\n" + "\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("📥 Télécharger CSV", csv, file_name="liste_courses.csv")

# ————————————————————————————————————————————————
#   Conseils & Astuces
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
#   Profil
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
        h = st.selectbox("Type de foyer", ["Solo","Couple","Famille"],
                         index=["Solo","Couple","Famille"].index(prof["household"]))
        c = st.number_input("Enfants", prof["children"], 0, 10)
        t = st.number_input("Ados", prof["teens"], 0, 10)
        a = st.number_input("Adultes", prof["adults"], 1, 20)
        m = st.slider("Repas par jour", 1, 6, prof["meals_per_day"])
        if st.button("✅ Valider le profil"):
            profiles_db[user] = {
                "household":h, "children":c,
                "teens":t, "adults":a,
                "meals_per_day":m
            }
            save_json(PROFILES_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_prof = False
            do_rerun()
