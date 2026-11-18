"""
build_unesco_wikipedia.py
-------------------------
Remplace ce qui venait des fiches whc.unesco.org dans data/corrections_unesco_noms.csv :
  - 38 noms  -> titre de l'article de Wikipédia en français (CC BY-SA) ;
  - 15 années -> année donnée par Wikipédia en français.
Chaque valeur garde le lien permanent de l'article (version précise, « oldid »).
La fiche UNESCO ne sert plus qu'à vérifier l'année (cache local) et comme lien.

Rattachement d'un article à un site, du plus sûr au moins sûr (le premier qui marche) :
  meme_element     lien Wikipédia de l'élément Wikidata retenu pour le site
  meme_numero      lien Wikipédia d'un autre élément qui porte le même numéro UNESCO
  infobox          article lié depuis la ligne du site, dont l'infobox déclare ce numéro
  ligne_entiere    dans « Liste du patrimoine mondial en… », le lien couvre tout le nom du site
  categorie_annee  article lié depuis la ligne, classé « Patrimoine mondial inscrit en <année> »
  article_lieu     pas d'article sur le site : article du lieu, choix validé (ARTICLES_DE_LIEU)
  sans_article     rien de tout cela : libellé Wikidata conservé, signalé dans le rapport

Année : infobox de l'article (avec le bon numéro), sinon article lié classé dans la catégorie
de cette année, sinon ligne de la liste Wikipédia du pays. Vide et signalée si rien.

Lancement depuis la racine :
    py scripts/build_unesco_wikipedia.py
    py scripts/build_unesco_noms.py --depuis-brut
"""

import csv
import datetime
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict

from build_pays_wikidata import CONTEXTE_SSL, sauver_brut, sites_unesco
from build_unesco_noms import (
    DOSSIER_FICHES, EXTENSIONS, FICHIER_BRUT, FICHIER_CORRECTIONS, FICHIER_LISTE, FICHIER_SORTIE,
    PREMIERE_LISTE, URL_UNESCO, fiche_unesco, ressemblance,
)

URL_WIKIPEDIA = "https://fr.wikipedia.org/w/api.php"
URL_WIKIDATA = "https://www.wikidata.org/w/api.php"
USER_AGENT = "StudentDatavizScript/1.0 (non-commercial coursework)"
TAILLE_LOT = 50
PAUSE = 1.2                                    # secondes entre deux requêtes
COUVERTURE_MIN = 0.9                           # part du nom couverte par le lien (ligne_entiere)

SITES_NOM = {"186", "233", "249", "428", "481", "493", "549", "574", "578", "642", "876", "890",
             "895", "941", "948", "951", "954", "976", "983", "993", "995", "999", "1084", "1193",
             "1194", "1226", "1274", "1343", "1500", "1559", "1577", "1592", "1671", "1698",
             "1708", "1709", "1732", "1747"}
SITES_ANNEE = {"84", "87", "156", "162", "252", "438", "482", "778", "791", "811", "1055", "1317",
               "1453", "1513", "1618"}
# Sites sans article propre : titre de l'article du lieu (décision du 18/11/2026).
ARTICLES_DE_LIEU = {
    "481": "Vat Phou", "876": "Alcalá de Henares", "890": "Diamantina",
    "895": "Campeche (ville)", "993": "Goiás (ville)", "995": "Córdoba (Argentine)",
    "1274": "San Miguel de Allende", "1343": "Al-Aïn", "1592": "Culture de Liangzhu",
    "1671": "Yogyakarta",
}
# Nom valable pour un seul pays : la ligne du Laos garde le libellé Wikidata de sa propre
# partie du site (Hin Nam No, Q5765542), pas le nom du parc vietnamien.
PAYS_DU_NOM = {"951": "VNM"}
NOTES_SITES = {
    "951": "nom valable pour le Vietnam ; ligne du Laos : libellé Wikidata de Hin Nam No (Q5765542)",
    "954": "nom gardé : le monastère est plus petit que la zone inscrite",
}
ELEMENTS_IMPOSES = {
    "1055": ("Q51100199", "élément imposé : Wikidata range le site inscrit comme partie de Lamu"),
    "1194": ("aucun", "aucun élément Wikidata ne représente le site entier"),
    "1681": ("Q28663704", "élément imposé : Wikidata range le site inscrit comme partie du bâtiment"),
}
LISTES = {
    "ARE": "aux Émirats arabes unis", "ARG": "en Argentine", "AUS": "en Australie",
    "BRA": "au Brésil", "CHN": "en Chine", "CRI": "au Costa Rica", "EGY": "en Égypte",
    "ESP": "en Espagne", "FRA": "en France", "GBR": "au Royaume-Uni", "GRC": "en Grèce",
    "IDN": "en Indonésie", "IND": "en Inde", "ITA": "en Italie", "JPN": "au Japon",
    "KEN": "au Kenya", "KOR": "en Corée du Sud", "LAO": "au Laos", "MEX": "au Mexique",
    "SEN": "au Sénégal", "THA": "en Thaïlande", "TZA": "en Tanzanie", "VNM": "au Vietnam",
}
COLONNES = ["id_unesco", "iso3", "nom_fr", "annee_inscription", "wikidata_qid", "source_nom", "source_annee",
            "rattachement_nom", "type_source_annee", "verification_annee", "fiche_unesco",
            "date_releve", "note"]


