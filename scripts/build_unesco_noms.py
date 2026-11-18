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
l'article Wikipédia en français, sinon anglais (colonne langue_nom).
Année d'inscription : la plus ancienne date de début (P580) de la désignation « patrimoine
mondial » (P1435 = Q9259) parmi tous les éléments du site ; vide si aucune (rien d'inventé).
Corrections (data/corrections_unesco_noms.csv, produit par build_unesco_wikipedia.py) : titre
d'article et année de Wikipédia en français, avec le lien de l'article (colonnes source_nom
et source_annee).

Rien n'est repris de whc.unesco.org : les fiches ne servent qu'à vérifier et à départager des
éléments Wikidata (jamais écrites dans un fichier publié), et lien_unesco n'est qu'un lien.

Lancement depuis la racine :
    py scripts/build_unesco_noms.py
    py scripts/build_unesco_noms.py --depuis-brut    (relit le relevé Wikidata, sans requête)
    py scripts/build_unesco_noms.py --verifier 10    (compare 10 années à whc.unesco.org)
"""

import csv
import difflib
import html
import json
import random
import re
import ssl
import subprocess
import sys
import time
import unicodedata
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
FICHIER_BRUT_NOMS = RACINE / "data" / "raw" / "wikidata_unesco_noms.json"
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
FICHIER_PAYS = RACINE / "data" / "pays.csv"
FICHIER_CORRECTIONS = RACINE / "data" / "corrections_unesco_noms.csv"   # facultatif
FICHIER_SORTIE = RACINE / "data" / "unesco_sites.csv"

TAILLE_LOT = 400                      # éléments par requête SPARQL
NOM_LONG = 80                         # signalé au-delà (affichage)
URL_UNESCO = "https://whc.unesco.org/fr/list/{}"
URL_UNESCO_EN = "https://whc.unesco.org/en/list/{}/"
EXTENSIONS = r"(bis|ter|quater|quinquies)"
DOSSIER_FICHES = RACINE / "data" / "raw" / "unesco_fiches"      # cache, non commité
SEUIL_TITRE = 0.6                     # en dessous : départage douteux -> correction manuelle
PREMIERE_LISTE = 1978                 # première inscription au patrimoine mondial : avant = erreur

COLONNES = ["iso3", "id_unesco", "categorie", "nom_fr", "langue_nom", "wikidata_qid",
            "regle_choix", "departage", "annee_inscription", "transfrontalier", "lien_unesco",
            "source_nom", "source_annee"]
PREFIXE_WIKIPEDIA = "https://fr.wikipedia.org/w/index.php?title="

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


def lire_trouves(brut):
    trouves = defaultdict(set)
    for l in (brut["results"]["bindings"] if brut else []):
        trouves[valeur(l, "id")].add(qid(valeur(l, "site")))
    return trouves


def chercher_partout(ids):
    """Éléments portant ces identifiants UNESCO, dans tout Wikidata."""
    if not ids:
        return {}, []
    brut = requete_sparql(REQUETE_GLOBALE % " ".join(f'"{i}"' for i in sorted(ids)))
    return lire_trouves(brut), brut


def lire_infos(bruts):
    infos = defaultdict(lambda: {"fr": "", "mul": "", "wikifr": "", "en": "", "est_site": False,
                                 "liens": 0, "annees": set()})
    for brut in bruts:
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
    return infos


def infos_elements(qids):
    bruts = []
    qids = sorted(qids, key=lambda q: int(q[1:]))
    for i in range(0, len(qids), TAILLE_LOT):
        lot = qids[i:i + TAILLE_LOT]
        print(f"   éléments {i + 1} à {i + len(lot)} sur {len(qids)}")
        bruts.append(requete_sparql(REQUETE_INFOS % " ".join(f"wd:{q}" for q in lot)))
    return lire_infos(bruts), bruts


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


REQUETE_PARTIES = """
SELECT ?a ?b WHERE {
  VALUES ?a { %s }
  VALUES ?b { %s }
  { ?a wdt:P361 ?b } UNION { ?b wdt:P527 ?a }     # a « fait partie de » b, ou b « contient » a
}
"""


def lire_parties(brut, groupes):
    groupes = [g for g in groupes if len(g) > 1]
    paires = {(qid(valeur(l, "a")), qid(valeur(l, "b")))
              for l in (brut["results"]["bindings"] if brut else [])}
    return {(a, b) for a, b in paires if any(a in g and b in g for g in groupes)}


def relations_parties(groupes):
    """Paires (a, b) où a est une partie de b, a et b candidats d'un même site."""
    multiples = [g for g in groupes if len(g) > 1]
    if not multiples:
        return set(), {}
    tous = " ".join(f"wd:{q}" for q in sorted({q for g in multiples for q in g}))
    brut = requete_sparql(REQUETE_PARTIES % (tous, tous))
    return lire_parties(brut, multiples), brut


def retirer_parties(qids, parties):
    """Écarte un candidat qui fait partie d'un autre candidat (on garde l'ensemble inscrit)."""
    gardes = {c for c in qids if not any((c, d) in parties for d in qids if d != c)}
    return gardes or set(qids)                       # cycle improbable : on ne retire rien


def departager(qids, infos):
    return sorted(qids, key=lambda q: (not infos[q]["est_site"], -infos[q]["liens"], int(q[1:])))[0]


def lire_corrections():
    """
    data/corrections_unesco_noms.csv (écrit par build_unesco_wikipedia.py) : nom_fr = titre de
    l'article de Wikipédia en français, annee_inscription = année donnée par Wikipédia, chacun
    avec son lien (source_nom, source_annee) ; wikidata_qid = « aucun » si aucun élément
    Wikidata ne représente le site entier, ou un QID pour imposer l'élément (quand la règle
    « partie de » se trompe de sens) ; iso3 = pays concerné si la correction n'en vise qu'un.
    Une ligne sans valeur signale un site sans article.
    """
    if not FICHIER_CORRECTIONS.exists():
        return {}
    with FICHIER_CORRECTIONS.open(encoding="utf-8", newline="") as f:
        lignes = [{k: (v or "").strip() for k, v in l.items()} for l in csv.DictReader(f)]
    erreurs = []
    for l in lignes:
        for champ, source in (("nom_fr", "source_nom"), ("annee_inscription", "source_annee")):
            if l.get(champ) and not l.get(source, "").startswith(PREFIXE_WIKIPEDIA):
                erreurs.append(f"{l.get('id_unesco')} : {champ} sans lien vers Wikipédia en français")
        if not (l.get("nom_fr") or l.get("annee_inscription") or l.get("wikidata_qid")
                or l.get("rattachement_nom") == "sans_article"):
            erreurs.append(f"{l.get('id_unesco')} : ligne vide")
        if l.get("annee_inscription") and not re.fullmatch(r"(19[7-9]\d|20\d\d)", l["annee_inscription"]):
            erreurs.append(f"{l.get('id_unesco')} : année invalide {l['annee_inscription']}")
    if erreurs:
        sys.exit(f"{FICHIER_CORRECTIONS.name} invalide :\n  - " + "\n  - ".join(erreurs))
    return {l["id_unesco"]: l for l in lignes}


# --- Fiches officielles whc.unesco.org (titre et année) ---------------------------------------
# Le titre officiel sert UNIQUEMENT de clé de comparaison pour départager des éléments
# Wikidata : il n'est jamais écrit dans un fichier publié (le cache n'est pas commité).
# Le site de l'UNESCO refuse urllib (403) mais accepte curl (fourni avec Windows 10 et plus).

def fiche_unesco(base, langue="en"):
    """(titre, année d'inscription) de la fiche officielle, avec un cache local."""
    DOSSIER_FICHES.mkdir(parents=True, exist_ok=True)
    cache = DOSSIER_FICHES / f"{langue}_{base}.html"
    if not cache.exists():
        url = (URL_UNESCO_EN if langue == "en" else URL_UNESCO).format(base)
        page = subprocess.run(["curl", "-s", "-L", "-m", "60", "-A", USER_AGENT, url],
                              capture_output=True).stdout
        cache.write_bytes(page)
        time.sleep(1)                                    # on reste poli avec le site
    page = cache.read_text(encoding="utf-8", errors="replace")
    titre = re.search(r"<h1[^>]*>(.*?)</h1>", page, re.S)          # peut contenir <em>…</em>
    annee = re.search(r"(?:Date of Inscription|Date d'inscription)\s*:?\s*</strong>\s*(\d{4})", page)
    return (" ".join(html.unescape(re.sub(r"<[^>]+>", "", titre.group(1))).split()) if titre else "",
            int(annee.group(1)) if annee else None)


def normaliser(texte):
    texte = unicodedata.normalize("NFKD", texte.lower())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", texte))


def ressemblance(a, b):
    """Entre 0 et 1 : le meilleur de la similarité des caractères et des mots communs."""
    a, b = normaliser(a), normaliser(b)
    if not a or not b:
        return 0.0
    mots_a, mots_b = set(a.split()), set(b.split())
    jaccard = len(mots_a & mots_b) / len(mots_a | mots_b)
    return max(difflib.SequenceMatcher(None, a, b).ratio(), jaccard)


def departager_par_titre(base, qids, infos):
    """Candidat dont le libellé ressemble le plus au titre officiel (anglais et français)."""
    titre_en, _ = fiche_unesco(base, "en")
    titre_fr, _ = fiche_unesco(base, "fr")
    scores = {q: max(ressemblance(titre_en, infos[q]["en"]),
                     ressemblance(titre_fr, infos[q]["fr"] or infos[q]["mul"]))
              for q in qids}
    meilleur = sorted(qids, key=lambda q: (-scores[q], int(q[1:])))[0]
    return meilleur, scores


def annee_officielle(base):
    return fiche_unesco(base, "en")[1]


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
    groupes = [qs for _, qs in regles.values()]
    if "--depuis-brut" in sys.argv:         # aucune requête : mêmes données Wikidata que le relevé
        print(f"2-4. Wikidata : relecture de {FICHIER_BRUT_NOMS.name}")
        sauve = json.loads(FICHIER_BRUT_NOMS.read_text(encoding="utf-8"))
        trouves = lire_trouves(sauve["recherche_globale"])
        infos = lire_infos(sauve["infos"])
        parties = lire_parties(sauve["parties"], groupes)
    else:
        print(f"2. Wikidata : {len(a_chercher) // 3} site(s) sans élément d'ensemble sur place, "
              "recherche dans tout Wikidata")
        trouves, brut_global = chercher_partout(a_chercher)
        tous_qids = {q for s in sites.values() for site in s.values()
                     for qs in site["ids"].values() for q in qs}
        tous_qids |= {q for qs in trouves.values() for q in qs}
        print(f"3. Wikidata : libellés, nature, articles Wikipédia et dates d'inscription")
        infos, bruts = infos_elements(tous_qids)
        print("4. Wikidata : relations « fait partie de » / « contient » entre candidats d'un même site")
        parties, brut_parties = relations_parties(groupes)
        sauver_brut("wikidata_unesco_noms.json", {"recherche_globale": brut_global, "infos": bruts,
                                                   "parties": brut_parties})
    print(f"   {len(parties)} relation(s) trouvée(s)")

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
            # départage : 1) on écarte les parties d'un autre candidat (P361 / P527) ;
            # 2) s'il en reste plusieurs, ressemblance avec le titre officiel (non publié) ;
            # 3) sinon nature « site du patrimoine mondial », articles Wikipédia, identifiant
            restants = retirer_parties(qs, parties) if qs else set()
            departage, score = ("partie_de" if len(restants) < len(qs) else "aucun"), None
            if len(restants) > 1:
                choisi, scores = departager_par_titre(base, restants, infos)
                score = scores[choisi]
                departage = "titre_unesco" if score >= SEUIL_TITRE else "douteux"
                if departage == "douteux":
                    choisi = departager(restants, infos)
            else:
                choisi = departager(restants, infos) if restants else ""
            correction = corrections.get(base, {})
            if correction.get("iso3") and correction["iso3"] != iso3:
                correction = {}                  # correction valable pour un seul pays du site
            force = correction.get("wikidata_qid", "")
            if force.startswith("Q"):            # élément imposé (la règle « partie de » se trompe)
                tous_elements = {q for qs2 in site["ids"].values() for q in qs2}
                if force not in tous_elements:
                    sys.exit(f"{FICHIER_CORRECTIONS.name} : {force} n'est pas un élément du site {base}")
                choisi, departage = force, "correction"
            e = infos[choisi] if choisi else infos["Q0"]
            # français, puis libellé multilingue (« mul », souvent seul depuis 2024, ex. Las
            # Médulas), puis titre de l'article Wikipédia en français, puis anglais
            nom, langue = next(((e[c], c) for c in ("fr", "mul", "wikifr", "en") if e[c]), ("", ""))
            if correction.get("nom_fr"):          # titre de l'article de Wikipédia en français
                nom, langue = correction["nom_fr"], "wikifr"
                regle = regle or "manuel"
            if force == "aucun":
                choisi, departage = "", "correction"    # aucun élément ne représente le site entier
            annees = {a for qs2 in site["ids"].values() for q in qs2 for a in infos[q]["annees"]}
            annees |= set(e["annees"])
            impossibles = sorted(a for a in annees if a < PREMIERE_LISTE)
            if impossibles:            # ex. Serengeti « 1960 » : erreur de saisie dans Wikidata
                avertir(f"{iso3}:{base} « {nom} » : année(s) {impossibles} écartée(s), "
                        f"antérieure(s) à la première liste ({PREMIERE_LISTE})")
                annees -= set(impossibles)
            if correction.get("annee_inscription"):
                annee_wikipedia = int(correction["annee_inscription"])
                if annees and min(annees) != annee_wikipedia:
                    avertir(f"{iso3}:{base} : Wikidata {min(annees)}, Wikipédia {annee_wikipedia} "
                            "-> Wikipédia retenue")
                annees = {annee_wikipedia}
            ligne = {
                "iso3": iso3, "id_unesco": base, "categorie": site["categorie"],
                "nom_fr": nom, "langue_nom": langue, "wikidata_qid": choisi,
                "regle_choix": regle or "", "departage": departage,
                "annee_inscription": min(annees) if annees else "",
                "transfrontalier": "true" if len(pays_du_site[base]) > 1 else "false",
                "lien_unesco": URL_UNESCO.format(base),
                "source_nom": correction.get("source_nom", "") if correction.get("nom_fr") else "",
                "source_annee": (correction.get("source_annee", "")
                                 if correction.get("annee_inscription") else ""),
            }
            lignes.append(ligne)
            # cas délicats, pour le rapport
            ligne_rapport = dict(ligne, score=score)
            if regle == "exact" and len(qs) > 1:
                delicats["plusieurs"].append((ligne_rapport, qs))
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
    venus_unesco = [f"{l['iso3']}:{l['id_unesco']}" for l in lignes
                    if l["langue_nom"] == "unesco_fr" or "unesco.org" in l["source_nom"] + l["source_annee"]]
    if venus_unesco:
        erreurs.append(f"contenu encore attribué à whc.unesco.org : {venus_unesco}")
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
        score = f", ressemblance {ligne['score']:.2f}" if ligne["score"] is not None else ""
        retenu = court(ligne["wikidata_qid"]) if ligne["wikidata_qid"] else "aucun élément"
        print(f"  {ligne['iso3']} n°{ligne['id_unesco']:<5} [{ligne['departage']}{score}] "
              f"retenu {retenu} -> « {ligne['nom_fr']} »")
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
    print(f"  noms qui ne viennent pas d'un libellé français de Wikidata ({len(en)}) : {en}")
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
