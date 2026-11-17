"""
build_pays_monde.py
-------------------
Une ligne par pays de la carte des visas (les 199 codes passeport de data/visas.csv),
avec ce dont le site a besoin pour TOUS les pays, pas seulement les 41 du quiz :

    nom français, code ISO2, drapeau        (Wikidata, SPARQL)
    revenu national brut par habitant       (Banque mondiale, NY.GNP.PCAP.CD, via Data360)

Sortie : data/pays_monde.csv. Sert au survol et à la recherche du globe, à la fiche
pays, au choix du pays de départ du budget (« jours de revenu ») et aux phrases
générées (« Pour un habitant du Népal… »).

Pour les 41 pays du quiz, le nom vient de data/pays_liste.csv (même nom partout
sur le site) et le revenu est comparé à celui de data/pays.csv.

Bibliothèque standard uniquement (+ certifi si installé). Lancement depuis la racine :
    py scripts/build_pays_monde.py
"""

import csv
import datetime
import ssl
import sys
import time
import urllib.error
from collections import defaultdict
from pathlib import Path

# Réutilise l'accès réseau des scripts existants (mêmes certificats, mêmes reprises)
from build_pays_wikidata import (
    ORIGINE_CERTIFICATS, AIDE_SSL, requete_sparql, sauver_brut,
    valeur, qid, fichier_commons, url_image, SERVICES_UTILISES,
)
from build_pays_banquemondiale import telecharger_json

# --- Configuration -----------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
FICHIER_VISAS = RACINE / "data" / "visas.csv"
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
FICHIER_PAYS = RACINE / "data" / "pays.csv"
FICHIER_SORTIE = RACINE / "data" / "pays_monde.csv"

# Codes que Wikidata ne relie pas par l'ISO3 (P298) : élément imposé à la main.
# Le Kosovo n'a pas de code ISO 3166 officiel ; XKX est le code d'usage (UE, Banque mondiale).
QID_IMPOSES = {"XKX": "Q1246"}
ISO2_IMPOSES = {"XKX": "XK"}          # code d'usage, reconnu par les sites de drapeaux

# Libellés Wikidata trop longs pour le site (survol, recherche, phrases) : nom d'usage.
# Pour les 41 pays du quiz, c'est data/pays_liste.csv qui fait foi.
NOMS_IMPOSES = {
    "NLD": "Pays-Bas",                # Wikidata : « Royaume des Pays-Bas » (l'État, Caraïbes comprises)
    "PSE": "Palestine",               # Wikidata : « État de Palestine »
    "FSM": "Micronésie",              # Wikidata : « États fédérés de Micronésie »
}

# Drapeau imposé (nom du fichier sur Commons), quand celui de Wikidata pose question.
# AFG : Wikidata donne « Flag of the Taliban.svg » (drapeau de fait) ; l'ONU utilise encore
# « Flag of Afghanistan (2013–2021).svg ». Choix à faire, puis à écrire ici.
DRAPEAUX_IMPOSES = {}

INDICATEUR_RNB = "NY.GNP.PCAP.CD"     # RNB par habitant, méthode Atlas, $ US courants
# Même série (World Development Indicators), servie par Data360, la nouvelle API de la
# Banque mondiale. L'ancienne API (api.worldbank.org/v2, utilisée pour pays.csv) renvoyait
# des erreurs 502 et des délais dépassés le 17/11/2026. Contrôle : France 2025 = 48 630 $
# dans les deux.
URL_RNB = ("https://data360api.worldbank.org/data360/data?DATABASE_ID=WB_WDI"
           f"&INDICATOR=WB_WDI_{INDICATEUR_RNB.replace('.', '_')}&skip={{skip}}")
TAILLE_PAGE = 1000                    # imposée par Data360
AGE_MAX_ANS = 5                     # plus ancien -> rnb_statut = « ancien » (même seuil que pays.csv)

COLONNES = ["iso3", "iso2", "nom_fr", "dans_selection", "wikidata_qid", "drapeau_url",
            "rnb_hab_usd", "annee_rnb", "rnb_statut", "date_extraction"]

