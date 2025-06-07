import streamlit as st
import pandas as pd
import json
from datetime import datetime

# -----------------------------
# 1) STATE INITIALIZATION
# -----------------------------
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 0
if "profile" not in st.session_state:
    st.session_state.profile = {
        "household_type": None,
        "num_children": 0,
        "num_adolescents": 0,
        "num_adults": 1
    }
if "recipes" not in st.session_state:
    st.session_state.recipes = []     # each: {id,name,ingredients,instructions,extras,image}
if "mealplan" not in st.session_state:
    st.session_state.mealplan = pd.DataFrame(columns=["Day","Meal","Recipe"])
if "next_recipe_id" not in st.session_state:
    st.session_state.next_recipe_id = 1

# -----------------------------
# 2) PAGE CONFIG + NAV
# -----------------------------
st.set_page_config(layout="wide", page_title="Batchist")
st.markdown("<h1 style='text-align:center;'>🍲 Batchist</h1>", unsafe_allow_html=True)

if st.session_state.onboard_step < 3:
    # ONBOARDING
    if st.session_state.onboard_step == 0:
        st.header("Bienvenue sur Batchist !") 
        st.write("D'abord, comment vivez-vous ?")
        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("Solo"):
                st.session_state.profile["household_type"]="Solo"
                st.session_state.onboard_step=1
                st.experimental_rerun()
        with c2:
            if st.button("Couple"):
                st.session_state.profile["household_type"]="Couple"
                st.session_state.onboard_step=1
                st.experimental_rerun()
        with c3:
            if st.button("Famille"):
                st.session_state.profile["household_type"]="Famille"
                st.session_state.onboard_step=1
                st.experimental_rerun()
        st.stop()

    if st.session_state.onboard_step == 1:
        st.header("Combien de personnes ?")
        p = st.session_state.profile
        if p["household_type"]=="Famille":
            p["num_children"]=st.number_input("Enfants (<12 ans)",0,10,p["num_children"])
            p["num_adolescents"]=st.number_input("Adolescents (12–18 ans)",0,10,p["num_adolescents"])
            p["num_adults"]=st.number_input("Adultes (>18 ans)",1,10,p["num_adults"])
        else:
            p["num_adults"]=1 if p["household_type"]=="Solo" else 2
            st.write(f"Nombre d'adultes fixé à : {p['num_adults']}")
        if st.button("Valider"):
            st.session_state.onboard_step=3
            st.experimental_rerun()
        st.stop()

# NAVIGATION
page = st.radio("", ["Accueil","Mes recettes","Planificateur","Liste de courses","Profil"], horizontal=True)
st.markdown("---")

# -----------------------------
# 3) ACCUEIL
# -----------------------------
if page=="Accueil":
    st.header("🏠 Tableau de bord")
    prof = st.session_state.profile
    st.markdown(f"- **Type de foyer :** {prof['household_type']}")
    st.markdown(f"- **Enfants :** {prof['num_children']}, **Ados :** {prof['num_adolescents']}, **Adultes :** {prof['num_adults']}")
    st.write("Rendez-vous dans les autres onglets pour créer vos recettes, planifier la semaine et générer la liste de courses.")

