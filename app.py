import io
import pandas as pd
import streamlit as st
import engine as E
import export as X
 
st.set_page_config(page_title="Tassement & poinçonnement", layout="wide")
st.title("Calcul de tassement et de poinçonnement des remblais")
 
# ---------- Paramètres ----------
with st.sidebar:
    st.header("Remblai")
    P = dict(
        largeur=st.number_input("Largeur plateforme (m)", 1.0, 100.0, 13.0, 0.5),
        pente=st.selectbox("Pente (H/V)", [1.0, 1.5, 2.0, 3.0], index=2),
        surcharge=st.number_input("Surcharge q (kPa)", 0.0, 200.0, 30.0, 5.0),
        gamma=st.number_input("Poids volumique (kN/m³)", 10.0, 30.0, 20.0, 0.5),
        pas=st.number_input("Pas de calcul Δz (m)", 0.1, 2.0, 0.5, 0.1),
        zmax=st.number_input("Profondeur max d'influence (m)", 5.0, 100.0, 28.0, 1.0),
    )
    st.header("Critères")
    seuil = st.number_input("Écart toléré W avec/sans charge (cm)", 0.1, 10.0, 1.0, 0.1)
    fs_req = st.number_input("Coefficient de sécurité requis au poinçonnement", 1.0, 5.0, 1.5, 0.1)
 
 
@st.cache_data(show_spinner="Lecture des essais...")
def lire(octets):
    return X.lire_essais_brut(io.BytesIO(octets))
 
 
# ---------- 1. Essais pressiométriques ----------
st.subheader("1. Essais pressiométriques")
st.markdown(
    "Chargez le classeur Excel. Dans la feuille « essais pressiométriques » : "
    "**colonne A = famille**, **colonne D = nom du sondage**, **colonne I = Pl**, "
    "**colonne J = Em**. Les données commencent à la **ligne 3**.")
up = st.file_uploader("Classeur Excel des essais", type=["xlsx", "xlsm"])
raw = essais = nom_essais = None
if up is not None:
    try:
        raw, essais, nom_essais = lire(up.getvalue())
        st.success(f"{len(essais)} essais lus (feuille « {nom_essais} »).")
    except Exception as e:
        st.error(f"Lecture impossible : {e}")
 
# ---------- 2. Modèles géotechniques ----------
st.subheader("2. Modèles géotechniques")
st.markdown(
    "Dans Excel, sélectionnez votre tableau avec les colonnes **dans cet ordre** : "
    "**Modèle | Couches | Sondages associés | Épaisseurs (m) | Hauteur maximal (m)**. "
    "Copiez avec Ctrl+C, collez dans la case ci-dessous avec Ctrl+V (les cellules fusionnées sont "
    "acceptées), puis cliquez sur « Charger le tableau ». Pl, Em et α sont calculés automatiquement "
    "à partir des essais.")
collage = st.text_area("Coller le tableau depuis Excel", height=160,
                       placeholder="Modèle\tCouches\tSondages associés\tÉpaisseurs (m)\tHauteur maximal (m)")
 
if st.button("Charger le tableau"):
    if essais is None:
        st.error("Chargez d'abord le classeur des essais (étape 1) : Pl, Em et α en sont déduits.")
    elif not collage.strip():
        st.error("Collez d'abord le tableau dans la case ci-dessus.")
    else:
        try:
            tab, avert = X.completer_modeles(X.parse_modeles(collage), essais)
            st.session_state.table = tab
            st.session_state.pop("res", None)
            for a in avert:
                st.warning(a)
        except Exception as e:
            st.error(f"Chargement impossible : {e}")
 
# ---------- 3. Calcul ----------
if "table" in st.session_state:
    st.markdown("**Tableau des modèles, avec Pl, Em et α calculés** (modifiable si besoin)")
    table = st.data_editor(st.session_state.table, num_rows="dynamic",
                           use_container_width=True, hide_index=True)
    if st.button("Calculer", type="primary"):
        modeles, punch, avert = X.calculer_tout(table, essais, P, seuil, fs_req)
        if not modeles:
            st.error("Aucun modèle complet dans le tableau (Pl, Em, α, épaisseur et hauteur sont nécessaires).")
        else:
            for a in avert:
                st.warning(a)
            xls = X.construire_excel(table, raw, nom_essais, P, seuil, modeles, punch)
            st.session_state.res = (modeles, punch, xls)
 
if "res" in st.session_state:
    modeles, punch, xls = st.session_state.res
    st.subheader("3. Résultats")
    S = pd.DataFrame([{
        "Modèle": m["m"], "W avec charge (cm)": round(m["w_avec"], 2),
        "W sans charge (cm)": round(m["w_sans"], 2),
        "Écart (cm)": round(m["w_avec"] - m["w_sans"], 2), "Spécification": m["spec"],
        "hPre (m)": m["pre"]["hp"] if m["pre"] else "—",
        "W avec / sans après préchargement (cm)":
            f"{m['pre']['w_avec']:.2f} / {m['pre']['w_sans']:.2f}" if m["pre"] else "—",
    } for m in modeles])
    st.markdown("**Synthèse des tassements**")
    st.dataframe(S, use_container_width=True, hide_index=True)
    st.markdown("**Poinçonnement (1ʳᵉ couche)**")
    st.dataframe(punch.style.map(
        lambda v: "color:#b00020;font-weight:bold" if v == "NON VÉRIFIÉ"
        else "color:#1b7f3b;font-weight:bold" if v == "OK" else "", subset=["Vérification"]),
        use_container_width=True, hide_index=True)
    for m in modeles:
        with st.expander(f"Détail, schéma et courbe — modèle {m['m']}"):
            st.image(X.schema_png(m["h"], P["largeur"], P["pente"], P["surcharge"]))
            d = m["det"]
            c = d.assign(Wcum_avec=d["W_avec"].cumsum(), Wcum_sans=d["W_sans"].cumsum()).set_index("z")
            st.line_chart(c[["Wcum_avec", "Wcum_sans"]], x_label="z (m)",
                          y_label="Tassement cumulé (cm)")
            st.dataframe(d.round(4), use_container_width=True, hide_index=True)
            if m["pre"]:
                st.markdown(f"**Avec préchargement hPre = {m['pre']['hp']:.1f} m**")
                st.image(X.schema_png(m["h"], P["largeur"], P["pente"], P["surcharge"], m["pre"]["hp"]))
    st.download_button("Télécharger le classeur Excel des résultats", xls, "resultats_tassement.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
 
