    return classeur.create_sheet(nom)


def detail_tassement(classeur, resultat, prechargement=False):
    modele, geo = resultat["modele"], resultat["geo"]
    hpre = resultat["synthese"][5] if prechargement else None
    titre = "Préchargement" if prechargement else "Tassement"
    feuille = nouvelle_feuille(classeur, f"{titre} modèle {modele}")
    feuille.merge_cells("A1:J1")
    feuille["A1"] = f"{titre.upper()} · MODÈLE {modele}"
    feuille["A1"].data_type = "s"
    feuille["A1"].alignment = Alignment(horizontal="center", vertical="center")
    feuille["A1"].font = Font(size=15, bold=True, color=BLEU)
    feuille.row_dimensions[1].height = 25
    feuille.add_image(schema(geo, hpre), "A2")
    feuille.merge_cells("A13:J13")
    feuille["A13"] = (f"γ = {geo.gamma:g} kN/m³  |  Δz = {geo.pas:g} m  |  "
                      f"Profondeur d’influence maximale = {geo.zmax:g} m"
                      + (f"  |  Hauteur de préchargement = {hpre:.1f} m" if hpre else ""))
    feuille["A13"].alignment = Alignment(horizontal="center")
    detail = resultat["pre"][3] if prechargement else resultat["detail"]
    reference = "avec préchargement seul" if prechargement else "sans surcharge"
    ordre = ["Couche", "z (m)", "I référence", "I avec surcharge", "Em (MPa)", "α",
             "Δσ référence (kPa)", "Δσ avec surcharge (kPa)", "ΔW avec surcharge (cm)", "ΔW référence (cm)"]
    entetes = ["Couche", "z (m)", f"I(z) {reference}", "I(z) avec surcharge", "Em (MPa)", "α",
               f"Δσ {reference} (kPa)", "Δσ avec surcharge (kPa)", "ΔW avec surcharge (cm)",
               f"ΔW {reference} (cm)"]
    debut = 15
    tableau(feuille, entetes, [[r[k] for k in ordre] for r in detail], debut,
            [16, 10, 23, 20, 13, 12, 24, 24, 25, 25],
            {3: "0.000000", 4: "0.000000", 6: "0.000000", 9: "0.000000", 10: "0.000000"})
    fin = debut + len(detail)
    premier = debut + 1
    couleur = 0
    for ligne in range(premier + 1, fin + 2):
        if ligne > fin or feuille.cell(ligne, 1).value != feuille.cell(premier, 1).value:
            fusionner(feuille, 1, premier, ligne - 1, COUCHES[couleur % len(COUCHES)])
            premier = ligne
            couleur += 1
    for offset, (label, formule) in enumerate([
        ("W total avec surcharge (cm)", f"=SUM(I{debut + 1}:I{fin})"),
        (f"W total {reference} (cm)", f"=SUM(J{debut + 1}:J{fin})"),
        ("Écart (cm)", f"=J{fin + 1}-J{fin + 2}"),
    ], 1):
        ligne = fin + offset
        feuille.merge_cells(start_row=ligne, start_column=7, end_row=ligne, end_column=9)
        feuille.cell(ligne, 7, label)
        feuille.cell(ligne, 10, formule).number_format = "0.000"
        for cellule in feuille[ligne][6:10]:
            cellule.border = BORDURE
            cellule.font = Font(bold=True)
            cellule.fill = PatternFill("solid", fgColor="E8F1F8")


def exporter(original, modeles, resultats):
    classeur = load_workbook(BytesIO(original))
    source = feuille_essais(classeur)
    noms_generes = {"plem", "modele", "poinconnement", "poincenement", "synthese", "synthese-pre"}
    for feuille in list(classeur):
        nom = cle(sans_accents(feuille.title))
        if nom in noms_generes or re.match(r"^(tassementmodele|prechargementmodele|modele.*-prech)", nom):
            classeur.remove(feuille)
    source.title = "Essais pressiométriques"
    feuille_modeles = classeur.create_sheet("Modèle")
    lignes = [couche[:8] for couches in modeles.values() for couche in couches]
    tableau(feuille_modeles, COLONNES[:8], lignes, largeurs=[13, 18, 56, 16, 16, 13, 18, 23],
            formats={6: "0.00000000"})
    debut = 2
    for couches in modeles.values():
        fin = debut + len(couches) - 1
        for col in (1, 8):
            fusionner(feuille_modeles, col, debut, fin)
        bloc = debut
        for ligne in range(debut + 1, fin + 2):
            if ligne > fin or feuille_modeles.cell(ligne, 3).value != feuille_modeles.cell(bloc, 3).value:
                fusionner(feuille_modeles, 3, bloc, ligne - 1)
                bloc = ligne
        debut = fin + 1
    feuille = classeur.create_sheet("Poinçonnement")
    tableau(feuille, POINCONNEMENT, [r["poinconnement"] for r in resultats],
            largeurs=[13, 20, 18, 20, 15, 15, 18, 14, 19])
    for r in resultats:
        detail_tassement(classeur, r)
    for r in resultats:
        if r["pre"]:
            detail_tassement(classeur, r, True)
    feuille = classeur.create_sheet("Synthèse")
    tableau(feuille, SYNTHESE, [r["synthese"] for r in resultats],
            largeurs=[13, 20, 20, 16, 29, 14, 23, 23, 23, 18, 20])
    geo = resultats[0]["geo"]
    feuille["W1"] = "Géométrie et critères"
    for ligne, (libelle, valeur) in enumerate([
        ("Largeur (m)", geo.largeur), ("Pente (H/V)", geo.pente), ("Surcharge (kPa)", geo.surcharge),
        ("Poids volumique (kN/m³)", geo.gamma), ("Pas (m)", geo.pas), ("Profondeur d’influence (m)", geo.zmax),
        ("Facteur de sécurité requis", resultats[0]["poinconnement"][7]),
    ], 2):
        feuille.cell(ligne, 23, libelle).border = BORDURE
        feuille.cell(ligne, 24, valeur).border = BORDURE
    feuille.column_dimensions["W"].width = 30
    feuille.column_dimensions["X"].width = 16
    classeur.active = feuille_modeles
    sortie = BytesIO()
    classeur.save(sortie)
    classeur.close()
    return sortie.getvalue()
