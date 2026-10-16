"""
build_pays_wikidata.py
----------------------
Interroge Wikidata (SPARQL) et Wikimedia Commons (API) pour les pays listés dans
data/pays_liste.csv, et écrit data/intermediaire/pays_wikidata.csv :

    capitale, coordonnées GPS de la capitale, photo (+ auteur et licence),
    drapeau, et nombre de sites du patrimoine mondial UNESCO
    (culturels / naturels / mixtes).

Ce fichier est une étape intermédiaire : pays.csv sera assemblé plus tard avec
les données Banque mondiale et ILOSTAT.

Bibliothèque standard uniquement. Lancement depuis la racine du projet :
    python scripts/build_pays_wikidata.py
"""

import csv
import datetime
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

# --- Configuration -----------------------------------------------------------

URL_SPARQL = "https://query.wikidata.org/sparql"           # service officiel de Wikidata
# Secours : QLever (Université de Fribourg), un autre moteur qui interroge les mêmes
# données Wikidata (copie mise à jour régulièrement), souvent bien plus rapide.
URL_SPARQL_SECOURS = "https://qlever.cs.uni-freiburg.de/api/wikidata"
SERVICES_UTILISES = []                                       # pour la section technique

# Préfixes déclarés explicitement : Wikidata les connaît d'office, QLever non.
PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX hint: <http://www.bigdata.com/queryHints#>
"""
URL_COMMONS = "https://commons.wikimedia.org/w/api.php"
# Wikimedia demande un User-Agent descriptif. Tu peux y ajouter un contact.
USER_AGENT = "ProjetDatavizVoyage/1.0 (projet etudiant, Universite Paris 8)"

RACINE = Path(__file__).resolve().parent.parent
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"            # rempli à la main
DOSSIER_BRUT = RACINE / "data" / "raw"
FICHIER_SORTIE = RACINE / "data" / "intermediaire" / "pays_wikidata.csv"

CRITERES_CULTURELS = {"i", "ii", "iii", "iv", "v", "vi"}
CRITERES_NATURELS = {"vii", "viii", "ix", "x"}

COLONNES_SORTIE = [
    "iso3", "iso2", "nom_fr", "region", "wikidata_qid",
    "capitale", "capitale_qid", "lat", "lon",
    "image_commons", "image_url", "image_auteur", "image_licence",
    "drapeau_url",
    "unesco_culturel", "unesco_naturel", "unesco_mixte", "unesco_sans_categorie",
    "date_extraction",
]

avertissements = []  # tout ce qui mérite un coup d'œil humain


def avertir(message):
    avertissements.append(message)


# --- Accès réseau (isolé pour pouvoir le tester) ------------------------------

def creer_contexte_ssl():
    """
    Utilise la liste de certificats à jour du paquet « certifi » s'il est installé
    (pip install certifi), sinon celle de Windows/du système.
    La vérification des certificats reste TOUJOURS active.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except ImportError:
        return ssl.create_default_context(), "système"


CONTEXTE_SSL, ORIGINE_CERTIFICATS = creer_contexte_ssl()

ERREURS_TEMPORAIRES = (429, 500, 502, 503, 504)


def envoyer_sparql(url, requete, pauses):
    donnees = urllib.parse.urlencode({"query": PREFIXES + requete}).encode()
    req = urllib.request.Request(
        url, data=donnees,  # POST : pas de limite de longueur d'URL
        headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json",
                 "Content-Type": "application/x-www-form-urlencoded"},
    )
    for tentative, pause in enumerate(list(pauses) + [None], start=1):
        try:
            with urllib.request.urlopen(req, timeout=120, context=CONTEXTE_SSL) as reponse:
                return json.loads(reponse.read().decode("utf-8"))
        except urllib.error.HTTPError as erreur:
            if erreur.code not in ERREURS_TEMPORAIRES or pause is None:
                raise
            print(f"   Erreur {erreur.code}, nouvel essai dans {pause} s...")
            time.sleep(pause)


