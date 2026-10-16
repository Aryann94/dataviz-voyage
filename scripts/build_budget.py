"""
build_budget.py
---------------
Vérifie la saisie manuelle data/saisie_budget.csv (relevé sur Budget Your Trip)
et la convertit en data/budget.csv, au format « long » utilisé par le site :

    iso3,niveau,categorie,montant_usd_jour,total_site_usd,source_url,date_releve

Correspondance des niveaux du site : Budget -> petit, Mid-Range -> moyen, Luxury -> confort
Catégories relevées : Accommodation -> hebergement, Local Transportation -> transport,
                      Food -> repas, Entertainment -> activites
(Alcohol est ignoré : le site ne donne qu'une fourchette.)

La saisie peut se faire petit à petit : les lignes encore vides sont ignorées.
Accepte les fichiers enregistrés par Excel en français (séparateur « ; », virgule décimale).

Aucun appel réseau. Lancement depuis la racine du projet :
    python scripts/build_budget.py
"""

import csv
import datetime
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHIER_SAISIE = RACINE / "data" / "saisie_budget.csv"
FICHIER_LISTE = RACINE / "data" / "pays_liste.csv"
FICHIER_SORTIE = RACINE / "data" / "budget.csv"

NIVEAUX = ["petit", "moyen", "confort"]
CATEGORIES = ["hebergement", "transport", "repas", "activites"]
ECART_MAX = 0.15           # écart toléré entre la somme des catégories et le total du site
SOURCE = "Budget Your Trip"

# Pays dont les données du site sont jugées non fiables : exclus de budget.csv (donc de la
# visualisation 3), mais toujours présents dans le quiz (qui utilise l'indice des prix).
# Pour réintégrer un pays, supprime simplement sa ligne.
EXCLUSIONS = {
    "ARG": "Repas (5,71 $/jour) et transport (2,86 $/jour) en niveau moyen invraisemblables, "
           "environ 7 fois sous la valeur attendue pour le niveau des prix ; prix en pesos "
           "probablement non actualisés depuis la forte inflation (vérifié sur la page le 2026-10-16)",
}

erreurs = []
avertissements = []


def lire_saisie():
    if not FICHIER_SAISIE.exists():
        sys.exit(f"Fichier manquant : {FICHIER_SAISIE.relative_to(RACINE)}")
    brut = FICHIER_SAISIE.read_bytes()
    try:
        texte = brut.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = brut.decode("cp1252")   # Excel Windows sans « CSV UTF-8 »
        avertissements.append("Fichier non enregistré en UTF-8 (accents peut-être abîmés) : "
                              "dans Excel, choisis « CSV UTF-8 » à l'enregistrement")
    premiere_ligne = texte.splitlines()[0] if texte else ""
    separateur = ";" if premiere_ligne.count(";") > premiere_ligne.count(",") else ","
    return list(csv.DictReader(io.StringIO(texte), delimiter=separateur))


def nombre(valeur, contexte):
    """'6,52' ou '6.52' ou '$6.52' -> 6.52 ; '' -> None ; erreur si illisible."""
    v = (valeur or "").strip().replace("$", "").replace(" ", "").replace(" ", "")
    if not v:
        return None
    v = v.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d+)?", v):
        erreurs.append(f"{contexte} : '{valeur}' n'est pas un montant valide")
        return None
    return float(v)


def date_valide(valeur):
    try:
        datetime.date.fromisoformat(valeur)
        return True
    except ValueError:
        return False