avertissements = []


def avertir(message):
    avertissements.append(message)


# --- Étape 1 : les codes ---------------------------------------------------------

def lire_codes():
    with FICHIER_VISAS.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.DictReader(f))
    passeports = sorted({l["passeport_iso3"] for l in lignes})
    destinations = sorted({l["destination_iso3"] for l in lignes})
    if passeports != destinations:
        sys.exit("visas.csv : les passeports et les destinations ne sont pas les mêmes pays")
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        selection = {l["iso3"].strip(): l["nom_fr"].strip() for l in csv.DictReader(f)}
    hors_carte = set(selection) - set(passeports)
    if hors_carte:
        sys.exit(f"Pays du quiz absents de visas.csv : {sorted(hors_carte)}")
    return passeports, selection


# --- Étape 2 : Wikidata ----------------------------------------------------------

REQUETE = """
SELECT ?iso3 ?pays ?iso2 ?nom ?drapeau ?rangDrapeau ?fin ?souverain WHERE {
  { VALUES ?iso3 { %s }  ?pays wdt:P298 ?iso3 . }
  UNION
  { VALUES (?pays ?iso3) { %s } }
  OPTIONAL { ?pays wdt:P297 ?iso2 }
  OPTIONAL { ?pays rdfs:label ?nom FILTER(LANG(?nom) = "fr") }
  OPTIONAL {
    ?pays p:P41 ?st . ?st ps:P41 ?drapeau ; wikibase:rank ?rangDrapeau .
    FILTER(?rangDrapeau != wikibase:DeprecatedRank)
    FILTER NOT EXISTS { ?st pq:P582 ?finDrapeau }          # pas d'anciens drapeaux
  }
  OPTIONAL { ?pays wdt:P576 ?fin }                         # date de dissolution
  OPTIONAL { ?pays wdt:P31 ?souverain FILTER(?souverain = wd:Q3624078) }
}
"""


def interroger_wikidata(codes):
    sans_imposes = [c for c in codes if c not in QID_IMPOSES]
    valeurs = " ".join(f'"{c}"' for c in sans_imposes)
    imposes = " ".join(f'(wd:{q} "{c}")' for c, q in QID_IMPOSES.items())
    brut = requete_sparql(REQUETE % (valeurs, imposes))
    sauver_brut("wikidata_pays_monde.json", brut)
    return brut


def extraire(brut, codes):
    """Regroupe par code, puis choisit un élément Wikidata et un drapeau par pays."""
    elements = defaultdict(lambda: defaultdict(lambda: {
        "iso2": "", "nom": "", "drapeaux": {}, "dissous": False, "souverain": False}))
    for l in brut["results"]["bindings"]:
        e = elements[valeur(l, "iso3")][qid(valeur(l, "pays"))]
        e["iso2"] = valeur(l, "iso2") or e["iso2"]
        e["nom"] = valeur(l, "nom") or e["nom"]
        e["dissous"] |= bool(valeur(l, "fin"))
        e["souverain"] |= bool(valeur(l, "souverain"))
        if valeur(l, "drapeau"):
            nom = fichier_commons(valeur(l, "drapeau"))
            e["drapeaux"][nom] = e["drapeaux"].get(nom, False) or \
                valeur(l, "rangDrapeau").endswith("PreferredRank")

    sortie = {}
    for iso3 in codes:
        candidats = elements.get(iso3, {})
        if not candidats:
            avertir(f"{iso3} : introuvable dans Wikidata -> ajoute-le à QID_IMPOSES")
            continue
        if iso3 in QID_IMPOSES:
            choix = QID_IMPOSES[iso3]
        else:
            # un pays qui existe encore, de préférence un État souverain
            actifs = {q: e for q, e in candidats.items() if not e["dissous"]} or candidats
            souverains = {q: e for q, e in actifs.items() if e["souverain"]} or actifs
            choix = sorted(souverains)[0]
            if len(souverains) > 1:
                avertir(f"{iso3} : plusieurs éléments {sorted(souverains)}, {choix} gardé "
                        "-> fixe le choix avec QID_IMPOSES")
        e = candidats[choix]

        drapeaux = e["drapeaux"]
        preferes = sorted(n for n, pref in drapeaux.items() if pref)
        liste = preferes or sorted(drapeaux)
        if iso3 in DRAPEAUX_IMPOSES:
            liste = [DRAPEAUX_IMPOSES[iso3]]
        if not liste:
            avertir(f"{iso3} : pas de drapeau dans Wikidata")
        elif len(liste) > 1:
            avertir(f"{iso3} : plusieurs drapeaux {liste}, le premier est gardé")

        sortie[iso3] = {
            "wikidata_qid": choix,
            "iso2": ISO2_IMPOSES.get(iso3, e["iso2"]),
            "nom_fr": e["nom"],
            "drapeau_url": url_image(liste[0]) if liste else "",
        }
    return sortie


