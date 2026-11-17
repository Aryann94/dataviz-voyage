"""
test_comptage_unesco.py
-----------------------
Vérifie que le comptage des sites UNESCO, recalculé à partir des données brutes
(data/raw/wikidata_unesco.json, extraction du 16/10/2026) et de data/corrections_unesco.csv,
retombe EXACTEMENT sur les colonnes unesco_* de data/pays.csv.

Sert de garde-fou quand on modifie build_pays_wikidata.py (sans réinterroger Wikidata).
Lancement depuis la racine :
    py scripts/test_comptage_unesco.py
"""

import csv
import json
import sys
from pathlib import Path

import build_pays_wikidata as bpw

RACINE = Path(__file__).resolve().parent.parent
COLONNES = ["unesco_culturel", "unesco_naturel", "unesco_mixte"]


def main():
    brut = json.loads((RACINE / "data" / "raw" / "wikidata_unesco.json").read_text(encoding="utf-8"))
    with (RACINE / "data" / "pays.csv").open(encoding="utf-8", newline="") as f:
        attendu = {l["iso3"]: l for l in csv.DictReader(f)}
    comptes = bpw.compter_unesco(brut, list(attendu))

    ecarts = []
    for iso3, ligne in attendu.items():
        for col in COLONNES:
            if int(ligne[col]) != comptes[iso3][col]:
                ecarts.append(f"{iso3} {col} : pays.csv {ligne[col]}, recalculé {comptes[iso3][col]}")
        if comptes[iso3]["unesco_sans_categorie"]:
            ecarts.append(f"{iso3} : {comptes[iso3]['unesco_sans_categorie']} site(s) sans catégorie")
        total = sum(comptes[iso3][c] for c in COLONNES)
        if int(ligne["unesco_total"]) != total:
            ecarts.append(f"{iso3} total : pays.csv {ligne['unesco_total']}, recalculé {total}")

    if ecarts:
        sys.exit("ÉCHEC du test de comptage UNESCO :\n  - " + "\n  - ".join(ecarts))
    n = sum(int(l["unesco_total"]) for l in attendu.values())
    print(f"OK : {len(attendu)} pays, {n} sites, culturel / naturel / mixte identiques à pays.csv")


if __name__ == "__main__":
    main()
