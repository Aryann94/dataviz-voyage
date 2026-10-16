"""
build_scores.py
---------------
Calcule les 6 scores du quiz (0 à 100) pour chaque pays, à partir de data/pays.csv,
et écrit data/scores.csv. Les scores sont des données DÉRIVÉES : pays.csv garde
les faits bruts, scores.csv nos choix de calcul (documentés ci-dessous).

Les 6 axes :
  culture      sites UNESCO culturels + mixtes (logarithme : passer de 2 à 10 sites
               compte plus que de 50 à 58, l'Italie n'écrase pas tout)
  nature       ½ « espaces naturels » + ¼ sites UNESCO naturels et mixtes
               + ¼ zones terrestres protégées.
               « Espaces naturels » = le MEILLEUR des deux : faible densité de population
               (grands espaces vides : Islande, Australie) OU forte couverture de forêt
               (pays peuplés mais très verts : Japon, Corée, Costa Rica). Avec la densité
               seule, un pays peuplé ne pouvait pas être « nature », même couvert de forêts.
  villes       part de la population dans des villes de plus d'un million d'habitants
  prix         niveau des prix inversé (100 = le moins cher), en logarithme
  distance     distance à vol d'oiseau entre Paris et la capitale (100 = le plus loin)
  mer          chaleur × côtes. Côtes = ½ longueur des côtes + ½ côtes par km² de terres
               (un archipel comme la Grèce compte autant qu'un très grand pays côtier).
               Chaleur = d'après la latitude du centre du pays : 1 jusqu'à 30°, 0 à partir
               de 60°, entre les deux proportionnellement (le Canada a les plus longues
               côtes du monde, mais on ne s'y baigne pas). Sans accès à la mer -> 0.
               Limite : mesure le POTENTIEL (beaucoup de côtes, latitude chaude), pas les
               plages de sable ni la réputation ; les courants froids (Chili) sont ignorés.

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
POIDS_NATURE = {"espaces": 0.50, "unesco": 0.25, "protegees": 0.25}
LATITUDE_CHAUDE, LATITUDE_FROIDE = 30, 60
AXES = ["culture", "nature", "villes", "prix", "distance", "mer"]


# --- Outils ------------------------------------------------------------------------

def ramener_0_100(valeurs):
    """Le plus petit devient 0, le plus grand 100, le reste proportionnellement."""
    bas, haut = min(valeurs.values()), max(valeurs.values())
    return {k: 100 * (v - bas) / (haut - bas) for k, v in valeurs.items()}


def chaleur(latitude):
    """1 près de l'équateur (jusqu'à 30°), 0 au-delà de 60°, proportionnel entre les deux."""
    lat = abs(latitude)
    return min(1, max(0, (LATITUDE_FROIDE - lat) / (LATITUDE_FROIDE - LATITUDE_CHAUDE)))


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
    foret = ramener_0_100({l["iso3"]: v(l, "foret_pct") for l in pays})
    espaces = {k: max(densite[k], foret[k]) for k in densite}
    unesco_nat = ramener_0_100({l["iso3"]: math.log1p(v(l, "unesco_naturel") + v(l, "unesco_mixte"))
                                for l in pays})
    protegees = ramener_0_100({l["iso3"]: v(l, "zones_protegees_pct") for l in pays})
    nature = ramener_0_100({k: POIDS_NATURE["espaces"] * espaces[k]
                               + POIDS_NATURE["unesco"] * unesco_nat[k]
                               + POIDS_NATURE["protegees"] * protegees[k] for k in densite})
    villes = ramener_0_100({l["iso3"]: v(l, "pop_villes_1m_pct") for l in pays})
    prix = ramener_0_100({l["iso3"]: -math.log(v(l, "niveau_prix")) for l in pays})
    km = {l["iso3"]: distance_km(*PARIS, v(l, "lat"), v(l, "lon")) for l in pays}
    distance = ramener_0_100(km)
    cotes = ramener_0_100({l["iso3"]: math.log1p(v(l, "cotes_km")) for l in pays})
    cotes_par_surface = ramener_0_100({
        l["iso3"]: math.log1p(1000 * v(l, "cotes_km") / v(l, "superficie_terres_km2")) for l in pays})
    mer = ramener_0_100({l["iso3"]: chaleur(v(l, "lat_centre")) * (cotes[l["iso3"]]
                                    + cotes_par_surface[l["iso3"]]) / 2 for l in pays})
    return {
        l["iso3"]: {
            "culture": culture[l["iso3"]], "nature": nature[l["iso3"]],
            "villes": villes[l["iso3"]], "prix": prix[l["iso3"]],
            "distance": distance[l["iso3"]], "mer": mer[l["iso3"]],
            "distance_paris_km": km[l["iso3"]],
        } for l in pays
    }


# --- Correspondance joueur / pays (même logique que sur le site) ---------------------

def poids_effectif(souhait, importance):
    """
    Une envie tiède (proche de 50) compte peu, une envie marquée (proche de 0 ou 100)
    compte beaucoup. Sans ce correctif, les pays « moyens partout » (le Brésil)
    gagnaient près d'une partie sur trois : testé sur les 27 648 combinaisons du quiz.
    """
    return importance * abs(souhait - 50) / 50


def compatibilite(profil, scores):
    """
    profil : {axe: (valeur souhaitée 0-100, importance 0-1)} ; importance 0 = « peu m'importe ».
    Les axes absents du profil ne comptent pas.
    Renvoie un pourcentage : 100 % = le pays a exactement le profil souhaité.
    Même formule que sur le site (fonction compat du prototype).
    """
    poids = {axe: poids_effectif(s, imp) for axe, (s, imp) in profil.items()}
    ecart = sum(poids[axe] * (s - scores[axe]) ** 2 for axe, (s, _) in profil.items())
    ecart_max = sum(p * 100 ** 2 for p in poids.values())
    return 100 * (1 - math.sqrt(ecart / ecart_max)) if ecart_max else 0


PROFILS_TEST = {
    # importance 0 = « peu m'importe » ; les axes absents ne comptent pas
    "Grandes villes et culture, loin":   {"culture": (80, 1), "nature": (30, .5), "villes": (100, 1),
                                          "prix": (40, .5), "distance": (90, .5)},
    "Nature sauvage, budget peu importe": {"culture": (20, .5), "nature": (100, 1), "villes": (0, 1)},
    "Petit budget, dépaysement":         {"culture": (60, .5), "nature": (50, .5), "villes": (30, .5),
                                          "prix": (100, 1), "distance": (90, 1)},
    "Culture, pas trop loin":            {"culture": (100, 1), "nature": (40, .5), "villes": (40, .5),
                                          "prix": (50, .5), "distance": (10, 1)},
    "Indifférent à tout sauf le prix":   {"prix": (100, 1)},
    "Plage et petit budget":             {"mer": (100, 1), "prix": (90, 1), "villes": (20, .5)},
    "Plage, pas trop loin":              {"mer": (100, 1), "distance": (10, 1)},
    "Grandes villes et campagne verte":  {"villes": (100, 1), "nature": (90, 1), "culture": (70, .5)},
}

# --- Programme principal -------------------------------------------------------------

def main():
    if not FICHIER_PAYS.exists():
        sys.exit("data/pays.csv manquant : lance d'abord build_pays.py")
    with FICHIER_PAYS.open(encoding="utf-8", newline="") as f:
        colonnes = csv.DictReader(f).fieldnames
    manque = [c for c in ["foret_pct", "cotes_km", "superficie_terres_km2", "lat_centre"]
              if c not in colonnes]
    if manque:
        sys.exit(f"pays.csv n'a pas les colonnes {manque} : lance build_pays_banquemondiale.py, "
                 "build_pays_cotes.py puis build_pays.py")
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

    print("\n=== Quelques pays (" + " / ".join(AXES) + ") ===")
    for iso3 in ["JPN", "FRA", "ISL", "IND", "THA", "GRC", "MAR", "USA", "NZL", "CHE"]:
        if iso3 in scores:
            print(f"  {noms[iso3]:14} " + " / ".join(f"{scores[iso3][a]:3.0f}" for a in AXES))

    print("\n=== Test : profils de voyageurs et pays proposés ===")
    for nom, profil in PROFILS_TEST.items():
        classement = sorted(scores, key=lambda k: -compatibilite(profil, scores[k]))
        top = ", ".join(f"{noms[k]} ({compatibilite(profil, scores[k]):.0f} %)" for k in classement[:3])
        print(f"  {nom:35} -> {top}")

    gagnants = {}
    for profil in PROFILS_TEST.values():
        k = max(scores, key=lambda k: compatibilite(profil, scores[k]))
        gagnants[k] = gagnants.get(k, 0) + 1
    print(f"\n{len(gagnants)} pays différents arrivent en tête pour {len(PROFILS_TEST)} profils.")


if __name__ == "__main__":
    main()
