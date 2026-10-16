"""
build_pays_cotes.py
-------------------
Récupère, pour les pays de data/pays_liste.csv, la longueur des côtes, la surface
des terres et la latitude du centre du pays, et écrit data/intermediaire/pays_cotes.csv.
Ces trois chiffres servent à l'axe « mer » du quiz (voir build_scores.py).

Source : CIA World Factbook (domaine public), copie archivée au format JSON sur
    https://github.com/factbook/factbook.json
La CIA a arrêté de publier le Factbook en février 2026 : on utilise donc la dernière
version archivée. Pour la longueur des côtes, ce n'est pas un problème, elle ne change pas.

Les fichiers JSON téléchargés sont gardés dans data/raw/factbook/ (preuve de la source,
et le script peut être relancé sans réseau).

Bibliothèque standard uniquement (+ certifi si installé). Lancement depuis la racine :
    python scripts/build_pays_cotes.py
"""

import csv
import datetime
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/factbook/factbook.json/master/{region}/{code}.json"
USER_AGENT = "ProjetDatavizVoyage/1.0 (projet etudiant, Universite Paris 8)"

RACINE = Path(__file__).resolve().parent.parent
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
DOSSIER_BRUT = RACINE / "data" / "raw" / "factbook"
FICHIER_SORTIE = RACINE / "data" / "intermediaire" / "pays_cotes.csv"

# Le Factbook n'utilise pas les codes ISO mais ses propres codes à 2 lettres,
# rangés par région. ISO3 -> (dossier de la région, code Factbook)
CODES_FACTBOOK = {
    "FRA": ("europe", "fr"), "ESP": ("europe", "sp"), "ITA": ("europe", "it"),
    "PRT": ("europe", "po"), "GRC": ("europe", "gr"), "GBR": ("europe", "uk"),
    "ISL": ("europe", "ic"), "HRV": ("europe", "hr"), "CHE": ("europe", "sz"),
    "HUN": ("europe", "hu"),
    "JPN": ("east-n-southeast-asia", "ja"), "KOR": ("east-n-southeast-asia", "ks"),
    "CHN": ("east-n-southeast-asia", "ch"), "THA": ("east-n-southeast-asia", "th"),
    "VNM": ("east-n-southeast-asia", "vm"), "IDN": ("east-n-southeast-asia", "id"),
    "LAO": ("east-n-southeast-asia", "la"),
    "IND": ("south-asia", "in"), "NPL": ("south-asia", "np"), "LKA": ("south-asia", "ce"),
    "TUR": ("middle-east", "tu"), "ARE": ("middle-east", "ae"), "JOR": ("middle-east", "jo"),
    "MAR": ("africa", "mo"), "EGY": ("africa", "eg"), "ZAF": ("africa", "sf"),
    "KEN": ("africa", "ke"), "TZA": ("africa", "tz"), "SEN": ("africa", "sg"),
    "GHA": ("africa", "gh"),
    "USA": ("north-america", "us"), "CAN": ("north-america", "ca"),
    "MEX": ("north-america", "mx"), "CRI": ("central-america-n-caribbean", "cs"),
    "COL": ("south-america", "co"), "PER": ("south-america", "pe"),
    "BRA": ("south-america", "br"), "ARG": ("south-america", "ar"),
    "CHL": ("south-america", "ci"),
    "AUS": ("australia-oceania", "as"), "NZL": ("australia-oceania", "nz"),
}

avertissements = []


# --- Accès réseau ---------------------------------------------------------------

def creer_contexte_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except ImportError:
        return ssl.create_default_context(), "système"


CONTEXTE_SSL, ORIGINE_CERTIFICATS = creer_contexte_ssl()


def fiche_factbook(iso3):
    """Renvoie la fiche JSON du pays : copie locale si elle existe, sinon téléchargement."""
    region, code = CODES_FACTBOOK[iso3]
    local = DOSSIER_BRUT / f"{code}.json"
    if local.exists():
        return json.loads(local.read_text(encoding="utf-8"))
    req = urllib.request.Request(URL.format(region=region, code=code),
                                 headers={"User-Agent": USER_AGENT})
    for pause in [5, 15, None]:
        try:
            with urllib.request.urlopen(req, timeout=60, context=CONTEXTE_SSL) as reponse:
                texte = reponse.read().decode("utf-8")
            break
        except urllib.error.HTTPError as erreur:
            if erreur.code not in (429, 500, 502, 503, 504) or pause is None:
                raise
            print(f"   Erreur {erreur.code}, nouvel essai dans {pause} s...")
            time.sleep(pause)
    DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
    local.write_text(texte, encoding="utf-8")
    time.sleep(0.3)   # politesse envers le serveur
    return json.loads(texte)


