"""
build_unesco_noms.py
--------------------
Noms français et année d'inscription des sites du patrimoine mondial des 41 pays du quiz,
pour « Pourquoi ce pays ? » : data/unesco_sites.csv (une ligne par pays et par site).

Part des MÊMES données brutes que le comptage de pays.csv (data/raw/wikidata_unesco.json,
16/10/2026) et de la même fonction (sites_unesco de build_pays_wikidata.py) : les sites
nommés sont exactement les sites comptés (contrôle bloquant).

Un site a souvent plusieurs éléments Wikidata. Choix de l'élément qui le représente :
  1. identifiant exact (« 83 ») ; 2. révision (« 228rev ») ; 3. extension (« 311bis ») ;
  4. sinon, l'élément de l'identifiant exact cherché dans tout Wikidata (sans filtre de pays :
     les éléments transfrontaliers n'ont souvent pas de pays principal) ;
  5. sinon, data/corrections_unesco_noms.csv (rempli à la main, avec source).
  À égalité : l'élément décrit comme site du patrimoine mondial (P31 = Q9259), puis le plus
  d'articles Wikipédia, puis le plus petit identifiant.
Nom : libellé français de Wikidata, sinon libellé multilingue (« mul »), sinon titre de
l'article Wikipédia en français, sinon anglais (colonne langue_nom), sinon correction manuelle.
Année d'inscription : la plus ancienne date de début (P580) de la désignation « patrimoine
mondial » (P1435 = Q9259) parmi tous les éléments du site ; vide si aucune (rien d'inventé).

Les noms viennent de Wikidata (CC0), pas de la liste de l'UNESCO, dont les conditions
interdisent la republication : ce fichier n'entre PAS dans le ZIP de téléchargement.

Lancement depuis la racine :
    py scripts/build_unesco_noms.py
    py scripts/build_unesco_noms.py --verifier 10    (compare 10 années à whc.unesco.org)
"""

import csv
import json
import random
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from build_pays_wikidata import (
    CONTEXTE_SSL, ORIGINE_CERTIFICATS, AIDE_SSL, USER_AGENT, SERVICES_UTILISES,
    requete_sparql, sauver_brut, sites_unesco, valeur, qid, avertissements as avert_comptage,
)

RACINE = Path(__file__).resolve().parent.parent
FICHIER_BRUT = RACINE / "data" / "raw" / "wikidata_unesco.json"
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
FICHIER_PAYS = RACINE / "data" / "pays.csv"
FICHIER_CORRECTIONS = RACINE / "data" / "corrections_unesco_noms.csv"   # facultatif
FICHIER_SORTIE = RACINE / "data" / "unesco_sites.csv"

TAILLE_LOT = 400                      # éléments par requête SPARQL
NOM_LONG = 80                         # signalé au-delà (affichage)
URL_UNESCO = "https://whc.unesco.org/fr/list/{}"
URL_UNESCO_EN = "https://whc.unesco.org/en/list/{}/"
EXTENSIONS = r"(bis|ter|quater|quinquies)"
PREMIERE_LISTE = 1978                 # première inscription au patrimoine mondial : avant = erreur

COLONNES = ["iso3", "id_unesco", "categorie", "nom_fr", "langue_nom", "wikidata_qid",
            "regle_choix", "annee_inscription", "transfrontalier", "lien_unesco"]

avertissements = []


def avertir(message):
    avertissements.append(message)


# --- Requêtes Wikidata -------------------------------------------------------------------

REQUETE_GLOBALE = """
SELECT ?site ?id WHERE {
  VALUES ?id { %s }
  ?site wdt:P757 ?id .
}
"""

REQUETE_INFOS = """
SELECT ?site ?fr ?mul ?wikifr ?en ?nature ?liens ?debut WHERE {
  VALUES ?site { %s }
  OPTIONAL { ?site rdfs:label ?fr FILTER(LANG(?fr) = "fr") }
  OPTIONAL { ?site rdfs:label ?mul FILTER(LANG(?mul) = "mul") }    # libellé multilingue (2024)
  OPTIONAL { ?article schema:about ?site ; schema:isPartOf <https://fr.wikipedia.org/> ;
                      schema:name ?wikifr . }                       # titre Wikipédia en français
  OPTIONAL { ?site rdfs:label ?en FILTER(LANG(?en) = "en") }
  OPTIONAL { ?site wdt:P31 ?nature FILTER(?nature = wd:Q9259) }   # « site du patrimoine mondial »
  OPTIONAL { ?site wikibase:sitelinks ?liens }
  OPTIONAL { ?site p:P1435 ?st . ?st ps:P1435 wd:Q9259 ; pq:P580 ?debut . }
}
"""


