"""
build_pays.py
-------------
Assemble data/pays.csv (le fichier final, publié sur le site) à partir de :
    data/pays_liste.csv                          liste des pays (saisie à la main)
    data/intermediaire/pays_wikidata.csv         capitale, GPS, image, drapeau, UNESCO
    data/intermediaire/pays_banquemondiale.csv   indicateurs Banque mondiale
    data/descriptions_pays.csv                   textes de présentation (rédigés à la main)

Au premier lancement, data/descriptions_pays.csv est créé avec des descriptions vides,
à remplir ensuite. Les salaires ILOSTAT ne sont PAS intégrés (choix documenté :
données incomplètes et non comparables entre pays).

Aucun appel réseau. Lancement depuis la racine du projet :
    python scripts/build_pays.py
"""

import csv
import datetime
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DATA = RACINE / "data"
FICHIER_LISTE = DATA / "pays_liste.csv"
FICHIER_WIKIDATA = DATA / "intermediaire" / "pays_wikidata.csv"
FICHIER_BM = DATA / "intermediaire" / "pays_banquemondiale.csv"
FICHIER_DESCRIPTIONS = DATA / "descriptions_pays.csv"
FICHIER_SORTIE = DATA / "pays.csv"

# Colonnes du fichier final, dans l'ordre : (nom, source)
COLONNES = [
    ("iso3", "liste"), ("iso2", "wikidata"), ("nom_fr", "liste"), ("region", "liste"),
    ("capitale", "wikidata"), ("lat", "wikidata"), ("lon", "wikidata"),
    ("description", "descriptions"),
    ("image_url", "wikidata"), ("image_auteur", "wikidata"), ("image_licence", "wikidata"),
    ("drapeau_url", "wikidata"),
    ("unesco_culturel", "wikidata"), ("unesco_naturel", "wikidata"), ("unesco_mixte", "wikidata"),
    ("unesco_total", "calcul"),
    ("zones_protegees_pct", "bm"), ("annee_zones_protegees", "bm"),
    ("densite_hab_km2", "bm"), ("annee_densite", "bm"),
    ("pop_urbaine_pct", "bm"), ("annee_pop_urbaine", "bm"),
    ("pop_villes_1m_pct", "bm"), ("annee_pop_villes_1m", "bm"),
    ("rnb_hab_usd", "bm"), ("annee_rnb", "bm"),
    ("niveau_prix", "calcul"), ("annee_niveau_prix", "calcul"),
    ("budget_dispo", "calcul"), ("budget_moyen_usd_jour", "calcul"),
    ("wikidata_qid", "wikidata"),
    ("dans_quiz", "calcul"),
    ("date_assemblage", "calcul"),
]

# Champs indispensables pour qu'un pays entre dans le quiz
# (le budget s'ajoutera ici quand budget.csv sera rempli)
OBLIGATOIRES_QUIZ = [
    "lat", "lon", "image_url", "unesco_total", "zones_protegees_pct",
    "densite_hab_km2", "pop_villes_1m_pct", "rnb_hab_usd", "niveau_prix",
]
NUMERIQUES = [c for c, s in COLONNES if s == "bm" and not c.startswith("annee_")] + [
    "lat", "lon", "unesco_culturel", "unesco_naturel", "unesco_mixte"]
FICHIER_BUDGET = DATA / "budget.csv"


def budgets_moyens():
    """Somme des 4 catégories du niveau « moyen » par pays, d'après data/budget.csv."""
    if not FICHIER_BUDGET.exists():
        avertissements.append("budget.csv absent : lance build_budget.py (budget_dispo = false partout)")
        return {}
    sommes = {}
    with FICHIER_BUDGET.open(encoding="utf-8", newline="") as f:
        for l in csv.DictReader(f):
            if l["niveau"] == "moyen":
                sommes[l["iso3"]] = sommes.get(l["iso3"], 0) + float(l["montant_usd_jour"])
    return sommes


def niveau_prix(bm):
    """Indice du niveau des prix : PPA / taux de change (États-Unis = 1)."""
    ppa, change = bm.get("ppa_mn_par_dollar_int", ""), bm.get("change_mn_par_usd", "")
    if not ppa or not change:
        return "", ""
    annee = min(bm.get("annee_ppa", ""), bm.get("annee_change", ""))
    if bm.get("annee_ppa") != bm.get("annee_change"):
        avertissements.append(f"{bm['iso3']} : PPA ({bm.get('annee_ppa')}) et taux de change "
                              f"({bm.get('annee_change')}) d'années différentes")
    return round(float(ppa) / float(change), 3), annee

problemes = []      # bloquants : le fichier n'est pas écrit
avertissements = []  # informatifs


def lire(chemin, obligatoire=True):
    if not chemin.exists():
        if obligatoire:
            sys.exit(f"Fichier manquant : {chemin.relative_to(RACINE)}\n"
                     "Lance d'abord le script qui le produit.")
        return None
    with chemin.open(encoding="utf-8", newline="") as f:
        lignes = [{k: (v or "").strip() for k, v in l.items()} for l in csv.DictReader(f)]
    par_pays = {}
    for l in lignes:
        if l["iso3"] in par_pays:
            problemes.append(f"{chemin.name} : {l['iso3']} apparaît deux fois")
        par_pays[l["iso3"]] = l
    return par_pays


