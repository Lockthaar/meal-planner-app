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
st.set_page_config(page_title="Batchist — Batch cooking simplifié", layout="wide")

# ————————————————————————————————————————————————
#   Dossier de données + création des JSON vides si besoin
# ————————————————————————————————————————————————
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
for fname in ("users.json", "recipes.json", "extras.json", "plans.json", "profiles.json"):
    fp = DATA_DIR / fname
    if not fp.exists():
        fp.write_text("{}")

USERS_FILE    = DATA_DIR / "users.json"
RECIPES_FILE  = DATA_DIR / "recipes.json"
EXTRAS_FILE   = DATA_DIR / "extras.json"
PLANS_FILE    = DATA_DIR / "plans.json"
PROFILES_FILE = DATA_DIR / "profiles.json"

def load_json(fp: Path):
    return json.loads(fp.read_text())

def save_json(fp: Path, data):
    fp.write_text(json.dumps(data, indent=2))

# ————————————————————————————————————————————————
#   Gestion des utilisateurs persistante (fichier users.json)
# ————————————————————————————————————————————————
users_db = load_json(USERS_FILE)

def register_user(u, p):
    u = u.strip()
    if not u or u in users_db:
        return False
    users_db[u] = {"password": p}
    save_json(USERS_FILE, users_db)
    return True

def check_login(u, p):
    u = u.strip()
    return u in users_db and users_db[u]["password"] == p

def do_logout():
    st.session_state.pop("user", None)
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
            elif register_user(new_u, new_p):
                st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
            else:
                st.error("Nom d'utilisateur déjà pris.")
        st.stop()

    # Connexion
    with st.form("form_log", clear_on_submit=False):
        u = st.text_input("Nom d'utilisateur")
        p = st.text_input("Mot de passe", type="password")
        sub = st.form_submit_button("Se connecter")
    if sub:
        if check_login(u, p):
            st.session_state.user = u.strip()
            do_rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()

# ————————————————————————————————————————————————
#   En-tête / Bannière
# ————————————————————————————————————————————————
st.markdown("## 🍽 Batchist — Batch cooking simplifié")

# ————————————————————————————————————————————————
#   Sidebar & Navigation
# ————————————————————————————————————————————————
user = st.session_state.user
st.sidebar.markdown(f"👤 **Connecté·e en tant que {user}**")
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
recipes_db  = load_json(RECIPES_FILE)
extras_db   = load_json(EXTRAS_FILE)
plans_db    = load_json(PLANS_FILE)
profiles_db = load_json(PROFILES_FILE)

# S’assurer que chaque user a ses clés
for db in (recipes_db, extras_db, plans_db, profiles_db):
    db.setdefault(user, {})

# Convertir en liste si vide
recipes_db[user]  = recipes_db[user]  or []
extras_db[user]   = extras_db[user]   or []
plans_db[user]    = plans_db[user]    or {}
profiles_db[user] = profiles_db[user] or {}

# ————————————————————————————————————————————————
#   Accueil
# ————————————————————————————————————————————————
if page == "Accueil":
    st.title("🏠 Accueil")
    st.write("Bienvenue sur **Batchist** ! Sélectionnez une section dans le menu latéral.")