def chercher_partout(ids):
    """Éléments portant ces identifiants UNESCO, dans tout Wikidata."""
    if not ids:
        return {}, []
    brut = requete_sparql(REQUETE_GLOBALE % " ".join(f'"{i}"' for i in sorted(ids)))
    trouves = defaultdict(set)
    for l in brut["results"]["bindings"]:
        trouves[valeur(l, "id")].add(qid(valeur(l, "site")))
    return trouves, brut


def infos_elements(qids):
    infos = defaultdict(lambda: {"fr": "", "mul": "", "wikifr": "", "en": "", "est_site": False,
                                 "liens": 0, "annees": set()})
    bruts = []
    qids = sorted(qids, key=lambda q: int(q[1:]))
    for i in range(0, len(qids), TAILLE_LOT):
        lot = qids[i:i + TAILLE_LOT]
        print(f"   éléments {i + 1} à {i + len(lot)} sur {len(qids)}")
        brut = requete_sparql(REQUETE_INFOS % " ".join(f"wd:{q}" for q in lot))
        bruts.append(brut)
        for l in brut["results"]["bindings"]:
            e = infos[qid(valeur(l, "site"))]
            for cle in ("fr", "mul", "wikifr", "en"):
                e[cle] = valeur(l, cle) or e[cle]
            e["est_site"] |= bool(valeur(l, "nature"))
            if valeur(l, "liens"):
                e["liens"] = int(valeur(l, "liens"))
            m = re.match(r"(-?\d{4})", valeur(l, "debut"))
            if m:
                e["annees"].add(int(m.group(1)))
    return infos, bruts


# --- Choix de l'élément ----------------------------------------------------------------

def candidats(base, ids):
    """(règle, {QID}) selon l'ordre de priorité, ou (None, set()) si rien sur place."""
    if ids.get(base):
        return "exact", set(ids[base])
    if ids.get(base + "rev"):
        return "revision", set(ids[base + "rev"])
    ext = {q for i, qs in ids.items() if re.fullmatch(base + EXTENSIONS, i) for q in qs}
    if ext:
        return "extension", ext
    return None, set()


def departager(qids, infos):
    return sorted(qids, key=lambda q: (not infos[q]["est_site"], -infos[q]["liens"], int(q[1:])))[0]


def lire_corrections():
    if not FICHIER_CORRECTIONS.exists():
        return {}
    with FICHIER_CORRECTIONS.open(encoding="utf-8", newline="") as f:
        lignes = [{k: (v or "").strip() for k, v in l.items()} for l in csv.DictReader(f)]
    erreurs = [f"{l.get('id_unesco')} : nom_fr et source_url obligatoires"
               for l in lignes if not (l.get("nom_fr") and l.get("source_url"))]
    if erreurs:
        sys.exit(f"{FICHIER_CORRECTIONS.name} invalide :\n  - " + "\n  - ".join(erreurs))
    return {l["id_unesco"]: l for l in lignes}


# --- Vérification des années sur la liste officielle (échantillon) -------------------------------

def annee_officielle(base):
    """
    Année d'inscription lue sur la fiche officielle. Le site de l'UNESCO refuse les requêtes
    de urllib (403) mais accepte curl (fourni avec Windows 10 et plus) : on passe par curl.
    """
    page = subprocess.run(["curl", "-s", "-m", "60", "-A", USER_AGENT, URL_UNESCO_EN.format(base)],
                          capture_output=True).stdout.decode("utf-8", "replace")
    m = re.search(r"Date of Inscription:\s*</strong>\s*(\d{4})", page)
    return int(m.group(1)) if m else None


def verifier(lignes, n):
    datees = sorted({(l["id_unesco"], l["annee_inscription"], l["nom_fr"]) for l in lignes
                     if l["annee_inscription"] != ""})
    echantillon = random.Random(20261117).sample(datees, n)       # graine fixe : rejouable
    print(f"\n=== Vérification de {n} années sur whc.unesco.org (échantillon tiré au hasard) ===")
    ok = 0
    for base, annee, nom in echantillon:
        officielle = annee_officielle(base)
        accord = officielle == annee
        ok += accord
        print(f"  n°{base:<6}{nom[:44]:<46}Wikidata {annee}  UNESCO {officielle}  "
              f"{'OK' if accord else 'ÉCART'}")
        time.sleep(1)
    print(f"  {ok}/{n} identiques")


