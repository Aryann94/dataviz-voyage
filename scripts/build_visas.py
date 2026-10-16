"""
build_visas.py
--------------
Télécharge le jeu de données Passport Index (dépôt GitHub imorte/passport-index-data)
et le convertit en data/visas.csv au format du projet :

    passeport_iso3,destination_iso3,statut,jours,date_verification

Puis applique les vérifications manuelles de data/corrections_visas.csv
(corrections ET confirmations, chacune avec sa source et sa date).

Utilise uniquement la bibliothèque standard de Python : aucun « pip install » nécessaire.

Lancement (depuis la racine du projet) :
    python scripts/build_visas.py
"""

import csv
import io
import json
import sys
import urllib.request
from collections import Counter
from pathlib import Path

# --- Configuration -----------------------------------------------------------

REPO = "imorte/passport-index-data"
FICHIER_SOURCE = "passport-index-tidy-iso3.csv"
URL_SOURCE = f"https://raw.githubusercontent.com/{REPO}/main/{FICHIER_SOURCE}"
# API GitHub : date du dernier commit qui a modifié le fichier source
URL_DERNIER_COMMIT = (
    f"https://api.github.com/repos/{REPO}/commits?path={FICHIER_SOURCE}&per_page=1"
)

RACINE = Path(__file__).resolve().parent.parent      # dossier du projet
DOSSIER_BRUT = RACINE / "data" / "raw"                # copie brute, jamais modifiée
FICHIER_BRUT = DOSSIER_BRUT / FICHIER_SOURCE
FICHIER_SORTIE = RACINE / "data" / "visas.csv"
FICHIER_CORRECTIONS = RACINE / "data" / "corrections_visas.csv"  # rempli à la main

# Correspondance valeurs de la source -> valeurs du projet
STATUTS = {
    "visa free": "sans_visa",
    "visa on arrival": "visa_arrivee",
    "eta": "eta",
    "e-visa": "e_visa",
    "visa required": "visa_requis",
    "no admission": "interdit",
}


# --- Étape 1 : téléchargement -------------------------------------------------

def telecharger(url: str) -> str:
    """Télécharge une URL et renvoie son contenu texte (UTF-8)."""
    requete = urllib.request.Request(url, headers={"User-Agent": "projet-dataviz-voyage"})
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        return reponse.read().decode("utf-8")


def date_derniere_maj():
    """Renvoie la date du dernier commit du fichier source (AAAA-MM-JJ), ou None."""
    try:
        commits = json.loads(telecharger(URL_DERNIER_COMMIT))
        return commits[0]["commit"]["committer"]["date"][:10]
    except Exception as erreur:  # l'API GitHub est limitée en nombre d'appels
        print(f"  (date de mise à jour indisponible : {erreur})")
        return None


# --- Étape 2 : conversion -----------------------------------------------------

def convertir_ligne(passeport: str, destination: str, exigence: str):
    """
    Transforme une ligne source en ligne projet.
    Renvoie None pour les lignes à ignorer (passeport == destination).
    Lève ValueError pour une valeur inconnue (pour ne rien perdre en silence).
    """
    exigence = exigence.strip().lower()

    if exigence == "-1":                 # passeport = destination
        return None
    # 5e colonne : date_verification, vide tant qu'aucune vérification manuelle
    if exigence.isdigit():               # ex. "90" -> sans visa pendant 90 jours
        return [passeport, destination, "sans_visa", int(exigence), ""]
    if exigence in STATUTS:
        return [passeport, destination, STATUTS[exigence], "", ""]

    raise ValueError(f"Valeur inconnue : '{exigence}' ({passeport} -> {destination})")


def convertir(texte_csv: str):
    lecteur = csv.DictReader(io.StringIO(texte_csv))
    colonnes_attendues = {"Passport", "Destination", "Requirement"}
    if not colonnes_attendues.issubset(lecteur.fieldnames or []):
        sys.exit(f"Colonnes inattendues dans la source : {lecteur.fieldnames}")

    lignes, inconnues, ignorees = [], [], 0
    for ligne in lecteur:
        try:
            resultat = convertir_ligne(
                ligne["Passport"].strip(), ligne["Destination"].strip(), ligne["Requirement"]
            )
        except ValueError as erreur:
            inconnues.append(str(erreur))
            continue
        if resultat is None:
            ignorees += 1
        else:
            lignes.append(resultat)
    return lignes, inconnues, ignorees


# --- Étape 3 : corrections manuelles ------------------------------------------

COLONNES_CORRECTIONS = [
    "passeport_iso3", "destination_iso3", "statut", "jours",
    "source_url", "date_verification", "note",
]


