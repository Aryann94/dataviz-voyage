"""
build_zip.py
------------
Construit data/telechargement/periple_donnees.zip, le fichier à télécharger sur le site :
  periple_donnees/LISEZMOI.txt, LICENCES.txt, dictionnaire_donnees.csv, periple_donnees.xlsx
  periple_donnees/donnees/ : les 12 CSV, identiques à ceux du dossier data/

Le script régénère d'abord le dictionnaire et le classeur Excel.

Contrôles bloquants, avant de remplacer le ZIP :
  - aucun fichier écarté du téléchargement n'entre dans l'archive ;
  - la citation de Budget Your Trip et les deux notices MIT sont présentes ;
  - chaque photo de pays.csv a un auteur et une licence ;
  - unesco_sites.csv ne reprend aucun nom attribué à whc.unesco.org ;
  - l'archive relue contient exactement les fichiers attendus, octet pour octet.

Lancement depuis la racine :
    py scripts/build_zip.py
"""

import csv
import hashlib
import os
import sys
import zipfile
from pathlib import Path

import build_dictionnaire
import build_excel

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data"
DOCUMENTATION = DONNEES / "documentation"
SORTIE = DONNEES / "telechargement" / "periple_donnees.zip"
DOSSIER_ZIP = "periple_donnees"
DATE_ZIP = (2026, 1, 1, 0, 0, 0)               # date fixe : même contenu, même archive

ECARTES = {"corrections_unesco_noms.csv", "saisie_budget.csv", "descriptions_pays.csv",
           "pays_liste.csv", "corrections_credits_photos.csv", "visas_historique.json"}
CITATION_BUDGET = ["https://www.budgetyourtrip.com", "16 octobre 2026", "non commercial",
                   "à la main pour une partie des pays", "pas une autorisation"]


def empreinte(contenu):
    return hashlib.sha256(contenu).hexdigest()


def plat(texte):
    return " ".join(texte.split())


def fichiers_attendus():
    """{chemin dans le ZIP : fichier source}"""
    attendus = {
        f"{DOSSIER_ZIP}/LISEZMOI.txt": DOCUMENTATION / "LISEZMOI.txt",
        f"{DOSSIER_ZIP}/LICENCES.txt": DOCUMENTATION / "LICENCES.txt",
        f"{DOSSIER_ZIP}/dictionnaire_donnees.csv": build_dictionnaire.SORTIE,
        f"{DOSSIER_ZIP}/periple_donnees.xlsx": build_excel.SORTIE,
    }
    for relatif in build_excel.FICHIERS:
        if not relatif.startswith("documentation/"):
            attendus[f"{DOSSIER_ZIP}/donnees/{relatif}"] = DONNEES / relatif
    return attendus


def controler_contenu(attendus):
    erreurs = []
    for nom, source in attendus.items():
        if not source.exists():
            erreurs.append(f"fichier manquant : {source}")
        if Path(nom).name in ECARTES:
            erreurs.append(f"fichier écarté dans le ZIP : {nom}")
    if erreurs:
        return erreurs
    lisezmoi = plat((DOCUMENTATION / "LISEZMOI.txt").read_text(encoding="utf-8"))
    licences = plat((DOCUMENTATION / "LICENCES.txt").read_text(encoding="utf-8"))
    for nom, texte in (("LISEZMOI.txt", lisezmoi), ("LICENCES.txt", licences)):
        for morceau in CITATION_BUDGET:
            if morceau not in texte:
                erreurs.append(f"{nom} : citation de Budget Your Trip incomplète ({morceau})")
    if licences.count("Permission is hereby granted") != 2:
        erreurs.append("LICENCES.txt : il faut les deux notices MIT")
    with (DONNEES / "pays.csv").open(encoding="utf-8", newline="") as f:
        for l in csv.DictReader(f):
            if not (l["image_url"] and l["image_auteur"] and l["image_licence"]):
                erreurs.append(f"pays.csv : crédit incomplet pour {l['iso3']}")
    with (DONNEES / "unesco_sites.csv").open(encoding="utf-8", newline="") as f:
        for l in csv.DictReader(f):
            if l["langue_nom"] == "unesco_fr" or "unesco.org" in l["source_nom"] + l["source_annee"]:
                erreurs.append(f"unesco_sites.csv : contenu attribué à l'UNESCO ({l['id_unesco']})")
    return erreurs


def ecrire(chemin, attendus):
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for nom in sorted(attendus):
            info = zipfile.ZipInfo(nom, DATE_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, attendus[nom].read_bytes())


def relire(chemin, attendus):
    erreurs = []
    with zipfile.ZipFile(chemin) as zf:
        if zf.testzip() is not None:
            return ["archive abîmée"]
        if set(zf.namelist()) != set(attendus):
            erreurs.append("liste de fichiers inattendue")
        for nom, source in attendus.items():
            if nom in zf.namelist() and (empreinte(zf.read(nom)) != empreinte(source.read_bytes())):
                erreurs.append(f"{nom} différent de sa source")
    return erreurs


def main():
    build_dictionnaire.main()
    build_excel.main()
    attendus = fichiers_attendus()
    erreurs = controler_contenu(attendus)
    if erreurs:
        sys.exit("Contrôles échoués, ZIP non écrit :\n  - " + "\n  - ".join(erreurs[:30]))
    temporaire = SORTIE.with_suffix(".tmp")
    try:
        ecrire(temporaire, attendus)
        erreurs = relire(temporaire, attendus)
        if erreurs:
            sys.exit("Contrôles échoués, ZIP non publié :\n  - " + "\n  - ".join(erreurs[:30]))
        os.replace(temporaire, SORTIE)
    finally:
        temporaire.unlink(missing_ok=True)
    print(f"ZIP écrit : {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size / 1e6:.1f} Mo, "
          f"{len(attendus)} fichiers), relu octet pour octet.")


if __name__ == "__main__":
    main()
