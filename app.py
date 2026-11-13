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
    fs_req = st.number_input("Coefficient de sécurité requis au poinçonnement", 1.0, 5.0, 2.0, 0.1)
    st.caption("Poinçonnement : kp = 1 pour les sols frottants (sable). "
               "Préchargement testé par pas de 0,1 m : 0,1 / 0,2 / 0,3 ...")
 
 
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
DEFAUT = pd.DataFrame([
    [1, "q2m", "SP-PRA1922-01+PZ, SCP1_APD_COM+PZ", 1.546, 16.019, 1 / 3, 24.0, 8.97],
    [1, "q2mg", "SP-PRA1922-01+PZ, SCP1_APD_COM+PZ", 4.783, 90.118, 0.5, 6.0, 8.97],
    [2, "q2m", "SP-OA-193+972, SP-PK193+950", 1.228, 11.967, 1 / 3, 6.0, 8.34],
    [2, "m", "SP-OA-193+972, SP-PK193+950", 1.058, 8.839, 0.5, 6.8, 8.34],
], columns=X.COLONNES)
if "table" not in st.session_state:
    st.session_state.table = DEFAUT.copy()
 
st.markdown("**Coller depuis Excel** : sélectionnez votre tableau dans Excel (avec ou sans la ligne "
            "d'en-têtes, les cellules fusionnées sont acceptées), copiez avec Ctrl+C, collez dans la "
            "case ci-dessous avec Ctrl+V, puis cliquez sur « Charger ». "
            "Colonnes attendues : " + " | ".join(X.COLONNES) + ".")
collage = st.text_area("Tableau collé depuis Excel", height=140, label_visibility="collapsed")
if st.button("Charger le tableau collé"):
    try:
        st.session_state.table = X.parse_modeles(collage)
        ok = True
    except Exception as e:
        ok = False
        st.error(f"Collage impossible : {e}")
    if ok:
        st.rerun()
 
if essais is not None and st.button("Recalculer Pl, Em et α depuis les essais"):
    t = st.session_state.table.copy()
    for i, r in t.iterrows():
        s = E.stats_essais(essais, r["Couches"], r["Sondages associés"])
        if s:
            t.loc[i, ["Pl", "Em"]] = [s["Pl"], s["Em"]]
            a = E.alpha_menard(r["Couches"], s["EmPl"])
            if a:
                t.loc[i, "α"] = a
        else:
            st.warning(f"Modèle {r['Modèle']} / {r['Couches']} : aucun essai trouvé.")
    st.session_state.table = t
    st.rerun()
 
table = st.data_editor(st.session_state.table, num_rows="dynamic",
                       use_container_width=True, hide_index=True)
st.caption("Une ligne par couche, de la surface vers la profondeur. Vous pouvez aussi modifier "
           "les cellules directement ici.")
 
# ---------- 3. Calcul ----------
if st.button("Calculer", type="primary"):
    if essais is None:
        st.error("Chargez d'abord le classeur des essais (étape 1) : il sert au Pl min du poinçonnement.")
    else:
        modeles, punch, avert = X.calculer_tout(table, essais, P, seuil, fs_req)
        if not modeles:
            st.error("Aucun modèle complet dans le tableau.")
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
 