def lire_corrections():
    """
    Lit data/corrections_visas.csv et vérifie chaque ligne.
    Arrête le script au moindre problème : une correction mal saisie
    ne doit jamais passer en silence.
    """
    if not FICHIER_CORRECTIONS.exists():
        print(f"   (pas de fichier {FICHIER_CORRECTIONS.name} : aucune correction appliquée)")
        return []

    with FICHIER_CORRECTIONS.open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        manquantes = set(COLONNES_CORRECTIONS) - set(lecteur.fieldnames or [])
        if manquantes:
            sys.exit(f"{FICHIER_CORRECTIONS.name} : colonnes manquantes {sorted(manquantes)}")

        corrections, erreurs, deja_vues, en_attente = [], [], set(), []
        statuts_valides = set(STATUTS.values())
        for numero, ligne in enumerate(lecteur, start=2):  # ligne 1 = en-tête
            c = {k: (ligne[k] or "").strip() for k in COLONNES_CORRECTIONS}
            paire = (c["passeport_iso3"], c["destination_iso3"])
            # Ligne préparée mais pas encore vérifiée (date vide) : ignorée pour l'instant
            if not c["date_verification"]:
                en_attente.append(f"{paire[0]}->{paire[1]}")
                deja_vues.add(paire)
                continue
            if c["statut"] not in statuts_valides:
                erreurs.append(f"ligne {numero} : statut '{c['statut']}' invalide")
            if c["jours"] and not c["jours"].isdigit():
                erreurs.append(f"ligne {numero} : jours '{c['jours']}' n'est pas un entier")
            if c["jours"] and c["statut"] != "sans_visa":
                erreurs.append(f"ligne {numero} : des jours ne s'indiquent qu'avec 'sans_visa'")
            if not c["source_url"] or not c["date_verification"]:
                erreurs.append(f"ligne {numero} : source_url et date_verification sont obligatoires")
            if paire in deja_vues:
                erreurs.append(f"ligne {numero} : paire {paire} en double")
            deja_vues.add(paire)
            corrections.append(c)

    if erreurs:
        sys.exit("Corrections invalides :\n  - " + "\n  - ".join(erreurs))
    if en_attente:
        print(f"   {len(en_attente)} ligne(s) en attente de vérification (date vide) : "
              f"{', '.join(en_attente)}")
    return corrections


def appliquer_corrections(lignes, corrections):
    """
    Remplace les lignes concernées et note la date de vérification.
    Une « correction » identique à la source est une CONFIRMATION :
    elle est utile (la ligne est marquée vérifiée) et elle signale aussi
    que la source a peut-être été mise à jour entre-temps.
    """
    index = {(l[0], l[1]): l for l in lignes}
    print(f"\n=== Corrections manuelles ({len(corrections)}) ===")
    for c in corrections:
        paire = (c["passeport_iso3"], c["destination_iso3"])
        ligne = index.get(paire)
        if ligne is None:
            sys.exit(f"Correction impossible : la paire {paire} n'existe pas dans la source")

        avant = f"{ligne[2]} {ligne[3]}".strip()
        apres = f"{c['statut']} {c['jours']}".strip()
        ligne[2] = c["statut"]
        ligne[3] = int(c["jours"]) if c["jours"] else ""
        ligne[4] = c["date_verification"]

        etiquette = "confirmé " if avant == apres else "corrigé  "
        print(f"  {etiquette}{paire[0]} -> {paire[1]} : {avant}  =>  {apres}")


# --- Étape 4 : vérifications --------------------------------------------------

def verifier(lignes, inconnues, ignorees):
    print("\n=== Vérifications ===")
    passeports = {l[0] for l in lignes}
    destinations = {l[1] for l in lignes}
    print(f"Lignes écrites           : {len(lignes)}")
    print(f"Lignes ignorées (-1)     : {ignorees}")
    print(f"Passeports distincts     : {len(passeports)}")
    print(f"Destinations distinctes  : {len(destinations)}")
    attendu = len(passeports) * (len(passeports) - 1)
    print(f"Attendu (n x (n-1))      : {attendu}  -> {'OK' if len(lignes) == attendu else 'ÉCART, à examiner'}")

    print("\nRépartition des statuts :")
    for statut, nombre in Counter(l[2] for l in lignes).most_common():
        print(f"  {statut:<14} {nombre}")

    print("\nContrôle de bon sens (à comparer avec ce que tu sais) :")
    index = {(l[0], l[1]): l for l in lignes}
    for paire in [("FRA", "JPN"), ("FRA", "BRA"), ("JPN", "USA"), ("IND", "FRA")]:
        l = index.get(paire)
        print(f"  {paire[0]} -> {paire[1]} : {l[2] + (f' ({l[3]} j)' if l[3] else '') if l else 'ABSENT'}")

    if inconnues:
        print(f"\n⚠️  {len(inconnues)} valeur(s) inconnue(s) non converties, par exemple :")
        for message in inconnues[:5]:
            print("  -", message)
        print("Ajoute-les au dictionnaire STATUTS puis relance le script.")


# --- Programme principal ------------------------------------------------------

def main():
    print(f"1. Téléchargement de {URL_SOURCE}")
    texte = telecharger(URL_SOURCE)
    DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
    FICHIER_BRUT.write_text(texte, encoding="utf-8")
    print(f"   Copie brute enregistrée : {FICHIER_BRUT.relative_to(RACINE)}")

    date_maj = date_derniere_maj()
    if date_maj:
        print(f"   Dernière mise à jour de la source : {date_maj}")

    print("2. Conversion")
    lignes, inconnues, ignorees = convertir(texte)
    lignes.sort(key=lambda l: (l[0], l[1]))

    print("3. Corrections manuelles")
    corrections = lire_corrections()
    if corrections:
        appliquer_corrections(lignes, corrections)

    FICHIER_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            ["passeport_iso3", "destination_iso3", "statut", "jours", "date_verification"]
        )
        ecrivain.writerows(lignes)
    print(f"\n   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)}")

    verifier(lignes, inconnues, ignorees)
    print(f"Lignes vérifiées à la main : {sum(1 for l in lignes if l[4])}")


if __name__ == "__main__":
    main()
