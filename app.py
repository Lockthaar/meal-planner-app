import streamlit as st
import pandas as pd

# -----------------------------------------------------------------------------
# 1) ÉTAT INITIAL
# -----------------------------------------------------------------------------
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 0
if "profile" not in st.session_state:
    st.session_state.profile = {"household": None, "meals_per_day": None}
if "recipes" not in st.session_state:
    st.session_state.recipes = []
    st.session_state.next_recipe_id = 1
if "ing_count" not in st.session_state:
    st.session_state.ing_count = 1

# -----------------------------------------------------------------------------
# 2) ONBOARDING
# -----------------------------------------------------------------------------
if st.session_state.onboard_step == 0:
    st.set_page_config(layout="wide", page_title="Bienvenue")
    st.markdown("<h1 style='text-align:center;'>Bienvenue sur Batchist!</h1>", unsafe_allow_html=True)
    st.write("## Comment vivez-vous ?")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.image("https://via.placeholder.com/150?text=Solo", use_column_width=True)
        if st.button("👤 Solo"):
            st.session_state.profile["household"] = "Solo"
            st.session_state.onboard_step = 1
    with c2:
        st.image("https://via.placeholder.com/150?text=Couple", use_column_width=True)
        if st.button("👫 Couple"):
            st.session_state.profile["household"] = "Couple"
            st.session_state.onboard_step = 1
    with c3:
        st.image("https://via.placeholder.com/150?text=Famille", use_column_width=True)
        if st.button("👪 Famille"):
            st.session_state.profile["household"] = "Famille"
            st.session_state.onboard_step = 1
    st.stop()

if st.session_state.onboard_step == 1:
    st.set_page_config(layout="wide", page_title="Configuration")
    st.markdown("<h1 style='text-align:center;'>Presque prêt ! 🎉</h1>", unsafe_allow_html=True)
    st.write("## Combien de repas par jour ?")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.image("https://via.placeholder.com/150?text=2+repas", use_column_width=True)
        if st.button("2 repas"):
            st.session_state.profile["meals_per_day"] = 2
            st.session_state.onboard_step = 2
    with c2:
        st.image("https://via.placeholder.com/150?text=3+repas", use_column_width=True)
        if st.button("3 repas"):
            st.session_state.profile["meals_per_day"] = 3
            st.session_state.onboard_step = 2
    with c3:
        st.image("https://via.placeholder.com/150?text=4+repas", use_column_width=True)
        if st.button("4 repas"):
            st.session_state.profile["meals_per_day"] = 4
            st.session_state.onboard_step = 2
    st.stop()

# -----------------------------------------------------------------------------
# 3) APPLICATION PRINCIPALE
# -----------------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Batchist")
st.markdown("<h1 style='text-align:center;'>🥣 Batchist</h1>", unsafe_allow_html=True)
st.write("---")

# Menu horizontal
pages = ["Accueil", "Mes recettes", "Planificateur", "Liste de courses", "Conseils", "Profil"]
page = st.radio("", pages, horizontal=True)
st.write("---")

# -- Page Accueil --
if page == "Accueil":
    p = st.session_state.profile
    st.header("🏠 Tableau de bord")
    st.markdown(f"- **Foyer:** {p['household']}")
    st.markdown(f"- **Repas/jour:** {p['meals_per_day']}")
    st.write("Naviguez ci-dessous pour ajouter vos recettes, planifier, etc.")

