"""
build_carte.py
--------------
Fond de carte du globe des visas et de la carte à plat de secours :
data/carte/pays_carte.topojson + data/carte/correspondance_carte.csv.

Source : Natural Earth v5.1.2, pays (admin 0), échelle 1:10 millions,
POINT DE VUE DE LA FRANCE (ne_10m_admin_0_countries_fra) : frontières telles que la
France les reconnaît (Crimée en Ukraine, Somaliland dans la Somalie, Kosovo présent).
Limite : le Sahara occidental y est rattaché au Maroc (position française, pas celle de l'ONU).

Étapes :
  1. téléchargement (version figée) et contrôle de l'empreinte SHA-256 ;
  2. jointure sur ADM0_A3 avec les 199 codes de data/pays_monde.csv (+ 3 cas en table) ;
  3. territoires sans passeport en gris, avec leur pays souverain ;
  4. repères cliquables pour les pays de moins de 3 000 km² ;
  5. simplification par mapshaper (garde les frontières communes), sortie TopoJSON ;
  6. contrôles après simplification (aucun pays ni aucune île perdus) et rapport.

Python, bibliothèque standard (+ certifi). L'étape 5 appelle mapshaper par npx
(Node.js requis). Lancement depuis la racine :
    py scripts/build_carte.py
"""

import csv
import gzip
import hashlib
import json
import math
import shutil
import subprocess
import sys
import urllib.request
from collections import Counter
from pathlib import Path

from build_pays_wikidata import CONTEXTE_SSL, USER_AGENT

# --- Configuration -----------------------------------------------------------

VERSION_NE = "v5.1.2"
FICHIER_NE = "ne_10m_admin_0_countries_fra.geojson"
URL_NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
          f"{VERSION_NE}/geojson/{FICHIER_NE}")
SHA256_NE = "273def0394f5e344ff4938b1cbe9c48f36aea2e8e1635a8814768bc50f5dd44c"

# mapshaper : version figée (0.7.101 du 29/10/2026 ; la série 0.8 est trop récente)
MAPSHAPER = "mapshaper@0.7.101"
# Part des points gardés (Visvalingam pondéré). Mesuré le 17/11 : à 6 % on perdait des
# îles de plus de 500 km² ; à 25 %, toutes les îles de plus de 100 km² restent, pour ~1 Mo.
SIMPLIFICATION = "25%"
# Grille de la TopoJSON : 1/400 000 de l'étendue (≈ 100 m). À 1/100 000 (≈ 400 m), le
# Vatican était écrasé en un segment d'aire nulle, que D3 peut prendre pour le globe entier.
QUANTIFICATION = 400000
# keep-shapes garantit une forme par PAYS, pas chaque île : les îlots disparaissent.
# Règle : toute île d'au moins ILE_MIN_KM2 doit survivre (contrôle bloquant).
ILE_MIN_KM2 = 100

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_BRUT = RACINE / "data" / "raw" / "natural_earth"     # non commité (.gitignore)
FICHIER_BRUT = DOSSIER_BRUT / FICHIER_NE
FICHIER_AVANT = DOSSIER_BRUT / "carte_avant_simplification.geojson"
FICHIER_PAYS = RACINE / "data" / "pays_monde.csv"
DOSSIER_SORTIE = RACINE / "data" / "carte"
FICHIER_TOPO = DOSSIER_SORTIE / "pays_carte.topojson"
FICHIER_CORRESPONDANCE = DOSSIER_SORTIE / "correspondance_carte.csv"

# Codes Natural Earth qui diffèrent du code Passport Index
TABLE_CODES = {
    "PSX": ("PSE", "Natural Earth : PSX (Palestine) ; ISO 3166 : PSE"),
    "SDS": ("SSD", "Natural Earth : SDS (Soudan du Sud) ; ISO 3166 : SSD"),
    "KOS": ("XKX", "Kosovo : pas de code ISO officiel ; XKX = code d'usage (UE, Banque mondiale)"),
}

SEUIL_REPERE_KM2 = 3000      # en dessous, un point cliquable en plus de la forme (Luxembourg et Samoa inclus)

# NAME_FR de Natural Earth faux ou à corriger (territoires sans passeport uniquement)
NOMS_TERRITOIRES = {
    "PGA": "Îles Spratleys",                 # Natural Earth : « Wake » (erreur)
}

# Champ TYPE de Natural Earth, pour la colonne note de correspondance_carte.csv
TYPES_FR = {
    "Country": "pays constitutif",           # Groenland, Aruba, Jersey...
    "Dependency": "dépendance",
    "Disputed": "territoire disputé",
    "Indeterminate": "statut indéterminé",
    "Lease": "territoire à bail",
}

RAYON_TERRE_KM = 6371.0088

