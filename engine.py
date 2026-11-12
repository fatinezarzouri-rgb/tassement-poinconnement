    return None


def moyennes(essais, famille):
    pl = [valeur for essai in essais if (valeur := positif(essai["Pl (MPa)"]))]
    em = [valeur for essai in essais if (valeur := positif(essai["Em (MPa)"]))]
    pl_moy = round(exp(sum(map(log, pl)) / len(pl)), 3) if pl else None
    em_moy = round(len(em) / sum(1 / valeur for valeur in em), 3) if em else None
    rapport = round(em_moy / pl_moy, 3) if pl_moy and em_moy else None
    return pl_moy, em_moy, rapport, alpha_vba(famille, rapport) if rapport else None


def influence(profondeur, extension, demi_largeur):
    angle_bord = atan(demi_largeur / profondeur)
    angle_talus = atan((extension + demi_largeur) / profondeur)
    return 2 / pi * ((extension + demi_largeur) / extension * angle_talus
                     - demi_largeur / extension * angle_bord)


def tassement(geo, couches, prechargement=0):
    if not all(positif(x) for x in (geo.hauteur, geo.largeur, geo.pente, geo.gamma, geo.pas, geo.zmax)):
        raise ValueError("Hauteur, largeur, pente, poids volumique et pas doivent être positifs.")
    if any(not isfinite(x) or x < 0 for x in (geo.surcharge, prechargement)):
        raise ValueError("La surcharge et la hauteur de préchargement doivent être positives ou nulles.")
    if not couches or any(not all(positif(x) for x in (c.epaisseur, c.em, c.alpha)) for c in couches):
        raise ValueError("Chaque couche doit avoir une épaisseur, un Em et un α positifs.")
    limites = list(accumulate(c.epaisseur for c in couches))
    profondeur_max = min(limites[-1], geo.zmax)
    if geo.pas < profondeur_max / 20000:
        raise ValueError("Le pas de calcul produit plus de 20 000 tranches.")
    hauteurs = (geo.hauteur + geo.surcharge / geo.gamma, geo.hauteur + prechargement)
    detail = []
    for k in range(ceil(profondeur_max / geo.pas)):
        z = (k + 0.5) * geo.pas
        couche = couches[min(bisect_left(limites, z - 1e-9), len(couches) - 1)]
        facteurs = [influence(z, geo.pente * h, geo.largeur / 2) for h in hauteurs]
        charges = [geo.gamma * h * facteur for h, facteur in zip(hauteurs, facteurs)]
        avec, ref = [couche.alpha * q * geo.pas / (couche.em * 10) for q in charges]
        detail.append({
            "Couche": couche.nom, "z (m)": z, "Em (MPa)": couche.em, "α": couche.alpha,
            "I avec surcharge": facteurs[0], "I référence": facteurs[1],
            "Δσ avec surcharge (kPa)": charges[0], "Δσ référence (kPa)": charges[1],
            "ΔW avec surcharge (cm)": avec, "ΔW référence (cm)": ref,
        })
    avec = sum(r["ΔW avec surcharge (cm)"] for r in detail)
    ref = sum(r["ΔW référence (cm)"] for r in detail)
    return avec, ref, avec - ref, detail


def methode_vba(famille):
    nom = cle(sans_accents(famille))
    if nom == "m" or any(m in nom for m in ("argile", "limon", "tuf", "marne", "q2l", "q1l", "mi")):
        return "Sols mous"
    if any(m in nom for m in ("sable", "q2m", "schiste", "conglomerat", "gres", "basalte", "q1lc")):
        return "Sols frottants"
    return None


def poinconnement(geo, epaisseur, pl_min, methode):
    q_app = geo.gamma * geo.hauteur + geo.surcharge
    if methode == "Sols mous":
        rapport = (geo.largeur + geo.pente * geo.hauteur) / epaisseur
        if rapport <= 1.5:
            nc = pi + 2
        elif rapport <= 10:
            nc = 0.468 * rapport + 4.445
        else:
            nc = 9.125
        q_max = nc * 21 * (pl_min * 10) ** 0.75
    elif methode == "Sols frottants":
        q_max = pl_min * 1000
    else:
        raise ValueError("Sélectionne la méthode de poinçonnement.")
    return q_app, q_max, q_max / q_app


def feuille_essais(classeur):
    return next((s for s in classeur if "essaispressiom" in cle(sans_accents(s.title))), None)


def lire_classeur(fichier):
    classeur = load_workbook(fichier, read_only=True, data_only=True)
    try:
        feuille = feuille_essais(classeur)
        if feuille is None:
            raise ValueError("La feuille des essais pressiométriques est introuvable.")
        essais = []
        for ligne, r in enumerate(feuille.iter_rows(min_row=3, max_col=10, values_only=True), 3):
            if r[0] and r[3]:
                essais.append({
                    "Ligne Excel": ligne, "Famille": str(r[0]).strip(), "Ouvrage": str(r[1] or ""),
                    "PK": r[2], "Sondage": str(r[3]).strip(), "Début (m)": r[5], "Fin (m)": r[6],
                    "Lithologie": r[7], "Pl (MPa)": positif(r[8]), "Em (MPa)": positif(r[9]),
                })
        modeles = {}
        if "plem" in classeur or "Modèle" in classeur:
            ancienne_structure = "plem" in classeur
            feuille_modele = classeur["plem" if ancienne_structure else "Modèle"]
            modele = None
            for r in feuille_modele.iter_rows(min_row=2, max_col=9, values_only=True):
                epaisseur, hauteur = (r[7], r[8]) if ancienne_structure else (r[6], r[7])
                if r[0] is not None:
                    modele = str(r[0])
                    modeles[modele] = {"hauteur": positif(hauteur), "couches": []}
                if modele and r[1]:
                    couches = modeles[modele]["couches"]
                    sondages = str(r[2]).split(",") if r[2] else (couches[-1]["sondages"] if couches else [])
                    couches.append({"nom": str(r[1]).strip(), "sondages": [s.strip() for s in sondages],
                                    "epaisseur": positif(epaisseur), "pl": positif(r[3]), "em": positif(r[4]), "alpha": positif(r[6] if ancienne_structure else r[5])})
        geometrie = {}
        nom_synthese = next((s.title for s in classeur if cle(sans_accents(s.title)) == "synthese"), None)
        if nom_synthese:
            valeurs = classeur[nom_synthese].iter_rows(min_row=2, max_row=7, min_col=24, max_col=24, values_only=True)
            geometrie = dict(zip(("largeur", "pente", "surcharge", "gamma", "pas", "zmax"), (v[0] for v in valeurs)))
            geometrie = {nom: valeur for nom, valeur in geometrie.items() if valeur is not None}
        return essais, modeles, geometrie
    finally:
        classeur.close()