# -----------------------------
# 4) MES RECETTES
# -----------------------------
elif page=="Mes recettes":
    st.header("📋 Mes recettes")

    left, right = st.columns([2,3])
    with left.form("new_recipe"):
        name = st.text_input("Nom de la recette")
        st.markdown("**Ingrédients**")
        n = st.number_input("Nombre d'ingrédients",1,20,1,key="n_ingr")
        ing_list=[]
        cols = st.columns([3,1,1])
        for i in range(n):
            ing = cols[0].text_input(f"Ingrédient #{i+1}", key=f"ingN{i}")
            qty = cols[1].number_input(f"Qté #{i+1}", 0.0,10000.0, step=1.0, key=f"qtyN{i}")
            unit= cols[2].selectbox(f"Unité #{i+1}",["g","kg","ml","l","u"], key=f"unitN{i}")
            ing_list.append({"name":ing,"qty":qty,"unit":unit})
        instr = st.text_area("Instructions")
        st.markdown("**Extras** (boissons, maison, animaux)")
        x = st.text_area("Un par ligne: nom,quantité,unité")
        extras=[]
        for line in x.splitlines():
            try:
                nm,qt,ut=line.split(",")
                extras.append({"name":nm.strip(),"qty":float(qt),"unit":ut.strip()})
            except: pass
        img_url = st.text_input("URL image (placeholder ok)", value="https://via.placeholder.com/150")
        if st.form_submit_button("Ajouter la recette"):
            rid = st.session_state.next_recipe_id
            st.session_state.recipes.append({
                "id":rid,"name":name,
                "ingredients":ing_list,
                "instructions":instr,
                "extras":extras,
                "image":img_url
            })
            st.session_state.next_recipe_id+=1
            st.success(f"Recette « {name} » ajoutée !")

    st.markdown("### Vos recettes")
    for r in st.session_state.recipes:
        st.markdown("---")
        c1,c2=st.columns([1,2])
        with c1:
            st.image(r["image"], use_column_width=True)
        with c2:
            st.subheader(r["name"])
            st.markdown("**Ingrédients :**")
            df_ings=pd.DataFrame(r["ingredients"])
            st.table(df_ings)
            if r["extras"]:
                st.markdown("**Extras :**")
                st.table(pd.DataFrame(r["extras"]))
            st.markdown(f"**Instructions :** {r['instructions']}")
            col1,col2,col3=st.columns(3)
            if col1.button("✏️ Modifier", key=f"mod{r['id']}"):
                st.warning("Édition non encore implémentée")
            if col2.button("🗑️ Supprimer", key=f"del{r['id']}"):
                st.session_state.recipes=[x for x in st.session_state.recipes if x["id"]!=r["id"]]
                st.experimental_rerun()
            if col3.button("🔗 Partager",key=f"share{r['id']}"):
                st.info("Partagez cette URL : "+st.runtime.get_url())

# -----------------------------
# 5) PLANIFICATEUR
# -----------------------------
elif page=="Planificateur":
    st.header("📅 Planificateur de la semaine")
    days=["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    meals=["Petit-déj","Déjeuner","Dîner"]
    plan=[]
    with st.form("plan_form"):
        for day in days:
            st.markdown(f"#### {day}")
            cols=st.columns(3)
            for i,meal in enumerate(meals):
                sel = cols[i].selectbox(meal,[""]+[r["name"] for r in st.session_state.recipes], key=f"{day}_{i}")
                plan.append({"Day":day,"Meal":meal,"Recipe":sel})
        if st.form_submit_button("Enregistrer"):
            st.session_state.mealplan=pd.DataFrame(plan)
            st.success("Planning enregistré !")
    st.markdown("### Aperçu")
    st.table(st.session_state.mealplan)

# -----------------------------
# 6) LISTE DE COURSES
# -----------------------------
elif page=="Liste de courses":
    st.header("🛒 Liste de courses")
    dfp=st.session_state.mealplan
    all_ings={}
    for nm in dfp["Recipe"].unique():
        rec=next((r for r in st.session_state.recipes if r["name"]==nm),None)
        if rec:
            for ing in rec["ingredients"]+rec["extras"]:
                key=(ing["name"],ing["unit"])
                all_ings[key]=all_ings.get(key,0)+ing["qty"]
    if not all_ings:
        st.info("Pas d'ingrédients à lister.")
    else:
        rows=[{"Ingr":k[0],"Unit":k[1],"Qty":v} for k,v in all_ings.items()]
        dfc=pd.DataFrame(rows)
        st.table(dfc)
        st.download_button("⬇️ CSV",dfc.to_csv(index=False), "courses.csv","text/csv")

# -----------------------------
# 7) PROFIL
# -----------------------------
elif page=="Profil":
    st.header("👤 Profil")
    p=st.session_state.profile
    st.markdown(f"- **Foyer :** {p['household_type']}")
    st.markdown(f"- **Enfants :** {p['num_children']}")
    st.markdown(f"- **Ados :** {p['num_adolescents']}")
    st.markdown(f"- **Adultes :** {p['num_adults']}")
    if st.button("Modifier le profil"):
        st.session_state.onboard_step=1
        st.experimental_rerun()
