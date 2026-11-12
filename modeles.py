        return str(int(valeur))
    return str(valeur).strip()


def lire_collage(contenu):
    lignes = list(csv.reader(StringIO(contenu), dialect="excel-tab"))
    lignes = [ligne for ligne in lignes if any(cellule.strip() for cellule in ligne)]
    if lignes and cle(sans_accents(lignes[0][0])) == "modele":
        lignes.pop(0)
    resultat = []
    for i, ligne in enumerate(lignes, 1):
        if not 8 <= len(ligne) <= 9:
            raise ValueError(f"Ligne {i} : colle les 8 colonnes de la feuille Modèle, ou 9 avec Pl min.")
        valeurs = [*map(texte, ligne[:3]), *map(nombre, ligne[3:])]
        resultat.append((valeurs + [None])[:9])
    if not resultat:
        raise ValueError("Le collage est vide.")
    return resultat


def groupes(lignes):
    """Restitue les cellules fusionnées sans propager d’un modèle au suivant."""
    modeles = {}
    modele = sondages = hauteur = ""
    for i, (identifiant, couche, nouveaux_sondages, pl, em, alpha, ep, h, plmin) in enumerate(lignes, 1):
        if all(vide(v) for v in (identifiant, couche, nouveaux_sondages, pl, em, alpha, ep, h, plmin)):
            continue
        identifiant = texte(identifiant)
        if identifiant and identifiant != modele:
            if identifiant in modeles:
                raise ValueError(f"Les couches du modèle {identifiant} doivent se suivre.")
            modele, sondages, hauteur = identifiant, "", None
            modeles[modele] = []
        if not modele or vide(couche):
            raise ValueError(f"Ligne {i} : renseigne le modèle et le nom de la couche.")
        sondages = texte(nouveaux_sondages) or sondages
        h = nombre(h)
        if h is not None and hauteur is not None and h != hauteur:
            raise ValueError(f"Modèle {modele} : indique une hauteur de remblai unique.")
        hauteur = h if h is not None else hauteur
        modeles[modele].append([modele, texte(couche), sondages, nombre(pl), nombre(em),
                                nombre(alpha), nombre(ep), hauteur, nombre(plmin)])
    if not modeles:
        raise ValueError("Ajoute au moins un modèle.")
    for modele, couches in modeles.items():
        hauteur = couches[-1][7]
        if not positif(hauteur):
            raise ValueError(f"Modèle {modele} : renseigne une hauteur positive.")
        for couche in couches:
            couche[7] = hauteur
    return modeles


def depuis_classeur(modeles):
    return [[modele, c["nom"], ", ".join(c["sondages"]), c["pl"], c["em"], c["alpha"],
             c["epaisseur"], data["hauteur"], None]
            for modele, data in modeles.items() for c in data["couches"]]


def calculer(modeles, essais, parametres, seuil, fs_requis, recalculer, plafond):
    index = {}
    for essai in essais:
        key = (cle(sans_accents(essai["Famille"])), cle(essai["Sondage"]))
        index.setdefault(key, []).append(essai)
    resultats = []
    for modele, lignes in modeles.items():
        couches = []
        for ligne in lignes:
            _, nom, sondages, _, em, alpha, ep, hauteur, plmin = ligne
            noms = dict.fromkeys(cle(s) for s in sondages.split(",") if s.strip())
            retenus = [e for s in noms for e in index.get((cle(sans_accents(nom)), s), [])]
            if recalculer:
                ligne[3], em, _, alpha = moyennes(retenus, nom)
                ligne[4:6] = [em, alpha]
            if not positif(ep) or not positif(em) or not positif(alpha):
                raise ValueError(f"Modèle {modele}, couche {nom} : vérifie l’épaisseur, Em, α et les sondages associés.")
            if retenus and (recalculer or not positif(plmin)):
                ligne[8] = min((e["Pl (MPa)"] for e in retenus if e["Pl (MPa)"]), default=None)
            couches.append(Couche(nom, ep, em, alpha))
        geo = Geometrie(hauteur, **parametres)
        avec, sans, ecart, detail = tassement(geo, couches)
        hauteur_pre = None
        resultat_pre = None
        if abs(ecart) > seuil:
            for palier in range(1, round(plafond * 10) + 1):
                candidat = palier / 10
                resultat = tassement(geo, couches, candidat)
                if abs(resultat[2]) <= seuil:
                    hauteur_pre, resultat_pre = candidat, resultat
                    break
        premiere = lignes[0]
        methode = methode_vba(premiere[1])
        plmin = positif(premiere[8])
        qapp = geo.hauteur * geo.gamma + geo.surcharge
        qmax = facteur = None
        if methode and plmin:
            qapp, qmax, facteur = poinconnement(geo, premiere[6], plmin, methode)
        verification = ("Non évalué" if facteur is None else
                        "Vérifié" if facteur >= fs_requis else "Non vérifié")
        decision = ("Non requis" if abs(ecart) <= seuil else
                    "Palier trouvé" if hauteur_pre is not None else f"Aucun palier jusqu’à {plafond:g} m")
        resultats.append({
            "modele": modele, "geo": geo, "detail": detail, "pre": resultat_pre,
            "synthese": [modele, avec, sans, ecart, decision, hauteur_pre,
                         *(resultat_pre[:3] if resultat_pre else (None, None, None)), facteur, verification],
            "poinconnement": [modele, premiere[1], plmin, methode or "Indéterminée", qapp, qmax,
                              facteur, fs_requis, verification],
        })
    return resultats


SYNTHESE = ["Modèle", "W avec surcharge (cm)", "W sans surcharge (cm)", "Écart (cm)",
            "Préchargement", "hPre (m)", "W avec surcharge après étude (cm)",
            "W avec préchargement seul (cm)", "Écart après préchargement (cm)",
            "Facteur de sécurité", "Poinçonnement"]
POINCONNEMENT = ["Modèle", "Couche d’assise", "Pl min (MPa)", "Méthode", "qapp (kPa)",
                 "qmax (kPa)", "F = qmax/qapp", "F requis", "Vérification"]