# --- Accès aux API ------------------------------------------------------------------------

def appeler(url, **parametres):
    parametres.update(format="json", formatversion="2")
    adresse = url + "?" + urllib.parse.urlencode(parametres)
    requete = urllib.request.Request(adresse, headers={"User-Agent": USER_AGENT})
    for attente in (0, 30, 60, 120):
        time.sleep(attente)
        try:
            with urllib.request.urlopen(requete, context=CONTEXTE_SSL, timeout=60) as reponse:
                donnees = json.load(reponse)
            time.sleep(PAUSE)
            if "error" in donnees:
                sys.exit(f"Erreur de l'API : {donnees['error']}")
            return donnees
        except (urllib.error.URLError, TimeoutError) as erreur:
            derniere = erreur
    sys.exit(f"API injoignable, rien n'a été écrit : {derniere}")


def elements_wikidata(qids):
    """{QID : {frwiki, p757}} : lien vers l'article français et numéros UNESCO."""
    resultat, qids = {}, sorted(set(qids))
    for i in range(0, len(qids), TAILLE_LOT):
        reponse = appeler(URL_WIKIDATA, action="wbgetentities", ids="|".join(qids[i:i + TAILLE_LOT]),
                          props="sitelinks|claims", sitefilter="frwiki")
        for q, e in reponse["entities"].items():
            numeros = [c["mainsnak"].get("datavalue", {}).get("value", "")
                       for c in e.get("claims", {}).get("P757", [])]
            resultat[q] = {"frwiki": e.get("sitelinks", {}).get("frwiki", {}).get("title", ""),
                           "p757": numeros}
    return resultat


def lire_pages(titres):
    """Texte, version et élément Wikidata des articles ; suit les redirections."""
    pages, renvois, titres = {}, {}, sorted(set(titres))
    for i in range(0, len(titres), TAILLE_LOT):
        q = appeler(URL_WIKIPEDIA, action="query", prop="revisions|pageprops", rvprop="ids|content",
                    rvslots="main", ppprop="wikibase_item|disambiguation", redirects=1,
                    titles="|".join(titres[i:i + TAILLE_LOT]))["query"]
        for r in q.get("normalized", []) + q.get("redirects", []):
            renvois[r["from"]] = r["to"]
        for p in q["pages"]:
            if p.get("missing") or not p.get("revisions"):
                continue
            pages[p["title"]] = {"oldid": p["revisions"][0]["revid"],
                                 "texte": p["revisions"][0]["slots"]["main"]["content"],
                                 "item": p.get("pageprops", {}).get("wikibase_item", ""),
                                 "homonymie": "disambiguation" in p.get("pageprops", {})}
    return pages, renvois


def resoudre(titre, renvois):
    vus = set()
    while titre in renvois and titre not in vus:
        vus.add(titre)
        titre = renvois[titre]
    return titre


def permalien(titre, oldid):
    return ("https://fr.wikipedia.org/w/index.php?title="
            f"{urllib.parse.quote(titre.replace(' ', '_'), safe='')}&oldid={oldid}")


# --- Lecture du wikicode ----------------------------------------------------------------------