def requete_sparql(requete):
    """Service officiel d'abord ; en cas d'échec répété, bascule sur QLever."""
    try:
        resultat = envoyer_sparql(URL_SPARQL, requete, pauses=[10, 30])
        SERVICES_UTILISES.append("query.wikidata.org")
        return resultat
    except urllib.error.HTTPError as erreur:
        if erreur.code not in ERREURS_TEMPORAIRES:
            raise
        print(f"   Wikidata officiel indisponible ({erreur.code}) -> essai avec QLever")
    # Les « hint: » sont propres au moteur de Wikidata : on les retire pour QLever.
    requete_qlever = "\n".join(l for l in requete.splitlines() if "hint:" not in l)
    resultat = envoyer_sparql(URL_SPARQL_SECOURS, requete_qlever, pauses=[10])
    SERVICES_UTILISES.append("QLever (copie de Wikidata)")
    return resultat


def requete_commons(titres):
    params = urllib.parse.urlencode({
        "action": "query", "format": "json", "prop": "imageinfo",
        "iiprop": "extmetadata", "titles": "|".join(titres),
    })
    req = urllib.request.Request(f"{URL_COMMONS}?{params}", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60, context=CONTEXTE_SSL) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def sauver_brut(nom, contenu):
    DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
    (DOSSIER_BRUT / nom).write_text(
        json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8"
    )


# --- Petits utilitaires -------------------------------------------------------

def valeur(ligne, cle):
    return ligne.get(cle, {}).get("value", "")


def qid(uri):
    """http://www.wikidata.org/entity/Q90 -> Q90"""
    return uri.rsplit("/", 1)[-1] if uri else ""


def fichier_commons(uri):
    """URL Special:FilePath -> nom du fichier ('Tokyo Tower.jpg')."""
    return urllib.parse.unquote(uri.rsplit("/", 1)[-1]) if uri else ""


def url_image(nom_fichier, largeur=None):
    if not nom_fichier:
        return ""
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(nom_fichier)
    return f"{url}?width={largeur}" if largeur else url


def coordonnees(point):
    """'Point(139.69 35.68)' -> (35.68, 139.69). Attention : WKT = longitude d'abord."""
    m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", point or "")
    return (round(float(m.group(2)), 4), round(float(m.group(1)), 4)) if m else ("", "")


def critere(label):
    """'criterion (vii)' -> 'vii' ; renvoie '' si aucun numéro romain reconnu."""
    label = (label or "").lower()
    m = re.search(r"\((x|ix|viii|vii|vi|v|iv|iii|ii|i)\)", label) or re.search(
        r"\b(x|ix|viii|vii|vi|v|iv|iii|ii|i)\s*$", label
    )
    return m.group(1) if m else ""


def html_vers_texte(html):
    texte = re.sub(r"<[^>]+>", "", html or "")
    return re.sub(r"\s+", " ", texte).strip()


# --- Étape 1 : la liste des pays ---------------------------------------------

def lire_liste():
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        pays = [{k: (v or "").strip() for k, v in ligne.items()} for ligne in csv.DictReader(f)]
    codes = [p["iso3"] for p in pays]
    doublons = {c for c in codes if codes.count(c) > 1}
    if doublons:
        sys.exit(f"{FICHIER_LISTE.name} : codes en double {sorted(doublons)}")
    if any(not re.fullmatch(r"[A-Z]{3}", c) for c in codes):
        sys.exit(f"{FICHIER_LISTE.name} : un code n'est pas un ISO3 en majuscules")
    return pays


def valeurs_sparql(codes):
    return " ".join(f'"{c}"' for c in codes)


# --- Étape 2 : capitales, coordonnées, images, drapeaux ----------------------

