"""Moteur de calcul : tassement (Ménard + Osterberg), préchargement, poinçonnement."""
import math, re, unicodedata
import pandas as pd

# ---------- Nettoyage des libellés ----------
def norm(txt) -> str:
    t = unicodedata.normalize("NFD", str(txt or ""))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"[\s_\-]", "", t)

# Table de synonymes -> famille canonique
SYNONYMES = {
    "argile": ["argilesetlimonsettufs", "argilesetlimons", "argiles", "argile", "limon",
               "limonsettufs", "q1l", "q2l"],
    "argile_compacte": ["argilesetlimonsettufscompactes"],
    "marne": ["marne", "marnes", "m", "mi"],
    "sable": ["sable", "sables", "q2m", "q2mg", "q2mm", "q2mgg", "2mgg"],
    "conglomerat": ["conglomerats", "conglomerat", "q1lc"],
    "gres": ["gres", "gress"],
    "schiste_sain": ["schistessains", "schistesains", "schistesain", "schistesain"],
    "schiste_altere": ["schistesaltères", "schistealtere", "schistesaltere", "tresaltere"],
    "basalte": ["basaltes", "basalte"],
}
_LOOKUP = {norm(s): fam for fam, L in SYNONYMES.items() for s in L}

# Fautes de frappe connues
ALIAS = {"gress": "gres"}
def canon(label) -> str:
    n = norm(label)
    return ALIAS.get(n, n)

def famille(label) -> str:
    return _LOOKUP.get(norm(label), "inconnu")

# ---------- Coefficient rhéologique alpha (Ménard) ----------
def alpha_menard(label, em_sur_pl):
    f = famille(label)
    try:
        v = float(em_sur_pl)
    except (TypeError, ValueError):
        return None
    if f == "argile":
        return 1.0 if v > 16 else 2/3 if v >= 9 else 0.5 if v >= 7 else None
    if f == "marne":
        return 1.0 if v > 16 else 2/3 if v >= 9 else 0.5
    if f == "sable":
        return 0.5 if v > 12 else 1/3
    if f == "conglomerat":
        return 1/3 if v > 10 else 1/4
    if f in ("gres", "schiste_sain", "argile_compacte", "basalte"):
        return 0.5
    if f == "schiste_altere":
        return 2/3
    return None

# ---------- Statistiques depuis les essais pressiométriques ----------
def stats_essais(essais: pd.DataFrame, label, sondages: str):
    """Pl : moyenne géométrique ; Em : moyenne harmonique ; Pl min."""
    sond = {norm(s) for s in str(sondages).split(",") if s.strip()}
    c = canon(label)
    d = essais[(essais["famille"].map(canon) == c) & (essais["sondage"].map(norm).isin(sond))]
    pl = pd.to_numeric(d["Pl"], errors="coerce"); pl = pl[pl > 0]
    em = pd.to_numeric(d["Em"], errors="coerce"); em = em[em > 0]
    if pl.empty or em.empty:
        return None
    pl_g = math.exp(sum(math.log(x) for x in pl) / len(pl))
    em_h = len(em) / sum(1 / x for x in em)
    return dict(Pl=round(pl_g, 3), Em=round(em_h, 3), EmPl=round(em_h / pl_g, 3), Plmin=float(pl.min()))

def lire_essais(fichier) -> pd.DataFrame:
    df = pd.read_excel(fichier, sheet_name=0, header=1)
    cols = list(df.columns)
    out = pd.DataFrame({"famille": df[cols[0]], "sondage": df[cols[3]],
                        "Pl": df[cols[8]], "Em": df[cols[9]]})
    return out.dropna(subset=["famille", "sondage"])

# ---------- Contraintes (Osterberg, sous l'axe du remblai) ----------
def influence(z, a, b):
    if z <= 0 or a <= 0 or b <= 0:
        return 0.0
    a1 = math.atan((a + b) / z) - math.atan(b / z)
    a2 = math.atan(b / z)
    return 2 / math.pi * (((a + b) / a) * (a1 + a2) - (b / a) * a2)

def _couche_a(z, epaisseurs):
    cum = 0
    for i, e in enumerate(epaisseurs):
        cum += e
        if z <= cum + 1e-9:
            return i
    return len(epaisseurs) - 1

def tassement(h, hpre, couches, p, detail=False):
    """couches : liste de dict(nom, Em [MPa], alpha, ep [m])."""
    b, dz, g = p["largeur"] / 2, p["pas"], p["gamma"]
    eps = [c["ep"] for c in couches]
    zmax = min(sum(eps), p["zmax"])
    steps = math.ceil(zmax / dz - 1e-9)
    h_eq = p["surcharge"] / g
    rows, s_no, s_with = [], 0.0, 0.0
    for k in range(1, steps + 1):
        z = (k - 0.5) * dz
        c = couches[_couche_a(z, eps)]
        i_no = influence(z, p["pente"] * (h + hpre), b)
        i_w = influence(z, p["pente"] * (h + h_eq), b)
        ds_no, ds_w = g * (h + hpre) * i_no, g * (h + h_eq) * i_w
        w_no = c["alpha"] * ds_no * dz / (c["Em"] * 1000) * 100
        w_w = c["alpha"] * ds_w * dz / (c["Em"] * 1000) * 100
        s_no += w_no; s_with += w_w
        rows.append(dict(couche=c["nom"], z=z, I_sans=i_no, I_avec=i_w, Em=c["Em"],
                         alpha=c["alpha"], dsig_sans=ds_no, dsig_avec=ds_w,
                         W_avec=w_w, W_sans=w_no))
    return (s_with, s_no, pd.DataFrame(rows)) if detail else (s_with, s_no)

def precharge(h, couches, p, seuil=1.0, hmax=3.0, pas=0.05):
    """Plus petit hPre tel que |W avec - W sans| <= seuil (cm)."""
    n = int(round(hmax / pas))
    for i in range(1, n + 1):
        hp = round(i * pas, 4)
        w_avec, w_sans = tassement(h, hp, couches, p)
        if abs(w_avec - w_sans) <= seuil:
            return hp, w_avec, w_sans
    return None

# ---------- Poinçonnement ----------
def poinconnement(label, plmin, h, ep, p, kp=1.0):
    """plmin en MPa, h = hauteur de remblai (m), ep = épaisseur de la couche (m)."""
    qapp = h * p["gamma"] + p["surcharge"]
    f = famille(label)
    if plmin <= 0 or f == "inconnu":
        return dict(methode="Inconnu", qapp=qapp, qmax=0.0, F=0.0)
    if f in ("argile", "marne", "argile_compacte"):
        B = p["largeur"] + p["pente"] * h
        r = B / ep
        nc = math.pi + 2 if r <= 1.5 else 0.468 * r + 4.445 if r <= 10 else 9.125
        cu = 21 * (plmin * 10) ** 0.75
        qmax, meth = nc * cu, "Sols mous"
    else:
        qmax, meth = kp * plmin * 1000, "Sols frottants"
    return dict(methode=meth, qapp=qapp, qmax=qmax, F=qmax / qapp if qapp > 0 else 0.0)
