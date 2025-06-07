import streamlit as st
import pandas as pd
from datetime import datetime

# ----------------------------------------------------------------
# 1) STATE INITIALIZATION
# ----------------------------------------------------------------
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 0
if "profile" not in st.session_state:
    st.session_state.profile = {
        "household_type": None,
        "children": 0,
        "adolescents": 0,
        "adults": 1
    }
if "recipes" not in st.session_state:
    st.session_state.recipes = []      # dict: id,name,ingredients,instructions,image
    st.session_state.next_recipe_id = 1
if "extras" not in st.session_state:
    st.session_state.extras = []       # mêmes champs que recipes
    st.session_state.next_extra_id = 1
if "mealplan" not in st.session_state:
    st.session_state.mealplan = pd.DataFrame(columns=["Day","Meal","Recipe"])
    
# ----------------------------------------------------------------
# 2) ONBOARDING FLOW
# ----------------------------------------------------------------
if st.session_state.onboard_step == 0:
    st.set_page_config(layout="wide", page_title="Batchist Onboarding")
    st.title("Bienvenue sur Batchist !")
    st.write("**1. Comment vivez-vous ?**")
    c1,c2,c3 = st.columns(3)
    if c1.button("Solo"):
        st.session_state.profile["household_type"]="Solo"
        st.session_state.onboard_step=1; st.experimental_rerun()
    if c2.button("Couple"):
        st.session_state.profile["household_type"]="Couple"
        st.session_state.onboard_step=1; st.experimental_rerun()
    if c3.button("Famille"):
        st.session_state.profile["household_type"]="Famille"
        st.session_state.onboard_step=1; st.experimental_rerun()
    st.stop()

if st.session_state.onboard_step == 1:
    st.set_page_config(layout="wide", page_title="Batchist Onboarding")
    st.title("Bienvenue sur Batchist !")
    st.write("**2. Combien de personnes dans le foyer ?**")
    p = st.session_state.profile
    if p["household_type"]=="Famille":
        p["children"] = st.number_input("Enfants (<12 ans)",0,10,p["children"])
        p["adolescents"] = st.number_input("Adolescents (12–18 ans)",0,10,p["adolescents"])
        p["adults"] = st.number_input("Adultes (>18 ans)",1,10,p["adults"])
    else:
        p["adults"] = 1 if p["household_type"]=="Solo" else 2
        st.write(f"Adultes fixés à {p['adults']}")
    if st.button("Valider le profil"):
        st.session_state.onboard_step=2; st.experimental_rerun()
    st.stop()

# ----------------------------------------------------------------
# 3) MAIN APP – NAVIGATION & FRAMEWORK
# ----------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Batchist")
st.markdown("<h1 style='text-align:center;'>🥣 Batchist</h1>", unsafe_allow_html=True)
st.write("---")

# Navigation header
tabs = st.tabs([
    "🏠 Accueil",
    "📋 Mes recettes",
    "🧩 Extras",
    "📅 Planificateur",
    "🛒 Liste de courses",
    "💡 Conseils",
    "👤 Profil",
])

# ----------------------------------------------------------------
# 4) ACCUEIL
# ----------------------------------------------------------------
with tabs[0]:
    st.header("Accueil")
    st.write("Bienvenue ! Utilisez les onglets pour gérer vos recettes, extras, planning, etc.")

# ----------------------------------------------------------------
# 5) MES RECETTES
# ----------------------------------------------------------------
with tabs[1]:
    st.header("Mes recettes")
    left,right = st.columns([2,3])
    with left.form("form_add_recipe"):
        name = st.text_input("Nom de la recette")
        st.write("**Ingrédients**")
        ings = []
        n = st.number_input("Nombre de lignes",1,20,1,key="n_ing")
        cols = st.columns([3,1,1])
        for i in range(n):
            nm = cols[0].text_input(f"Nom #{i+1}", key=f"r_ing_{i}")
            q  = cols[1].number_input(f"Qté #{i+1}",0.0,10000.0, step=1.0, key=f"r_qty_{i}")
            u  = cols[2].selectbox(f"Unité #{i+1}", ["g","kg","ml","l","u"], key=f"r_unit_{i}")
            ings.append({"name":nm,"qty":q,"unit":u})
        instr = st.text_area("Instructions")
        img = st.text_input("URL image", value="https://via.placeholder.com/150")
        if st.form_submit_button("Ajouter recette"):
            rid = st.session_state.next_recipe_id
            st.session_state.recipes.append({
                "id":rid, "name":name, "ingredients":ings,
                "instructions":instr, "image":img
            })
            st.session_state.next_recipe_id+=1
            st.success("Recette ajoutée !")

    st.write("### Vos recettes")
    for r in st.session_state.recipes:
        st.markdown("---")
        c1,c2 = st.columns([1,3])
        with c1:
            st.image(r["image"], use_column_width=True)
        with c2:
            st.subheader(r["name"])
            st.table(pd.DataFrame(r["ingredients"]))
            st.write(r["instructions"])
            b1,b2,b3 = st.columns(3)
            if b1.button("✏️ Modifier", key=f"mod_{r['id']}"):
                st.info("Édition à implémenter")
            if b2.button("🗑️ Supprimer", key=f"del_{r['id']}"):
                st.session_state.recipes = [x for x in st.session_state.recipes if x["id"]!=r["id"]]
                st.experimental_rerun()
            if b3.button("🔗 Partager", key=f"share_{r['id']}"):
                st.info("URL de partage : "+st.runtime.get_url())

