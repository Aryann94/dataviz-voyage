"""
build_quiz_photos.py
--------------------
Photos d'ambiance des duels du quiz : data/quiz_photos.csv (auteur, licence, lien, lieu).

Une photo montre un goût, jamais un pays de la sélection : chaque photo est prise hors des
41 pays du quiz. Les fichiers sont choisis à la main ici, le reste est lu sur Wikimedia Commons.

Contrôles bloquants (rien n'est écrit si l'un échoue) :
  - chaque réponse de chaque duel a sa photo, et aucune photo ne sert deux fois ;
  - le lieu de la photo est un pays connu, hors de la sélection de 41 pays ;
  - la photo a un auteur, une licence CC BY, CC BY-SA ou CC0, et un format paysage ;
  - sa page ne porte aucun avertissement de droits ni demande de suppression.

Lancement depuis la racine :
    py scripts/build_quiz_photos.py
"""

import csv
import datetime
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from build_pays_wikidata import CONTEXTE_SSL, html_vers_texte, url_image

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data"
SORTIE = DONNEES / "quiz_photos.csv"
USER_AGENT = "StudentDatavizScript/1.0 (non-commercial coursework)"
URL_API = "https://commons.wikimedia.org/w/api.php"
LICENCES = re.compile(r"CC BY(-SA)? [34]\.0|CC0")
MODELES_INTERDITS = re.compile(r"(?i)nofop|delete|deletion|copyvio|speedy|fop-|no permission|no source")
LARGEURS = (960, 1280, 1920)     # tailles de vignettes standard de Wikimedia
HAUTEUR_UTILE = 640              # hauteur minimale de la vignette, pour remplir la carte

COLONNES = ["question", "option", "fichier", "image_url", "auteur", "licence", "page", "lieu",
            "date_verification"]

# (question, réponse) : (fichier Commons, pays de la prise de vue)
PHOTOS = {
    ("reveil", 0): ("Granite rocks on the coast of Curieuse Island - Seychelles - 01.jpg", "Seychelles"),
    ("reveil", 1): ("2011 Butrint 02 Agora.jpg", "Albanie"),
    ("soir", 0): ("Skyline Frankfurt Flößerbrücke.jpg", "Allemagne"),
    ("soir", 1): ("Suobbattjåhkå stream and the Tjakkeli mountain during golden hour, Sarek National Park (DSCF2833).jpg", "Suède"),
    ("connexion", 0): ("Singapore (SG), Marina Bay -- 2019 -- 4561-9.jpg", "Singapour"),
    ("connexion", 1): ("Sno river valley, Caucasian mountains, Georgia.jpg", "Géorgie"),
    ("marche", 0): ("Landscape of upper Tyedalen, 2011 August.jpg", "Norvège"),
    ("marche", 1): ("2011 Butrint 05 Prytaneion and Asclepios Sanctuary.jpg", "Albanie"),
    ("chaleur", 0): ("Gjipe Beach, Albania.JPG", "Albanie"),
    ("chaleur", 1): ("The ruins of Ancient Dvin 19.jpg", "Arménie"),
    ("photo", 0): ("2014 Prowincja Armawir, Zwartnoc, Ruiny katedry Zwartnoc 07.JPG", "Arménie"),
    ("photo", 1): ("Singapore (SG), Marina Bay, Night View -- 2019 -- 4573-81.jpg", "Singapour"),
    ("photo", 2): ("Sossusvlei, Namibia, 2018-08-06, DD 040.jpg", "Namibie"),
}


def appeler(**parametres):
    parametres.update(format="json", formatversion="2")
    adresse = URL_API + "?" + urllib.parse.urlencode(parametres)
    requete = urllib.request.Request(adresse, headers={"User-Agent": USER_AGENT})
    for attente in (0, 30, 60):
        time.sleep(attente)
        try:
            with urllib.request.urlopen(requete, context=CONTEXTE_SSL, timeout=60) as reponse:
                return json.load(reponse)
        except OSError as erreur:
            derniere = erreur
    sys.exit(f"Commons injoignable, rien n'a été écrit : {derniere}")