# ————————————————————————————————————————————————
#   Mes recettes
# ————————————————————————————————————————————————
elif page == "Mes recettes":
    st.title("📋 Mes recettes")

    # ** AFFICHAGE CARTE DE MODIFICATION **
    if st.session_state.get("edit_idx", None) is not None:
        idx = st.session_state.edit_idx
        rec = recipes_db[user][idx]
        st.subheader(f"✏️ Modifier « {rec['name']} »")

        # Champs d’édition avec clés uniques
        new_name = st.text_input("Nom de la recette", value=rec["name"], key=f"edit_name_{idx}")
        new_instr = st.text_area("Instructions", value=rec["instr"], height=100, key=f"edit_instr_{idx}")
        new_img   = st.text_input("URL de l'image", value=rec["img"], key=f"edit_img_{idx}")

        # Ingrédients d’édition
        if f"edit_ings_{idx}" not in st.session_state:
            st.session_state[f"edit_ings_{idx}"] = json.loads(json.dumps(rec["ings"]))
        ings2 = st.session_state[f"edit_ings_{idx}"]

        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Ingrédient", key=f"edit_add_ing_{idx}"):
                ings2.append({"name":"", "qty":0.0, "unit":"g"})
                do_rerun()
            for i, ing in enumerate(ings2):
                c0,c1,c2,c3 = st.columns([3,1,1,1])
                ing["name"] = c0.text_input(f"Ingrédient #{i+1}", value=ing["name"], key=f"edit_nm_{idx}_{i}")
                ing["qty"]  = c1.number_input("", value=ing["qty"], key=f"edit_qt_{idx}_{i}")
                ing["unit"] = c2.selectbox("", ["g","kg","ml","l","pcs"],
                                          index=["g","kg","ml","l","pcs"].index(ing["unit"]),
                                          key=f"edit_un_{idx}_{i}")
                if c3.button("🗑️", key=f"edit_del_{idx}_{i}"):
                    ings2.pop(i)
                    do_rerun()
        with col2:
            st.markdown("**Aperçu des ingrédients**")
            for ing in ings2:
                st.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")

        if st.button("💾 Enregistrer modifications", key=f"edit_save_{idx}"):
            recipes_db[user][idx] = {
                "name":  new_name,
                "instr": new_instr,
                "img":   new_img,
                "ings":  ings2.copy()
            }
            save_json(RECIPES_FILE, recipes_db)
            st.success("Recette mise à jour !")
            st.session_state.pop("edit_idx")
            st.session_state.pop(f"edit_ings_{idx}", None)
            do_rerun()

        st.write("---")
        st.stop()

    # — Formulaire d’ajout
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
    if st.button("+ Ajouter une recette", key="toggle_add_form"):
        st.session_state.show_form = not st.session_state.show_form

    if st.session_state.show_form:
        if "tmp_ings" not in st.session_state:
            st.session_state.tmp_ings = [{"name":"", "qty":0.0, "unit":"g"}]

        with st.form("add_recipe_form", clear_on_submit=True):
            name  = st.text_input("Nom de la recette", key="tmp_name")
            instr = st.text_area("Instructions", height=100, key="tmp_instr")
            img   = st.text_input("URL de l'image (placeholder OK)", key="tmp_img")

            c1, c2 = st.columns(2)
            with c1:
                if st.form_submit_button("+ Ingrédient"):
                    st.session_state.tmp_ings.append({"name":"", "qty":0.0, "unit":"g"})
                    do_rerun()
                for i, ing in enumerate(st.session_state.tmp_ings):
                    d0,d1,d2,d3 = st.columns([3,1,1,1])
                    ing["name"] = d0.text_input(f"Ingrédient #{i+1}", value=ing["name"], key=f"tmp_nm_{i}")
                    ing["qty"]  = d1.number_input("", value=ing["qty"], key=f"tmp_qt_{i}")
                    ing["unit"] = d2.selectbox("", ["g","kg","ml","l","pcs"],
                                              index=["g","kg","ml","l","pcs"].index(ing["unit"]),
                                              key=f"tmp_un_{i}")
                    if d3.button("🗑️", key=f"tmp_del_{i}"):
                        st.session_state.tmp_ings.pop(i)
                        do_rerun()
            with c2:
                st.markdown("**Aperçu des ingrédients**")
                for ing in st.session_state.tmp_ings:
                    st.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")

            submit = st.form_submit_button("Ajouter la recette")
        if submit:
            if not name.strip():
                st.error("Le nom est requis.")
            else:
                recipes_db[user].append({
                    "name":  name.strip(),
                    "instr": instr,
                    "img":   img,
                    "ings":  st.session_state.tmp_ings.copy()
                })
                save_json(RECIPES_FILE, recipes_db)
                st.success("Recette ajoutée !")
                st.session_state.pop("tmp_ings")
                st.session_state.show_form = False
                do_rerun()

    st.write("---")

    # — Affichage des cartes
    cols = st.columns(2)
    for idx, rec in enumerate(recipes_db[user]):
        c = cols[idx % 2]
        if rec["img"]:
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        c.write(rec["instr"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        btn_col1, btn_col2, btn_col3 = c.columns(3)
        if btn_col1.button("✏️ Modifier", key=f"m_{idx}"):
            st.session_state.edit_idx = idx
            do_rerun()
        if btn_col2.button("🗑️ Supprimer", key=f"d_{idx}"):
            recipes_db[user].pop(idx)
            save_json(RECIPES_FILE, recipes_db)
            do_rerun()
        if btn_col3.button("🔗 Partager", key=f"s_{idx}"):
            st.info(f"Partager « {rec['name']} »…")

# ————————————————————————————————————————————————
#   Extras
# ————————————————————————————————————————————————
elif page == "Extras":
    st.title("➕ Extras")
    with st.expander("+ Ajouter un extra"):
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
    if st.button("Enregistrer le plan"):
        save_json(PLANS_FILE, plans_db)
        st.success("Plan enregistré !")

# ————————————————————————————————————————————————
#   Liste de courses
# ————————————————————————————————————————————————
elif page == "Liste de courses":
    st.title("🛒 Liste de courses")
    shop = {}
    for key, recname in plans_db[user].items():
        if recname == "": continue
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
    st.download_button("Télécharger CSV", csv, file_name="liste_courses.csv")

# ————————————————————————————————————————————————
#   Conseils & Astuces
# ————————————————————————————————————————————————
elif page == "Conseils":
    st.title("💡 Conseils & Astuces")
    tips = [
        "Planifiez vos repas à l'avance.",
        "Variez les couleurs dans vos assiettes.",
        "Préparez des portions à congeler.",
        "Utilisez des herbes fraîches pour relever vos plats."
    ]
    for tip in tips:
        st.info(tip)

# ————————————————————————————————————————————————
#   Profil
# ————————————————————————————————————————————————
elif page == "Profil":
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

    if st.session_state.get("edit_prof", False):
        with st.form("form_prof", clear_on_submit=True):
            h = st.selectbox("Type de foyer", ["Solo","Couple","Famille"],
                             index=["Solo","Couple","Famille"].index(prof["household"]),
                             key="prof_h")
            c = st.number_input("Enfants", prof["children"], 0, 10, key="prof_c")
            t = st.number_input("Ados", prof["teens"], 0, 10, key="prof_t")
            a = st.number_input("Adultes", prof["adults"], 1, 20, key="prof_a")
            m = st.slider("Repas par jour", 1, 6, prof["meals_per_day"], key="prof_m")
            ok = st.form_submit_button("Valider")
        if ok:
            profiles_db[user] = {
                "household":h, "children":c,
                "teens":t, "adults":a,
                "meals_per_day":m
            }
            save_json(PROFILES_FILE, profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_prof = False
            do_rerun()
