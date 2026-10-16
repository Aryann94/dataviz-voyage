"""
build_pays_ilostat.py
---------------------
Salaire moyen des salariés (horaire ou mensuel selon le fichier), en dollars US
courants (OIT / ILOSTAT). Fichier recommandé : EAR_EHRA_SEX_CUR_NB_A (horaire),
pour les pays de data/pays_liste.csv -> data/intermediaire/pays_ilostat.csv

Étapes :
  1. Cherche dans le catalogue ILOSTAT le jeu « Average monthly earnings of employees
     ... currency » (annuel). Son identifiant a changé selon les versions, d'où la
     recherche automatique (EAR_4MTH_SEX_CUR_NB_A, EAR_4MTH_SEX_ECO_CUR_NB_A...).
  2. Télécharge les données de nos 41 pays via l'API officielle :
     https://rplumber.ilo.org/data/indicator
  3. Garde : sexe = total, monnaie = dollars US, toutes activités, année la plus récente.

Si data/raw/ilostat_salaires.csv existe déjà, il est utilisé (pas de téléchargement).
Pour forcer un nouveau téléchargement : supprime ce fichier.

Bibliothèque standard uniquement (+ certifi si installé). Lancement depuis la racine :
    python scripts/build_pays_ilostat.py
"""

import csv
import datetime
import gzip
import io
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

# --- Configuration -----------------------------------------------------------

URL_API = "https://rplumber.ilo.org"
URL_CATALOGUE = f"{URL_API}/metadata/toc/indicator?lang=en&format=.csv"
USER_AGENT = "ProjetDatavizVoyage/1.0 (projet etudiant, Universite Paris 8)"

# Identifiants acceptés, par ordre de préférence (le premier trouvé est utilisé)
IDENTIFIANTS_CANDIDATS = [
    "EAR_4MTH_SEX_CUR_NB_A",       # par sexe et monnaie
    "EAR_4MTH_SEX_ECO_CUR_NB_A",   # par sexe, activité économique et monnaie
]
MOTIF_IDENTIFIANT = re.compile(r"^EAR_4MTH_SEX_\w*CUR_NB_A$")

SEXE_TOTAL = "SEX_T"
MONNAIE = "CUR_TYPE_USD"           # dollars US courants (choix expliqué dans la section technique)
# Codes « toutes activités confondues » quand le jeu est ventilé par activité
ACTIVITE_TOTALE = {"ECO_AGGREGATE_TOTAL", "ECO_SECTOR_TOTAL", "ECO_ISIC4_TOTAL", "ECO_ISIC3_TOTAL"}
ANNEE_MIN = 2010
AGE_MAX_ANS = 5

RACINE = Path(__file__).resolve().parent.parent
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
DOSSIER_BRUT = RACINE / "data" / "raw"
FICHIER_BRUT = DOSSIER_BRUT / "ilostat_salaires.csv"
FICHIER_SORTIE = RACINE / "data" / "intermediaire" / "pays_ilostat.csv"

avertissements = []


def avertir(message):
    avertissements.append(message)


# --- Réseau ---------------------------------------------------------------------

def creer_contexte_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except ImportError:
        return ssl.create_default_context(), "système"


CONTEXTE_SSL, ORIGINE_CERTIFICATS = creer_contexte_ssl()


def decoder(brut):
    """Texte d'un fichier, décompressé s'il est au format gzip (.csv.gz)."""
    if brut[:2] == b"\x1f\x8b":
        brut = gzip.decompress(brut)
    return brut.decode("utf-8-sig")


def telecharger_texte(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180, context=CONTEXTE_SSL) as reponse:
        return decoder(reponse.read())


def fichier_local():
    """Fichier déjà présent dans data/raw : téléchargé à la main ou lors d'un lancement précédent."""
    # Les identifiants ILOSTAT changent selon les versions : on accepte tout fichier EAR_*
    manuels = sorted(DOSSIER_BRUT.glob("EAR_*.csv*"))
    if manuels:
        if len(manuels) > 1:
            print(f"   Plusieurs fichiers trouvés : {[m.name for m in manuels]}, le premier est utilisé")
        return manuels[0]
    return FICHIER_BRUT if FICHIER_BRUT.exists() else None