def lignes_de_liste(texte):
    """{numéro : (cellule du nom, cellule de l'année)}, biens inscrits seulement."""
    fin = re.search(r"(?m)^={2,}\s*Liste indicative", texte)
    texte = texte[:fin.start()] if fin else texte
    lignes = {}
    for bloc in re.split(r"\{\{\s*[Ll]igne de tableau [Pp]atrimoine mondial", texte)[1:]:
        champs = {}
        for m in re.finditer(r"\n\s*\|\s*(référence|bien|année)\s*=\s*([^\n]*)", bloc):
            champs.setdefault(m.group(1), m.group(2).strip())
        for numero in re.findall(r"\d+", champs.get("référence", "")):
            lignes.setdefault(numero, (champs.get("bien", ""), champs.get("année", "")))
    motif = (r'!\s*scope="row"[^|\n]*\|\s*\[https?://whc\.unesco\.org/\w+/list/(\d+)[^\]]*\]\s*\n'
             r"\|\s*([^\n]*)\n\|[^\n]*\n\|\s*([^\n]*)\n")
    for m in re.finditer(motif, texte):
        lignes.setdefault(m.group(1), (m.group(2).strip(), m.group(3).strip()))
    return lignes


def texte_simple(s):
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"\{\{\s*[sS]-?\|([^|}]*)\|?[^}]*\}\}", r"\1", s)
    s = re.sub(r"\{\{\s*[Ll]ien\|[^}]*?texte=([^|}]*)[^}]*\}\}", r"\1", s)
    s = re.sub(r"\{\{\s*[Ll]ien\|[^}]*?fr=([^|}]*)[^}]*\}\}", r"\1", s)
    s = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]*)\]\]", r"\1", s)
    return s.strip()


def liens_de_cellule(cellule):
    """[(titre visé, texte affiché)], dans l'ordre de la cellule."""
    cellule = re.sub(r"'{2,}", "", cellule)
    motif = r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|((?:[^\]{]|\{\{[^}]*\}\})*))?\]\]"
    return [(m.group(1).strip(), texte_simple(m.group(2) or m.group(1)))
            for m in re.finditer(motif, cellule) if ":" not in m.group(1)]


def sans_article_initial(s):
    return re.sub(r"^(?:Les?|La|L['’])\s*", "", s.strip())


def couvre_tout_le_nom(cellule, affiche):
    """Le lien couvre le nom du site (avant la première virgule, deux-points ou parenthèse)."""
    nom = sans_article_initial(re.split(r"[,:(]", texte_simple(cellule))[0]).strip()
    affiche = sans_article_initial(affiche)
    return bool(nom) and affiche in nom and len(affiche) >= COUVERTURE_MIN * len(nom)


def infobox(texte):
    """[(numéro, année)] déclarés par l'infobox de l'article."""
    numeros = re.findall(r"(?i)\bID\s+unesco\s*=\s*(\d+)", texte)
    annees = re.findall(r"(?i)ann[ée]e\s+unesco\s*=\s*\D*?(\d{4})", texte)
    return list(zip(numeros, annees))


def categories_annee(texte):
    return {int(a) for a in re.findall(
        r"(?i)\[\[\s*Catégorie\s*:\s*Patrimoine mondial inscrit en (\d{4})", texte)}


def annee_valide(annee):
    return PREMIERE_LISTE <= annee <= datetime.date.today().year


def annee_de_cellule(cellule):
    annees = {int(a) for a in re.findall(r"(?<!\d)(\d{4})(?!\d)", cellule)}
    annees = {a for a in annees if annee_valide(a)}
    return min(annees) if annees else None


def sans_parenthese(titre):
    return re.sub(r"\s*\([^()]*\)$", "", titre)


def fiche_en_cache(numero):
    """(titre, année) de la fiche déjà en cache ; aucune requête vers le site de l'UNESCO."""
    for langue in ("fr", "en"):
        if (DOSSIER_FICHES / f"{langue}_{numero}.html").exists():
            return fiche_unesco(numero, langue)
    return "", None


# --- Programme principal ------------------------------------------------------------------