REQUETE_PAYS = """
SELECT ?iso3 ?pays ?iso2 ?cap ?capLabel ?rang ?coord ?capImage ?drapeau WHERE {
  VALUES ?iso3 { %s }
  ?pays wdt:P298 ?iso3 ; wdt:P31 wd:Q3624078 .          # État souverain
  OPTIONAL { ?pays wdt:P297 ?iso2 }
  OPTIONAL { ?pays wdt:P41 ?drapeau }
  OPTIONAL {
    ?pays p:P36 ?st . ?st ps:P36 ?cap ; wikibase:rank ?rang .
    FILTER(?rang != wikibase:DeprecatedRank)
    FILTER NOT EXISTS { ?st pq:P582 ?fin }               # pas d'anciennes capitales
    OPTIONAL { ?cap wdt:P625 ?coord }
    OPTIONAL { ?cap wdt:P18 ?capImage }
    OPTIONAL { ?cap rdfs:label ?capLabel FILTER(LANG(?capLabel) = "fr") }
  }
}
"""


def extraire_pays(resultats, liste):
    """Regroupe les lignes SPARQL par pays et choisit une capitale par pays."""
    par_pays = defaultdict(lambda: {"capitales": {}, "iso2": "", "drapeaux": set(), "qid": set()})
    for l in resultats["results"]["bindings"]:
        p = par_pays[valeur(l, "iso3")]
        p["qid"].add(qid(valeur(l, "pays")))
        p["iso2"] = valeur(l, "iso2") or p["iso2"]
        if valeur(l, "drapeau"):
            p["drapeaux"].add(fichier_commons(valeur(l, "drapeau")))
        cap = qid(valeur(l, "cap"))
        if cap:
            c = p["capitales"].setdefault(cap, {
                "nom": "", "prefere": False, "coords": set(), "images": set()})
            c["nom"] = valeur(l, "capLabel") or c["nom"]
            c["prefere"] |= valeur(l, "rang").endswith("PreferredRank")
            if valeur(l, "coord"):
                c["coords"].add(valeur(l, "coord"))
            if valeur(l, "capImage"):
                c["images"].add(fichier_commons(valeur(l, "capImage")))

    sortie = {}
    for pays in liste:
        iso3 = pays["iso3"]
        if iso3 not in par_pays:
            avertir(f"{iso3} : introuvable dans Wikidata (code ISO3 ou statut d'État ?)")
            continue
        p = par_pays[iso3]
        if len(p["qid"]) > 1:
            avertir(f"{iso3} : plusieurs éléments Wikidata {sorted(p['qid'])}, le premier est gardé")

        capitales = p["capitales"]
        preferees = {k: v for k, v in capitales.items() if v["prefere"]}
        candidates = preferees or capitales
        if pays["capitale_qid"]:
            if pays["capitale_qid"] not in capitales:
                sys.exit(f"{iso3} : capitale_qid {pays['capitale_qid']} absente de Wikidata")
            choix = pays["capitale_qid"]
        elif candidates:
            choix = sorted(candidates)[0]
            if len(candidates) > 1:
                noms = ", ".join(f"{v['nom'] or k} ({k})" for k, v in sorted(candidates.items()))
                avertir(f"{iso3} : plusieurs capitales [{noms}] -> {choix} gardée. "
                         f"Fixe ton choix avec la colonne capitale_qid.")
        else:
            choix = ""
            avertir(f"{iso3} : aucune capitale trouvée")

        cap = capitales.get(choix, {"nom": "", "coords": set(), "images": set()})
        lat, lon = coordonnees(sorted(cap["coords"])[0]) if cap["coords"] else ("", "")
        if choix and lat == "":
            avertir(f"{iso3} : pas de coordonnées pour la capitale")
        if len(cap["coords"]) > 1:
            avertir(f"{iso3} : plusieurs coordonnées pour la capitale, la première est gardée")

        image = pays["image_commons"] or (sorted(cap["images"])[0] if cap["images"] else "")
        if not image:
            avertir(f"{iso3} : pas d'image, renseigne image_commons dans {FICHIER_LISTE.name}")

        drapeaux = sorted(p["drapeaux"])
        if len(drapeaux) > 1:
            avertir(f"{iso3} : plusieurs drapeaux {drapeaux}, le premier est gardé")

        sortie[iso3] = {
            "wikidata_qid": sorted(p["qid"])[0],
            "iso2": p["iso2"],
            "capitale": cap["nom"],
            "capitale_qid": choix,
            "lat": lat, "lon": lon,
            "image_commons": image,
            "image_url": url_image(image, largeur=800),
            "drapeau_url": url_image(drapeaux[0]) if drapeaux else "",
        }
    return sortie