def url_donnees(identifiant, codes):
    params = {
        "id": identifiant, "ref_area": "+".join(codes), "sex": SEXE_TOTAL,
        "timefrom": str(ANNEE_MIN), "type": "code", "format": ".csv",
    }
    # safe="+" : l'API attend les pays séparés par des « + » non encodés
    return f"{URL_API}/data/indicator?" + urllib.parse.urlencode(params, safe="+")


# --- Étape 1 : trouver l'identifiant ------------------------------------------------

def trouver_identifiant():
    print(f"   Lecture du catalogue : {URL_CATALOGUE}")
    texte = telecharger_texte(URL_CATALOGUE)
    trouves = set()
    for ligne in csv.reader(io.StringIO(texte)):
        for cellule in ligne:
            cellule = cellule.strip()
            if MOTIF_IDENTIFIANT.match(cellule):
                trouves.add(cellule)
    print(f"   Jeux trouvés : {sorted(trouves) or 'aucun'}")
    for candidat in IDENTIFIANTS_CANDIDATS:
        if candidat in trouves:
            return candidat
    if trouves:
        return sorted(trouves)[0]
    autres = sorted({c for c in re.findall(r"EAR_\w+", texte)})[:15]
    sys.exit(
        "Aucun jeu « EAR_4MTH_SEX_..._CUR_NB_A » trouvé automatiquement.\n"
        f"(début du catalogue reçu : {texte[:150]!r})\n"
        f"(identifiants EAR_ vus : {autres or 'aucun'})\n"
        f"{AIDE_MANUELLE}"
    )


# --- Étape 2 : lire les données --------------------------------------------------------

def lire_lignes(texte):
    lecteur = csv.DictReader(io.StringIO(texte))
    colonnes = set(lecteur.fieldnames or [])
    attendues = {"ref_area", "sex", "time", "obs_value"}
    if not attendues.issubset(colonnes):
        sys.exit(f"Colonnes inattendues : {sorted(colonnes)}\n"
                 f"Attendues au minimum : {sorted(attendues)}. Envoie ce message à Claude.")
    return list(lecteur)


def est_retenue(l):
    """Sexe total, monnaie USD et, si le jeu est ventilé par activité, toutes activités."""
    if l.get("sex") != SEXE_TOTAL:
        return False
    classifs = [(l.get("classif1") or "").strip(), (l.get("classif2") or "").strip()]
    monnaies = [c for c in classifs if c.startswith("CUR_TYPE_")]
    activites = [c for c in classifs if c.startswith("ECO_")]
    if monnaies != [MONNAIE]:
        return False
    if activites and activites[0] not in ACTIVITE_TOTALE:
        return False
    return True


def selectionner(lignes, codes):
    par_pays = defaultdict(lambda: defaultdict(list))   # iso3 -> année -> [lignes]
    for l in lignes:
        iso3 = (l.get("ref_area") or "").strip()
        if iso3 not in codes or not est_retenue(l) or not (l.get("obs_value") or "").strip():
            continue
        try:
            annee = int(str(l["time"])[:4])
            float(l["obs_value"])
        except ValueError:
            continue
        par_pays[iso3][annee].append(l)

    annee_courante = datetime.date.today().year
    resultat = {}
    for iso3 in codes:
        if not par_pays[iso3]:
            avertir(f"{iso3} : aucun salaire en USD dans ILOSTAT depuis {ANNEE_MIN}")
            continue
        annee = max(par_pays[iso3])
        candidates = par_pays[iso3][annee]
        if len(candidates) > 1:
            valeurs = ", ".join(f"{float(c['obs_value']):.0f} ({c.get('source', '?')})"
                                for c in candidates)
            avertir(f"{iso3} : {len(candidates)} valeurs en {annee} [{valeurs}] -> la première est gardée")
        choix = candidates[0]
        if annee_courante - annee > AGE_MAX_ANS:
            avertir(f"{iso3} : salaire de {annee} (plus de {AGE_MAX_ANS} ans)")
        statut = (choix.get("obs_status") or "").strip()
        if statut:
            avertir(f"{iso3} : valeur marquée '{statut}' par l'OIT (rupture de série, estimation...)")
        resultat[iso3] = {
            "salaire_usd": round(float(choix["obs_value"]), 2),
            "annee_salaire": annee,
            "source_salaire": (choix.get("source") or "").strip(),
        }
    return resultat


