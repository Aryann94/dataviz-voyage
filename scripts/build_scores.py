"""
build_scores.py
---------------
Calcule les 5 scores du quiz (0 à 100) pour chaque pays, à partir de data/pays.csv,
et écrit data/scores.csv. Les scores sont des données DÉRIVÉES : pays.csv garde
les faits bruts, scores.csv nos choix de calcul (documentés ci-dessous).

Les 5 axes :
  culture      sites UNESCO culturels + mixtes (logarithme : passer de 2 à 10 sites
               compte plus que de 50 à 58, l'Italie n'écrase pas tout)
  nature       ½ faible densité de population + ¼ sites UNESCO naturels et mixtes
               + ¼ zones terrestres protégées (la densité pèse le plus : les zones
               protégées « sur le papier » avantagent l'Europe)
  villes       part de la population dans des villes de plus d'un million d'habitants
  prix         niveau des prix inversé (100 = le moins cher), en logarithme
  distance     distance à vol d'oiseau entre Paris et la capitale (100 = le plus loin)

Chaque axe est ramené de 0 à 100 PAR RAPPORT AUX PAYS DE LA LISTE :
le plus fort obtient 100, le plus faible 0. Un score est donc relatif à la sélection.

Le script se termine par un test : quelques profils de voyageurs types et les pays
qui leur correspondent le mieux, avec la même méthode que celle du site
(« le pays qui te ressemble le plus »).

Aucun appel réseau. Lancement depuis la racine du projet :
    python scripts/build_scores.py
"""

import csv
import datetime
import math
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_PAYS = RACINE / "data" / "pays.csv"
FICHIER_SORTIE = RACINE / "data" / "scores.csv"

PARIS = (48.8567, 2.3522)
POIDS_NATURE = {"densite": 0.50, "unesco": 0.25, "protegees": 0.25}
AXES = ["culture", "nature", "villes", "prix", "distance"]


# --- Outils ------------------------------------------------------------------------

def ramener_0_100(valeurs):
    """Le plus petit devient 0, le plus grand 100, le reste proportionnellement."""
    bas, haut = min(valeurs.values()), max(valeurs.values())
    return {k: 100 * (v - bas) / (haut - bas) for k, v in valeurs.items()}


