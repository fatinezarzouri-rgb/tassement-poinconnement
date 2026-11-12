import io
import pandas as pd
import streamlit as st
import engine as E

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
    kp = st.number_input("kp (sols frottants)", 0.1, 2.0, 1.0, 0.05,
                         help="Le classeur d'origine utilise kp = 1. À justifier selon le Fascicule 62 Titre V.")
    fs_req = st.number_input("Coefficient de sécurité requis au poinçonnement", 1.0, 5.0, 2.0, 0.1)

# ---------- 1. Essais pressiométriques ----------
st.subheader("1. Essais pressiométriques (facultatif)")
up = st.file_uploader("Classeur Excel des essais (1ère feuille, en-têtes ligne 2, colonnes A, D, I, J)",
                      type=["xlsx", "xlsm"])
essais = E.lire_essais(up) if up else None
if essais is not None:
    st.success(f"{len(essais)} essais lus.")

# ---------- 2. Modèles géotechniques ----------
st.subheader("2. Modèles géotechniques")
DEFAUT = pd.DataFrame([
    [1, "q2m",  "SP-PRA1922-01+PZ, SCP1_APD_COM+PZ", 1.546, 16.019, 1/3, 24.0, 8.97, 0.38],
    [1, "q2mg", "SP-PRA1922-01+PZ, SCP1_APD_COM+PZ", 4.783, 90.118, 0.5, 6.0, 8.97, 0.0],
    [2, "q2m",  "SP-OA-193+972, SP-PK193+950", 1.228, 11.967, 1/3, 6.0, 8.34, 0.95],
    [2, "m",    "SP-OA-193+972, SP-PK193+950", 1.058, 8.839, 0.5, 6.8, 8.34, 0.0],
], columns=["Modèle", "Couche", "Sondages", "Pl", "Em", "alpha", "Épaisseur", "H remblai", "Pl min"])
if "table" not in st.session_state:
    st.session_state.table = DEFAUT.copy()

if essais is not None and st.button("Calculer Pl, Em, α et Pl min depuis les essais"):
    t = st.session_state.table.copy()
    for i, r in t.iterrows():
        s = E.stats_essais(essais, r["Couche"], r["Sondages"])
        if s:
            t.loc[i, ["Pl", "Em"]] = [s["Pl"], s["Em"]]
            a = E.alpha_menard(r["Couche"], s["EmPl"])
            if a: t.loc[i, "alpha"] = a
            t.loc[i, "Pl min"] = s["Plmin"]
        else:
            st.warning(f"Modèle {r['Modèle']} / {r['Couche']} : aucun essai trouvé.")
    st.session_state.table = t

table = st.data_editor(st.session_state.table, num_rows="dynamic", use_container_width=True, hide_index=True)
st.caption("Une ligne par couche, dans l'ordre de la surface vers la profondeur. "
           "« Pl min » n'est utilisé que pour la 1ʳᵉ couche (poinçonnement).")

# ---------- 3. Calcul ----------
if st.button("Calculer", type="primary"):
    synth, punch, details = [], [], {}
    for m, g in table.dropna(subset=["Couche", "Em", "alpha", "Épaisseur"]).groupby("Modèle", sort=True):
        couches = [dict(nom=r["Couche"], Em=r["Em"], alpha=r["alpha"], ep=r["Épaisseur"]) for _, r in g.iterrows()]
        h = float(g["H remblai"].iloc[0])
        w_avec, w_sans, det = E.tassement(h, 0, couches, P, detail=True)
        ecart = w_avec - w_sans
        pre = E.precharge(h, couches, P, seuil) if abs(ecart) > seuil else None
        if abs(ecart) <= seuil:
            spec = "conforme"
        elif pre:
            spec = f"préchargement hPre = {pre[0]:.2f} m"
        else:
            spec = "préchargement insuffisant (> 3 m) : revoir le projet"
        synth.append({"Modèle": m, "W avec charge (cm)": round(w_avec, 2), "W sans charge (cm)": round(w_sans, 2),
                      "Écart (cm)": round(ecart, 2), "Spécification": spec,
                      "W avec/sans après préchargement (cm)": f"{pre[1]:.2f} / {pre[2]:.2f}" if pre else "—"})
        first = g.iloc[0]
        r = E.poinconnement(first["Couche"], first["Pl min"], h, first["Épaisseur"], P, kp)
        punch.append({"Modèle": m, "Couche": first["Couche"], "Pl min (MPa)": first["Pl min"],
                      "Méthode": r["methode"], "qapp (kPa)": round(r["qapp"], 1), "qmax (kPa)": round(r["qmax"], 1),
                      "F = qmax/qapp": round(r["F"], 2),
                      "Vérification": "OK" if r["F"] >= fs_req else "NON VÉRIFIÉ"})
        details[m] = det
    st.session_state.res = (pd.DataFrame(synth), pd.DataFrame(punch), details)

if "res" in st.session_state:
    S, Pn, D = st.session_state.res
    st.subheader("3. Résultats")
    st.markdown("**Tassements**"); st.dataframe(S, use_container_width=True, hide_index=True)
    st.markdown("**Poinçonnement (1ʳᵉ couche)**")
    st.dataframe(Pn.style.map(lambda v: "color:#b00020;font-weight:bold" if v == "NON VÉRIFIÉ" else
                                        "color:#1b7f3b" if v == "OK" else "", subset=["Vérification"]),
                 use_container_width=True, hide_index=True)
    for m, det in D.items():
        with st.expander(f"Détail et courbe — modèle {m}"):
            c = det.assign(Wcum_avec=det["W_avec"].cumsum(), Wcum_sans=det["W_sans"].cumsum()).set_index("z")
            st.line_chart(c[["Wcum_avec", "Wcum_sans"]], x_label="z (m)", y_label="Tassement cumulé (cm)")
            st.dataframe(det.round(4), use_container_width=True, hide_index=True)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        S.to_excel(xw, sheet_name="Synthese", index=False); Pn.to_excel(xw, sheet_name="Poinconnement", index=False)
        pd.DataFrame([P]).T.rename(columns={0: "valeur"}).to_excel(xw, sheet_name="Hypotheses")
        for m, det in D.items(): det.to_excel(xw, sheet_name=f"Modele {m}", index=False)
    st.download_button("Télécharger les résultats (Excel)", buf.getvalue(), "resultats_tassement.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