# --- Programme principal ------------------------------------------------------

def main():
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        codes = [l["iso3"].strip() for l in csv.DictReader(f)]
    print(f"1. {len(codes)} pays lus dans {FICHIER_LISTE.name}")

    local = fichier_local()
    if local:
        date = datetime.date.fromtimestamp(local.stat().st_mtime).isoformat()
        print(f"2. Fichier local utilisé : {local.relative_to(RACINE)} (du {date})")
        texte = decoder(local.read_bytes())
        identifiant = local.name.split(".")[0] if local != FICHIER_BRUT else "(fichier local)"
        # retire l'horodatage ajouté par le site au téléchargement (-20261016T1135)
        identifiant = re.sub(r"-\d{8}T\d{4,6}$", "", identifiant)
    else:
        print("2. ILOSTAT : recherche du jeu de données")
        identifiant = trouver_identifiant()
        url = url_donnees(identifiant, codes)
        print(f"   Jeu utilisé : {identifiant}")
        print(f"   Téléchargement : {url}")
        texte = telecharger_texte(url)

    lignes = lire_lignes(texte)          # vérifie les colonnes AVANT d'enregistrer
    if not local:
        DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
        FICHIER_BRUT.write_text(texte, encoding="utf-8")
    print(f"   {len(lignes)} lignes reçues")

    print("3. Sélection : sexe total, dollars US, toutes activités, année la plus récente")
    valeurs = selectionner(lignes, codes)

    # Unité déduite de l'identifiant : EHR = horaire (EAR_EHRA...), sinon mensuel
    horaire = "EHR" in identifiant
    col_salaire = "salaire_horaire_usd" if horaire else "salaire_mensuel_usd"
    unite = "USD/heure" if horaire else "USD/mois"
    print(f"   Unité : {unite} (d'après l'identifiant {identifiant})")

    colonnes = ["iso3", col_salaire, "annee_salaire", "source_salaire",
                "jeu_ilostat", "date_extraction"]
    aujourd_hui = datetime.date.today().isoformat()
    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes, restval="")
        ecrivain.writeheader()
        for iso3 in codes:
            v = dict(valeurs.get(iso3, {}))
            if "salaire_usd" in v:
                v[col_salaire] = v.pop("salaire_usd")
            ecrivain.writerow({"iso3": iso3, **v, "jeu_ilostat": identifiant,
                               "date_extraction": aujourd_hui})
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    print("\n=== Résumé par pays ===")
    print(f"{'ISO3':<6}{unite:>10}{'Année':>8}  Source")
    for iso3 in codes:
        v = valeurs.get(iso3)
        if v:
            print(f"{iso3:<6}{v['salaire_usd']:>10}{v['annee_salaire']:>8}  {v['source_salaire']}")
        else:
            print(f"{iso3:<6}{'—':>10}")
    print(f"\nPays avec un salaire : {len(valeurs)}/{len(codes)}")
    print(f"Jeu ILOSTAT (à citer) : {identifiant}")

    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


AIDE_MANUELLE = f"""
Solution : télécharge le fichier à la main.
  1. Ouvre https://ilostat.ilo.org/data/bulk/ puis le répertoire « indicator ».
  2. Dans « Search by file name... », tape : EAR_4MTH
  3. Télécharge en .csv.gz le fichier EAR_4MTH_SEX_ECO_CUR_NB_A
     (ou à défaut EAR_4MTH_SEX_CUR_NB_A).
  4. Mets-le, sans le renommer ni le décompresser, dans : {DOSSIER_BRUT}
  5. Relance ce script.
"""

AIDE_RESEAU = f"""
Le téléchargement a échoué. Envoie ce message complet à Claude.
En attendant, tu peux tester l'API dans ton navigateur :
  {URL_API}/__docs__/
"""

if __name__ == "__main__":
    print(f"(certificats utilisés : {ORIGINE_CERTIFICATS})")
    try:
        main()
    except urllib.error.HTTPError as erreur:
        sys.exit(f"Erreur HTTP {erreur.code} sur {erreur.url}\n{AIDE_RESEAU}")
    except urllib.error.URLError as erreur:
        sys.exit(f"Erreur réseau : {erreur.reason}\n{AIDE_RESEAU}")