def main():
    with FICHIER_LISTE.open(encoding="utf-8", newline="") as f:
        codes = [l["iso3"].strip() for l in csv.DictReader(f)]
    saisie = lire_saisie()
    print(f"1. {len(saisie)} lignes lues dans {FICHIER_SAISIE.name}")

    colonnes_attendues = {"iso3", "niveau", "total_site", "url", "date_releve", *CATEGORIES}
    manquantes = colonnes_attendues - set(saisie[0].keys() if saisie else [])
    if manquantes:
        sys.exit(f"Colonnes manquantes dans {FICHIER_SAISIE.name} : {sorted(manquantes)}\n"
                 "As-tu supprimé ou renommé une colonne ?")

    print("2. Vérification")
    sortie, remplis, vus = [], defaultdict(dict), set()
    for numero, l in enumerate(saisie, start=2):
        iso3, niveau = (l["iso3"] or "").strip(), (l["niveau"] or "").strip()
        contexte = f"ligne {numero} ({iso3} {niveau})"
        if iso3 not in codes:
            erreurs.append(f"{contexte} : code pays inconnu")
            continue
        if niveau not in NIVEAUX:
            erreurs.append(f"{contexte} : niveau '{niveau}' (attendu : {NIVEAUX})")
            continue
        if (iso3, niveau) in vus:
            erreurs.append(f"{contexte} : ligne en double")
        vus.add((iso3, niveau))

        montants = {c: nombre(l[c], f"{contexte} {c}") for c in CATEGORIES}
        total = nombre(l["total_site"], f"{contexte} total_site")
        if all(v is None for v in montants.values()) and total is None:
            continue                                      # ligne pas encore saisie

        # ligne commencée : elle doit être complète
        vides = [c for c, v in montants.items() if v is None]
        if vides:
            erreurs.append(f"{contexte} : montants manquants {vides}")
            continue
        # total_site est facultatif : quand il est présent, il sert à détecter les fautes de frappe
        url, date = (l["url"] or "").strip(), (l["date_releve"] or "").strip()
        if not url.startswith("https://www.budgetyourtrip.com/"):
            erreurs.append(f"{contexte} : url manquante ou qui n'est pas une page Budget Your Trip")
        if not date_valide(date):
            erreurs.append(f"{contexte} : date_releve '{date}' (format attendu : 2026-10-20)")

        somme = sum(montants.values())
        if total and abs(somme - total) / total > ECART_MAX:
            avertissements.append(
                f"{contexte} : somme des catégories {somme:.0f} $ contre {total:.0f} $ affichés "
                f"(écart {abs(somme - total) / total:.0%}) -> faute de frappe ?")

        maj_site = (l.get("date_maj_site") or "").strip()   # colonne facultative
        if maj_site and not date_valide(maj_site):
            erreurs.append(f"{contexte} : date_maj_site '{maj_site}' (format attendu : 2026-08-26)")

        remplis[iso3][niveau] = somme
        for c in CATEGORIES:
            sortie.append({"iso3": iso3, "niveau": niveau, "categorie": c,
                           "montant_usd_jour": montants[c],
                           "total_site_usd": total if total is not None else "",
                           "source_url": url, "date_releve": date, "date_maj_site": maj_site})

    # cohérence entre niveaux d'un même pays : petit < moyen < confort
    for iso3, niveaux in remplis.items():
        presents = [n for n in NIVEAUX if n in niveaux]
        for a, b in zip(presents, presents[1:]):
            if niveaux[a] >= niveaux[b]:
                avertissements.append(f"{iso3} : le niveau {a} ({niveaux[a]:.0f} $) n'est pas "
                                      f"moins cher que {b} ({niveaux[b]:.0f} $) -> lignes inversées ?")

    if erreurs:
        sys.exit(f"\n{len(erreurs)} erreur(s), budget.csv n'a PAS été écrit :\n  - "
                 + "\n  - ".join(erreurs))

    exclus = sorted({l["iso3"] for l in sortie if l["iso3"] in EXCLUSIONS})
    sortie = [l for l in sortie if l["iso3"] not in EXCLUSIONS]
    for iso3 in exclus:
        remplis.pop(iso3, None)
        print(f"   Exclu volontairement : {iso3} — {EXCLUSIONS[iso3]}")

    with FICHIER_SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=["iso3", "niveau", "categorie", "montant_usd_jour",
                                                 "total_site_usd", "source_url", "date_releve",
                                                 "date_maj_site"])
        ecrivain.writeheader()
        ecrivain.writerows(sortie)
    print(f"   Fichier écrit : {FICHIER_SORTIE.relative_to(RACINE)} ({len(sortie)} lignes)")

    # --- Avancement ---
    print("\n=== Avancement de la saisie ===")
    complets = [c for c in codes if all(n in remplis.get(c, {}) for n in NIVEAUX)]
    avec_moyen = [c for c in codes if "moyen" in remplis.get(c, {})]
    print(f"Pays avec les 3 niveaux   : {len(complets)}/{len(codes)}")
    print(f"Pays avec le niveau moyen : {len(avec_moyen)}/{len(codes)} (minimum pour le quiz)")
    reste = [c for c in codes if c not in avec_moyen]
    if reste:
        print(f"Pas encore saisis         : {', '.join(reste)}")

    print(f"\n=== À vérifier ({len(avertissements)}) ===")
    for a in avertissements:
        print("  -", a)
    if not avertissements:
        print("  rien à signaler")


if __name__ == "__main__":
    main()
