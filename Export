"""Lecture des essais, collage depuis Excel, schéma du remblai et classeur Excel de résultats."""
import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
import engine as E
 
COLONNES = ["Modèle", "Couches", "Sondages associés", "Pl", "Em", "α",
            "Épaisseurs (m)", "Hauteur maximal (m)"]
 
 
# ====================== Lecture des essais ======================
def lire_essais_brut(fichier):
    """Retourne (feuille brute, essais [famille, sondage, Pl, Em], nom de la feuille).
    Colonnes lues : A = famille, D = sondage, I = Pl, J = Em ; données à partir de la ligne 3."""
    xl = pd.ExcelFile(fichier)
    noms = xl.sheet_names
    nom = next((n for n in noms if "essais" in E.norm(n)), noms[0])
    raw = pd.read_excel(xl, sheet_name=nom, header=None)
    if raw.shape[1] < 10:
        raise ValueError("La feuille des essais doit avoir au moins 10 colonnes (A à J).")
    essais = pd.DataFrame({"famille": raw[0], "sondage": raw[3], "Pl": raw[8], "Em": raw[9]}).iloc[2:]
    essais = essais.dropna(subset=["famille", "sondage"])
    return raw, essais, nom
 
 
# ====================== Collage depuis Excel ======================
def _num(s):
    s = str(s).strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        if "/" in s:
            a, b = s.split("/")
            return float(a) / float(b)
        return float(s)
    except ValueError:
        return float("nan")
 
 
def parse_modeles(text: str) -> pd.DataFrame:
    """Tableau copié depuis Excel (avec ou sans en-têtes, cellules fusionnées acceptées)."""
    df = pd.read_csv(io.StringIO(text), sep="\t", header=None, dtype=str,
                     keep_default_na=False, skip_blank_lines=True)
    if df.shape[1] < 8:
        raise ValueError(f"{df.shape[1]} colonne(s) trouvée(s), il en faut 8 : " + ", ".join(COLONNES))
    df = df.iloc[:, :8]
    df.columns = COLONNES
    df = df.apply(lambda c: c.str.strip()).replace("", np.nan)
    if np.isnan(_num(df.iloc[0, 0])):          # 1re ligne = en-têtes
        df = df.iloc[1:]
    for c in ["Modèle", "Sondages associés", "Hauteur maximal (m)"]:   # colonnes fusionnées
        df[c] = df[c].ffill()
    df["Sondages associés"] = df["Sondages associés"].str.replace(r"\s+", " ", regex=True)
    for c in ["Modèle", "Pl", "Em", "α", "Épaisseurs (m)", "Hauteur maximal (m)"]:
        df[c] = df[c].map(_num)
    df = df.dropna(subset=["Couches", "Modèle"]).reset_index(drop=True)
    df["Modèle"] = df["Modèle"].round().astype(int)
    return df
 
 
# ====================== Schéma du remblai ======================
def _fr(x, nd=2):
    return f"{x:.{nd}f}".rstrip("0").rstrip(".").replace(".", ",")
 
 
def texte_pente(p):
    if abs(p - 1) < 1e-4: return "1H/1V"
    if abs(p - 2) < 1e-4: return "2H/1V"
    if abs(p - 1.5) < 1e-4: return "3H/2V"
    return f"{_fr(p)}H/1V"
 
 