# ----------------------------------------------------------------
# 6) EXTRAS
# ----------------------------------------------------------------
with tabs[2]:
    st.header("Extras (boissons, maison, animaux)")
    left,right = st.columns([2,3])
    with left.form("form_add_extra"):
        name = st.text_input("Nom de l'extra")
        qty  = st.number_input("Quantité",0.0,10000.0, step=1.0)
        unit = st.selectbox("Unité", ["g","kg","ml","l","u"])
        if st.form_submit_button("Ajouter extra"):
            eid = st.session_state.next_extra_id
            st.session_state.extras.append({
                "id":eid, "name":name, "qty":qty, "unit":unit
            })
            st.session_state.next_extra_id+=1
            st.success("Extra ajouté !")
    st.write("### Vos extras")
    df_e = pd.DataFrame(st.session_state.extras)
    if not df_e.empty:
        st.table(df_e)
        for e in st.session_state.extras:
            if st.button("🗑️", key=f"dx_{e['id']}"):
                st.session_state.extras = [x for x in st.session_state.extras if x["id"]!=e["id"]]
                st.experimental_rerun()

# ----------------------------------------------------------------
# 7) PLANIFICATEUR
# ----------------------------------------------------------------
with tabs[3]:
    st.header("Planificateur de la semaine")
    days=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    meals=["Petit-déj","Déjeuner","Dîner"]
    plan=[]
    with st.form("form_plan"):
        for day in days:
            st.markdown(f"#### {day}")
            cols = st.columns(3)
            for i,meal in enumerate(meals):
                sel = cols[i].selectbox(meal, [""]+[r["name"] for r in st.session_state.recipes], key=f"p_{day}_{i}")
                plan.append({"Day":day,"Meal":meal,"Recipe":sel})
        if st.form_submit_button("Enregistrer planning"):
            st.session_state.mealplan = pd.DataFrame(plan)
            st.success("Planning enregistré !")
    st.write(st.session_state.mealplan)

# ----------------------------------------------------------------
# 8) LISTE DE COURSES
# ----------------------------------------------------------------
with tabs[4]:
    st.header("Liste de courses")
    mp = st.session_state.mealplan
    agg = {}
    # ingrédients recettes
    for nm in mp["Recipe"].unique():
        rec = next((r for r in st.session_state.recipes if r["name"]==nm), None)
        if rec:
            for ing in rec["ingredients"]:
                key=(ing["name"],ing["unit"])
                agg[key]=agg.get(key,0)+ing["qty"]
    # extras
    for ex in st.session_state.extras:
        key=(ex["name"],ex["unit"])
        agg[key]=agg.get(key,0)+ex["qty"]
    if not agg:
        st.info("Rien à afficher.")
    else:
        dfc = pd.DataFrame([{"Item":k[0],"Unit":k[1],"Qty":v} for k,v in agg.items()])
        st.table(dfc)
        csv = dfc.to_csv(index=False).encode()
        st.download_button("Télécharger CSV", csv, "liste_courses.csv")

# ----------------------------------------------------------------
# 9) CONSEILS & ASTUCES
# ----------------------------------------------------------------
with tabs[5]:
    st.header("Conseils & Astuces")
    st.write("- Astuce 1…")
    st.write("- Astuce 2…")

# ----------------------------------------------------------------
# 10) PROFIL
# ----------------------------------------------------------------
with tabs[6]:
    st.header("Profil")
    p = st.session_state.profile
    st.write(f"- Foyer : {p['household_type']}")
    st.write(f"- Enfants : {p['children']}")
    st.write(f"- Adolescents : {p['adolescents']}")
    st.write(f"- Adultes : {p['adults']}")
    if st.button("Modifier profil"):
        st.session_state.onboard_step = 1
        st.experimental_rerun()