avertissements = []


def avertir(message):
    avertissements.append(message)


# --- Étape 1 : la source -----------------------------------------------------------

def empreinte(chemin):
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def charger_source():
    if not FICHIER_BRUT.exists():
        print(f"   téléchargement de {URL_NE}")
        DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL_NE, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=120, context=CONTEXTE_SSL) as r:
            FICHIER_BRUT.write_bytes(r.read())
    obtenue = empreinte(FICHIER_BRUT)
    if obtenue != SHA256_NE:
        sys.exit(f"Empreinte SHA-256 différente : {obtenue}\nattendue : {SHA256_NE}\n"
                 f"Le fichier a changé : supprime {FICHIER_BRUT.name} et relance, "
                 "ou vérifie la version.")
    return json.loads(FICHIER_BRUT.read_text(encoding="utf-8"))


# --- Utilitaires géométriques ----------------------------------------------------------

def polygones(geometrie):
    if geometrie["type"] == "Polygon":
        return [geometrie["coordinates"]]
    if geometrie["type"] == "MultiPolygon":
        return geometrie["coordinates"]
    return []


def aire_anneau_km2(anneau):
    """Aire sur la sphère (formule utilisée par OpenLayers et Turf), en km², non signée."""
    total = 0.0
    for (lon1, lat1), (lon2, lat2) in zip(anneau, anneau[1:]):
        total += math.radians(lon2 - lon1) * (
            2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2)))
    return abs(total) * RAYON_TERRE_KM ** 2 / 2


def aire_km2(geometrie):
    return sum(aire_anneau_km2(p[0]) - sum(aire_anneau_km2(t) for t in p[1:])
               for p in polygones(geometrie))


# --- Étapes 2 à 4 : jointure, territoires, repères ------------------------------------------

def lire_pays():
    with FICHIER_PAYS.open(encoding="utf-8", newline="") as f:
        return {l["iso3"]: l["nom_fr"] for l in csv.DictReader(f)}


def preparer(source, pays):
    entites = source["features"]
    # pays souverain d'un territoire : l'entité « partie principale » (HOMEPART = 1) du même SOV_A3
    principale = {e["properties"]["SOV_A3"]: e["properties"]["ADM0_A3"]
                  for e in entites if e["properties"]["HOMEPART"] == 1}

    sorties, correspondance, vus = [], [], Counter()
    for e in entites:
        p = e["properties"]
        adm0 = p["ADM0_A3"]
        iso3, note = TABLE_CODES.get(adm0, (adm0, ""))
        couvert = iso3 in pays
        regle = ("table" if adm0 in TABLE_CODES else "identique") if couvert else "sans_passeport"
        surface = aire_km2(e["geometry"])

        if couvert:
            vus[iso3] += 1
            nom, souverain = pays[iso3], None
        else:
            iso3 = None
            nom = NOMS_TERRITOIRES.get(adm0, p["NAME_FR"] or p["NAME"])
            nom = nom[0].upper() + nom[1:]                    # « îles Caïmans » -> « Îles Caïmans »
            # pas d'entité principale : zone sans souverain (Bir Tawil, Antarctique...)
            code_souv = principale.get(p["SOV_A3"])
            code_souv = TABLE_CODES.get(code_souv, (code_souv, ""))[0]
            souverain = pays.get(code_souv) if code_souv and code_souv != adm0 else None
            if code_souv and code_souv != adm0 and not souverain:
                avertir(f"{adm0} ({nom}) : pays souverain {p['SOVEREIGNT']} introuvable")
            if not note:
                note = TYPES_FR.get(p["TYPE"], p["TYPE"]) + (
                    f", souverain : {souverain}" if souverain else "")

        repere = couvert and surface < SEUIL_REPERE_KM2
        proprietes = {
            "iso3": iso3, "adm0_a3": adm0, "nom_fr": nom, "couvert": couvert,
            "souverain": souverain,
            # mapshaper garde mal les tableaux : deux colonnes, regroupées après coup
            "repere_lon": round(p["LABEL_X"], 3) if repere else None,
            "repere_lat": round(p["LABEL_Y"], 3) if repere else None,
        }
        sorties.append({"type": "Feature", "properties": proprietes, "geometry": e["geometry"]})
        correspondance.append({
            "adm0_a3": adm0, "nom_ne": p["NAME"], "iso_a3_ne": p["ISO_A3"],
            "iso3_passeport": iso3 or "", "regle": regle,
            "repere": "true" if repere else "false",
            "surface_km2": round(surface, 1), "note": note,
        })

    # --- Contrôles bloquants ---
    erreurs = []
    manquants = sorted(set(pays) - set(vus))
    if manquants:
        erreurs.append(f"codes passeport absents de la carte : {manquants}")
    doublons = sorted(c for c, n in vus.items() if n > 1)
    if doublons:
        erreurs.append(f"codes passeport présents plusieurs fois : {doublons}")
    inutiles = sorted(set(TABLE_CODES) - {e["properties"]["ADM0_A3"] for e in entites})
    if inutiles:
        erreurs.append(f"TABLE_CODES contient des codes absents de la carte : {inutiles}")
    if erreurs:
        sys.exit("Contrôles échoués :\n  - " + "\n  - ".join(erreurs))
    return sorties, correspondance