# --- Étape 3 : patrimoine mondial UNESCO -------------------------------------

# Version légère : on part des éléments qui ont un identifiant UNESCO (P757),
# quelques milliers dans le monde, au lieu de toutes les protections patrimoniales
# (des millions). On récupère TOUS les pays et le filtrage se fait en Python :
# c'est beaucoup plus rapide que de laisser Wikidata filtrer.
REQUETE_UNESCO = """
SELECT ?iso3 ?site ?idUnesco ?critereLabel WHERE {
  hint:Query hint:optimizer "None" .                     # impose l'ordre ci-dessous
  ?site wdt:P757 ?idUnesco .                             # 1) les sites UNESCO (peu nombreux)
  ?site wdt:P17 ?pays .                                  # 2) leur pays
  ?pays wdt:P298 ?iso3 .                                 # 3) son code ISO3
  MINUS {                                                # exclut les sites retirés
    ?site p:P1435 ?st . ?st ps:P1435 wd:Q9259 ; pq:P582 ?fin .
  }
  OPTIONAL { ?site wdt:P2614 ?critere .
             ?critere rdfs:label ?critereLabel FILTER(LANG(?critereLabel) = "en") }
}
"""


FICHIER_CORRECTIONS_UNESCO = RACINE / "data" / "corrections_unesco.csv"   # rempli à la main
CATEGORIES = {"culturel", "naturel", "mixte"}


def numero_de_base(id_unesco):
    """
    Un même site a souvent plusieurs identifiants dans Wikidata :
      '80', '80bis', '80ter'  -> extensions successives du même site
      '868-001', '868-002'    -> composantes d'un site en série
      '228rev'                -> révision du dossier
    On ne garde que le numéro : '80ter-002' -> '80'. Renvoie '' si pas de numéro.
    """
    m = re.match(r"\s*(\d+)", id_unesco or "")
    return m.group(1) if m else ""


def lire_corrections_unesco():
    """
    data/corrections_unesco.csv (facultatif) :
      iso3,id_unesco,action,categorie,source_url,note
      action = 'exclure'    -> le numéro n'est pas un site de ce pays (erreur Wikidata)
      action = 'categorie'  -> impose la catégorie (culturel / naturel / mixte)
    """
    if not FICHIER_CORRECTIONS_UNESCO.exists():
        return {}
    corrections, erreurs = {}, []
    with FICHIER_CORRECTIONS_UNESCO.open(encoding="utf-8", newline="") as f:
        for numero, l in enumerate(csv.DictReader(f), start=2):
            l = {k: (v or "").strip() for k, v in l.items()}
            cle = (l.get("iso3", ""), numero_de_base(l.get("id_unesco", "")))
            if not all(cle):
                erreurs.append(f"ligne {numero} : iso3 ou id_unesco invalide")
            if l.get("action") not in ("exclure", "categorie"):
                erreurs.append(f"ligne {numero} : action '{l.get('action')}' (exclure ou categorie)")
            if l.get("action") == "categorie" and l.get("categorie") not in CATEGORIES:
                erreurs.append(f"ligne {numero} : categorie '{l.get('categorie')}' invalide")
            if not l.get("source_url"):
                erreurs.append(f"ligne {numero} : source_url obligatoire")
            if cle in corrections:
                erreurs.append(f"ligne {numero} : {cle} en double")
            corrections[cle] = l
    if erreurs:
        sys.exit(f"{FICHIER_CORRECTIONS_UNESCO.name} invalide :\n  - " + "\n  - ".join(erreurs))
    return corrections


