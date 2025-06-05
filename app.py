import streamlit as st
import pandas as pd
import json
from collections import defaultdict

# ----------------------------------------------------------------
# INITIALISATION DU STATE
# ----------------------------------------------------------------

# DataFrame des recettes (Name, Ingredients (JSON), Instructions)
if "recipes_df" not in st.session_state:
    st.session_state.recipes_df = pd.DataFrame(columns=["Name", "Ingredients", "Instructions"])

# DataFrame du planning des repas
if "mealplan_df" not in st.session_state:
    st.session_state.mealplan_df = pd.DataFrame(columns=["Day", "Meal", "Recipe"])

# Compteur de lignes d'ingrédients pour le formulaire
if "ing_count" not in st.session_state:
    st.session_state.ing_count = 1  # On commence avec une seule ligne

# ----------------------------------------------------------------
# FONCTION UTILITAIRE DE PARSAGE DES INGREDIENTS
# ----------------------------------------------------------------
@st.cache_data
def parse_ingredients(ing_str: str):
    """
    Convertit la chaîne JSON enregistrée dans 'Ingredients' en liste de dict.
    """
    try:
        return json.loads(ing_str)
    except:
        return []

# ----------------------------------------------------------------
# INTERFACE PRINCIPALE
# ----------------------------------------------------------------
st.set_page_config(page_title="Meal Planner", layout="wide")
st.title("Meal Planner Application")

# Menu de navigation
section = st.sidebar.selectbox("Choisir une section", ["Recettes", "Planificateur", "Liste de courses", "Impression"])

# ----------------------------------------------------------------
# SECTION 1 : GÉRER LES RECETTES (AJOUT / AFFICHAGE / SUPPRESSION)
# ----------------------------------------------------------------
if section == "Recettes":
    st.header("Ajouter / Voir les recettes")

    st.write("**1. Ajouter une nouvelle recette**")
    with st.expander("🆕 Ajouter une nouvelle recette"):
        # Champ pour le nom de la recette
        name = st.text_input("Nom de la recette", key="new_name")

        # Gestion dynamique du nombre de lignes d’ingrédients
        st.write("**Ingrédients**")
        st.write("Pour ajouter une nouvelle ligne :")
        if st.button("➕ Ajouter une ligne d’ingrédient"):
            st.session_state.ing_count += 1

        # Construction du formulaire : ing_count lignes
        ingrédients_temp = []
        unités_dispo = ["mg", "g", "kg", "cl", "dl", "l", "pièce(s)"]

        for i in range(st.session_state.ing_count):
            c1, c2, c3 = st.columns([4, 2, 2])
            with c1:
                ingr_i = st.text_input(f"Ingrédient #{i+1}", key=f"ing_nom_{i}")
            with c2:
                qty_i = st.number_input(f"Quantité #{i+1}", min_value=0.0, format="%.2f", key=f"ing_qty_{i}")
            with c3:
                unit_i = st.selectbox(f"Unité #{i+1}", unités_dispo, key=f"ing_unit_{i}")
            ingrédients_temp.append((ingr_i, qty_i, unit_i))

        # Champ d’instructions
        instructions = st.text_area("Instructions", key="new_instructions")

        # Bouton pour enregistrer la recette
        if st.button("💾 Enregistrer la recette", key="save_recipe"):
            # Vérifie que le nom n’est pas vide et qu’il n’existe pas déjà
            if not name.strip():
                st.error("Le nom de la recette ne peut pas être vide.")
            elif name in st.session_state.recipes_df["Name"].tolist():
                st.error(f"Une recette appelée '{name}' existe déjà.")
            else:
                # On filtre les lignes d’ingrédient où le nom est non vide et quantité > 0
                ingrédients_list = []
                for ingr_i, qty_i, unit_i in ingrédients_temp:
                    if ingr_i.strip() != "" and qty_i > 0:
                        ingrédients_list.append({
                            "ingredient": ingr_i.strip(),
                            "quantity": float(qty_i),
                            "unit": unit_i
                        })

                # Si aucun ingrédient valide, affiche une erreur
                if len(ingrédients_list) == 0:
                    st.error("Veuillez remplir au moins un ingrédient valide (nom non vide et quantité > 0).")
                else:
                    # Création du dict pour la nouvelle ligne
                    new_row = {
                        "Name": name.strip(),
                        "Ingredients": json.dumps(ingrédients_list, ensure_ascii=False),
                        "Instructions": instructions.strip()
                    }

                    # Ajout au DataFrame via pd.concat
                    st.session_state.recipes_df = pd.concat(
                        [st.session_state.recipes_df, pd.DataFrame([new_row])],
                        ignore_index=True
                    )

                    st.success(f"Recette '{name}' ajoutée.")

                    # ----------------------------
                    # RÉINITIALISATION DU FORMULAIRE
                    # ----------------------------
                    # On supprime la clé "new_name" si elle est présente
                    if "new_name" in st.session_state:
                        del st.session_state["new_name"]
                    # On supprime la clé "new_instructions"
                    if "new_instructions" in st.session_state:
                        del st.session_state["new_instructions"]
                    # Pour chaque ligne d’ingrédient, on supprime les clés utilisées
                    for j in range(st.session_state.ing_count):
                        for field in (f"ing_nom_{j}", f"ing_qty_{j}", f"ing_unit_{j}"):
                            if field in st.session_state:
                                del st.session_state[field]
                    # On remet le compteur d’ingrédients à 1
                    st.session_state.ing_count = 1

                    # On relance l’app pour que les champs se resetent
                    st.experimental_rerun()

    st.markdown("---")
    st.write("**2. Liste des recettes existantes**")
    if st.session_state.recipes_df.empty:
        st.info("Aucune recette disponible.")
    else:
        # Affichage de chaque recette avec son bouton de suppression
        for idx, row in st.session_state.recipes_df.iterrows():
            col1, col2 = st.columns([8, 1])
            with col1:
                st.markdown(f"### {row['Name']}")
                # Affiche la liste des ingrédients
                ingrédients = parse_ingredients(row["Ingredients"])
                for ing in ingrédients:
                    st.write(f"- {ing['ingredient']}: {ing['quantity']} {ing['unit']}")
                st.write("**Instructions :**")
                st.write(row["Instructions"])
            with col2:
                # Bouton supprimer (clé unique par idx pour ne pas colliser)
                if st.button("🗑️ Supprimer", key=f"delete_{idx}"):
                    # Supprime la ligne du DataFrame et réindexe
                    df = st.session_state.recipes_df.drop(idx).reset_index(drop=True)
                    st.session_state.recipes_df = df
                    st.experimental_rerun()  # relance l’app pour actualiser l’affichage
            st.markdown("---")