# --- Étape 5 : mapshaper ----------------------------------------------------------------

def commande_mapshaper(entree, sortie):
    return [
        "-i", str(entree),
        "-clean",                                    # répare les défauts de géométrie
        "-simplify", "visvalingam", "weighted", SIMPLIFICATION, "keep-shapes",
        "-rename-layers", "pays",
        "-o", "format=topojson", f"quantization={QUANTIFICATION}", str(sortie),
    ]


def lancer_mapshaper(entree, sortie):
    npx = shutil.which("npx")
    if not npx:
        sys.exit("npx introuvable : installe Node.js (https://nodejs.org) puis relance.")
    commande = [npx, "--yes", MAPSHAPER] + commande_mapshaper(entree, sortie)
    print("   " + " ".join(["npx", "--yes", MAPSHAPER] + commande_mapshaper(
        entree.relative_to(RACINE), sortie.relative_to(RACINE))))
    resultat = subprocess.run(commande, capture_output=True, text=True, encoding="utf-8")
    for ligne in (resultat.stdout + resultat.stderr).splitlines():
        print("   | " + ligne)
    if resultat.returncode != 0:
        sys.exit("mapshaper a échoué")


# --- Étape 6 : relecture de la TopoJSON -------------------------------------------------------

def decoder_arcs(topo):
    """Arcs quantifiés et codés en différences -> coordonnées en degrés."""
    (kx, ky), (dx, dy) = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        points = []
        for px, py in arc:
            x, y = x + px, y + py
            points.append((x * kx + dx, y * ky + dy))
        arcs.append(points)
    return arcs


def anneau(arcs, indices):
    points = []
    for i in indices:
        arc = arcs[i] if i >= 0 else arcs[~i][::-1]
        points.extend(arc if not points else arc[1:])
    return points


def polygones_topo(geometrie, arcs):
    if geometrie.get("type") == "Polygon":
        liste = [geometrie["arcs"]]
    elif geometrie.get("type") == "MultiPolygon":
        liste = geometrie["arcs"]
    else:
        return []
    return [[anneau(arcs, r) for r in poly] for poly in liste]


def aire_plane_signee(points):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:])) / 2


def finaliser(aires_avant):
    """
    aires_avant : adm0_a3 -> aires (km²) des polygones de la source.
    Une île de la source (>= ILE_MIN_KM2) est perdue si le pays a moins de polygones d'au
    moins la moitié de cette taille après simplification (marge pour les contours simplifiés).
    """
    topo = json.loads(FICHIER_TOPO.read_text(encoding="utf-8"))
    arcs = decoder_arcs(topo)
    geometries = topo["objects"]["pays"]["geometries"]
    pertes, vides, sens = [], [], Counter()
    ilots_retires = 0
    for g in geometries:
        pr = g["properties"]
        # repère en un seul champ [lon, lat] ou null
        lon, lat = pr.pop("repere_lon", None), pr.pop("repere_lat", None)
        pr["repere"] = [lon, lat] if lon is not None else None
        pr["couvert"] = pr["couvert"] in (True, "true")
        for cle in ("iso3", "souverain"):
            pr[cle] = pr.get(cle) or None

        polys = polygones_topo(g, arcs)
        if not polys:
            vides.append(pr["adm0_a3"])
            continue
        avant = aires_avant[pr["adm0_a3"]]
        apres = [aire_anneau_km2(p[0]) for p in polys]
        grandes_avant = sum(a >= ILE_MIN_KM2 for a in avant)
        grandes_apres = sum(a >= ILE_MIN_KM2 / 2 for a in apres)
        if grandes_apres < grandes_avant:
            pertes.append(f"{pr['adm0_a3']} {pr['nom_fr']} : {grandes_avant - grandes_apres} "
                          f"île(s) de plus de {ILE_MIN_KM2} km²")
        ilots_retires += max(0, len(avant) - len(polys))
        # orientation : D3 attend l'extérieur dans le sens horaire (aire plane négative) ;
        # un contour plat ou à l'envers serait dessiné comme « tout le globe sauf ce pays »
        for p in polys:
            horaire = aire_plane_signee(p[0]) < 0
            sens["horaire" if horaire else "antihoraire ou plat"] += 1
            if not horaire:
                pertes.append(f"{pr['adm0_a3']} {pr['nom_fr']} : contour extérieur plat ou à l'envers")
    FICHIER_TOPO.write_text(json.dumps(topo, ensure_ascii=False, separators=(",", ":")),
                            encoding="utf-8")
    return geometries, pertes, vides, sens, ilots_retires


