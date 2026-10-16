"""
import_budget_collage.py
------------------------
Lit les tableaux Budget Your Trip copiés-collés dans data/raw/budget_collage.txt
et remplit automatiquement data/saisie_budget.csv (aucune saisie de chiffres à la main).

Format du fichier de collage : pour chaque pays, une ligne « === nom-de-la-page === »
(le nom tel qu'il apparaît dans l'adresse : france, costa-rica...), puis le tableau
collé tel quel depuis le site, puis la ligne « Travel Costs Last Updated: ... ».

Lancement depuis la racine du projet :
    python scripts/import_budget_collage.py
puis :
    python scripts/build_budget.py
"""

import csv
import datetime
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_COLLAGE = RACINE / "data" / "raw" / "budget_collage.txt"
FICHIER_SAISIE = RACINE / "data" / "saisie_budget.csv"

PAGES = {   # nom dans l'adresse de la page -> code ISO3
    "france": "FRA", "italy": "ITA", "portugal": "PRT", "greece": "GRC", "switzerland": "CHE",
    "hungary": "HUN", "south-korea": "KOR", "thailand": "THA", "vietnam": "VNM",
    "indonesia": "IDN", "nepal": "NPL", "united-arab-emirates": "ARE", "jordan": "JOR",
    "morocco": "MAR", "tanzania": "TZA", "ghana": "GHA", "canada": "CAN", "costa-rica": "CRI",
    "colombia": "COL", "peru": "PER", "argentina": "ARG",
    # pays déjà relevés, acceptés aussi si tu veux les recoller pour vérification
    "spain": "ESP", "united-kingdom": "GBR", "iceland": "ISL", "croatia": "HRV", "japan": "JPN",
    "china": "CHN", "india": "IND", "sri-lanka": "LKA", "laos": "LAO", "turkey": "TUR",
    "egypt": "EGY", "south-africa": "ZAF", "kenya": "KEN", "senegal": "SEN",
    "united-states-of-america": "USA", "mexico": "MEX", "brazil": "BRA", "chile": "CHL",
    "australia": "AUS", "new-zealand": "NZL",
}
# Libellé sur le site -> colonne du fichier de saisie (dans l'ordre du tableau)
CATEGORIES = [("Accommodation", "hebergement"), ("Local Transportation", "transport"),
              ("Food", "repas"), ("Entertainment", "activites")]
NIVEAUX = ["petit", "moyen", "confort"]   # colonnes Budget, Mid-Range, Luxury
MOIS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def lire_blocs(texte):
    """Découpe le fichier en {nom_de_page: texte collé}."""
    blocs, nom = {}, None
    for ligne in texte.splitlines():
        m = re.match(r"\s*===\s*([a-z-]+)\s*===\s*$", ligne.strip().lower())
        if m:
            nom = m.group(1)
            blocs[nom] = ""
        elif nom:
            blocs[nom] += ligne + "\n"
    return blocs


def extraire(nom, bloc):
    """Renvoie ({niveau: {colonne: montant}}, date_maj) ou lève ValueError."""
    if not bloc.strip():
        raise ValueError("rien de collé")
    # On retire les montants en monnaie locale, entre parenthèses : (€49), (C$69), (₩27,495)...
    sans_parentheses = re.sub(r"\([^)]*\)", " ", bloc)
    libelles = [c for c, _ in CATEGORIES] + ["Alcohol", "Travel Costs"]
    resultat = {n: {} for n in NIVEAUX}
    for libelle, colonne in CATEGORIES:
        debut = sans_parentheses.find(libelle)
        if debut < 0:
            raise ValueError(f"ligne « {libelle} » introuvable")
        suite = sans_parentheses[debut + len(libelle):]
        fins = [suite.find(l) for l in libelles if suite.find(l) >= 0]
        cellule = suite[:min(fins)] if fins else suite
        montants = re.findall(r"\$\s*([\d,]+(?:\.\d+)?)(?!\s*-)", cellule)
        if len(montants) != 3:
            raise ValueError(f"« {libelle} » : {len(montants)} montant(s) trouvé(s) au lieu de 3")
        for niveau, valeur in zip(NIVEAUX, montants):
            resultat[niveau][colonne] = float(valeur.replace(",", ""))

    m = re.search(r"Last Updated:?\s*([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", bloc)
    if not m:
        raise ValueError("ligne « Travel Costs Last Updated » introuvable (colle-la aussi)")
    date = datetime.date(int(m.group(3)), MOIS[m.group(1).lower()], int(m.group(2)))
    return resultat, date.isoformat()


def main():
    if not FICHIER_COLLAGE.exists():
        sys.exit(f"Fichier manquant : {FICHIER_COLLAGE.relative_to(RACINE)}")
    blocs = lire_blocs(FICHIER_COLLAGE.read_text(encoding="utf-8-sig"))
    print(f"1. {len(blocs)} pays trouvés dans {FICHIER_COLLAGE.name}")

    with FICHIER_SAISIE.open(encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f)
        champs = list(lecteur.fieldnames)
        lignes = list(lecteur)
    if "date_maj_site" not in champs:
        champs.append("date_maj_site")

    print("2. Extraction")
    importes, problemes, vides = [], [], []
    aujourd_hui = datetime.date.today().isoformat()
    for nom, bloc in blocs.items():
        if nom not in PAGES:
            problemes.append(f"{nom} : nom de page inconnu (vérifie l'orthographe de la ligne ===)")
            continue
        try:
            valeurs, date_maj = extraire(nom, bloc)
        except ValueError as erreur:
            if str(erreur) == "rien de collé":
                vides.append(nom)
            else:
                problemes.append(f"{nom} : {erreur}")
            continue
        if not date_maj.startswith("2026"):
            problemes.append(f"{nom} : mis à jour le {date_maj}, données trop anciennes -> ignoré")
            continue
        iso3 = PAGES[nom]
        for l in lignes:
            if l["iso3"] == iso3 and l["niveau"] in valeurs:
                l.update({k: str(v) for k, v in valeurs[l["niveau"]].items()})
                l.update(total_site="", url=f"https://www.budgetyourtrip.com/{nom}",
                         date_releve=aujourd_hui, date_maj_site=date_maj)
        importes.append(f"{iso3} ({nom}, maj {date_maj}) : moyen = "
                        + " / ".join(f"{valeurs['moyen'][c]:g}" for _, c in CATEGORIES))

    if problemes:
        print("\nProblèmes (ces pays n'ont PAS été importés) :")
        for p in problemes:
            print("  -", p)

    with FICHIER_SAISIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=champs, restval="")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    print(f"\n=== Importés ({len(importes)}) — héberg. / transport / repas / activités ===")
    for i in importes:
        print("  ", i)
    if vides:
        print(f"\nPas encore collés ({len(vides)}) : {', '.join(vides)}")
    print(f"\n{FICHIER_SAISIE.name} mis à jour. Lance maintenant : py scripts\\build_budget.py")


if __name__ == "__main__":
    main()