# -- Page Mes recettes --
elif page == "Mes recettes":
    st.header("📋 Mes recettes")

    # ➊ Bouton ➕ Ingrédient (hors du form)
    if st.button("➕ Ingrédient"):
        st.session_state.ing_count += 1

    # ➋ Formulaire d’ajout avec clear_on_submit pour remettre à zéro
    with st.form("recipe_form", clear_on_submit=True):
        name = st.text_input("Nom de la recette")

        st.write("#### Ingrédients manuels")
        cols = st.columns([3, 1, 1])
        manual_ings = []
        for i in range(st.session_state.ing_count):
            with cols[0]:
                nm = st.text_input(f"Ingrédient #{i+1}", key=f"nm_{i}")
            with cols[1]:
                qt = st.number_input(f"Qté #{i+1}", 0.0, 10000.0, key=f"qt_{i}")
            with cols[2]:
                ut = st.selectbox(f"Unité #{i+1}", ["g","kg","ml","l","u"], key=f"ut_{i}")
            manual_ings.append({"name": nm, "qty": qt, "unit": ut})

        instr = st.text_area("Instructions", height=120)
        img   = st.text_input("URL image (placeholder OK)", "https://via.placeholder.com/150")

        submitted = st.form_submit_button("Ajouter la recette")
        if submitted:
            if not name.strip():
                st.error("⚠️ Le nom de la recette est requis.")
            else:
                # filtrage des lignes vides
                manual_ings = [ing for ing in manual_ings if ing["name"].strip()]
                if not manual_ings:
                    st.error("⚠️ Ajoutez au moins un ingrédient.")
                else:
                    rid = st.session_state.next_recipe_id
                    st.session_state.recipes.append({
                        "id": rid,
                        "name": name.strip(),
                        "ingredients": manual_ings,
                        "instructions": instr.strip(),
                        "image": img.strip(),
                    })
                    st.session_state.next_recipe_id += 1
                    st.session_state.ing_count = 1
                    st.success(f"✅ Recette « {name} » ajoutée !")

    st.write("---")
    st.write("## Vos recettes enregistrées")
    if not st.session_state.recipes:
        st.info("Aucune recette pour l'instant.")
    else:
        for r in st.session_state.recipes:
            st.markdown("—")
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
                        x for x in st.session_state.recipes if x["id"] != r["id"]
                    ]
                    st.experimental_rerun()
                if b2.button("🔗 Partager", key=f"share_{r['id']}"):
                    st.info("URL à partager : " + st.runtime.get_url())

# -- Page Planificateur --
elif page == "Planificateur":
    st.header("📅 Planificateur de la semaine")
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    meals = ["Petit-déj","Déjeuner","Dîner"]
    plan = []
    with st.form("plan_form"):
        for chunk in (days[:3], days[3:6], days[6:]):
            cols = st.columns(3)
            for col, day in zip(cols, chunk + [""]*(3-len(chunk))):
                if not day:
                    col.write("")
                    continue
                col.markdown(f"**{day}**")
                for m in meals:
                    sel = col.selectbox(m, [""] + [r["name"] for r in st.session_state.recipes], key=f"{day}_{m}")
                    plan.append({"Day":day,"Meal":m,"Recipe":sel})
        if st.form_submit_button("Enregistrer"):
            st.session_state.plan_df = pd.DataFrame(plan)
            st.success("Planning enregistré !")
    if "plan_df" in st.session_state:
        st.table(st.session_state.plan_df)

# -- Page Liste de courses --
elif page == "Liste de courses":
    st.header("🛒 Liste de courses")
    if "plan_df" not in st.session_state or st.session_state.plan_df.empty:
        st.info("Planifiez d'abord vos repas.")
    else:
        agg = {}
        for nm in st.session_state.plan_df["Recipe"].unique():
            rec = next((r for r in st.session_state.recipes if r["name"]==nm), None)
            if rec:
                for ing in rec["ingredients"]:
                    key = (ing["name"], ing["unit"])
                    agg[key] = agg.get(key, 0) + ing["qty"]
        dfc = pd.DataFrame([
            {"Item": k[0], "Unit": k[1], "Qty": v}
            for k, v in agg.items()
        ])
        st.table(dfc)
        csv = dfc.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Télécharger CSV", csv, "courses.csv", "text/csv")

# -- Page Conseils --
elif page == "Conseils":
    st.header("💡 Conseils & Astuces")
    st.write("- Astuce 1")
    st.write("- Astuce 2")

# -- Page Profil --
elif page == "Profil":
    st.header("👤 Profil")
    p = st.session_state.profile
    st.markdown(f"- **Foyer :** {p['household']}")
    st.markdown(f"- **Repas/jour :** {p['meals_per_day']}")
    if st.button("🔄 Refaire l’onboarding"):
        st.session_state.onboard_step = 0
        st.experimental_rerun()