def compter_unesco(resultats, codes):
    """Compte les sites par numéro de base (voir numero_de_base) et par catégorie."""
    sites = defaultdict(lambda: defaultdict(lambda: {"criteres": set(), "elements": set()}))
    ids_invalides, labels_non_reconnus = set(), set()

    for l in resultats["results"]["bindings"]:
        iso3, id_unesco = valeur(l, "iso3"), valeur(l, "idUnesco")
        if iso3 not in codes:
            continue
        base = numero_de_base(id_unesco)
        if not base:                       # ex. valeur saisie par erreur dans Wikidata
            ids_invalides.add(f"{iso3}:{id_unesco[:30]}")
            continue
        site = sites[iso3][base]
        site["elements"].add(qid(valeur(l, "site")))
        label = valeur(l, "critereLabel")
        if label:
            c = critere(label)
            if c:
                site["criteres"].add(c)
            else:
                labels_non_reconnus.add(label)

    if ids_invalides:
        avertir(f"Identifiants UNESCO sans numéro, ignorés : {sorted(ids_invalides)}")
    if labels_non_reconnus:
        avertir(f"Libellés de critères non reconnus : {sorted(labels_non_reconnus)[:5]}")

    corrections = lire_corrections_unesco()
    for (iso3, base) in corrections:
        if base not in sites.get(iso3, {}):
            avertir(f"Correction UNESCO inutile : {iso3} {base} absent des données "
                    "(Wikidata a peut-être été corrigé entre-temps)")

    comptes = {}
    for iso3 in codes:
        n = {"unesco_culturel": 0, "unesco_naturel": 0, "unesco_mixte": 0,
             "unesco_sans_categorie": 0}
        for base, site in sorted(sites[iso3].items(), key=lambda x: int(x[0])):
            correction = corrections.get((iso3, base))
            if correction and correction["action"] == "exclure":
                continue
            crit = site["criteres"]
            if correction:                              # action = categorie
                categorie = correction["categorie"]
            elif crit & CRITERES_CULTURELS and crit & CRITERES_NATURELS:
                categorie = "mixte"
            elif crit & CRITERES_CULTURELS:
                categorie = "culturel"
            elif crit & CRITERES_NATURELS:
                categorie = "naturel"
            else:
                categorie = "sans_categorie"
                exemple = sorted(site["elements"])[0]
                avertir(f"{iso3} : site n°{base} sans critère dans Wikidata "
                        f"(https://www.wikidata.org/wiki/{exemple} / "
                        f"https://whc.unesco.org/en/list/{base}) -> à trancher dans "
                        f"{FICHIER_CORRECTIONS_UNESCO.name}")
            n[f"unesco_{categorie}"] += 1
        comptes[iso3] = n
    return comptes


# --- Étape 4 : auteurs et licences des images (Commons) -----------------------

def credits_images(noms_fichiers):
    credits = {}
    noms = sorted({n for n in noms_fichiers if n})
    brut = []
    for i in range(0, len(noms), 50):                     # 50 titres max par appel
        lot = noms[i:i + 50]
        reponse = requete_commons([f"File:{n}" for n in lot])
        brut.append(reponse)
        requete = reponse.get("query", {})
        # Commons peut renommer les titres (ex. '_' -> ' ') : on garde la correspondance
        renommes = {r["to"]: r["from"] for r in requete.get("normalized", [])}
        for page in requete.get("pages", {}).values():
            titre = renommes.get(page["title"], page["title"])
            meta = (page.get("imageinfo") or [{}])[0].get("extmetadata", {})
            credits[titre[len("File:"):]] = {
                "image_auteur": html_vers_texte(meta.get("Artist", {}).get("value", "")),
                "image_licence": meta.get("LicenseShortName", {}).get("value", ""),
            }
    sauver_brut("commons_credits.json", brut)
    return credits