def largeur_vignette(largeur, hauteur):
    voulue = HAUTEUR_UTILE * largeur / hauteur
    return next((l for l in LARGEURS if l >= voulue), LARGEURS[-1])


def main():
    banque = json.loads((DONNEES / "quiz_questions.json").read_text(encoding="utf-8"))
    with (DONNEES / "pays_monde.csv").open(encoding="utf-8", newline="") as f:
        monde = {l["nom_fr"]: l["dans_selection"] for l in csv.DictReader(f)}
    erreurs = []
    attendues = {(q["id"], i) for q in banque["questions"] if q["type"] == "duel"
                 for i in range(len(q["options"]))}
    if attendues != set(PHOTOS):
        erreurs.append(f"réponses de duel sans photo ou en trop : {sorted(attendues ^ set(PHOTOS))}")
    fichiers = [f for f, _ in PHOTOS.values()]
    if len(set(fichiers)) != len(fichiers):
        erreurs.append("une photo sert deux fois")
    for (q, o), (fichier, lieu) in PHOTOS.items():
        if lieu not in monde:
            erreurs.append(f"{q}/{o} : lieu inconnu {lieu}")
        elif monde[lieu] != "false":
            erreurs.append(f"{q}/{o} : {lieu} fait partie des 41 pays du quiz")

    pages, renommes = {}, {}
    for i in range(0, len(fichiers), 20):
        r = appeler(action="query", prop="imageinfo|revisions|templates", iiprop="extmetadata|size",
                    rvprop="ids", tllimit="max", titles="|".join(f"File:{f}" for f in fichiers[i:i + 20]))
        for n in r["query"].get("normalized", []):
            renommes[n["from"]] = n["to"]
        pages.update({p["title"]: p for p in r["query"]["pages"]})
        time.sleep(1)

    aujourd_hui = datetime.date.today().isoformat()
    lignes = []
    for (question, option), (fichier, lieu) in PHOTOS.items():
        titre = renommes.get(f"File:{fichier}", f"File:{fichier}")
        page = pages.get(titre)
        if not page or page.get("missing"):
            erreurs.append(f"{fichier} : page introuvable")
            continue
        info = page["imageinfo"][0]
        meta = info["extmetadata"]
        auteur = html_vers_texte(meta.get("Artist", {}).get("value", ""))
        licence = meta.get("LicenseShortName", {}).get("value", "")
        if not auteur:
            erreurs.append(f"{fichier} : pas d'auteur")
        if not LICENCES.fullmatch(licence):
            erreurs.append(f"{fichier} : licence refusée ({licence})")
        if info["width"] < info["height"] * 1.2 or info["width"] < 2000:
            erreurs.append(f"{fichier} : format inadapté ({info['width']}x{info['height']})")
        modeles = [m["title"] for m in page.get("templates", []) if MODELES_INTERDITS.search(m["title"])]
        if modeles:
            erreurs.append(f"{fichier} : avertissements {modeles}")
        titre_url = urllib.parse.quote(titre.replace(" ", "_"), safe=":,()")
        lignes.append({
            "question": question, "option": option, "fichier": titre[len("File:"):],
            "image_url": url_image(titre[len("File:"):], largeur=largeur_vignette(info["width"], info["height"])),
            "auteur": auteur, "licence": licence,
            "page": f"https://commons.wikimedia.org/w/index.php?title={titre_url}&oldid={page['revisions'][0]['revid']}",
            "lieu": lieu, "date_verification": aujourd_hui,
        })
    if erreurs:
        sys.exit("Contrôles échoués, rien n'a été écrit :\n  - " + "\n  - ".join(erreurs))
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"Fichier écrit : {SORTIE.relative_to(RACINE)} ({len(lignes)} photos)")
    for l in lignes:
        print(f"  {l['question']}/{l['option']} {l['lieu']:<11}{l['licence']:<13}{l['auteur'][:32]}")


if __name__ == "__main__":
    main()
