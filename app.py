import streamlit as st
import pandas as pd

# ---------------------------
# 1) STATE INITIALIZATION
# ---------------------------
if "onboard_step" not in st.session_state:
    st.session_state.onboard_step = 0
if "profile" not in st.session_state:
    st.session_state.profile = {
        "household": None,
        "meals_per_day": None
    }
if "recipes" not in st.session_state:
    st.session_state.recipes = []
    st.session_state.next_recipe_id = 1
if "extras" not in st.session_state:
    st.session_state.extras = []
    st.session_state.next_extra_id = 1
if "mealplan" not in st.session_state:
    st.session_state.mealplan = pd.DataFrame(columns=["Day","Meal","Recipe"])

# ---------------------------
# 2) ONBOARDING MODALS
# ---------------------------
def step1_modal():
    with st.modal("Comment vivez-vous ?"):
        st.markdown("### Sélectionnez votre type de foyer")
        c1, c2, c3 = st.columns(3)
        if c1.button("👤 Solo"):
            st.session_state.profile["household"] = "Solo"
            st.session_state.onboard_step = 1
            st.experimental_rerun()
        if c2.button("👫 Couple"):
            st.session_state.profile["household"] = "Couple"
            st.session_state.onboard_step = 1
            st.experimental_rerun()
        if c3.button("👪 Famille"):
            st.session_state.profile["household"] = "Famille"
            st.session_state.onboard_step = 1
            st.experimental_rerun()

def step2_modal():
    with st.modal("Combien de repas par jour souhaitez-vous préparer ?"):
        st.markdown("### Choisissez le nombre de repas quotidiens")
        cols = st.columns(3)
        for col, num in zip(cols, (2, 3, 4)):
            if col.button(f"{num} repas"):
                st.session_state.profile["meals_per_day"] = num
                st.session_state.onboard_step = 2
                st.experimental_rerun()

# Lancer le 1ᵉʳ modal
if st.session_state.onboard_step == 0:
    step1_modal()
    st.stop()

# Lancer le 2ᵉ modal
if st.session_state.onboard_step == 1:
    step2_modal()
    st.stop()

# ---------------------------
# 3) MAIN APP LAYOUT
# ---------------------------
st.set_page_config(layout="wide", page_title="Batchist")
st.markdown("<h1 style='text-align:center;'>🥣 Batchist</h1>", unsafe_allow_html=True)
st.write("---")

# Top navigation
pages = ["Accueil", "Mes recettes", "Extras", "Planificateur", "Liste de courses", "Conseils", "Profil"]
page = st.radio("", pages, horizontal=True)

# ---------------------------
# 4) PAGE: ACCUEIL
# ---------------------------
if page == "Accueil":
    st.header("🏠 Tableau de bord")
    prof = st.session_state.profile
    st.markdown(f"- **Type de foyer :** {prof['household']}")
    st.markdown(f"- **Repas/jour :** {prof['meals_per_day']}")
    st.write("Utilisez la navigation ci-dessus pour gérer vos recettes, extras, planning, etc.")

# ---------------------------
# 5) PAGE: MES RECETTES
# ---------------------------
elif page == "Mes recettes":
    st.header("📋 Mes recettes")
    left, right = st.columns([2,3])
    with left.form("form_add_recipe"):
        name = st.text_input("Nom de la recette")
        st.markdown("**Ingrédients**")
        ingredients = []
        n = st.number_input("Nombre d'ingrédients", 1, 20, 1, key="n_ing")
        cols = st.columns([3,1,1])
        for i in range(n):
            nm = cols[0].text_input(f"Nom #{i+1}", key=f"rec_ing_nm_{i}")
            qt = cols[1].number_input(f"Qté #{i+1}", 0.0, 10000.0, step=1.0, key=f"rec_ing_qt_{i}")
            ut = cols[2].selectbox(f"Unité #{i+1}", ["g","kg","ml","l","u"], key=f"rec_ing_ut_{i}")
            ingredients.append({"name":nm,"qty":qt,"unit":ut})
        instr = st.text_area("Instructions")
        img = st.text_input("URL image (placeholder)", "https://via.placeholder.com/150")
        if st.form_submit_button("Ajouter la recette"):
            rid = st.session_state.next_recipe_id
            st.session_state.recipes.append({
                "id": rid, "name": name,
                "ingredients": ingredients,
                "instructions": instr, "image": img
            })
            st.session_state.next_recipe_id += 1
            st.success("Recette ajoutée !")

    st.markdown("### Vos recettes existantes")
    for r in st.session_state.recipes:
        st.markdown("---")
        c1, c2 = st.columns([1,3])
        with c1:
            st.image(r["image"], use_column_width=True)
        with c2:
            st.subheader(r["name"])
            st.table(pd.DataFrame(r["ingredients"]))
            st.write(r["instructions"])
            b1, b2, b3 = st.columns(3)
            if b1.button("✏️ Modifier", key=f"mod_r_{r['id']}"):
                st.info("Fonction d'édition non implémentée.")
            if b2.button("🗑️ Supprimer", key=f"del_r_{r['id']}"):
                st.session_state.recipes = [x for x in st.session_state.recipes if x["id"]!=r["id"]]
                st.experimental_rerun()
            if b3.button("🔗 Partager", key=f"share_r_{r['id']}"):
                st.info("Partagez cette URL : " + st.runtime.get_url())

