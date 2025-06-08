import streamlit as st
import json
from pathlib import Path

# ─── Configuration de la page & style centré ─────────────────────────
st.set_page_config(page_title="Batchist", layout="wide")
st.markdown(
    """
    <style>
    .appview-container .main {
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Dossiers & fichiers JSON ────────────────────────────────────────
DATA_DIR = Path(st.secrets.get("DATA_DIR", "."))
FILES = {
    "users":    DATA_DIR / "users.json",
    "recipes":  DATA_DIR / "recipes.json",
    "extras":   DATA_DIR / "extras.json",
    "plans":    DATA_DIR / "plans.json",
    "profiles": DATA_DIR / "profiles.json",
}
for fp in FILES.values():
    fp.parent.mkdir(parents=True, exist_ok=True)
    if not fp.exists():
        fp.write_text("{}")

def load(fp):
    return json.loads(fp.read_text() or "{}")

def save(fp, data):
    fp.write_text(json.dumps(data, indent=2, ensure_ascii=False))

# ─── Chargement des données ──────────────────────────────────────────
users_db    = load(FILES["users"])
recipes_db  = load(FILES["recipes"])
extras_db   = load(FILES["extras"])
plans_db    = load(FILES["plans"])
profiles_db = load(FILES["profiles"])

# ─── Fonctions utilitaires ───────────────────────────────────────────
def register(u, p):
    if u in users_db: return False
    users_db[u] = {"password": p}
    save(FILES["users"], users_db)
    return True

def authenticate(u, p):
    return u in users_db and users_db[u]["password"] == p

def do_logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.experimental_rerun()

# ─── Écran Connexion / Inscription ───────────────────────────────────
if "user" not in st.session_state:
    st.title("🔒 Connexion / Inscription")
    mode = st.radio("", ["Connexion", "Inscription"], horizontal=True)

    if mode == "Inscription":
        nu = st.text_input("Nom d'utilisateur", key="r_u")
        npw = st.text_input("Mot de passe", type="password", key="r_p")
        if st.button("S'inscrire"):
            if not nu or not npw:
                st.error("Tous les champs sont requis.")
            elif register(nu.strip(), npw):
                st.success("Inscription réussie ! Vous pouvez maintenant vous connecter.")
            else:
                st.error("Ce nom d'utilisateur existe déjà.")
        st.stop()

    # Connexion
    lu = st.text_input("Nom d'utilisateur", key="l_u")
    lp = st.text_input("Mot de passe", type="password", key="l_p")
    if st.button("Se connecter"):
        if authenticate(lu.strip(), lp):
            st.session_state.user = lu.strip()
            st.experimental_rerun()
        else:
            st.error("Identifiants incorrects.")
    st.stop()

# ─── Préparation des données utilisateur ──────────────────────────────
user = st.session_state.user
for db, default in [
    (recipes_db, []),
    (extras_db, []),
    (plans_db, {}),
    (profiles_db, {}),
]:
    db.setdefault(user, default)

# ─── Barre latérale / Navigation ─────────────────────────────────────
st.sidebar.markdown(f"👤 **Connecté·e : {user}**")
page = st.sidebar.radio("Navigation", [
    "Accueil", "Mes recettes", "Extras",
    "Planificateur", "Liste de courses",
    "Conseils", "Profil", "Se déconnecter"
])
if page == "Se déconnecter":
    do_logout()

# ─── ACCUEIL ─────────────────────────────────────────────────────────
if page == "Accueil":
    st.title("🏠 Batchist — Votre batch cooking simplifié")
    st.write("Bienvenue ! Sélectionnez une section dans la barre latérale.")

# ─── MES RECETTES ────────────────────────────────────────────────────
elif page == "Mes recettes":
    st.title("📋 Mes recettes")

    # Toggle formulaire
    if "show_form" not in st.session_state:
        st.session_state.show_form = False
        st.session_state.num_ing = 1

    if st.button("➕ Ajouter une recette"):
        st.session_state.show_form = not st.session_state.show_form

    if st.session_state.show_form:
        st.subheader("Nouvelle recette")
        name  = st.text_input("Nom de la recette", key="rec_name")
        instr = st.text_area("Instructions", key="rec_instr")
        img   = st.text_input("URL de l'image", key="rec_img")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("+ Ingrédient"):
                st.session_state.num_ing += 1
            if st.button("- Ingrédient") and st.session_state.num_ing > 1:
                st.session_state.num_ing -= 1
        c2.write(f"Nombre d'ingrédients : {st.session_state.num_ing}")

        ings = []
        for i in range(st.session_state.num_ing):
            ic0, ic1, ic2 = st.columns([3,1,1])
            n = ic0.text_input(f"Ingrédient #{i+1}", key=f"ing_n_{i}")
            q = ic1.number_input("", min_value=0.0, key=f"ing_q_{i}")
            u_ = ic2.selectbox("", ["g","kg","ml","l","pcs"], key=f"ing_u_{i}")
            ings.append({"name": n, "qty": q, "unit": u_})

        if st.button("✅ Enregistrer la recette"):
            if not name.strip():
                st.error("Le nom de la recette est requis.")
            else:
                recipes_db[user].append({
                    "name": name.strip(),
                    "instr": instr,
                    "img": img,
                    "ings": ings
                })
                save(FILES["recipes"], recipes_db)
                st.success("Recette ajoutée !")
                # Reset
                st.session_state.show_form = False
                st.session_state.num_ing = 1
                for i in range(len(ings)):
                    for suffix in ("n","q","u"):
                        st.session_state.pop(f"ing_{suffix}_{i}", None)
                st.experimental_rerun()

    st.markdown("---")
    cols = st.columns(2)
    for idx, rec in enumerate(recipes_db[user]):
        c = cols[idx % 2]
        if rec["img"]:
            c.image(rec["img"], width=150)
        c.subheader(rec["name"])
        for ing in rec["ings"]:
            c.write(f"- {ing['name']}: {ing['qty']} {ing['unit']}")
        b1, b2, b3 = c.columns(3)
        if b1.button("✏️ Modifier", key=f"mod_{idx}"):
            # Précharge en édition
            st.session_state.show_form = True
            st.session_state.rec_name = rec["name"]
            st.session_state.rec_instr = rec["instr"]
            st.session_state.rec_img   = rec["img"]
            st.session_state.num_ing    = len(rec["ings"])
            for i, ing in enumerate(rec["ings"]):
                st.session_state[f"ing_n_{i}"] = ing["name"]
                st.session_state[f"ing_q_{i}"] = ing["qty"]
                st.session_state[f"ing_u_{i}"] = ing["unit"]
            recipes_db[user].pop(idx)
            save(FILES["recipes"], recipes_db)
            st.experimental_rerun()
        if b2.button("🗑️ Supprimer", key=f"del_{idx}"):
            recipes_db[user].pop(idx)
            save(FILES["recipes"], recipes_db)
            st.experimental_rerun()
        if b3.button("🔗 Partager", key=f"share_{idx}"):
            st.info(f"Partager « {rec['name']} »…")

# ─── EXTRAS ───────────────────────────────────────────────────────────
elif page == "Extras":
    st.title("➕ Extras (boissons, ménager, animaux…)")

    with st.expander("Ajouter un extra"):
        nom  = st.text_input("Produit", key="ex_n")
        qty  = st.number_input("Quantité", min_value=0.0, key="ex_q")
        unit = st.selectbox("Unité", ["g","kg","ml","l","pcs"], key="ex_u")
        if st.button("✅ Ajouter"):
            if nom.strip():
                extras_db[user].append({"name":nom,"qty":qty,"unit":unit})
                save(FILES["extras"], extras_db)
                st.success("Extra ajouté !")
                for k in ("ex_n","ex_q","ex_u"):
                    st.session_state.pop(k, None)
                st.experimental_rerun()

    st.markdown("---")
    for i, ex in enumerate(extras_db[user]):
        c0, c1, c2, c3 = st.columns([4,1,1,1])
        c0.write(ex["name"]); c1.write(ex["qty"]); c2.write(ex["unit"])
        if c3.button("🗑️", key=f"exdel_{i}"):
            extras_db[user].pop(i)
            save(FILES["extras"], extras_db)
            st.experimental_rerun()

# ─── PLANIFICATEUR ──────────────────────────────────────────────────
elif page == "Planificateur":
    st.title("📅 Planificateur de la semaine")
    prof = profiles_db[user] or {"meals_per_day": 3}
    mpd = prof["meals_per_day"]
    jours = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    cols = st.columns(7)
    for d, jour in enumerate(jours):
        with cols[d]:
            st.subheader(jour)
            for m in range(mpd):
                key = f"{jour}_{m}"
                choix = [""] + [r["name"] for r in recipes_db[user]]
                val = plans_db[user].get(key, "")
                idx = choix.index(val) if val in choix else 0
                plans_db[user][key] = st.selectbox("", choix, index=idx, key=key)
    if st.button("💾 Enregistrer le plan"):
        save(FILES["plans"], plans_db)
        st.success("Plan sauvegardé !")

# ─── LISTE DE COURSES ────────────────────────────────────────────────
elif page == "Liste de courses":
    st.title("🛒 Liste de courses")
    shop = {}
    # Ingrédients du plan
    for recn in plans_db[user].values():
        if not recn: continue
        rec = next((r for r in recipes_db[user] if r["name"] == recn), None)
        if rec:
            for ing in rec["ings"]:
                k = (ing["name"], ing["unit"])
                shop[k] = shop.get(k, 0) + ing["qty"]
    # Extras
    for ex in extras_db[user]:
        k = (ex["name"], ex["unit"])
        shop[k] = shop.get(k, 0) + ex["qty"]

    for (n,u), q in shop.items():
        st.write(f"- {n}: {q} {u}")
    csv = "Produit,Quantité,Unité\n" + "\n".join(f"{n},{q},{u}" for (n,u),q in shop.items())
    st.download_button("📥 Télécharger CSV", csv, file_name="liste_courses.csv")

# ─── CONSEILS ────────────────────────────────────────────────────────
elif page == "Conseils":
    st.title("💡 Conseils & Astuces")
    tips = [
        "Planifiez vos repas à l'avance.",
        "Variez les couleurs dans vos assiettes.",
        "Préparez des portions à congeler.",
        "Utilisez des herbes fraîches pour relever vos plats."
    ]
    for t in tips:
        st.info(t)

# ─── PROFIL ─────────────────────────────────────────────────────────
elif page == "Profil":
    st.title("👤 Profil")
    prof = profiles_db[user] or {
        "household":"Solo","children":0,"teens":0,
        "adults":1,"meals_per_day":3
    }
    st.write(f"- Foyer      : {prof['household']}")
    st.write(f"- Enfants    : {prof['children']}")
    st.write(f"- Ados       : {prof['teens']}")
    st.write(f"- Adultes    : {prof['adults']}")
    st.write(f"- Repas/jour : {prof['meals_per_day']}")

    if "edit_prof" not in st.session_state:
        st.session_state.edit_prof = False
    if st.button("✏️ Modifier le profil"):
        st.session_state.edit_prof = True

    if st.session_state.edit_prof:
        h = st.selectbox("Type de foyer", ["Solo","Couple","Famille"],
                         index=["Solo","Couple","Famille"].index(prof["household"]))
        c = st.number_input("Enfants", prof["children"], 0, 10)
        t = st.number_input("Ados", prof["teens"], 0, 10)
        a = st.number_input("Adultes", prof["adults"], 1, 20)
        m = st.slider("Repas par jour", 1, 6, prof["meals_per_day"])
        if st.button("✅ Valider le profil"):
            profiles_db[user] = {
                "household": h,
                "children": c,
                "teens": t,
                "adults": a,
                "meals_per_day": m
            }
            save(FILES["profiles"], profiles_db)
            st.success("Profil mis à jour !")
            st.session_state.edit_prof = False
            st.experimental_rerun()
