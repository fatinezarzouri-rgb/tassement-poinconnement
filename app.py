from hashlib import sha256
from io import BytesIO

import pandas as pd
import streamlit as st

from engine import lire_classeur
from export_excel import exporter
from modeles import (
    COLONNES, POINCONNEMENT, SYNTHESE, calculer, depuis_classeur, groupes, lire_collage,
)

st.set_page_config(page_title="Tassement et poinçonnement", layout="wide")
st.title("Tassement et poinçonnement des remblais")

st.subheader("1. Essais pressiométriques")
st.caption("Colonne A = famille · D = nom du sondage · I = Pl (MPa) · J = Em (MPa). Les données commencent à la ligne 3.")
fichier = st.file_uploader("Importer le classeur Excel", type=["xlsx", "xlsm"])
if not fichier:
    st.info("Importe le classeur pour afficher les modèles et préparer l’export des résultats.")
    st.stop()

original = fichier.getvalue()
identifiant = sha256(original).hexdigest()
if st.session_state.get("source_id") != identifiant:
    try:
        essais, modeles, valeurs = lire_classeur(BytesIO(original))
    except Exception as erreur:
        st.error(f"Import impossible. {erreur}")
        st.stop()
    st.session_state.update(
        source_id=identifiant, source_essais=essais, source_valeurs=valeurs,
        table=depuis_classeur(modeles), version_table=0, resultat=None,
    )

essais = st.session_state.source_essais
valeurs = st.session_state.source_valeurs
st.success(f"{len(essais):,} lignes d’essais importées.".replace(",", " "))

with st.sidebar:
    st.header("Géométrie du remblai")
    champs = [
        ("largeur", "Largeur de plateforme (m)", 13.0, 0.01, 0.5),
        ("pente", "Pente (H/V)", 2.0, 0.01, 0.1),
        ("surcharge", "Surcharge (kPa)", 30.0, 0.0, 5.0),
        ("gamma", "Poids volumique (kN/m³)", 20.0, 0.01, 0.5),
        ("pas", "Pas des tranches (m)", 0.5, 0.001, 0.1),
        ("zmax", "Profondeur maximale d’influence (m)", 28.0, 0.01, 1.0),
    ]
    p = {}
    for nom, label, defaut, minimum, pas in champs:
        valeur = valeurs.get(nom)
        initial = float(valeur) if isinstance(valeur, (int, float)) and valeur >= minimum else defaut
        p[nom] = st.number_input(label, min_value=minimum, value=initial, step=pas,
                                 format="%.3f", key=f"{identifiant}_{nom}")
    st.header("Critères de vérification")
    seuil = st.number_input("Écart admissible (cm)", min_value=0.01, value=1.0, step=0.1)
    fs_requis = st.number_input("Facteur de sécurité requis", min_value=0.01, value=2.0, step=0.1)
    plafond = st.slider("Hauteur maximale de préchargement à tester (m)", 0.1, 10.0, 3.0, 0.1)
    st.caption("Préchargement par paliers de 0,10 m. Kp = 1 pour les sables.")

st.subheader("2. Modèles géotechniques")
with st.expander("Coller un tableau depuis Excel"):
    st.write("Sélectionne les colonnes A à H du tableau Modèle, puis colle-les ici. "
             "Tu peux aussi inclure une 9ᵉ colonne pour Pl min. Les en-têtes sont acceptés.")
    collage = st.text_area("Tableau Excel à coller", height=140, key=f"{identifiant}_collage")
    if st.button("Importer le tableau collé"):
        try:
            lignes_collees = lire_collage(collage)
            groupes(lignes_collees)
        except ValueError as erreur:
            st.error(str(erreur))
        else:
            st.session_state.table = lignes_collees
            st.session_state.version_table += 1
            st.session_state.resultat = None
            st.success("Tableau importé. Vérifie les couches avant de calculer.")

st.caption("Une ligne par couche, de la surface vers la profondeur. Pour les cellules fusionnées, "
           "les valeurs du modèle, des sondages et de la hauteur sont reprises sur ses lignes suivantes.")
df = pd.DataFrame(st.session_state.table, columns=COLONNES)
for colonne in COLONNES[3:]:
    df[colonne] = pd.to_numeric(df[colonne], errors="coerce").astype(float)
table = st.data_editor(df, num_rows="dynamic", hide_index=True,
                       column_config={"Modèle": st.column_config.TextColumn(),
                                      "Couches": st.column_config.TextColumn(),
                                      "Sondages associés": st.column_config.TextColumn(width="large")},
                       key=f"{identifiant}_table_{st.session_state.version_table}")
recalculer = st.checkbox("Recalculer Pl, Em, α et Pl min à partir des essais associés")
st.caption("Au poinçonnement, seul le Pl min de la couche d’assise est utilisé. "
           "S’il est vide, l’application le recherche dans les sondages associés.")

lignes = list(table.itertuples(index=False, name=None))
signature = (table.to_csv(index=False), tuple(p.items()), seuil, fs_requis, recalculer, plafond)
if st.button("Calculer les modèles", type="primary"):
    st.session_state.resultat = None
    try:
        modeles = groupes(lignes)
        resultats = calculer(modeles, essais, p, seuil, fs_requis, recalculer, plafond)
        sortie = exporter(original, modeles, resultats)
    except Exception as erreur:
        st.error(str(erreur))
    else:
        st.session_state.resultat = (signature, resultats, sortie)

stocke = st.session_state.resultat
if stocke and stocke[0] != signature:
    st.info("Les données ont changé. Relance le calcul pour actualiser les résultats.")
if stocke and stocke[0] == signature:
    _, resultats, sortie = stocke
    st.subheader("3. Résultats")
    synthese, poinconnement, detail = st.tabs(["Synthèse", "Poinçonnement", "Détail par modèle"])
    with synthese:
        st.dataframe(pd.DataFrame([r["synthese"] for r in resultats], columns=SYNTHESE).round(3), hide_index=True)
    with poinconnement:
        st.dataframe(pd.DataFrame([r["poinconnement"] for r in resultats], columns=POINCONNEMENT).round(3),
                     hide_index=True)
    with detail:
        for r in resultats:
            with st.expander(f"Modèle {r['modele']}"):
                det = pd.DataFrame(r["detail"]).set_index("z (m)")
                courbes = det[["ΔW avec surcharge (cm)", "ΔW référence (cm)"]].cumsum()
                courbes.columns = ["Avec surcharge", "Sans surcharge"]
                st.line_chart(courbes)
                st.dataframe(det.round(6))
                if r["pre"]:
                    st.markdown(f"**Préchargement retenu : {r['synthese'][5]:.1f} m**")
                    st.dataframe(pd.DataFrame(r["pre"][3]).round(6), hide_index=True)