def schema_png(h, largeur, pente, surcharge, hpre=0.0):
    ht = h + hpre
    half, a = largeur / 2, pente * ht
    xl, xr = -half - a, half + a
    W = xr - xl
    bleu = "#3C6EC8"
    fig, ax = plt.subplots(figsize=(9, 3.1), dpi=100)
    ax.fill([xl, -half, half, xr], [0, ht, ht, 0], color="#D2BC96", ec="#785A37", lw=1)
    if hpre > 0:
        hw = half + pente * hpre
        ax.fill([-hw, -half, half, hw], [h, ht, ht, h], color="#E8924A", ec="#785A37", lw=1)
    ax.plot([xl - 0.08 * W, xr + 0.08 * W], [0, 0], color="#646464", lw=1)
    # cote H (et hPre)
    xh = xl - 0.04 * W
    ax.annotate("", xy=(xh, h), xytext=(xh, 0), arrowprops=dict(arrowstyle="<->", color=bleu))
    ax.text(xh - 0.01 * W, h / 2, f"H = {_fr(h)} m", ha="right", va="center", fontsize=9)
    if hpre > 0:
        ax.annotate("", xy=(xh, ht), xytext=(xh, h), arrowprops=dict(arrowstyle="<->", color="#C0501E"))
        ax.text(xh - 0.01 * W, h + hpre / 2, f"hPre = {_fr(hpre)} m", ha="right", va="center",
                fontsize=9, color="#C0501E", fontweight="bold")
    # surcharge
    for x in np.linspace(-half * 0.92, half * 0.92, 9):
        ax.annotate("", xy=(x, ht * 1.02), xytext=(x, ht * 1.28),
                    arrowprops=dict(arrowstyle="-|>", color=bleu, lw=1))
    ax.text(half + 0.03 * W, ht * 1.15, f"q = {_fr(surcharge)} kPa", fontsize=9, va="center")
    # largeur
    ax.annotate("", xy=(-half, ht * 1.6), xytext=(half, ht * 1.6),
                arrowprops=dict(arrowstyle="<->", color=bleu))
    ax.text(0, ht * 1.68, f"Largeur plateforme = {_fr(largeur)} m", ha="center", va="bottom", fontsize=9)
    ax.text(xr + 0.01 * W, ht * 0.5, f"Pente : {texte_pente(pente)}", fontsize=9, va="center")
    ax.set_xlim(xl - 0.22 * W, xr + 0.25 * W)
    ax.set_ylim(-0.12 * ht, ht * 1.95)
    ax.axis("off")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
 
 
# ====================== Classeur Excel ======================
THIN = Side(style="thin", color="787878")
BORD = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FOND_ENTETE = PatternFill("solid", fgColor="DDEBF7")
CENTRE = Alignment(horizontal="center", vertical="center", wrap_text=True)
_FAM = {"argile": "E63C3C", "argile_compacte": "E6E6E6", "marne": "FFAAC8", "sable": "FFB45A",
        "conglomerat": "6EA0E6", "gres": "FFEB50", "schiste_sain": "DCDCDC",
        "schiste_altere": "8C8C8C", "basalte": "8C5A32"}
_DIRECT = {"q2m": "FFEB50", "q2mg": "8C5A32"}
 
 
def couleur(label):
    return _DIRECT.get(E.norm(label)) or _FAM.get(E.famille(label), "F0F0F0")
 
 
def _police(hexa):
    r, g, b = (int(hexa[i:i + 2], 16) for i in (0, 2, 4))
    return Font(bold=True, color="FFFFFF" if 0.299 * r + 0.587 * g + 0.114 * b < 110 else "000000")
 
 
def _boite(ws, r1, c1, r2, c2):
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            ws.cell(r, c).border = BORD
 
 
def _entete(ws, row, col, labels, hauteur=32):
    for i, t in enumerate(labels):
        c = ws.cell(row, col + i, t)
        c.font, c.fill, c.alignment, c.border = Font(bold=True), FOND_ENTETE, CENTRE, BORD
    ws.row_dimensions[row].height = hauteur
 
 
def _feuille_essais(wb, raw, nom):
    ws = wb.active
    ws.title = nom
    for ligne in raw.itertuples(index=False):
        ws.append([None if pd.isna(v) else (v.item() if isinstance(v, np.generic) else v) for v in ligne])
    for r in (1, 2):
        for c in ws[r]:
            c.font = Font(bold=True)
            if r == 2:
                c.fill, c.alignment = FOND_ENTETE, CENTRE
    for col in "ABCDEFGHIJK":
        ws.column_dimensions[col].width = 18
    ws.freeze_panes = "A3"
 
 