# ----------------------------------------------------------------
# SECTION 2 : PLANIFICATEUR DE LA SEMAINE
# ----------------------------------------------------------------
elif section == "Planificateur":
    st.header("Planifier les repas de la semaine")
    days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    meals = ["Petit-déjeuner", "Déjeuner", "Dîner"]

    with st.form(key="plan_form"):
        cols = st.columns(3)
        selections = []
        for i, day in enumerate(days):
            # Répartition en trois colonnes
            col = cols[0] if i < 3 else (cols[1] if i < 6 else cols[2])
            with col:
                st.subheader(day)
                for meal in meals:
                    recette_choices = [""] + st.session_state.recipes_df["Name"].tolist()
                    recipe_choice = st.selectbox(
                        f"{meal} :",
                        options=recette_choices,
                        key=f"{day}_{meal}"
                    )
                    selections.append((day, meal, recipe_choice))

        submit = st.form_submit_button("💾 Enregistrer le plan")
        if submit:
            df = pd.DataFrame(selections, columns=["Day", "Meal", "Recipe"])
            # On enlève les choix vides
            df = df[df["Recipe"] != ""].reset_index(drop=True)
            st.session_state.mealplan_df = df
            st.success("Plan de la semaine enregistré.")

    st.markdown("**Plan actuel**")
    if st.session_state.mealplan_df.empty:
        st.info("Aucun plan enregistré.")
    else:
        st.table(st.session_state.mealplan_df)

# ----------------------------------------------------------------
# SECTION 3 : GÉNÉRER LA LISTE DE COURSES
# ----------------------------------------------------------------
elif section == "Liste de courses":
    st.header("Liste de courses générée")
    if st.session_state.mealplan_df.empty:
        st.info("Veuillez d'abord planifier vos repas.")
    else:
        # Agrégation des ingrédients
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        for recette_name in st.session_state.mealplan_df["Recipe"]:
            row = st.session_state.recipes_df[st.session_state.recipes_df["Name"] == recette_name]
            if not row.empty:
                ing_list = parse_ingredients(row.iloc[0]["Ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    if total_ingredients[clé]["unit"] and total_ingredients[clé]["unit"] != unit:
                        # Si unités différentes, avertir
                        st.warning(f"Unité différente pour '{clé}', vérifiez manuellement.")
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        # Construction du DataFrame de la liste de courses
        shopping_data = []
        for ing, vals in total_ingredients.items():
            shopping_data.append({
                "Ingrédient": ing,
                "Quantité": vals["quantity"],
                "Unité": vals["unit"]
            })
        shopping_df = pd.DataFrame(shopping_data)
        st.table(shopping_df)

# ----------------------------------------------------------------
# SECTION 4 : IMPRESSION DE LA LISTE DE COURSES
# ----------------------------------------------------------------
else:  # section == "Impression"
    st.header("Liste de courses imprimable")
    if st.session_state.mealplan_df.empty:
        st.info("Veuillez d'abord planifier vos repas pour obtenir la liste de courses.")
    else:
        total_ingredients = defaultdict(lambda: {"quantity": 0, "unit": ""})
        for recette_name in st.session_state.mealplan_df["Recipe"]:
            row = st.session_state.recipes_df[st.session_state.recipes_df["Name"] == recette_name]
            if not row.empty:
                ing_list = parse_ingredients(row.iloc[0]["Ingredients"])
                for ing in ing_list:
                    clé = ing["ingredient"]
                    qty = ing["quantity"]
                    unit = ing["unit"]
                    total_ingredients[clé]["quantity"] += qty
                    total_ingredients[clé]["unit"] = unit

        shopping_data = []
        for ing, vals in total_ingredients.items():
            shopping_data.append({
                "Ingrédient": ing,
                "Quantité": vals["quantity"],
                "Unité": vals["unit"]
            })
        shopping_df = pd.DataFrame(shopping_data)

        st.markdown("---")
        st.write("## Liste de courses à imprimer")
        st.table(shopping_df)

# ----------------------------------------------------------------
# INSTRUCTIONS DANS LA BARRE LATÉRALE
# ----------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.write(
    "**Instructions pour lancer cette app en local :**\\n"
    "1. Installez Streamlit : `pip install streamlit pandas`\\n"
    "2. Placez ce fichier en tant que `app.py` dans votre projet.\\n"
    "3. Lancez : `streamlit run app.py`\\n"
    "4. Ouvrez l’URL locale affichée dans votre navigateur."
)
"""

# On sauve le fichier à l’endroit /mnt/data pour que vous puissiez le télécharger
with open("/mnt/data/app.py", "w") as f:
    f.write(app_py_content)

# Affichez simplement le chemin pour le lien de téléchargement
"/mnt/data/app.py"
