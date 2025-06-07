import streamlit as st
import pandas as pd

# ------------------------------------------------------------------
# 1) Initialisation session_state
# ------------------------------------------------------------------
if "recipes" not in st.session_state:
    st.session_state.recipes = []        # liste des dict {name, ingredients: [{ing,qty,unit}], instructions}

if "mealplan" not in st.session_state:
    # Un DataFrame vide avec colonnes Day, Meal, Recipe
    st.session_state.mealplan = pd.DataFrame(columns=["Day","Meal","Recipe"])

# ------------------------------------------------------------------
# 2) Barre de navigation (toujours visible)
# ------------------------------------------------------------------
st.set_page_config(layout="wide")
st.markdown("<h1 style='text-align:center;'>🍲 Batchist Simplifié</h1>", unsafe_allow_html=True)
page = st.radio(
    "Menu",
    ["Accueil", "Mes recettes", "Planificateur", "Liste de courses"],
    horizontal=True
)
st.markdown("---")

# ------------------------------------------------------------------
# 3) Pages
# ------------------------------------------------------------------

# --- ACCUEIL ---
if page == "Accueil":
    st.header("🏠 Bienvenue sur Batchist")
    st.write("""
      Ce prototype vous permet de :
      1. Ajouter vos recettes  
      2. Planifier vos repas  
      3. Générer automatiquement la liste de courses  
      
      **→ Choisissez un onglet ci-dessous pour commencer.**
    """)

# --- MES RECETTES ---
elif page == "Mes recettes":
    st.header("📋 Mes recettes")
    with st.expander("➕ Ajouter une nouvelle recette", expanded=True):
        with st.form("form_add"):
            name = st.text_input("Nom de la recette")
            st.markdown("**Ingrédients**")
            ings = []
            n = st.number_input("Nombre d’ingrédients", min_value=1, max_value=20, value=1, key="n_ings")
            cols = st.columns([3,1,1])
            for i in range(n):
                ing = cols[0].text_input(f"Ingrédient #{i+1}", key=f"ing_{i}")
                qty = cols[1].number_input(f"Qté #{i+1}", min_value=0.0, key=f"qty_{i}")
                unit = cols[2].selectbox(f"Unité #{i+1}", ["g","kg","ml","l","unité"], key=f"unit_{i}")
                ings.append(dict(name=ing, qty=qty, unit=unit))
            instr = st.text_area("Instructions")
            if st.form_submit_button("Enregistrer la recette"):
                st.session_state.recipes.append(dict(
                    name=name, ingredients=ings, instructions=instr
                ))
                st.success(f"Recette « {name} » ajoutée !")

    st.markdown("### Vos recettes existantes")
    for idx, r in enumerate(st.session_state.recipes):
        st.markdown(f"**{idx+1}. {r['name']}**")
        df_ings = pd.DataFrame(r["ingredients"])
        st.table(df_ings)
        st.markdown(f"**Instructions :** {r['instructions']}")
        if st.button(f"Supprimer #{idx+1}", key=f"del_{idx}"):
            st.session_state.recipes.pop(idx)
            st.experimental_rerun()

# --- PLANIFICATEUR ---
elif page == "Planificateur":
    st.header("📅 Planificateur de la semaine")
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    meals = ["Petit-déjeuner","Déjeuner","Dîner"]
    df = st.session_state.mealplan.copy()
    with st.form("form_plan"):
        plan = []
        for day in days:
            for meal in meals:
                recipe = st.selectbox(f"{day} – {meal}", 
                                      options=[""] + [r["name"] for r in st.session_state.recipes],
                                      key=f"plan_{day}_{meal}")
                plan.append(dict(Day=day, Meal=meal, Recipe=recipe))
        if st.form_submit_button("Enregistrer le plan"):
            st.session_state.mealplan = pd.DataFrame(plan)
            st.success("Planning mis à jour !")

    st.markdown("### Aperçu du plan actuel")
    st.table(st.session_state.mealplan)

# --- LISTE DE COURSES ---
elif page == "Liste de courses":
    st.header("🛒 Liste de courses générée")
    dfp = st.session_state.mealplan.dropna(subset=["Recipe"])
    # Récupère ingrédients de chaque recette planifiée
    all_ings = {}
    for recipe_name in dfp["Recipe"].unique():
        rec = next((r for r in st.session_state.recipes if r["name"]==recipe_name), None)
        if rec:
            for ing in rec["ingredients"]:
                key = (ing["name"], ing["unit"])
                all_ings[key] = all_ings.get(key,0) + ing["qty"]

    if not all_ings:
        st.info("Aucun ingrédient à lister (plan vide ou recettes manquantes).")
    else:
        # Constitue un DataFrame
        data = [{"Ingrédient":k[0], "Unité":k[1], "Quantité":v} 
                for k,v in all_ings.items()]
        df_shop = pd.DataFrame(data)
        st.table(df_shop)
        # Bouton pour télécharger en CSV
        csv = df_shop.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Télécharger CSV", csv, "liste_courses.csv", "text/csv")

# ------------------------------------------------------------------
# 4) Fin du code
# ------------------------------------------------------------------
