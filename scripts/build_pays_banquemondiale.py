"""
build_pays_banquemondiale.py
----------------------------
Interroge l'API de la Banque mondiale (World Development Indicators) pour les pays
de data/pays_liste.csv et écrit data/intermediaire/pays_banquemondiale.csv.

Indicateurs retenus (dernière valeur disponible, année conservée) :
    ER.LND.PTLD.ZS    zones terrestres protégées (% du territoire)        -> axe « nature »
    EN.POP.DNST       densité de population (hab./km²)                   -> axe « nature »
    SP.URB.TOTL.IN.ZS population urbaine (% de la population)            -> axe « villes »
    EN.URB.MCTY.TL.ZS population des agglomérations > 1 million (%)      -> axe « villes »
    NY.GNP.PCAP.CD    revenu national brut par habitant ($ US, Atlas)    -> visu 3 (effort)
    PA.NUS.PPP        facteur de parité de pouvoir d'achat              -> axe « budget »
    PA.NUS.FCRF       taux de change officiel (monnaie locale / $)      -> axe « budget »
Le choix final des indicateurs par axe se fait au moment du calcul des scores.

Indicateur écarté volontairement : ST.INT.ARVL (arrivées touristiques).
  - la série s'arrête en 2020 (années suivantes vides) ;
  - la dernière valeur mélange 2019 et 2020 (année Covid) selon les pays ;
  - les définitions varient (la France compte les visiteurs à la journée).
  => non comparable entre pays. Voir INDICATEURS_ECARTES pour le réactiver en test.

Bibliothèque standard uniquement (+ certifi si installé). Lancement depuis la racine :
    python scripts/build_pays_banquemondiale.py
"""

import csv
import datetime
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --- Configuration -----------------------------------------------------------

URL_API = "https://api.worldbank.org/v2/country/{pays}/indicator/{indicateur}"
USER_AGENT = "ProjetDatavizVoyage/1.0 (projet etudiant, Universite Paris 8)"

# code Banque mondiale -> (colonne valeur, colonne année, décimales)
INDICATEURS = {
    "ER.LND.PTLD.ZS": ("zones_protegees_pct", "annee_zones_protegees", 1),
    "SP.URB.TOTL.IN.ZS": ("pop_urbaine_pct", "annee_pop_urbaine", 1),
    # % de la population vivant dans une agglomération de plus d'un million d'habitants
    # (meilleure mesure des « grandes villes » que le simple taux d'urbanisation)
    "EN.URB.MCTY.TL.ZS": ("pop_villes_1m_pct", "annee_pop_villes_1m", 1),
    # habitants par km² (faible = grands espaces : Islande, Canada, Australie...)
    "EN.POP.DNST": ("densite_hab_km2", "annee_densite", 1),
    # revenu national brut par habitant, méthode Atlas, dollars US courants
    # -> mesure de l'« effort » d'un voyage (choisi à la place des salaires ILOSTAT,
    #    incomplets et non comparables entre pays : voir la section technique)
    "NY.GNP.PCAP.CD": ("rnb_hab_usd", "annee_rnb", 0),
    # Pour l'indice du niveau des prix (calculé dans build_pays.py) :
    #   niveau_prix = parité de pouvoir d'achat / taux de change   (États-Unis = 1)
    "PA.NUS.PPP": ("ppa_mn_par_dollar_int", "annee_ppa", 4),
    "PA.NUS.FCRF": ("change_mn_par_usd", "annee_change", 4),
}

# Absence de valeur qui a un sens connu : un pays sans agglomération de plus d'un
# million d'habitants n'apparaît pas dans la série -> 0 %. Signalé dans le rapport.
VALEUR_SI_ABSENT = {
    "EN.URB.MCTY.TL.ZS": 0,
}
INDICATEURS_ECARTES = {
    "ST.INT.ARVL": ("arrivees_touristes", "annee_arrivees", 0),
}

# Une valeur plus ancienne que ça est signalée (pas supprimée)
AGE_MAX_ANS = 5

RACINE = Path(__file__).resolve().parent.parent
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
DOSSIER_BRUT = RACINE / "data" / "raw"
FICHIER_SORTIE = RACINE / "data" / "intermediaire" / "pays_banquemondiale.csv"

avertissements = []


def avertir(message):
    avertissements.append(message)


# --- Accès réseau ---------------------------------------------------------------

def creer_contexte_ssl():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except ImportError:
        return ssl.create_default_context(), "système"


CONTEXTE_SSL, ORIGINE_CERTIFICATS = creer_contexte_ssl()


