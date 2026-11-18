"""
build_quiz_photos.py
--------------------
Photos des duels du quiz : data/quiz_photos.csv (description, auteur, licence, lien).

Chaque photo a été ouverte et regardée avant d'être gardée : elle montre ce que dit le choix, et
sa description sert aussi de texte alternatif sur la page. Elle peut venir de n'importe quel
pays, tant qu'elle ne montre aucun lieu célèbre reconnaissable.

Contrôles bloquants (rien n'est écrit si l'un échoue) :
  - chaque réponse de chaque duel a sa photo, et aucune photo ne sert deux fois ;
  - chaque photo a une description, écrite en une phrase ;
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

COLONNES = ["question", "option", "fichier", "description", "image_url", "auteur", "licence", "page",
            "date_verification"]

# (question, réponse) : (fichier Commons, ce qu'on voit sur la photo)
PHOTOS = {
    ("reveil", 0): ("Waves crashing at the Flat Point Tide Pools, Saba.jpg",
                    "Des vagues se brisent en écume blanche sur des rochers sombres."),
    ("reveil", 1): ("On bell tower at Rizopolozhensky Monastery in Suzdal.jpg",
                    "Une grande cloche de bronze est suspendue sous la voûte blanche d'un clocher."),
    ("soir", 0): ("Moon above city's night-lights as a lantern.jpg",
                  "Des tours illuminées se détachent dans la nuit, sous une pleine lune."),
    ("soir", 1): ("Campfire in Tulppio.jpg",
                  "Un petit feu brûle entre des bancs de bois, au milieu d'une forêt de pins."),
    ("marche", 0): ("Ridge of Veliki Vrh, Karawanks, Slovenia 11.jpg",
                    "Un sentier suit une crête herbeuse, avec des montagnes et de gros nuages au fond."),
    ("marche", 1): ("Kastelos 1.jpg",
                    "Les hauts murs de pierre d'un château en ruine dominent des buissons."),
    ("chaleur", 0): ("Sea-1019222.jpg",
                     "Des silhouettes sur un rocher en pleine mer, dont une qui saute dans l'eau."),
    ("chaleur", 1): ("Romanesque church. - panoramio.jpg",
                     "La nef sombre d'une église de pierre, sous un plafond de bois."),
    ("photo", 0): ("Sunset at Grobiņa Castle ruins.jpg",
                   "Les murs percés d'une ruine prennent la lumière dorée du soir, entre de grands arbres."),
    ("photo", 1): ("Aerial View of a city in night.jpg",
                   "Les lumières d'une ville s'étendent dans la nuit, vues d'avion."),
    ("photo", 2): ("Landscape of upper Tyedalen, 2011 August.jpg",
                   "Un plateau d'herbe et de rochers s'étend sous un ciel gris, sans personne ni maison."),
}
# La page Commons donne parfois un lien à la place d'un nom lisible.
AUTEURS_AFFICHES = {"Sea-1019222.jpg": "slavikfi (Pixabay)"}


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
    return next((l for l in LARGEURS if l >= voulue and l <= largeur), min(largeur, LARGEURS[-1]))


def main():
    banque = json.loads((DONNEES / "quiz_questions.json").read_text(encoding="utf-8"))
    erreurs = []
    attendues = {(q["id"], i) for q in banque["questions"] if q["type"] == "duel"
                 for i in range(len(q["options"]))}
    if attendues != set(PHOTOS):
        erreurs.append(f"réponses de duel sans photo ou en trop : {sorted(attendues ^ set(PHOTOS))}")
    fichiers = [f for f, _ in PHOTOS.values()]
    if len(set(fichiers)) != len(fichiers):
        erreurs.append("une photo sert deux fois")
    for (q, o), (_, description) in PHOTOS.items():
        if not description.endswith(".") or description.count(".") != 1:
            erreurs.append(f"{q}/{o} : la description doit tenir en une phrase")

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
    for (question, option), (fichier, description) in PHOTOS.items():
        titre = renommes.get(f"File:{fichier}", f"File:{fichier}")
        page = pages.get(titre)
        if not page or page.get("missing"):
            erreurs.append(f"{fichier} : page introuvable")
            continue
        info = page["imageinfo"][0]
        meta = info["extmetadata"]
        auteur = AUTEURS_AFFICHES.get(fichier) or html_vers_texte(meta.get("Artist", {}).get("value", ""))
        licence = meta.get("LicenseShortName", {}).get("value", "")
        if not auteur or auteur.startswith("http"):
            erreurs.append(f"{fichier} : pas d'auteur lisible")
        if not LICENCES.fullmatch(licence):
            erreurs.append(f"{fichier} : licence refusée ({licence})")
        if info["width"] < info["height"] * 1.2 or info["width"] < 1800:
            erreurs.append(f"{fichier} : format inadapté ({info['width']}x{info['height']})")
        modeles = [m["title"] for m in page.get("templates", []) if MODELES_INTERDITS.search(m["title"])]
        if modeles:
            erreurs.append(f"{fichier} : avertissements {modeles}")
        titre_url = urllib.parse.quote(titre.replace(" ", "_"), safe=":,()")
        lignes.append({
            "question": question, "option": option, "fichier": titre[len("File:"):],
            "description": description,
            "image_url": url_image(titre[len("File:"):], largeur=largeur_vignette(info["width"], info["height"])),
            "auteur": auteur, "licence": licence,
            "page": f"https://commons.wikimedia.org/w/index.php?title={titre_url}&oldid={page['revisions'][0]['revid']}",
            "date_verification": aujourd_hui,
        })
    if erreurs:
        sys.exit("Contrôles échoués, rien n'a été écrit :\n  - " + "\n  - ".join(erreurs))
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(lignes)
    print(f"Fichier écrit : {SORTIE.relative_to(RACINE)} ({len(lignes)} photos)")
    for l in lignes:
        print(f"  {l['question']}/{l['option']} {l['licence']:<13}{l['auteur'][:32]}")


if __name__ == "__main__":
    main()