# --- Lecture des textes du Factbook --------------------------------------------------
# Le Factbook donne du texte, pas des nombres : « 29,751 km », « 36 00 N, 138 00 E ».

def premier_nombre(texte):
    """« 5,835 km (mainland 1,777 km; ...) » -> 5835.0"""
    trouve = re.search(r"(\d[\d,]*(?:\.\d+)?)", texte)
    return float(trouve.group(1).replace(",", "")) if trouve else None


def latitude(texte):
    """« 36 00 N, 138 00 E » -> 36.0 ; « 27 00 S, ... » -> -27.0 (premier point cité)."""
    trouve = re.search(r"(\d+)\s+(\d+)\s*([NS])", texte)
    if not trouve:
        return None
    degres = int(trouve.group(1)) + int(trouve.group(2)) / 60
    return round(degres if trouve.group(3) == "N" else -degres, 2)


def champ(fiche, *chemin):
    for cle in chemin:
        # certaines clés du Factbook ont un espace en trop (« total  »)
        fiche = next((v for k, v in fiche.items() if k.strip() == cle), None)
        if fiche is None:
            return ""
    return fiche.get("text", "") if isinstance(fiche, dict) else ""


# --- Programme principal ------------------------------------------------------------

def main():
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        codes = [l["iso3"].strip() for l in csv.DictReader(f)]
    print(f"1. {len(codes)} pays lus dans {FICHIER_LISTE.name}")
    inconnus = [c for c in codes if c not in CODES_FACTBOOK]
    if inconnus:
        sys.exit(f"Code Factbook inconnu pour {inconnus} : ajoute-le dans CODES_FACTBOOK")

    print("2. Lecture des fiches du Factbook (copie locale ou téléchargement)")
    lignes = []
    for iso3 in codes:
        fiche = fiche_factbook(iso3)
        geo = fiche.get("Geography", {})
        texte_cotes = champ(geo, "Coastline")
        cotes = premier_nombre(texte_cotes)
        terres = premier_nombre(champ(geo, "Area", "land"))
        lat = latitude(champ(geo, "Geographic coordinates"))
        if cotes is None or terres is None or lat is None:
            avertissements.append(f"{iso3} : valeur illisible (côtes « {texte_cotes} »)")
        if "excludes islands" in texte_cotes:
            avertissements.append(f"{iso3} : côtes sans les îles (« {texte_cotes} »), sous-estimées")
        lignes.append({
            "iso3": iso3,
            "cotes_km": int(cotes) if cotes is not None else "",
            "sans_littoral": "true" if cotes == 0 else "false",
            "superficie_terres_km2": int(terres) if terres is not None else "",
            "lat_centre": lat if lat is not None else "",
            "source_url": URL.format(region=CODES_FACTBOOK[iso3][0], code=CODES_FACTBOOK[iso3][1]),
            "date_extraction": datetime.date.today().isoformat(),
        })

    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=list(lignes[0]))
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    print("\n=== Résumé ===")
    print(f"{'ISO3':5}{'côtes (km)':>12}{'terres (km²)':>14}{'latitude':>10}")
    for l in lignes:
        print(f"{l['iso3']:5}{l['cotes_km']:>12}{l['superficie_terres_km2']:>14}{l['lat_centre']:>10}")
    print(f"\nPays sans accès à la mer : "
          f"{', '.join(l['iso3'] for l in lignes if l['sans_littoral'] == 'true') or 'aucun'}")
    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


AIDE_SSL = """
Erreur de certificat SSL. Installe la liste à jour : py -m pip install certifi
puis relance. Ne désactive jamais la vérification des certificats.
"""

if __name__ == "__main__":
    print(f"(certificats utilisés : {ORIGINE_CERTIFICATS})")
    try:
        main()
    except urllib.error.URLError as erreur:
        if isinstance(erreur.reason, ssl.SSLError):
            sys.exit(f"{erreur.reason}\n{AIDE_SSL}")
        raise