def _feuille_modele(wb, table):
    ws = wb.create_sheet("modele")
    _entete(ws, 1, 1, ["Modèle", "Couches", "Sondages associés", "Pl", "Em", "α",
                       "Épaisseurs (m)", "Hauteur maximal (m)"])
    r = 2
    for m, g in table.groupby("Modèle", sort=False):
        r0 = r
        for _, row in g.iterrows():
            vals = [m, row["Couches"], row["Sondages associés"], row["Pl"], row["Em"], row["α"],
                    row["Épaisseurs (m)"], row["Hauteur maximal (m)"]]
            for c, v in enumerate(vals, 1):
                cell = ws.cell(r, c, v)
                cell.alignment, cell.border = CENTRE, BORD
            ws.cell(r, 4).number_format = ws.cell(r, 5).number_format = "0.000"
            ws.cell(r, 8).number_format = "0.00"
            r += 1
        if r - 1 > r0:
            for c in (1, 3, 8):
                ws.merge_cells(start_row=r0, start_column=c, end_row=r - 1, end_column=c)
        ws.cell(r0, 1).font = ws.cell(r0, 8).font = Font(bold=True)
    for col, w in zip("ABCDEFGH", (10, 16, 36, 10, 10, 12, 16, 20)):
        ws.column_dimensions[col].width = w
 
 
def _feuille_poinconnement(wb, punch):
    ws = wb.create_sheet("Poinçonnement")
    cols = list(punch.columns)
    _entete(ws, 1, 1, cols, 34)
    for i, row in enumerate(punch.itertuples(index=False), 2):
        for c, v in enumerate(row, 1):
            cell = ws.cell(i, c, v)
            cell.alignment, cell.border = CENTRE, BORD
        v = ws.cell(i, len(cols))
        v.font = Font(bold=True, color="1B7F3B" if v.value == "OK" else "B00020")
    for j, w in enumerate((10, 14, 14, 16, 12, 12, 16, 16), 1):
        ws.column_dimensions[chr(64 + j)].width = w
 
 
def _feuille_tassement(wb, nom, titre, h, det, w_avec, w_sans, P, hpre=None):
    ws = wb.create_sheet(nom)
    ws.merge_cells("A1:J1")
    ws["A1"] = titre
    ws["A1"].font, ws["A1"].alignment = Font(bold=True, size=14), CENTRE
    for r in range(2, 13):
        ws.row_dimensions[r].height = 22
    img = XLImage(io.BytesIO(schema_png(h, P["largeur"], P["pente"], P["surcharge"], hpre or 0.0)))
    ratio = img.height / img.width
    img.width, img.height = 900, int(900 * ratio)
    ws.add_image(img, "A2")
    _entete(ws, 13, 1, ["Couche", "z (m)", "I(z) sans charge", "I(z) avec charge", "Em (MPa)", "α",
                        "Δσv (kPa) sans charge", "Δσv (kPa) avec charge",
                        "W avec charge (cm)", "W sans charge (cm)"])
    r = 14
    debut, courante = 14, None
    fmts = ["0.00", "0.000000", "0.000000", "0.000", "0.000000", "0.000", "0.000", "0.000000", "0.000000"]
    cles = ["z", "I_sans", "I_avec", "Em", "alpha", "dsig_sans", "dsig_avec", "W_avec", "W_sans"]
 
    def fermer(fin):
        if courante is None:
            return
        if fin > debut:
            ws.merge_cells(start_row=debut, start_column=1, end_row=fin, end_column=1)
        c = ws.cell(debut, 1)
        c.value, c.alignment = courante, CENTRE
        c.fill = PatternFill("solid", fgColor=couleur(courante))
        c.font = _police(couleur(courante))
 
    for _, row in det.iterrows():
        if row["couche"] != courante:
            fermer(r - 1)
            debut, courante = r, row["couche"]
        for j, (k, f) in enumerate(zip(cles, fmts), 2):
            cell = ws.cell(r, j, float(row[k]))
            cell.number_format, cell.alignment = f, Alignment(horizontal="center", vertical="center")
        r += 1
    fermer(r - 1)
    ws.merge_cells(start_row=r, start_column=7, end_row=r, end_column=8)
    ws.merge_cells(start_row=r + 1, start_column=7, end_row=r + 1, end_column=8)
    ws.cell(r, 7, "W avec charge (cm)").font = Font(bold=True)
    ws.cell(r + 1, 7, "W sans charge (cm)").font = Font(bold=True)
    ws.cell(r, 9, float(w_avec)).font = Font(bold=True)
    ws.cell(r + 1, 10, float(w_sans)).font = Font(bold=True)
    ws.cell(r, 9).number_format = ws.cell(r + 1, 10).number_format = "0.000000"
    _boite(ws, 13, 1, r + 1, 10)
    for c in (7, 9):
        ws.cell(r, c).alignment = ws.cell(r + 1, c + (1 if c == 9 else 0)).alignment = CENTRE
    for col in "ABCDEFGHIJ":
        ws.column_dimensions[col].width = 14
    # bloc de paramètres
    lignes = [("H remblai (m)", h)]
    if hpre:
        lignes += [("hPre (m)", hpre), ("H + hPre (m)", h + hpre)]
    lignes += [("Largeur plateforme (m)", P["largeur"]), ("b = largeur / 2 (m)", P["largeur"] / 2),
               ("Pente (H/V)", P["pente"]), ("Surcharge q (kPa)", P["surcharge"]),
               ("Poids volumique (kN/m³)", P["gamma"]), ("Δz (m)", P["pas"]),
               ("Profondeur max (m)", P["zmax"])]
    _entete(ws, 13, 12, ["Paramètres", ""])
    ws.merge_cells("L13:M13")
    for i, (k, v) in enumerate(lignes, 14):
        ws.cell(i, 12, k)
        ws.cell(i, 13, v).alignment = Alignment(horizontal="center")
    _boite(ws, 13, 12, 13 + len(lignes), 13)
    if hpre:
        n = 14 + len(lignes)
        ws.merge_cells(start_row=n, start_column=12, end_row=n + 1, end_column=13)
        ws.cell(n, 12, "« sans charge » = remblai H + préchargement hPre").alignment = CENTRE
    ws.column_dimensions["L"].width, ws.column_dimensions["M"].width = 28, 12
 
 