# --- Étape 3 : Banque mondiale -----------------------------------------------------

def telecharger_patient(url):
    """Comme telecharger_json, mais réessaie aussi après un délai dépassé."""
    for pause in [10, 30, None]:
        try:
            return telecharger_json(url)
        except (TimeoutError, urllib.error.URLError) as erreur:
            if isinstance(getattr(erreur, "reason", None), ssl.SSLError) or pause is None:
                raise
            print(f"   {type(erreur).__name__}, nouvel essai dans {pause} s...")
            time.sleep(pause)


def interroger_rnb(codes):
    """
    Toute la série, page par page (tous les pays et toutes les années, agrégats
    régionaux compris), puis la dernière année non vide de chacun de nos pays.
    """
    observations, skip, total = [], 0, None
    while total is None or skip < total:
        reponse = telecharger_patient(URL_RNB.format(skip=skip))
        if "value" not in reponse:
            sys.exit(f"Data360 : réponse inattendue : {str(reponse)[:200]}")
        total = reponse["count"]
        observations += reponse["value"]
        skip += TAILLE_PAGE
        print(f"   {min(skip, total)} / {total} observations")
        time.sleep(0.5)                                  # on reste poli avec l'API
    if len(observations) != total:
        sys.exit(f"Data360 : {len(observations)} observations reçues, {total} annoncées")
    # Trace brute allégée (8 Mo sinon) : nos pays et les champs utiles seulement
    champs = ("REF_AREA", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "UNIT_MEASURE", "LATEST_DATA")
    sauver_brut(f"banquemondiale_{INDICATEUR_RNB}_monde.json",
                [{c: o.get(c) for c in champs} for o in observations if o.get("REF_AREA") in codes])

    valeurs, derniere_marquee = {}, {}
    for o in observations:
        iso3, v = o.get("REF_AREA", ""), o.get("OBS_VALUE")
        if iso3 not in codes or v in (None, ""):
            continue
        annee = int(o["TIME_PERIOD"])
        if iso3 not in valeurs or annee > valeurs[iso3][1]:
            valeurs[iso3] = (int(round(float(v))), annee)
        if o.get("LATEST_DATA"):
            derniere_marquee[iso3] = annee
    # Contrôle : notre « dernière année » = celle que Data360 marque comme la plus récente
    for iso3, (_, annee) in valeurs.items():
        if iso3 in derniere_marquee and derniere_marquee[iso3] != annee:
            avertir(f"{iso3} : dernière année {annee}, Data360 indique {derniere_marquee[iso3]}")
    return valeurs, "Data360, extraction du " + datetime.date.today().isoformat()


# --- Programme principal -----------------------------------------------------------