def distance_km(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau sur la sphère terrestre (formule de haversine)."""
    p1, l1, p2, l2 = map(math.radians, (lat1, lon1, lat2, lon2))
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin((l2 - l1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


# --- Calcul des scores ---------------------------------------------------------------

def calculer(pays):
    v = lambda l, c: float(l[c])
    culture = ramener_0_100({l["iso3"]: math.log1p(v(l, "unesco_culturel") + v(l, "unesco_mixte"))
                             for l in pays})
    densite = ramener_0_100({l["iso3"]: -math.log(v(l, "densite_hab_km2")) for l in pays})
    unesco_nat = ramener_0_100({l["iso3"]: math.log1p(v(l, "unesco_naturel") + v(l, "unesco_mixte"))
                                for l in pays})
    protegees = ramener_0_100({l["iso3"]: v(l, "zones_protegees_pct") for l in pays})
    nature = ramener_0_100({k: POIDS_NATURE["densite"] * densite[k]
                               + POIDS_NATURE["unesco"] * unesco_nat[k]
                               + POIDS_NATURE["protegees"] * protegees[k] for k in densite})
    villes = ramener_0_100({l["iso3"]: v(l, "pop_villes_1m_pct") for l in pays})
    prix = ramener_0_100({l["iso3"]: -math.log(v(l, "niveau_prix")) for l in pays})
    km = {l["iso3"]: distance_km(*PARIS, v(l, "lat"), v(l, "lon")) for l in pays}
    distance = ramener_0_100(km)
    return {
        l["iso3"]: {
            "culture": culture[l["iso3"]], "nature": nature[l["iso3"]],
            "villes": villes[l["iso3"]], "prix": prix[l["iso3"]],
            "distance": distance[l["iso3"]], "distance_paris_km": km[l["iso3"]],
        } for l in pays
    }


# --- Correspondance joueur / pays (même logique que sur le site) ---------------------

def compatibilite(profil, scores):
    """
    profil : {axe: (valeur souhaitée 0-100, importance 0-1)} ; importance 0 = « peu m'importe ».
    Renvoie un pourcentage : 100 % = le pays a exactement le profil souhaité.
    """
    ecart = sum(imp * (souhait - scores[axe]) ** 2 for axe, (souhait, imp) in profil.items())
    ecart_max = sum(imp * 100 ** 2 for _, imp in profil.values())
    return 100 * (1 - math.sqrt(ecart / ecart_max)) if ecart_max else 0


PROFILS_TEST = {
    "Grandes villes et culture, loin":   {"culture": (80, 1), "nature": (30, .5), "villes": (100, 1),
                                          "prix": (40, .5), "distance": (90, .5)},
    "Nature sauvage, budget peu importe": {"culture": (20, .5), "nature": (100, 1), "villes": (0, 1),
                                          "prix": (0, 0), "distance": (50, 0)},
    "Petit budget, dépaysement":         {"culture": (60, .5), "nature": (50, .5), "villes": (30, .5),
                                          "prix": (100, 1), "distance": (90, 1)},
    "Culture, pas trop loin":            {"culture": (100, 1), "nature": (40, .5), "villes": (40, .5),
                                          "prix": (50, .5), "distance": (10, 1)},
    "Indifférent à tout sauf le prix":   {"culture": (50, 0), "nature": (50, 0), "villes": (50, 0),
                                          "prix": (100, 1), "distance": (50, 0)},
}


# --- Programme principal -------------------------------------------------------------

def main():
    if not FICHIER_PAYS.exists():
        sys.exit("data/pays.csv manquant : lance d'abord build_pays.py")
    with FICHIER_PAYS.open(encoding="utf-8", newline="") as f:
        pays = [l for l in csv.DictReader(f) if l["dans_quiz"] == "true"]
    noms = {l["iso3"]: l["nom_fr"] for l in pays}
    print(f"1. {len(pays)} pays du quiz lus dans pays.csv")

    scores = calculer(pays)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["iso3"] + [f"score_{a}" for a in AXES]
                          + ["distance_paris_km", "date_calcul"])
        for iso3, s in scores.items():
            ecrivain.writerow([iso3] + [round(s[a]) for a in AXES]
                              + [round(s["distance_paris_km"]), datetime.date.today().isoformat()])
    print(f"2. Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    print("\n=== Les 3 premiers et les 2 derniers de chaque axe ===")
    for axe in AXES:
        classes = sorted(scores, key=lambda k: -scores[k][axe])
        haut = ", ".join(f"{noms[k]} {scores[k][axe]:.0f}" for k in classes[:3])
        bas = ", ".join(f"{noms[k]} {scores[k][axe]:.0f}" for k in classes[-2:])
        print(f"{axe:9} : {haut}   …   {bas}")

    print("\n=== Quelques pays (culture / nature / villes / prix / distance) ===")
    for iso3 in ["JPN", "FRA", "ISL", "IND", "THA", "MAR", "USA", "NZL"]:
        if iso3 in scores:
            print(f"  {noms[iso3]:14} " + " / ".join(f"{scores[iso3][a]:3.0f}" for a in AXES))

    print("\n=== Test : profils de voyageurs et pays proposés ===")
    for nom, profil in PROFILS_TEST.items():
        classement = sorted(scores, key=lambda k: -compatibilite(profil, scores[k]))
        top = ", ".join(f"{noms[k]} ({compatibilite(profil, scores[k]):.0f} %)" for k in classement[:3])
        print(f"  {nom:36} -> {top}")

    gagnants = {}
    for profil in PROFILS_TEST.values():
        k = max(scores, key=lambda k: compatibilite(profil, scores[k]))
        gagnants[k] = gagnants.get(k, 0) + 1
    print(f"\n{len(gagnants)} pays différents arrivent en tête pour {len(PROFILS_TEST)} profils.")


if __name__ == "__main__":
    main()