def main():
    if len(SITES_NOM) != 38 or len(SITES_ANNEE) != 15 or SITES_NOM & SITES_ANNEE:
        sys.exit("Listes de sites incohérentes : 38 noms et 15 années distincts attendus.")
    with FICHIER_SORTIE.open(encoding="utf-8", newline="") as f:
        actuel = defaultdict(list)
        for l in csv.DictReader(f):
            actuel[l["id_unesco"]].append(l)
    cibles = sorted(SITES_NOM | SITES_ANNEE | set(ELEMENTS_IMPOSES), key=int)
    absents = [c for c in cibles if c not in actuel]
    if absents:
        sys.exit(f"Sites absents de {FICHIER_SORTIE.name} : {absents}")

    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        codes = [l["iso3"].strip() for l in csv.DictReader(f)]
    sites = sites_unesco(json.loads(FICHIER_BRUT.read_text(encoding="utf-8")), codes)

    print("1. Wikipédia : listes du patrimoine mondial par pays")
    pays_utiles = sorted({l["iso3"] for c in cibles for l in actuel[c]})
    inconnus = [p for p in pays_utiles if p not in LISTES]
    if inconnus:
        sys.exit(f"Liste Wikipédia non définie pour : {inconnus}")
    titres = {p: f"Liste du patrimoine mondial {LISTES[p]}" for p in pays_utiles}
    pages_listes, _ = lire_pages(titres.values())
    listes = {}
    for p, titre in titres.items():
        if titre not in pages_listes:
            sys.exit(f"Page introuvable : {titre}")
        listes[p] = lignes_de_liste(pages_listes[titre]["texte"])
        if not listes[p]:
            sys.exit(f"Aucune ligne lue dans {titre} : format inconnu, rien n'a été écrit")

    print("2. Wikidata : liens vers Wikipédia des éléments de chaque site")
    familles, a_lire = {}, set()
    for c in cibles:
        familles[c] = {}
        for l in actuel[c]:
            for numero, qs in sites[l["iso3"]][c]["ids"].items():
                for q in qs:
                    familles[c][q] = numero
            if l["wikidata_qid"]:
                familles[c][l["wikidata_qid"]] = c
        a_lire |= set(familles[c])
    elements = elements_wikidata(a_lire)

    print("3. Wikipédia : articles candidats")
    lignes_site, titres_articles = {}, set()
    for c in cibles:
        lignes_site[c] = [dict(iso3=l["iso3"], cellule=listes[l["iso3"]][c][0],
                               annee=annee_de_cellule(listes[l["iso3"]][c][1]),
                               annee_brute=listes[l["iso3"]][c][1])
                          for l in actuel[c] if c in listes[l["iso3"]]]
        for ligne in lignes_site[c]:
            titres_articles |= {t for t, _ in liens_de_cellule(ligne["cellule"])}
        titres_articles |= {elements[q]["frwiki"] for q in familles[c]
                            if q in elements and elements[q]["frwiki"]}
    articles, renvois = lire_pages(titres_articles)
    items = elements_wikidata({a["item"] for a in articles.values() if a["item"]})

    aujourd_hui = datetime.date.today().isoformat()
    sorties, rapport, erreurs = [], [], []

    def utilisable(titre):
        a = articles.get(titre)
        return bool(a and a["item"] and not a["homonymie"])

    for c in cibles:
        choisi = actuel[c][0]["wikidata_qid"]
        motif = re.compile(re.escape(c) + r"(rev|" + EXTENSIONS.strip("()") + r")?")
        lignes = lignes_site[c]
        liens_ligne = [[(resoudre(t, renvois), aff) for t, aff in liens_de_cellule(l["cellule"])]
                       for l in lignes]
        titres_ligne = [t for groupe in liens_ligne for t, _ in groupe]

        # articles du même élément ou du même numéro UNESCO
        groupe = []
        if choisi and elements.get(choisi, {}).get("frwiki"):
            groupe.append((resoudre(elements[choisi]["frwiki"], renvois), "meme_element"))
        for q, numero in sorted(familles[c].items(), key=lambda x: int(x[0][1:])):
            if q != choisi and motif.fullmatch(numero) and elements.get(q, {}).get("frwiki"):
                groupe.append((resoudre(elements[q]["frwiki"], renvois), "meme_numero"))
        groupe = [(t, r) for t, r in groupe if utilisable(t)]

        # --- nom ---
        titre_nom, rattachement = "", ""
        if c in SITES_NOM:
            dans_la_ligne = [x for x in groupe if x[0] in titres_ligne]
            if dans_la_ligne or groupe:
                titre_nom, rattachement = (dans_la_ligne or groupe)[0]
            if not titre_nom:
                for t in titres_ligne:
                    if utilisable(t) and any(n == c for n, _ in infobox(articles[t]["texte"])):
                        titre_nom, rattachement = t, "infobox"
                        break
            if not titre_nom:
                for ligne, liens in zip(lignes, liens_ligne):
                    for t, affiche in liens:
                        if utilisable(t) and couvre_tout_le_nom(ligne["cellule"], affiche):
                            titre_nom, rattachement = t, "ligne_entiere"
                            break
                    if titre_nom:
                        break
            if not titre_nom:
                for ligne, liens in zip(lignes, liens_ligne):
                    for t, _ in liens:
                        if (utilisable(t) and ligne["annee"]
                                and ligne["annee"] in categories_annee(articles[t]["texte"])):
                            titre_nom, rattachement = t, "categorie_annee"
                            break
                    if titre_nom:
                        break
            if not titre_nom and c in ARTICLES_DE_LIEU:
                t = resoudre(ARTICLES_DE_LIEU[c], renvois)
                if not utilisable(t) or t not in titres_ligne:
                    erreurs.append(f"{c} : article du lieu « {t} » absent de la ligne ou inutilisable")
                else:
                    titre_nom, rattachement = t, "article_lieu"
            rattachement = rattachement or "sans_article"

        # --- année ---
        annee, source_annee, type_annee = None, "", ""
        if c in SITES_ANNEE:
            candidats = [t for t, _ in groupe] + [t for t in titres_ligne if utilisable(t)]
            for t in dict.fromkeys(candidats):
                trouve = [int(a) for n, a in infobox(articles[t]["texte"]) if n == c]
                if trouve and annee_valide(trouve[0]):
                    annee, type_annee = trouve[0], "infobox_article"
                    source_annee = permalien(t, articles[t]["oldid"])
                    break
            if annee is None:
                for ligne in lignes:
                    if ligne["annee"] is None:
                        continue
                    for t in dict.fromkeys(candidats):
                        if ligne["annee"] in categories_annee(articles[t]["texte"]):
                            annee, type_annee = ligne["annee"], "categorie_article"
                            source_annee = permalien(t, articles[t]["oldid"])
                            break
                    if annee is not None:
                        break
            if annee is None:
                for ligne in lignes:
                    if ligne["annee"] is not None:
                        titre = titres[ligne["iso3"]]
                        annee, type_annee = ligne["annee"], "liste_pays"
                        source_annee = permalien(titre, pages_listes[titre]["oldid"])
                        break
            type_annee = type_annee or "sans_annee"

        # --- vérifications (la fiche UNESCO n'est jamais recopiée) ---
        titre_fiche, annee_fiche = fiche_en_cache(c)
        verification = ""
        if c in SITES_ANNEE:
            if annee is None:
                verification = "sans_annee"
            elif annee_fiche is None:
                verification = "non_verifiee"
            else:
                verification = "identique" if annee == annee_fiche else "ecart"

        notes = []
        impose, note_imposee = ELEMENTS_IMPOSES.get(c, ("", ""))
        if note_imposee:
            notes.append(note_imposee)
        if c in NOTES_SITES:
            notes.append(NOTES_SITES[c])
        if rattachement == "sans_article":
            notes.append("pas d'article Wikipédia sur ce site : libellé Wikidata conservé")
        if rattachement == "article_lieu":
            notes.append("pas d'article sur le site : titre de l'article du lieu")
        if rattachement == "categorie_annee":
            notes.append("article sur le lieu ou l'élément principal du site")
        numeros_article = items.get(articles[titre_nom]["item"], {}).get("p757", []) if titre_nom else []
        base_numeros = {re.match(r"\d+", n).group() for n in numeros_article if re.match(r"\d+", n)}
        if base_numeros and c not in base_numeros:
            notes.append(f"l'élément Wikidata de l'article porte un autre numéro UNESCO ({sorted(base_numeros)})")
        if verification == "ecart":
            notes.append("année différente de la fiche UNESCO : à vérifier")

        ligne_sortie = {
            "id_unesco": c, "iso3": PAYS_DU_NOM.get(c, ""),
            "nom_fr": sans_parenthese(titre_nom), "annee_inscription": annee or "",
            "wikidata_qid": impose,
            "source_nom": permalien(titre_nom, articles[titre_nom]["oldid"]) if titre_nom else "",
            "source_annee": source_annee, "rattachement_nom": rattachement,
            "type_source_annee": type_annee, "verification_annee": verification,
            "fiche_unesco": URL_UNESCO.format(c), "date_releve": aujourd_hui,
            "note": " ; ".join(notes),
        }
        sorties.append(ligne_sortie)
        rapport.append((ligne_sortie, titre_nom, actuel[c],
                        ressemblance(titre_fiche, sans_parenthese(titre_nom)) if titre_nom and titre_fiche else None,
                        [t for t in titres_ligne if t in articles]))

    # --- Contrôles bloquants ---
    for s in sorties:
        c = s["id_unesco"]
        for champ, cle in (("nom_fr", "source_nom"), ("annee_inscription", "source_annee")):
            if s[champ] != "" and not s[cle].startswith("https://fr.wikipedia.org/w/index.php?title="):
                erreurs.append(f"{c} : {champ} sans lien Wikipédia")
            if "unesco.org" in s[cle]:
                erreurs.append(f"{c} : {cle} pointe vers l'UNESCO")
            if s[champ] == "" and s[cle]:
                erreurs.append(f"{c} : {cle} sans valeur")
        if c in SITES_NOM and not s["nom_fr"] and s["rattachement_nom"] != "sans_article":
            erreurs.append(f"{c} : nom vide sans être signalé")
        if s["annee_inscription"] != "" and not annee_valide(int(s["annee_inscription"])):
            erreurs.append(f"{c} : année impossible {s['annee_inscription']}")
    if len(sorties) != len(cibles) or len({s["id_unesco"] for s in sorties}) != len(cibles):
        erreurs.append("nombre de lignes incorrect")
    if erreurs:
        sys.exit("Contrôles échoués, rien n'a été écrit :\n  - " + "\n  - ".join(erreurs))

    sauver_brut("wikipedia_unesco.json", {
        "date_releve": aujourd_hui,
        "listes": {p: {"titre": t, "oldid": pages_listes[t]["oldid"]} for p, t in titres.items()},
        "lignes": {c: [{"iso3": l["iso3"], "annee": l["annee"],
                        "liens": [resoudre(t, renvois) for t, _ in liens_de_cellule(l["cellule"])]}
                       for l in lignes_site[c]] for c in cibles},
        "articles": {t: {"oldid": a["oldid"], "element": a["item"], "homonymie": a["homonymie"],
                         "infobox": infobox(a["texte"]),
                         "categories_annee": sorted(categories_annee(a["texte"]))}
                     for t, a in sorted(articles.items())},
        "elements": elements,
    })
    with FICHIER_CORRECTIONS.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(sorties)
    print(f"   Fichier écrit : {FICHIER_CORRECTIONS.name} ({len(sorties)} lignes)")

    # --- Rapport ---
    print("\n=== Noms ===")
    for rang in ("meme_element", "meme_numero", "infobox", "ligne_entiere", "categorie_annee",
                 "article_lieu", "sans_article"):
        groupe = [r for r in rapport if r[0]["rattachement_nom"] == rang]
        print(f"\n[{rang}] {len(groupe)}")
        for s, titre, lignes, score, liens in groupe:
            pays = "/".join(l["iso3"] for l in lignes)
            ancien = lignes[0]["wikidata_qid"]
            info = f" ressemblance fiche {score:.2f}" if score is not None else ""
            if rang == "sans_article":
                print(f"  n°{s['id_unesco']:<5}{pays:<9}élément {ancien or '-'} ; articles liés : {liens}")
            else:
                print(f"  n°{s['id_unesco']:<5}{pays:<9}« {s['nom_fr']} » [{titre}]{info}"
                      + (f"  ! {s['note']}" if s["note"] else ""))
    print("\n=== Années ===")
    for s, titre, lignes, _, _ in rapport:
        if s["id_unesco"] in SITES_ANNEE:
            print(f"  n°{s['id_unesco']:<5}{lignes[0]['iso3']:<5}{s['annee_inscription'] or 'VIDE':<6}"
                  f"{s['type_source_annee']:<19}{s['verification_annee']}")


if __name__ == "__main__":
    main()