def main():
    aujourd_hui = datetime.date.today()
    codes, selection = lire_codes()
    print(f"1. {len(codes)} pays dans {FICHIER_VISAS.name}, dont {len(selection)} dans le quiz")

    print("2. Wikidata : noms français, ISO2, drapeaux")
    wikidata = extraire(interroger_wikidata(codes), codes)

    print(f"3. Banque mondiale : {INDICATEUR_RNB} (tous les pays)")
    rnb, maj_rnb = interroger_rnb(set(codes))

    with FICHIER_PAYS.open(encoding="utf-8", newline="") as f:
        rnb_quiz = {l["iso3"]: (l["rnb_hab_usd"], l["annee_rnb"]) for l in csv.DictReader(f)}

    lignes = []
    for iso3 in codes:
        w = wikidata.get(iso3, {})
        nom = w.get("nom_fr", "")
        if iso3 in selection:                       # le nom choisi à la main fait foi
            if nom and nom != selection[iso3]:
                avertir(f"{iso3} : Wikidata « {nom} », gardé « {selection[iso3]} » (pays_liste.csv)")
            nom = selection[iso3]
        elif iso3 in NOMS_IMPOSES:
            nom = NOMS_IMPOSES[iso3]

        valeur_rnb, annee = rnb.get(iso3, ("", ""))
        if valeur_rnb == "":
            statut = "absent"
        elif aujourd_hui.year - annee > AGE_MAX_ANS:
            statut = "ancien"
        else:
            statut = "ok"
        if iso3 in rnb_quiz and rnb_quiz[iso3] != (str(valeur_rnb), str(annee)):
            avertir(f"{iso3} : RNB {valeur_rnb} ({annee}) ≠ pays.csv {rnb_quiz[iso3][0]} "
                    f"({rnb_quiz[iso3][1]}) : la Banque mondiale a mis à jour la série")

        lignes.append({
            "iso3": iso3, "iso2": w.get("iso2", ""), "nom_fr": nom,
            "dans_selection": "true" if iso3 in selection else "false",
            "wikidata_qid": w.get("wikidata_qid", ""), "drapeau_url": w.get("drapeau_url", ""),
            "rnb_hab_usd": valeur_rnb, "annee_rnb": annee, "rnb_statut": statut,
            "date_extraction": aujourd_hui.isoformat(),
        })

    # --- Contrôles bloquants : le site s'appuie sur ces colonnes ---
    erreurs = []
    for col in ("nom_fr", "iso2"):
        vides = [l["iso3"] for l in lignes if not l[col]]
        if vides:
            erreurs.append(f"{col} vide pour {vides}")
        vus = defaultdict(list)
        for l in lignes:
            if l[col]:
                vus[l[col]].append(l["iso3"])
        doublons = {k: v for k, v in vus.items() if len(v) > 1}
        if doublons:
            erreurs.append(f"{col} en double : {doublons}")
    if erreurs:
        sys.exit("Contrôles échoués, fichier non écrit :\n  - " + "\n  - ".join(erreurs))

    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    # --- Rapport ---
    print("\n=== Tous les pays ===")
    for l in lignes:
        rnb_txt = f"{l['rnb_hab_usd']} $ ({l['annee_rnb']})" if l["rnb_hab_usd"] != "" else "—"
        print(f"{l['iso3']} {l['iso2']:<3}{'*' if l['dans_selection'] == 'true' else ' '} "
              f"{l['nom_fr'][:38]:<39}{rnb_txt:>18}  {l['rnb_statut']}"
              f"{'' if l['drapeau_url'] else '  (pas de drapeau)'}")

    par_statut = defaultdict(list)
    for l in lignes:
        par_statut[l["rnb_statut"]].append(l["iso3"])
    print("\n=== Revenu par habitant ===")
    for statut in ("ok", "ancien", "absent"):
        print(f"  {statut:<7}: {len(par_statut[statut]):>3}  "
              f"{' '.join(par_statut[statut]) if statut != 'ok' else ''}")
    annees = sorted({l["annee_rnb"] for l in lignes if l["annee_rnb"] != ""})
    print(f"  années présentes : {annees}")
    print(f"  dernière mise à jour de la série (à citer) : {maj_rnb}")
    print(f"\nServices SPARQL utilisés (à citer) : {', '.join(sorted(set(SERVICES_UTILISES)))}")

    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


if __name__ == "__main__":
    print(f"(certificats utilisés : {ORIGINE_CERTIFICATS})")
    try:
        main()
    except urllib.error.URLError as erreur:
        if isinstance(erreur.reason, ssl.SSLError):
            sys.exit(f"{erreur.reason}\n{AIDE_SSL}")
        raise
