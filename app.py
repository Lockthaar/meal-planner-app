import streamlit as st
import pandas as pd

# -----------------------------------------------------------------------------
# 1) INITIALISATION DE L’ÉTAT
# -----------------------------------------------------------------------------
if "recipes" not in st.session_state:
    st.session_state.recipes = []
    st.session_state.next_recipe_id = 1
if "ing_count" not in st.session_state:
    st.session_state.ing_count = 1

# -----------------------------------------------------------------------------
# PAGE MES RECETTES
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Batchist – Mes recettes")
st.title("📋 Mes recettes")

# Colonnes : 2/3 pour le formulaire, 3/3 pour la preview
col_form, col_preview = st.columns([2, 3])

# ➊ Bouton global pour ajouter une ligne d’ingrédient manuel
with col_form:
    st.write("## Ajouter une nouvelle recette")
    st.write("**Mode manuel :**")
    if st.button("➕ Ingrédient", key="add_ing"):
        st.session_state.ing_count += 1

# ➋ Formulaire d’ajout (manuel ou import)
with col_form.form("recipe_form", clear_on_submit=False):
    # Nom de la recette
    name = st.text_input("Nom de la recette")

    # Choix du mode
    mode = st.radio("Mode d’ajout", ["Manuel", "Importer"], horizontal=True)

    # Si on importe : copier/coller ou fichier .txt
    parsed_ingredients = []
    if mode == "Importer":
        raw_text = st.text_area(
            "Copiez-collez votre liste (une ligne = ingrédient, quantité, unité)", 
            height=150
        )
        uploaded = st.file_uploader("…ou importez un fichier .txt", type=["txt"])
        if uploaded:
            try:
                raw_text = uploaded.getvalue().decode()
            except:
                st.error("Impossible de décoder le fichier.")
        if raw_text:
            for line in raw_text.splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) == 3:
                    nm, qt_str, ut = parts
                    try:
                        qt = float(qt_str)
                    except:
                        qt = 0.0
                    parsed_ingredients.append({"name": nm, "qty": qt, "unit": ut})
        st.write("#### Ingrédients importés")
        st.table(pd.DataFrame(parsed_ingredients))

    # Si mode manuel : on affiche les champs dynamiques
    manual_ingredients = []
    if mode == "Manuel":
        st.write("#### Ingrédients manuels")
        cols = st.columns([3, 1, 1])
        for i in range(st.session_state.ing_count):
            with cols[0]:
                nm = st.text_input(f"Ingréd. #{i+1}", key=f"ing_nm_{i}")
            with cols[1]:
                qt = st.number_input(f"Qté #{i+1}", 0.0, 10000.0, key=f"ing_qt_{i}")
            with cols[2]:
                ut = st.selectbox(f"Unité #{i+1}", ["g", "kg", "ml", "l", "u"], key=f"ing_ut_{i}")
            manual_ingredients.append({"name": nm, "qty": qt, "unit": ut})

    # Instructions et image
    instructions = st.text_area("Instructions", height=120)
    image_url    = st.text_input("URL de l’image (placeholder OK)", "https://via.placeholder.com/150")

    # Bouton de soumission
    submitted = st.form_submit_button("Ajouter la recette")
    if submitted:
        if not name.strip():
            st.error("Le nom de la recette est requis.")
        else:
            ingredients = parsed_ingredients if mode == "Importer" else manual_ingredients
            # Retirer les lignes vides
            ingredients = [ing for ing in ingredients if ing["name"].strip()]
            if not ingredients:
                st.error("Au moins un ingrédient doit être renseigné.")
            else:
                rid = st.session_state.next_recipe_id
                st.session_state.recipes.append({
                    "id": rid,
                    "name": name.strip(),
                    "ingredients": ingredients,
                    "instructions": instructions.strip(),
                    "image": image_url.strip(),
                })
                st.session_state.next_recipe_id += 1
                # reset
                st.session_state.ing_count = 1
                st.success(f"Recette **{name}** ajoutée !")
                st.experimental_rerun()  # recharge pour vider le form

# ➌ Aperçu en direct de ce qui vient d'être saisi
with col_preview:
    st.write("## Aperçu de la recette")
    if submitted:
        st.info("La recette a été ajoutée, regardez la liste ci-dessous.")
    if mode == "Importer":
        if parsed_ingredients:
            st.table(pd.DataFrame(parsed_ingredients))
    else:
        if manual_ingredients:
            st.table(pd.DataFrame(manual_ingredients))
    st.write("### Instructions")
    st.write(instructions)
    st.image(image_url, use_column_width=True)

# ➍ Liste des recettes existantes
st.write("---")
st.write("## Vos recettes enregistrées")
if not st.session_state.recipes:
    st.info("Aucune recette pour le moment.")
else:
    for r in st.session_state.recipes:
        st.write("---")
        c1, c2 = st.columns([1, 4])
        with c1:
            st.image(r["image"], use_column_width=True)
        with c2:
            st.subheader(r["name"])
            st.table(pd.DataFrame(r["ingredients"]))
            st.write(r["instructions"])
            b1, b2 = st.columns(2)
            if b1.button("🗑️ Supprimer", key=f"del_{r['id']}"):
                st.session_state.recipes = [
                    rec for rec in st.session_state.recipes if rec["id"] != r["id"]
                ]
                st.experimental_rerun()
            if b2.button("🔗 Partager", key=f"share_{r['id']}"):
                st.info("URL à partager : " + st.runtime.get_url())