# ---------------------------
# 6) PAGE: EXTRAS
# ---------------------------
elif page == "Extras":
    st.header("🧩 Extras (boissons, maison, animaux)")
    left, right = st.columns([2,3])
    with left.form("form_add_extra"):
        name = st.text_input("Nom de l'extra")
        qty  = st.number_input("Quantité", 0.0, 10000.0, step=1.0)
        unit = st.selectbox("Unité", ["g","kg","ml","l","u"])
        if st.form_submit_button("Ajouter extra"):
            eid = st.session_state.next_extra_id
            st.session_state.extras.append({"id":eid,"name":name,"qty":qty,"unit":unit})
            st.session_state.next_extra_id += 1
            st.success("Extra ajouté !")
    st.markdown("### Vos extras")
    for ex in st.session_state.extras:
        st.write(f"- {ex['name']} : {ex['qty']} {ex['unit']} ", end="")
        if st.button("🗑️", key=f"del_ex_{ex['id']}"):
            st.session_state.extras = [x for x in st.session_state.extras if x["id"]!=ex["id"]]
            st.experimental_rerun()

# ---------------------------
# 7) PAGE: PLANIFICATEUR
# ---------------------------
elif page == "Planificateur":
    st.header("📅 Planificateur de la semaine")
    days = ["Lundi","Mardi","Mercredi","Jeudi","Vendredi","Samedi","Dimanche"]
    meals = ["Petit-déj","Déjeuner","Dîner"]

    with st.form("form_plan"):
        plan = []
        # on crée deux rangées de 3 cartes, puis une rangée de 1 carte
        for chunk in (days[:3], days[3:6], days[6:]):
            cols = st.columns(3)
            for col, day in zip(cols, chunk + [""]*(3-len(chunk))):
                if not day: 
                    col.write("") 
                    continue
                col.markdown(
                    f"<div style='border:1px solid #666; border-radius:8px; padding:12px; margin-bottom:8px;'>"
                    f"<strong>{day}</strong></div>",
                    unsafe_allow_html=True
                )
                for meal in meals:
                    sel = col.selectbox(f"{meal} ", 
                        [""]+[r["name"] for r in st.session_state.recipes],
                        key=f"{day}_{meal}"
                    )
                    plan.append({"Day":day,"Meal":meal,"Recipe":sel})
        if st.form_submit_button("Enregistrer le planning"):
            st.session_state.mealplan = pd.DataFrame(plan)
            st.success("Planning enregistré !")

    st.markdown("### Aperçu du planning")
    st.table(st.session_state.mealplan)

# ---------------------------
# 8) PAGE: LISTE DE COURSES
# ---------------------------
elif page == "Liste de courses":
    st.header("🛒 Liste de courses")
    mp = st.session_state.mealplan
    agg = {}
    # recettes
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
        st.info("Aucun ingrédient à lister.")
    else:
        dfc = pd.DataFrame([{"Item":k[0],"Unit":k[1],"Qty":v} for k,v in agg.items()])
        st.table(dfc)
        csv = dfc.to_csv(index=False).encode()
        st.download_button("⬇️ Télécharger CSV", csv, "courses.csv", "text/csv")

# ---------------------------
# 9) PAGE: CONSEILS & ASTUCES
# ---------------------------
elif page == "Conseils":
    st.header("💡 Conseils & Astuces")
    st.write("- Astuce 1…")
    st.write("- Astuce 2…")

# ---------------------------
# 10) PAGE: PROFIL
# ---------------------------
elif page == "Profil":
    st.header("👤 Profil")
    p = st.session_state.profile
    st.markdown(f"- **Foyer :** {p['household']}")
    st.markdown(f"- **Repas/jour :** {p['meals_per_day']}")
    if st.button("Modifier le profil"):
        st.session_state.onboard_step = 0
        st.experimental_rerun()