def tailles(chemin):
    brut = chemin.read_bytes()
    return len(brut), len(gzip.compress(brut, compresslevel=9))


def ko(n):
    return f"{n / 1024:,.0f} Ko".replace(",", " ")


# --- Programme principal -------------------------------------------------------------------

def main():
    print(f"1. Natural Earth {VERSION_NE}, {FICHIER_NE}")
    source = charger_source()
    print(f"   {len(source['features'])} entités, empreinte SHA-256 conforme")

    pays = lire_pays()
    print(f"2. Jointure ADM0_A3 avec les {len(pays)} codes de {FICHIER_PAYS.name}")
    entites, correspondance = preparer(source, pays)

    FICHIER_AVANT.write_text(json.dumps({"type": "FeatureCollection", "features": entites},
                                        ensure_ascii=False), encoding="utf-8")
    print("3. mapshaper")
    DOSSIER_SORTIE.mkdir(parents=True, exist_ok=True)
    lancer_mapshaper(FICHIER_AVANT, FICHIER_TOPO)

    print("4. Contrôles après simplification")
    aires = {e["properties"]["adm0_a3"]: [aire_anneau_km2(p[0]) for p in polygones(e["geometry"])]
             for e in entites}
    geometries, pertes, vides, sens, ilots_retires = finaliser(aires)
    erreurs = []
    if len(geometries) != len(entites):
        erreurs.append(f"{len(entites)} entités avant, {len(geometries)} après")
    if vides:
        erreurs.append(f"entités vides après simplification : {vides}")
    codes_apres = {g["properties"]["iso3"] for g in geometries} - {None}
    if codes_apres != set(pays):
        erreurs.append(f"codes perdus : {sorted(set(pays) - codes_apres)}")
    if pertes:
        erreurs.append("formes perdues ou abîmées :\n      " + "\n      ".join(pertes))
    if erreurs:
        sys.exit("Contrôles échoués :\n  - " + "\n  - ".join(erreurs))
    total_avant = sum(len(v) for v in aires.values())
    print(f"   199 codes présents, aucune entité vide, aucune île de plus de {ILE_MIN_KM2} km² perdue")
    print(f"   îlots retirés par la simplification : {ilots_retires} sur {total_avant} polygones")

    with FICHIER_CORRESPONDANCE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(correspondance[0]))
        ecrivain.writeheader()
        ecrivain.writerows(sorted(correspondance, key=lambda l: l["adm0_a3"]))

    # --- Rapport ---
    print("\n=== Codes réglés par la table ===")
    for adm0, (iso3, note) in TABLE_CODES.items():
        print(f"  {adm0} -> {iso3}  ({note})")

    gris = [l for l in correspondance if l["regle"] == "sans_passeport"]
    print(f"\n=== Territoires sans passeport, en gris ({len(gris)}) ===")
    for l in sorted(gris, key=lambda l: l["adm0_a3"]):
        print(f"  {l['adm0_a3']}  {l['nom_ne'][:34]:<35}{l['note']}")

    reperes = sorted((l for l in correspondance if l["repere"] == "true"),
                     key=lambda l: l["surface_km2"])
    print(f"\n=== Repères (moins de {SEUIL_REPERE_KM2} km² sur la carte) : {len(reperes)} pays ===")
    for l in reperes:
        print(f"  {l['iso3_passeport']}  {pays[l['iso3_passeport']]:<34}{l['surface_km2']:>9.1f} km²")

    points_avant = sum(len(r) for e in entites for p in polygones(e["geometry"]) for r in p)
    topo = json.loads(FICHIER_TOPO.read_text(encoding="utf-8"))
    points_apres = sum(len(a) for a in topo["arcs"])
    brut_avant, gz_avant = tailles(FICHIER_BRUT)
    brut_apres, gz_apres = tailles(FICHIER_TOPO)
    print("\n=== Taille ===")
    print(f"  points : {points_avant:,} avant, {points_apres:,} après (arcs partagés)".replace(",", " "))
    print(f"  avant : {FICHIER_NE} : {ko(brut_avant)} brut, {ko(gz_avant)} compressé (gzip)")
    print(f"  après : {FICHIER_TOPO.name} : {ko(brut_apres)} brut, {ko(gz_apres)} compressé (gzip)")
    print(f"  orientation des contours extérieurs : {dict(sens)}")

    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


if __name__ == "__main__":
    main()
