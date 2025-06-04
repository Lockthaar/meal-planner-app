import streamlit as st
import pandas as pd
import json
from collections import defaultdict

# -- Data storage --
# We will store data in session state as pandas DataFrames for this prototype.
# In a production app, you might connect to a real database.

# Initialize session state for recipes and meal planner
if 'recipes_df' not in st.session_state:
    # Sample structure for recipes: Name, Ingredients (JSON list of {ingredient, quantity, unit}), Instructions
    st.session_state.recipes_df = pd.DataFrame(columns=['Name', 'Ingredients', 'Instructions'])

if 'mealplan_df' not in st.session_state:
    # Meal planner: Day, Meal (Breakfast/Lunch/Dinner), Recipe Name
    st.session_state.mealplan_df = pd.DataFrame(columns=['Day', 'Meal', 'Recipe'])

# Utility to parse ingredients JSON stored as string
@st.cache_data
def parse_ingredients(ing_str):
    try:
        return json.loads(ing_str)
    except:
        return []

# -- Sidebar navigation --
st.title("Meal Planner Application")
section = st.sidebar.selectbox("Choisir une section", ['Recettes', 'Planificateur', 'Liste de courses', 'Impression'])

# -- Section: Recettes --
if section == 'Recettes':
    st.header("Ajouter / Voir les recettes")

    with st.expander("Ajouter une nouvelle recette"):  
        name = st.text_input("Nom de la recette", key="new_name")
        ingredients_raw = st.text_area("Ingrédients (un par ligne au format: ingrédient, quantité, unité)", key="new_ingredients")
        instructions = st.text_area("Instructions", key="new_instructions")
        if st.button("Enregistrer la recette"):
            # Parse ingredients_raw into JSON
            ingredients_list = []
            for line in ingredients_raw.split("\n"):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 3:
                    ingr, qty, unit = parts
                    try:
                        qty_val = float(qty)
                    except:
                        qty_val = qty
                    ingredients_list.append({"ingredient": ingr, "quantity": qty_val, "unit": unit})
            new_row = {
                'Name': name,
                'Ingredients': json.dumps(ingredients_list, ensure_ascii=False),
                'Instructions': instructions
            }
            st.session_state.recipes_df = st.session_state.recipes_df.append(new_row, ignore_index=True)
            st.success(f"Recette '{name}' ajoutée.")

    st.subheader("Toutes les recettes")
    if not st.session_state.recipes_df.empty:
        for idx, row in st.session_state.recipes_df.iterrows():
            st.markdown(f"**{row['Name']}**")
            ingredients = parse_ingredients(row['Ingredients'])
            for ing in ingredients:
                st.write(f"- {ing['ingredient']}: {ing['quantity']} {ing['unit']}")
            st.write("Instructions:")
            st.write(row['Instructions'])
            st.markdown("---")
    else:
        st.info("Aucune recette disponible.")

# -- Section: Planificateur --
elif section == 'Planificateur':
    st.header("Planifier les repas de la semaine")
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    meals = ['Petit-déjeuner', 'Déjeuner', 'Dîner']

    with st.form(key='plan_form'):
        col1, col2, col3 = st.columns(3)
        selections = []
        for i, day in enumerate(days):
            with col1 if i < 3 else (col2 if i < 6 else col3):
                st.subheader(day)
                for meal in meals:
                    recipe_choice = st.selectbox(f"{meal}:", options=[''] + st.session_state.recipes_df['Name'].tolist(), key=f"{day}_{meal}")
                    selections.append((day, meal, recipe_choice))
        submit = st.form_submit_button("Enregistrer le plan")
        if submit:
            df = pd.DataFrame(selections, columns=['Day', 'Meal', 'Recipe'])
            # Remove empty selections
            df = df[df['Recipe'] != '']
            st.session_state.mealplan_df = df
            st.success("Plan de la semaine enregistré.")

    st.subheader("Plan actuel")
    if not st.session_state.mealplan_df.empty:
        st.table(st.session_state.mealplan_df)
    else:
        st.info("Aucun plan enregistré.")

# -- Section: Liste de courses --
elif section == 'Liste de courses':
    st.header("Liste de courses générée")
    if st.session_state.mealplan_df.empty:
        st.info("Veuillez d'abord planifier vos repas.")
    else:
        # Aggregate ingredients from all recipes in plan
        total_ingredients = defaultdict(lambda: {'quantity': 0, 'unit': ''})
        for recipe_name in st.session_state.mealplan_df['Recipe']:
            row = st.session_state.recipes_df[st.session_state.recipes_df['Name'] == recipe_name]
            if not row.empty:
                ingredients = parse_ingredients(row.iloc[0]['Ingredients'])
                for ing in ingredients:
                    key = ing['ingredient']
                    qty = ing['quantity']
                    unit = ing['unit']
                    if total_ingredients[key]['unit'] and total_ingredients[key]['unit'] != unit:
                        # If unit mismatch, skip aggregation for simplicity
                        st.warning(f"Unité différente pour {key}, vérifiez manuellement.")
                    total_ingredients[key]['quantity'] += qty
                    total_ingredients[key]['unit'] = unit

        # Display aggregated list
        shopping_data = []
        for ing, vals in total_ingredients.items():
            shopping_data.append({'Ingrédient': ing, 'Quantité': vals['quantity'], 'Unité': vals['unit']})
        shopping_df = pd.DataFrame(shopping_data)
        st.table(shopping_df)

# -- Section: Impression --
else:
    st.header("Liste de courses imprimable")
    if st.session_state.mealplan_df.empty:
        st.info("Veuillez d'abord planifier vos repas pour obtenir la liste de courses.")
    else:
        # Reuse shopping_df from above logic
        total_ingredients = defaultdict(lambda: {'quantity': 0, 'unit': ''})
        for recipe_name in st.session_state.mealplan_df['Recipe']:
            row = st.session_state.recipes_df[st.session_state.recipes_df['Name'] == recipe_name]
            if not row.empty:
                ingredients = parse_ingredients(row.iloc[0]['Ingredients'])
                for ing in ingredients:
                    key = ing['ingredient']
                    qty = ing['quantity']
                    unit = ing['unit']
                    if total_ingredients[key]['unit'] and total_ingredients[key]['unit'] != unit:
                        pass  # unit mismatch ignored in print view
                    total_ingredients[key]['quantity'] += qty
                    total_ingredients[key]['unit'] = unit

        shopping_data = []
        for ing, vals in total_ingredients.items():
            shopping_data.append({'Ingrédient': ing, 'Quantité': vals['quantity'], 'Unité': vals['unit']})
        shopping_df = pd.DataFrame(shopping_data)
        st.markdown("---")
        st.write("## Liste de courses à imprimer")
        st.table(shopping_df)

# Instructions for running the app:
st.sidebar.markdown("---")
st.sidebar.write(
    "**Instructions:**\n"
    "1. Installez Streamlit: `pip install streamlit pandas`\n"
    "2. Sauvegardez ce fichier en tant que `app.py`.\n"
    "3. Lancez l'application: `streamlit run app.py`.\n"
    "4. Accédez à l'adresse fournie dans votre navigateur."
)