def _feuille_synthese(wb, modeles, P, seuil):
    ws = wb.create_sheet("synthese")
    cols = ["Modèle", "W avec charge (cm)", "W sans charge (cm)", "Écart (cm)", "Spécification",
            "hPre (m)", "W avec charge après préchargement (cm)",
            "W sans charge après préchargement (cm)", "Écart après préchargement (cm)"]
    _entete(ws, 1, 1, cols, 48)
    for i, m in enumerate(modeles, 2):
        pre = m["pre"]
        vals = [m["m"], m["w_avec"], m["w_sans"], m["w_avec"] - m["w_sans"], m["spec"],
                pre["hp"] if pre else None, pre["w_avec"] if pre else None,
                pre["w_sans"] if pre else None, (pre["w_avec"] - pre["w_sans"]) if pre else None]
        for c, v in enumerate(vals, 1):
            cell = ws.cell(i, c, v if v is not None else "—")
            cell.alignment, cell.border = CENTRE, BORD
            if isinstance(v, float):
                cell.number_format = "0.00"
        ws.cell(i, 6).number_format = "0.0"
        ok = m["spec"] == "conforme"
        ws.cell(i, 5).font = Font(bold=not ok, color="1B7F3B" if ok else "B00020")
    for j, w in enumerate((10, 16, 16, 12, 34, 10, 24, 24, 22), 1):
        ws.column_dimensions[chr(64 + j)].width = w
    _entete(ws, 1, 11, ["Géométrie de remblai", ""], 48)
    ws.merge_cells("K1:L1")
    blocs = [("Largeur (m)", P["largeur"]), ("Pente (H/V)", P["pente"]),
             ("Surcharge (kPa)", P["surcharge"]), ("Poids volumique (kN/m³)", P["gamma"]),
             ("Pas (m)", P["pas"]), ("Profondeur max (m)", P["zmax"]),
             ("Écart toléré (cm)", seuil)]
    for i, (k, v) in enumerate(blocs, 2):
        ws.cell(i, 11, k)
        ws.cell(i, 12, v).alignment = Alignment(horizontal="center")
    _boite(ws, 1, 11, 1 + len(blocs), 12)
    ws.column_dimensions["K"].width, ws.column_dimensions["L"].width = 26, 12
 
 