# --- Programme principal ------------------------------------------------------

def main():
    aujourd_hui = datetime.date.today().isoformat()
    liste = lire_liste()
    codes = [p["iso3"] for p in liste]
    print(f"1. {len(codes)} pays lus dans {FICHIER_LISTE.name}")

    print("2. Wikidata : capitales, coordonnées, images, drapeaux")
    brut_pays = requete_sparql(REQUETE_PAYS % valeurs_sparql(codes))
    sauver_brut("wikidata_pays.json", brut_pays)
    infos = extraire_pays(brut_pays, liste)

    print("3. Wikidata : sites du patrimoine mondial")
    brut_unesco = requete_sparql(REQUETE_UNESCO)
    print(f"   {len(brut_unesco['results']['bindings'])} lignes reçues (monde entier)")
    sauver_brut("wikidata_unesco.json", brut_unesco)
    unesco = compter_unesco(brut_unesco, codes)

    print("4. Commons : auteurs et licences des images")
    credits = credits_images(i["image_commons"] for i in infos.values())

    lignes = []
    for pays in liste:
        iso3 = pays["iso3"]
        i = infos.get(iso3, {})
        credit = credits.get(i.get("image_commons", ""), {})
        if i.get("image_commons") and not credit.get("image_licence"):
            avertir(f"{iso3} : licence de l'image introuvable sur Commons")
        # Pays introuvable : on laisse UNESCO vide (inconnu), pas 0 (aucun site)
        comptes = unesco[iso3] if i else {k: "" for k in unesco[iso3]}
        lignes.append({
            "iso3": iso3, "nom_fr": pays["nom_fr"], "region": pays["region"],
            **i, **credit, **comptes, "date_extraction": aujourd_hui,
        })

    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES_SORTIE, restval="")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    # --- Rapport ---
    print("\n=== Résumé par pays ===")
    print(f"{'ISO3':<5}{'Capitale':<22}{'Lat':>9}{'Lon':>10}  Img Drap  UNESCO c/n/m")
    for l in lignes:
        print(f"{l['iso3']:<5}{(l.get('capitale') or '—')[:21]:<22}"
              f"{str(l.get('lat', '')):>9}{str(l.get('lon', '')):>10}  "
              f"{'ok ' if l.get('image_url') else '-- '} {'ok  ' if l.get('drapeau_url') else '--  '}"
              f" {l['unesco_culturel']}/{l['unesco_naturel']}/{l['unesco_mixte']}")

    print(f"\nServices SPARQL utilisés (à citer) : {', '.join(sorted(set(SERVICES_UTILISES)))}")
    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


AIDE_SSL = """
Erreur de certificat SSL : la connexion sécurisée a été refusée.
Ce n'est pas un bug du script. Dans l'ordre :
  1. Vérifie la date et l'heure de Windows (Paramètres > Heure et langue).
  2. Installe la liste de certificats à jour :   py -m pip install certifi
     puis relance le script.
  3. Ouvre https://query.wikidata.org dans ton navigateur :
     un avertissement de sécurité => antivirus ou réseau (wifi de la fac...).
     Essaie alors avec un autre réseau, par exemple le partage de connexion du téléphone.
Ne désactive jamais la vérification des certificats pour contourner l'erreur.
"""

if __name__ == "__main__":
    print(f"(certificats utilisés : {ORIGINE_CERTIFICATS})")
    try:
        main()
    except urllib.error.HTTPError as erreur:
        if erreur.code in (429, 500, 502, 503, 504):
            sys.exit(f"Ni Wikidata ni QLever ne répondent (erreur {erreur.code}).\n"
                     "Envoie ce message à Claude.")
        raise
    except urllib.error.URLError as erreur:
        if isinstance(erreur.reason, ssl.SSLError):
            sys.exit(f"{erreur.reason}\n{AIDE_SSL}")
        raise