# --- Programme principal -------------------------------------------------------------------

def main():
    brut = json.loads(FICHIER_BRUT.read_text(encoding="utf-8"))
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        codes = [l["iso3"].strip() for l in csv.DictReader(f)]
    print(f"1. Sites des {len(codes)} pays (même fonction que le comptage de pays.csv)")
    sites = sites_unesco(brut, codes)

    # pays de chaque site dans le monde entier (transfrontalier), sans les exclusions ;
    # les avertissements de ce passage concernent d'autres pays : on ne les garde pas
    deja = len(avert_comptage)
    tous = sites_unesco(brut, sorted({valeur(l, "iso3") for l in brut["results"]["bindings"]}))
    del avert_comptage[deja:]
    pays_du_site = defaultdict(set)
    for iso3, s in tous.items():
        for base in s:
            pays_du_site[base].add(iso3)

    regles, a_chercher = {}, set()
    for iso3, s in sites.items():
        for base, site in s.items():
            regle, qs = candidats(base, site["ids"])
            regles[(iso3, base)] = (regle, qs)
            if not regle:
                a_chercher |= {base, base + "rev", base + "bis"}
    print(f"2. Wikidata : {len(a_chercher) // 3} site(s) sans élément d'ensemble sur place, "
          "recherche dans tout Wikidata")
    trouves, brut_global = chercher_partout(a_chercher)

    tous_qids = {q for s in sites.values() for site in s.values()
                 for qs in site["ids"].values() for q in qs}
    tous_qids |= {q for qs in trouves.values() for q in qs}
    print(f"3. Wikidata : libellés, nature, articles Wikipédia et dates d'inscription")
    infos, bruts = infos_elements(tous_qids)
    sauver_brut("wikidata_unesco_noms.json", {"recherche_globale": brut_global, "infos": bruts})

    corrections = lire_corrections()
    lignes, delicats = [], {"plusieurs": [], "sans_exact": []}
    for iso3, s in sites.items():
        for base, site in s.items():
            regle, qs = regles[(iso3, base)]
            if not regle:
                for cle, nom_regle in ((base, "global_exact"), (base + "rev", "global_revision"),
                                       (base + "bis", "global_extension")):
                    if trouves.get(cle):
                        regle, qs = nom_regle, set(trouves[cle])
                        break
            choisi = departager(qs, infos) if qs else ""
            e = infos[choisi] if choisi else infos["Q0"]
            # français, puis libellé multilingue (« mul », souvent seul depuis 2024, ex. Las
            # Médulas), puis titre de l'article Wikipédia en français, puis anglais
            nom, langue = next(((e[c], c) for c in ("fr", "mul", "wikifr", "en") if e[c]), ("", ""))
            if base in corrections:
                nom, langue = corrections[base]["nom_fr"], "manuel"
                regle = regle or "manuel"
            annees = {a for qs2 in site["ids"].values() for q in qs2 for a in infos[q]["annees"]}
            annees |= set(e["annees"])
            impossibles = sorted(a for a in annees if a < PREMIERE_LISTE)
            if impossibles:            # ex. Serengeti « 1960 » : erreur de saisie dans Wikidata
                avertir(f"{iso3}:{base} « {nom} » : année(s) {impossibles} écartée(s), "
                        f"antérieure(s) à la première liste ({PREMIERE_LISTE})")
                annees -= set(impossibles)
            ligne = {
                "iso3": iso3, "id_unesco": base, "categorie": site["categorie"],
                "nom_fr": nom, "langue_nom": langue, "wikidata_qid": choisi,
                "regle_choix": regle or "", "annee_inscription": min(annees) if annees else "",
                "transfrontalier": "true" if len(pays_du_site[base]) > 1 else "false",
                "lien_unesco": URL_UNESCO.format(base),
            }
            lignes.append(ligne)
            # cas délicats, pour le rapport
            if regle == "exact" and len(qs) > 1:
                delicats["plusieurs"].append((ligne, qs))
            elif regle != "exact":
                delicats["sans_exact"].append((ligne, site["ids"]))

    # --- Contrôles bloquants ---
    erreurs = []
    with FICHIER_PAYS.open(encoding="utf-8", newline="") as f:
        attendu = {l["iso3"]: l for l in csv.DictReader(f)}
    for iso3 in codes:
        for cat in ("culturel", "naturel", "mixte"):
            n = sum(1 for l in lignes if l["iso3"] == iso3 and l["categorie"] == cat)
            if n != int(attendu[iso3][f"unesco_{cat}"]):
                erreurs.append(f"{iso3} {cat} : {n} sites nommés, {attendu[iso3][f'unesco_{cat}']} comptés")
    sans_nom = [f"{l['iso3']}:{l['id_unesco']}" for l in lignes if not l["nom_fr"]]
    if sans_nom:
        erreurs.append(f"sites sans nom (à ajouter dans {FICHIER_CORRECTIONS.name}) : {sans_nom}")
    if erreurs:
        sys.exit("Contrôles échoués, fichier non écrit :\n  - " + "\n  - ".join(erreurs))

    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)} ({len(lignes)} lignes)")

    # --- Rapport ---
    def court(q):
        e = infos[q]
        return (f"{q} « {e['fr'] or e['en'] or '?'} » "
                f"[{'site' if e['est_site'] else 'pas site'}, {e['liens']} art.]")

    print(f"\n=== Plusieurs éléments avec l'identifiant exact ({len(delicats['plusieurs'])}) ===")
    for ligne, qs in delicats["plusieurs"]:
        autres = [court(q) for q in sorted(qs, key=lambda q: int(q[1:])) if q != ligne["wikidata_qid"]]
        print(f"  {ligne['iso3']} n°{ligne['id_unesco']:<5} retenu {court(ligne['wikidata_qid'])}")
        print(f"  {'':10}écarté {' | '.join(autres)}")

    print(f"\n=== Pas d'élément avec l'identifiant exact sur place ({len(delicats['sans_exact'])}) ===")
    for ligne, ids in delicats["sans_exact"]:
        apercu = ", ".join(sorted(ids)[:4]) + (" …" if len(ids) > 4 else "")
        print(f"  {ligne['iso3']} n°{ligne['id_unesco']:<5} {ligne['regle_choix']:<17}"
              f"« {ligne['nom_fr']} » ({ligne['wikidata_qid'] or '—'})   ids : {apercu}")

    regles_n = defaultdict(int)
    for l in lignes:
        regles_n[l["regle_choix"]] += 1
    print("\n=== Résumé ===")
    print("  règle de choix : " + ", ".join(f"{k} {v}" for k, v in sorted(regles_n.items())))
    en = [f"{l['iso3']}:{l['id_unesco']} « {l['nom_fr']} » ({l['langue_nom']})" for l in lignes
          if l["langue_nom"] != "fr"]
    print(f"  noms sans libellé français ({len(en)}) : {en}")
    sans_annee = [f"{l['iso3']}:{l['id_unesco']} « {l['nom_fr']} »" for l in lignes
                  if l["annee_inscription"] == ""]
    print(f"  sites sans année d'inscription ({len(sans_annee)}) : {sans_annee}")
    longs = [f"{l['iso3']}:{l['id_unesco']} ({len(l['nom_fr'])} car.)" for l in lignes
             if len(l["nom_fr"]) > NOM_LONG]
    print(f"  noms de plus de {NOM_LONG} caractères ({len(longs)}) : {longs}")
    doublons = defaultdict(list)
    for l in lignes:
        doublons[(l["iso3"], l["nom_fr"])].append(l["id_unesco"])
    d = {f"{k[0]} « {k[1]} »": v for k, v in doublons.items() if len(v) > 1}
    print(f"  même nom pour deux sites d'un pays ({len(d)}) : {d}")
    annees = defaultdict(int)
    for l in lignes:
        if l["annee_inscription"] != "":
            annees[l["annee_inscription"]] += 1
    print(f"  années : de {min(annees)} à {max(annees)} ; les plus fréquentes : "
          + ", ".join(f"{a} ({n})" for a, n in sorted(annees.items(), key=lambda x: -x[1])[:5]))
    print(f"  transfrontaliers : {sum(l['transfrontalier'] == 'true' for l in lignes)} lignes")
    print(f"  services SPARQL : {', '.join(sorted(set(SERVICES_UTILISES)))}")
    tous_avert = avert_comptage + avertissements
    print(f"\n=== À vérifier ({len(tous_avert)}) ===")
    for a in tous_avert:
        print("  -", a)

    if "--verifier" in sys.argv:
        verifier(lignes, int(sys.argv[sys.argv.index("--verifier") + 1]))


if __name__ == "__main__":
    print(f"(certificats utilisés : {ORIGINE_CERTIFICATS})")
    try:
        main()
    except urllib.error.URLError as erreur:
        if isinstance(erreur.reason, ssl.SSLError):
            sys.exit(f"{erreur.reason}\n{AIDE_SSL}")
        raise