def construire_excel(table, raw, nom_essais, P, seuil, modeles, punch):
    wb = Workbook()
    _feuille_essais(wb, raw, "essais pressiométriques")
    _feuille_modele(wb, table)
    _feuille_poinconnement(wb, punch)
    for m in modeles:
        _feuille_tassement(wb, f"tassement modele {m['m']}", f"CALCUL DES TASSEMENTS - MODELE {m['m']}",
                           m["h"], m["det"], m["w_avec"], m["w_sans"], P)
    for m in modeles:
        if m["pre"]:
            p = m["pre"]
            _feuille_tassement(wb, f"modele {m['m']}-prech",
                               f"CALCUL DES TASSEMENTS AVEC PRÉCHARGEMENT - MODELE {m['m']}",
                               m["h"], p["det"], p["w_avec"], p["w_sans"], P, hpre=p["hp"])
    _feuille_synthese(wb, modeles, P, seuil)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
 
 
# ====================== Calcul complet ======================
def calculer_tout(table, essais, P, seuil, fs_req):
    """Retourne (modèles, tableau poinçonnement, avertissements). kp = 1 (sols frottants)."""
    t = table.copy()
    t["Modèle"] = t["Modèle"].ffill()
    for c in ["Sondages associés", "Hauteur maximal (m)"]:
        t[c] = t.groupby("Modèle")[c].transform("first")
    for c in ["Pl", "Em", "α", "Épaisseurs (m)", "Hauteur maximal (m)"]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t = t.dropna(subset=["Modèle", "Couches", "Em", "α", "Épaisseurs (m)", "Hauteur maximal (m)"])
    modeles, punch, avert = [], [], []
    for m, g in t.groupby("Modèle", sort=True):
        m = int(m)
        couches = [dict(nom=r["Couches"], Em=r["Em"], alpha=r["α"], ep=r["Épaisseurs (m)"])
                   for _, r in g.iterrows()]
        h = float(g["Hauteur maximal (m)"].iloc[0])
        w_avec, w_sans, det = E.tassement(h, 0, couches, P, detail=True)
        ecart = w_avec - w_sans
        pre = None
        if abs(ecart) <= seuil:
            spec = "conforme"
        else:
            res = E.precharge(h, couches, P, seuil, hmax=3.0, pas=0.1)   # 0,1 - 0,2 - 0,3 ...
            if res:
                hp, wa, ws_ = res
                pre = dict(hp=hp, w_avec=wa, w_sans=ws_,
                           det=E.tassement(h, hp, couches, P, detail=True)[2])
                spec = f"préchargement hPre = {hp:.1f} m"
            else:
                spec = "préchargement insuffisant (> 3 m) : revoir le projet"
        modeles.append(dict(m=m, h=h, couches=couches, w_avec=w_avec, w_sans=w_sans,
                            det=det, pre=pre, spec=spec))
        first = g.iloc[0]
        s = E.stats_essais(essais, first["Couches"], first["Sondages associés"])
        if s is None:
            avert.append(f"Modèle {m} : aucun essai trouvé pour « {first['Couches']} » "
                         f"dans les sondages indiqués, Pl min = 0 pour le poinçonnement.")
        plmin = s["Plmin"] if s else 0.0
        r = E.poinconnement(first["Couches"], plmin, h, first["Épaisseurs (m)"], P, kp=1.0)
        punch.append({"Modèle": m, "Couche": first["Couches"], "Plmin (MPa)": plmin,
                      "Méthode": r["methode"], "qapp (kPa)": round(r["qapp"], 2),
                      "qmax (kPa)": round(r["qmax"], 2), "F = qmax/qapp": round(r["F"], 3),
                      "Vérification": "OK" if r["F"] >= fs_req else "NON VÉRIFIÉ"})
    return modeles, pd.DataFrame(punch), avert
 