def telecharger_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for pause in [5, 15, None]:
        try:
            with urllib.request.urlopen(req, timeout=60, context=CONTEXTE_SSL) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as erreur:
            if erreur.code not in (429, 500, 502, 503, 504) or pause is None:
                raise
            print(f"   Erreur {erreur.code}, nouvel essai dans {pause} s...")
            time.sleep(pause)


# --- Lecture de la réponse de l'API ---------------------------------------------

def lire_reponse(reponse, indicateur):
    """
    L'API renvoie [métadonnées, [enregistrements]] en cas de succès,
    ou [{"message": [...]}] en cas d'erreur (code pays ou indicateur invalide).
    Renvoie (métadonnées, enregistrements).
    """
    if not isinstance(reponse, list) or not reponse:
        sys.exit(f"{indicateur} : réponse inattendue de l'API : {str(reponse)[:200]}")
    if "message" in reponse[0]:
        sys.exit(f"{indicateur} : l'API a renvoyé une erreur : {reponse[0]['message']}")
    meta = reponse[0]
    enregistrements = reponse[1] if len(reponse) > 1 and reponse[1] else []
    if meta.get("pages", 1) > 1:
        sys.exit(f"{indicateur} : réponse sur plusieurs pages, augmente per_page")
    return meta, enregistrements


def recuperer_indicateur(indicateur, codes):
    url = (URL_API.format(pays=";".join(codes), indicateur=indicateur)
           + "?format=json&mrnev=1&per_page=1000")   # mrnev=1 : dernière valeur non vide
    reponse = telecharger_json(url)
    DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
    (DOSSIER_BRUT / f"banquemondiale_{indicateur}.json").write_text(
        json.dumps(reponse, ensure_ascii=False, indent=1), encoding="utf-8")
    meta, enregistrements = lire_reponse(reponse, indicateur)

    valeurs = {}
    for e in enregistrements:
        iso3, valeur = e.get("countryiso3code", ""), e.get("value")
        if iso3 in codes and valeur is not None:
            valeurs[iso3] = (valeur, int(e["date"]))
    return valeurs, meta.get("lastupdated", "")


# --- Programme principal ------------------------------------------------------------

def main(indicateurs=INDICATEURS):
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        codes = [l["iso3"].strip() for l in csv.DictReader(f)]
    print(f"1. {len(codes)} pays lus dans {FICHIER_LISTE.name}")

    annee_courante = datetime.date.today().year
    lignes = {iso3: {"iso3": iso3} for iso3 in codes}
    colonnes = ["iso3"]
    mises_a_jour = {}

    for numero, (indicateur, (col_val, col_annee, decimales)) in enumerate(
            indicateurs.items(), start=2):
        print(f"{numero}. Banque mondiale : {indicateur} -> {col_val}")
        valeurs, mises_a_jour[indicateur] = recuperer_indicateur(indicateur, codes)
        colonnes += [col_val, col_annee]
        for iso3 in codes:
            if iso3 not in valeurs:
                if indicateur in VALEUR_SI_ABSENT:
                    defaut = VALEUR_SI_ABSENT[indicateur]
                    avertir(f"{iso3} : absent de {indicateur} -> {defaut} "
                            "(aucune agglomération de plus d'un million d'habitants ; à vérifier)")
                    lignes[iso3].update({col_val: defaut, col_annee: ""})
                else:
                    avertir(f"{iso3} : aucune valeur pour {indicateur}")
                    lignes[iso3].update({col_val: "", col_annee: ""})
                continue
            valeur, annee = valeurs[iso3]
            lignes[iso3][col_val] = round(valeur, decimales) if decimales else int(round(valeur))
            lignes[iso3][col_annee] = annee
            if annee_courante - annee > AGE_MAX_ANS:
                avertir(f"{iso3} : {indicateur} date de {annee} (plus de {AGE_MAX_ANS} ans)")

    colonnes.append("date_extraction")
    for ligne in lignes.values():
        ligne["date_extraction"] = datetime.date.today().isoformat()

    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=colonnes)
        ecrivain.writeheader()
        ecrivain.writerows(lignes[c] for c in codes)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    # --- Rapport ---
    print("\n=== Résumé par pays ===")
    entete = "ISO3 " + "".join(f"{v[0]:>22}" for v in indicateurs.values())
    print(entete)
    for iso3 in codes:
        l = lignes[iso3]
        cellules = "".join(
            f"{(f'{l[c]} ({l[a]})' if l[c] != '' else '—'):>22}"
            for c, a, _ in indicateurs.values())
        print(f"{iso3:<5}{cellules}")

    print("\nDernière mise à jour des séries (à citer) :")
    for indicateur, date in mises_a_jour.items():
        print(f"  {indicateur} : {date}")

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