def creer_modele_descriptions(liste):
    with FICHIER_DESCRIPTIONS.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["iso3", "nom_fr", "description"])
        for iso3, l in liste.items():
            ecrivain.writerow([iso3, l["nom_fr"], ""])
    print(f"   Modèle créé : {FICHIER_DESCRIPTIONS.relative_to(RACINE)} (descriptions à rédiger)")


def main():
    print("1. Lecture des fichiers")
    liste = lire(FICHIER_LISTE)
    sources = {"wikidata": lire(FICHIER_WIKIDATA), "bm": lire(FICHIER_BM)}
    descriptions = lire(FICHIER_DESCRIPTIONS, obligatoire=False)
    if descriptions is None:
        creer_modele_descriptions(liste)
        descriptions = {}
    sources["descriptions"] = descriptions
    sources["liste"] = liste

    print("2. Contrôle de cohérence entre fichiers")
    scripts = {"wikidata": "build_pays_wikidata.py", "bm": "build_pays_banquemondiale.py"}
    for nom, script in scripts.items():
        manquants = set(liste) - set(sources[nom])
        en_trop = set(sources[nom]) - set(liste)
        if manquants:
            problemes.append(f"{nom} : pays absents {sorted(manquants)} -> relance {script}")
        if en_trop:
            avertissements.append(f"{nom} : pays hors liste ignorés {sorted(en_trop)}")
    for iso3 in set(descriptions) - set(liste):
        avertissements.append(f"descriptions : {iso3} ne fait pas partie de la liste")

    print("3. Assemblage")
    budgets = budgets_moyens()
    lignes = []
    aujourd_hui = datetime.date.today().isoformat()
    for iso3 in liste:
        ligne = {}
        for colonne, source in COLONNES:
            if source in sources:
                ligne[colonne] = sources[source].get(iso3, {}).get(colonne, "")
        # calculs
        unesco = [ligne["unesco_culturel"], ligne["unesco_naturel"], ligne["unesco_mixte"],
                  sources["wikidata"].get(iso3, {}).get("unesco_sans_categorie", "")]
        ligne["unesco_total"] = (sum(int(u) for u in unesco if u)
                                 if all(u != "" for u in unesco[:3]) else "")
        ligne["date_assemblage"] = aujourd_hui
        bm = sources["bm"].get(iso3, {})
        if bm and "ppa_mn_par_dollar_int" not in bm:
            problemes.append("pays_banquemondiale.csv n'a pas les colonnes de prix : "
                             "relance build_pays_banquemondiale.py (nouvelle version)")
        ligne["niveau_prix"], ligne["annee_niveau_prix"] = niveau_prix(bm) if bm else ("", "")
        budget = budgets.get(iso3)
        ligne["budget_dispo"] = "true" if budget is not None else "false"
        ligne["budget_moyen_usd_jour"] = round(budget, 2) if budget is not None else ""

        for c in NUMERIQUES:
            if ligne[c] != "":
                try:
                    float(ligne[c])
                except ValueError:
                    problemes.append(f"{iso3} : {c} = '{ligne[c]}' n'est pas un nombre")
        if ligne["lat"] and ligne["lon"]:
            lat, lon = float(ligne["lat"]), float(ligne["lon"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                problemes.append(f"{iso3} : coordonnées impossibles ({lat}, {lon})")

        manquants = [c for c in OBLIGATOIRES_QUIZ if ligne[c] == ""]
        ligne["dans_quiz"] = "false" if manquants else "true"
        if manquants:
            avertissements.append(f"{iso3} : exclu du quiz, champs vides {manquants}")
        lignes.append(ligne)

    if problemes:
        sys.exit("Problèmes bloquants, pays.csv n'a PAS été écrit :\n  - "
                 + "\n  - ".join(sorted(set(problemes))))

    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=[c for c, _ in COLONNES])
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    # --- Rapport ---
    sans_description = [l["iso3"] for l in lignes if not l["description"]]
    print("\n=== Bilan ===")
    print(f"Pays                      : {len(lignes)}")
    print(f"Colonnes                  : {len(COLONNES)}")
    print(f"Pays dans le quiz         : {sum(l['dans_quiz'] == 'true' for l in lignes)}")
    print(f"Descriptions rédigées     : {len(lignes) - len(sans_description)}/{len(lignes)}")
    print(f"Budget détaillé disponible: {sum(l['budget_dispo'] == 'true' for l in lignes)}/{len(lignes)}")

    print("\n=== Aperçu (3 premières lignes) ===")
    apercu = ["iso3", "nom_fr", "unesco_total", "densite_hab_km2", "pop_villes_1m_pct",
              "rnb_hab_usd", "niveau_prix", "budget_moyen_usd_jour", "dans_quiz"]
    print(" | ".join(apercu))
    for l in lignes[:3]:
        print(" | ".join(str(l[c]) for c in apercu))

    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


if __name__ == "__main__":
    main()
