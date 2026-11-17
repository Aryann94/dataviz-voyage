"""
build_visas_historique.py
-------------------------
Historique des visas 2019-2026 : 56 versions du jeu de données Passport Index archivées
dans l'historique Git d'ilyankou/passport-index-dataset (17/04/2019 au 12/01/2025),
plus la version 2026 du projet (data/visas.csv : imorte du 18/02/2026 + corrections
France Diplomatie). 57 versions en tout, 199 passeports, 39 402 paires chacune.

Le jeu de données a changé quatre fois de format, avec deux pièges :
  - en 2019, les codes 1 et 2 changent de sens entre le format « Value » et le format
    « Code » (visa à l'arrivée et eTA inversés) ;
  - de février à mai 2020, les étiquettes VOA et ETA sont inversées DANS LES DONNÉES
    (France -> États-Unis vaut « VOA », France -> Népal « ETA »). Corrigé ici, et vérifié
    par des tests de bon sens bloquants sur chaque version.

Sorties :
  data/visas_historique_comptes.csv   passeport x version : nombre de pays par statut (courbe)
  data/visas_historique.json          8 photos annuelles pour le curseur du globe
  data/visas_historique_annuel.csv    les 8 photos en format long (téléchargement, ~7 Mo)
  data/visas_historique_sources.csv   une ligne par version : commit, format, empreinte

Python, bibliothèque standard ; git doit être installé (lecture des versions).
Lancement depuis la racine :
    py scripts/build_visas_historique.py
"""

import csv
import datetime
import hashlib
import io
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

from build_visas import STATUTS as STATUTS_TEXTE     # vocabulaire du format récent

# --- Configuration -----------------------------------------------------------

DEPOT = "https://github.com/ilyankou/passport-index-dataset.git"
COMMIT_FIGE = "e111423a6e7d39823dccfabf0c1801a725b82f6b"   # 18/02/2026, dépôt archivé
FICHIER = "passport-index-tidy-iso3.csv"

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_DEPOT = RACINE / "data" / "raw" / "passport_index_historique"   # non commité
FICHIER_2026 = RACINE / "data" / "visas.csv"                 # imorte + corrections
FICHIER_2026_BRUT = RACINE / "data" / "raw" / "passport-index-tidy-iso3.csv"   # imorte seul
DATE_2026 = "2026-02-18"
SORTIE_COMPTES = RACINE / "data" / "visas_historique_comptes.csv"
SORTIE_JSON = RACINE / "data" / "visas_historique.json"
SORTIE_ANNUEL = RACINE / "data" / "visas_historique_annuel.csv"
SORTIE_SOURCES = RACINE / "data" / "visas_historique_sources.csv"

# Au-delà de cet écart entre deux versions, la courbe ne relie pas les points (pointillés).
# Les versions sont mensuelles ; le plus grand écart « normal » est de 88 jours (2021).
TROU_JOURS = 100

# Statuts du projet, et leur lettre dans les matrices du JSON
LETTRES = {
    "sans_visa": "S", "visa_arrivee": "A", "eta": "T", "e_visa": "E",
    "visa_requis": "R", "covid_ban": "C", "interdit": "I",
}
STATUTS = list(LETTRES)

# Classes comparables sur toute la période (couleurs du globe en mode historique).
# L'eTA, l'e-visa et le visa requis sont regroupés : leur frontière change avec le format
# (pas d'e-visa avant 11/2020 ; eTA comptées avec les e-visas de 11/2020 à 12/2024).
CLASSE_HISTORIQUE = {
    "sans_visa": "sans_visa",
    "visa_arrivee": "visa_arrivee",
    "eta": "demarche", "e_visa": "demarche", "visa_requis": "demarche",
    "covid_ban": "entree_interdite", "interdit": "entree_interdite",
}
LIBELLES_CLASSES = {
    "sans_visa": "sans visa",
    "visa_arrivee": "visa à l'arrivée",
    "demarche": "démarche avant le départ (eTA, e-visa ou visa)",
    "entree_interdite": "entrée interdite",
}
# Raison affichée dans l'infobulle pour la classe « entrée interdite » : en 2026, les 48 cas
# ne sont pas le Covid (conflits, bans réciproques...). Sur le globe, cette classe a une
# couleur bien distincte du gris des territoires non couverts (« interdit » ≠ « pas de données »).
RAISONS = {"covid_ban": "restrictions Covid", "interdit": "entrée interdite par le pays"}

# --- Décodage des quatre formats ------------------------------------------------------

# 04/2019 à 09/2019, colonne « Value » (et un en-tête cassé « Passport,,0 » le 17/04/2019)
CODES_VALUE = {"3": "sans_visa", "2": "eta", "1": "visa_arrivee", "0": "visa_requis"}
# 10/2019 à 01/2020, colonne « Code » : 1 et 2 ont changé de sens
CODES_CODE = {"3": "sans_visa", "2": "visa_arrivee", "1": "eta", "0": "visa_requis"}
# 02/2020 à 05/2020, colonne « Code » en lettres : VOA et ETA inversés dans les données
CODES_LETTRES = {"VF": "sans_visa", "VOA": "eta", "ETA": "visa_arrivee", "VR": "visa_requis"}
# 11/2020 à 2025 (et imorte 2026) : texte
CODES_TEXTE = {**STATUTS_TEXTE,
               "covid ban": "covid_ban",
               "evw": "eta",                       # electronic visa waiver (Royaume-Uni)
               "hayya entry permit": "e_visa"}     # Qatar, Coupe du monde 2022

FORMATS = {
    "value_2019": "colonne Value, codes 0-3 (2 = eTA, 1 = visa à l'arrivée)",
    "code_2019": "colonne Code, codes 0-3 (2 = visa à l'arrivée, 1 = eTA)",
    "code_2020": "colonne Code, jours + VF/VOA/ETA/VR (VOA et ETA inversés dans les données)",
    "requirement": "colonne Requirement, jours + texte",
    "projet_2026": "data/visas.csv (imorte 18/02/2026 + corrections France Diplomatie)",
}


def detecter_format(entete, valeurs):
    if entete[0] != "Passport":
        sys.exit(f"En-tête inattendu : {entete}")
    if entete[2] in ("Value", "0"):
        return "value_2019"
    if entete[2] == "Requirement":
        return "requirement"
    if entete[2] == "Code":
        return "code_2020" if valeurs & set(CODES_LETTRES) else "code_2019"
    sys.exit(f"Format inconnu : {entete}")


def decoder(valeur, fmt):
    """Renvoie (statut, jours) ; (None, None) si passeport = destination."""
    v = valeur.strip()
    if v == "-1":
        return None, None
    if fmt == "value_2019":
        return CODES_VALUE[v], ""
    if fmt == "code_2019":
        return CODES_CODE[v], ""
    if v.isdigit():                                     # nombre de jours sans visa
        return "sans_visa", int(v)
    if fmt == "code_2020":
        return CODES_LETTRES[v], ""
    return CODES_TEXTE[v.lower()], ""


def lire_version(texte, date):
    lignes = list(csv.reader(io.StringIO(texte)))
    entete, donnees = lignes[0], lignes[1:]
    fmt = detecter_format(entete, {l[2] for l in donnees})
    paires = {}
    for p, d, v in donnees:
        try:
            statut, jours = decoder(v, fmt)
        except KeyError:
            sys.exit(f"{date} : valeur inconnue « {v} » ({p} -> {d}), format {fmt}")
        if statut is None:
            continue
        if (p, d) in paires:
            sys.exit(f"{date} : paire en double {p} -> {d}")
        paires[(p, d)] = (statut, jours)
    return fmt, paires


# --- Les versions ----------------------------------------------------------------------

def git(*args):
    return subprocess.run(["git", "-C", str(DOSSIER_DEPOT), *args],
                          capture_output=True, check=True).stdout


def preparer_depot():
    if not DOSSIER_DEPOT.exists():
        print(f"   clonage de {DEPOT}")
        subprocess.run(["git", "clone", "-q", DEPOT, str(DOSSIER_DEPOT)], check=True)
    git("checkout", "-q", COMMIT_FIGE)
    tete = git("rev-parse", "HEAD").decode().strip()
    if tete != COMMIT_FIGE:
        sys.exit(f"Le dépôt n'est pas au commit figé ({tete})")


def lister_versions():
    """Toutes les versions du fichier dans l'historique, de la plus ancienne à la plus récente."""
    sortie = git("log", "--reverse", "--format=%H %ad", "--date=short", COMMIT_FIGE, "--", FICHIER)
    versions = []
    for ligne in sortie.decode().splitlines():
        commit, date = ligne.split()
        lecture = subprocess.run(["git", "-C", str(DOSSIER_DEPOT), "show", f"{commit}:{FICHIER}"],
                                 capture_output=True)
        brut = lecture.stdout if lecture.returncode == 0 else b""
        if not brut.strip():                  # 28/10/2019 : fichier supprimé puis remis le même jour
            print(f"   {date} {commit[:7]} : fichier absent à ce commit, ignoré")
            continue
        versions.append({"date": date, "commit": commit, "source": "ilyankou",
                         "brut": brut})
    return versions


def lire_2026():
    with FICHIER_2026.open(encoding="utf-8", newline="") as f:
        paires = {(l["passeport_iso3"], l["destination_iso3"]):
                  (l["statut"], int(l["jours"]) if l["jours"] else "")
                  for l in csv.DictReader(f)}
    return paires


# --- Tests de bon sens (bloquants, sur chaque version) ---------------------------------------

TESTS = [
    # (passeport, destination, statuts admis, raison)
    ("FRA", "DEU", {"sans_visa"}, "libre circulation dans l'UE"),
    ("FRA", "USA", {"eta", "e_visa", "covid_ban"}, "ESTA : jamais visa à l'arrivée"),
    ("FRA", "CAN", {"eta", "e_visa", "covid_ban"}, "eTA canadienne"),
    # jamais eTA ni e-visa (détecte l'inversion VOA/ETA). Visa requis admis : fin 2021, à la
    # réouverture après le Covid, le Népal a d'abord exigé un visa préalable des Français et
    # des Allemands (pas des Britanniques ni des Américains) ; valeur brute « visa required ».
    ("FRA", "NPL", {"visa_arrivee", "covid_ban", "visa_requis"}, "jamais eTA au Népal"),
    ("IND", "NPL", {"sans_visa", "covid_ban"}, "libre circulation Inde-Népal"),
    ("CHN", "USA", {"visa_requis", "covid_ban", "interdit"}, "visa obligatoire"),
]


def tester(date, paires, codes):
    erreurs = []
    attendu = {(p, d) for p in codes for d in codes if p != d}
    if set(paires) != attendu:
        erreurs.append(f"{len(set(paires) ^ attendu)} paires manquantes ou en trop")
    for p, d, admis, raison in TESTS:
        statut = paires.get((p, d), ("absent",))[0]
        if statut not in admis:
            erreurs.append(f"{p} -> {d} = {statut} (attendu {'/'.join(sorted(admis))} : {raison})")
    return erreurs


# --- Comptes ---------------------------------------------------------------------------

def compter(paires, codes):
    comptes = {p: Counter() for p in codes}
    for (p, _), (statut, _) in paires.items():
        comptes[p][statut] += 1
    return comptes


def sans_demarche(c):
    """Définition unique du site : « pays sans démarche avant le départ »."""
    return c["sans_visa"] + c["visa_arrivee"]


# --- Rupture de source 2025 -> 2026 ----------------------------------------------------------

def analyser_rupture(v2025, imorte, finale, codes, rythme_mensuel):
    print("\n=== Rupture de source : ilyankou 12/01/2025 -> 2026 ===")
    print("  Vocabulaire : imorte reprend exactement les catégories d'ilyankou depuis le")
    print("  12/01/2025 (même site source, mêmes 199 codes, eta séparé des e-visas).")
    changes = [k for k in v2025 if v2025[k][0] != imorte[k][0]]
    mois = (datetime.date.fromisoformat(DATE_2026) - datetime.date(2025, 1, 12)).days / 30.44
    print(f"  Paires qui changent de statut en {mois:.1f} mois : {len(changes)} "
          f"({len(changes) / mois:.0f} par mois)")
    print(f"  Rythme habituel entre deux versions ilyankou (2023-2024, hors Covid) : "
          f"{rythme_mensuel:.0f} par mois")
    transitions = Counter((v2025[k][0], imorte[k][0]) for k in changes)
    print("  Transitions les plus fréquentes :")
    for (a, b), n in transitions.most_common(8):
        print(f"    {a:>12} -> {b:<12} {n:>5}")

    print("\n  Pays sans démarche avant le départ :")
    print(f"  {'passeport':<10}{'2025-01':>8}{'imorte':>8}{'2026':>7}   source/temps  corrections")
    for p in ("FRA", "USA", "GBR", "JPN", "IND", "CHN", "BRA", "NGA", "ZAF", "MAR"):
        a = sum(1 for d in codes if d != p and v2025[(p, d)][0] in ("sans_visa", "visa_arrivee"))
        b = sum(1 for d in codes if d != p and imorte[(p, d)][0] in ("sans_visa", "visa_arrivee"))
        c = sum(1 for d in codes if d != p and finale[(p, d)][0] in ("sans_visa", "visa_arrivee"))
        print(f"  {p:<10}{a:>8}{b:>8}{c:>7}   {b - a:>+12}  {c - b:>+11}")
    print("\n  France : paires qui changent entre 2025-01 et 2026 (imorte, avant corrections)")
    for k in sorted(changes):
        if k[0] == "FRA":
            print(f"    FRA -> {k[1]} : {v2025[k][0]} -> {imorte[k][0]}"
                  + (f" (corrigé : {finale[k][0]})" if finale[k][0] != imorte[k][0] else ""))
    corr = [k for k in imorte if imorte[k][0] != finale[k][0]]
    print(f"  Corrections France Diplomatie qui changent un statut : "
          f"{', '.join(f'{p}->{d} {imorte[(p, d)][0]}->{finale[(p, d)][0]}' for p, d in corr)}")


# --- Programme principal -------------------------------------------------------------

def main():
    print("1. Dépôt ilyankou au commit figé")
    preparer_depot()
    versions = lister_versions()
    print(f"   {len(versions)} versions lues dans l'historique Git")

    print("2. Décodage et tests de bon sens")
    with FICHIER_2026.open(encoding="utf-8", newline="") as f:
        codes = sorted({l["passeport_iso3"] for l in csv.DictReader(f)})
    echecs = []
    for v in versions:
        texte = v["brut"].decode("utf-8-sig").replace("\r", "")
        v["format"], v["paires"] = lire_version(texte, v["date"])
        v["empreinte"] = hashlib.sha256(v["brut"]).hexdigest()
        v["lignes"] = texte.count("\n")
        erreurs = tester(v["date"], v["paires"], codes)
        echecs += [f"{v['date']} ({v['format']}) : {e}" for e in erreurs]
    v2026 = {"date": DATE_2026, "commit": "", "source": "imorte + corrections",
             "format": "projet_2026", "paires": lire_2026(),
             "empreinte": hashlib.sha256(FICHIER_2026.read_bytes()).hexdigest(),
             "lignes": sum(1 for _ in FICHIER_2026.open(encoding="utf-8")) - 1}
    echecs += [f"{DATE_2026} : {e}" for e in tester(DATE_2026, v2026["paires"], codes)]
    versions.append(v2026)
    if echecs:
        sys.exit("Tests de bon sens échoués :\n  - " + "\n  - ".join(echecs))
    print(f"   {len(versions)} versions : {len(TESTS)} tests de bon sens et 39 402 paires "
          "vérifiés sur chacune")

    # --- Photos annuelles : la première version de chaque année ---
    photos = {}
    for v in versions:
        photos.setdefault(int(v["date"][:4]), v)
    for v in versions:
        v["photo"] = photos[int(v["date"][:4])] is v

    # --- Comptes par passeport et par version ---
    lignes_comptes, precedente = [], None
    for v in versions:
        ecart = ((datetime.date.fromisoformat(v["date"]) -
                  datetime.date.fromisoformat(precedente)).days if precedente else "")
        trou = bool(ecart) and ecart > TROU_JOURS
        v["ecart"], v["trou"] = ecart, trou
        precedente = v["date"]
        comptes = compter(v["paires"], codes)
        v["comptes"] = comptes
        for p in codes:
            c = comptes[p]
            lignes_comptes.append({
                "passeport_iso3": p, "date": v["date"], "source": v["source"],
                "format": v["format"],
                **{s: c[s] for s in STATUTS},
                "sans_demarche": sans_demarche(c),
                "demarche": c["eta"] + c["e_visa"] + c["visa_requis"],
                "entree_interdite": c["covid_ban"] + c["interdit"],
                "total": sum(c.values()),
                "ecart_jours": ecart, "trou_avant": "true" if trou else "false",
            })
    with SORTIE_COMPTES.open("w", encoding="utf-8", newline="") as f:
        e = csv.DictWriter(f, fieldnames=list(lignes_comptes[0]))
        e.writeheader()
        e.writerows(lignes_comptes)

    # --- JSON des photos annuelles (globe) ---
    index = {c: i for i, c in enumerate(codes)}
    photos_json = []
    for annee, v in sorted(photos.items()):
        matrice = []
        for p in codes:
            for d in codes:
                matrice.append("-" if p == d else LETTRES[v["paires"][(p, d)][0]])
        photos_json.append({
            "annee": annee, "date": v["date"], "source": v["source"],
            "commit": v["commit"][:7], "format": v["format"],
            # détail eTA / e-visa / visa requis fiable seulement pour 2026 : avant, les
            # frontières entre ces catégories changent avec le format de la source
            "detail_fiable": v["format"] == "projet_2026",
            "matrice": "".join(matrice),
        })
    contenu = {
        "description": "Statut d'entrée par passeport (ligne) et destination (colonne), "
                       "une photo par année. matrice[i * n + j] = passeport codes[i] vers "
                       "destination codes[j] ; « - » = même pays.",
        "codes": codes,
        "statuts": {l: {"statut": s, "classe_historique": CLASSE_HISTORIQUE[s],
                        **({"raison": RAISONS[s]} if s in RAISONS else {})}
                    for s, l in LETTRES.items()},
        "classes_historiques": LIBELLES_CLASSES,
        "sans_demarche": ["sans_visa", "visa_arrivee"],
        "photos": photos_json,
    }
    SORTIE_JSON.write_text(json.dumps(contenu, ensure_ascii=False, separators=(",", ":")),
                           encoding="utf-8")
    assert all(len(ph["matrice"]) == len(codes) ** 2 for ph in photos_json)
    assert all(ph["matrice"][index[c] * len(codes) + index[c]] == "-"
               for ph in photos_json for c in codes)

    # --- CSV long des photos annuelles (téléchargement, pas chargé par le site) ---
    # Colonnes réduites au minimum (~8 Mo au lieu de 14) : la date exacte de chaque photo est
    # dans visas_historique_sources.csv (photo_annuelle = true), la classe historique se
    # déduit du statut (dictionnaire des données).
    with SORTIE_ANNUEL.open("w", encoding="utf-8", newline="") as f:
        e = csv.writer(f)
        e.writerow(["passeport_iso3", "destination_iso3", "annee", "statut", "jours"])
        for annee, v in sorted(photos.items()):
            for (p, d), (statut, jours) in sorted(v["paires"].items()):
                e.writerow([p, d, annee, statut, jours])

    # --- Sources ---
    with SORTIE_SOURCES.open("w", encoding="utf-8", newline="") as f:
        e = csv.writer(f)
        e.writerow(["date", "source", "commit", "format", "description_format",
                    "sha256", "lignes", "photo_annuelle", "ecart_jours", "trou_avant"])
        for v in versions:
            e.writerow([v["date"], v["source"], v["commit"], v["format"], FORMATS[v["format"]],
                        v["empreinte"], v["lignes"], "true" if v["photo"] else "false",
                        v["ecart"], "true" if v["trou"] else "false"])

    # --- Rapport ---
    print("\n=== Versions ===")
    print(f"  {'date':<11}{'format':<13}{'FRA sans démarche':>18}{'dont sans visa':>15}"
          f"{'covid':>7}  {'photo':<6}{'trou'}")
    for v in versions:
        c = v["comptes"]["FRA"]
        photo = "oui" if v["photo"] else ""
        trou = f"oui ({v['ecart']} j)" if v["trou"] else ""
        print(f"  {v['date']:<11}{v['format']:<13}{sans_demarche(c):>18}{c['sans_visa']:>15}"
              f"{c['covid_ban']:>7}  {photo:<6}{trou}")

    print("\n=== Photos annuelles (curseur du globe) ===")
    for annee, v in sorted(photos.items()):
        total = Counter(CLASSE_HISTORIQUE[s] for s, _ in v["paires"].values())
        print(f"  {annee} : {v['date']}  " + "  ".join(f"{k} {total[k]}" for k in LIBELLES_CLASSES))

    # rythme habituel de changement (versions ilyankou de 2023-2024, hors Covid)
    rythmes = []
    ily = [v for v in versions if v["source"] == "ilyankou"]
    for a, b in zip(ily, ily[1:]):
        if a["date"] >= "2023-04-06" and b["date"] <= "2025-01-02":
            mois = (datetime.date.fromisoformat(b["date"]) -
                    datetime.date.fromisoformat(a["date"])).days / 30.44
            n = sum(1 for k in a["paires"] if a["paires"][k][0] != b["paires"][k][0])
            rythmes.append(n / mois)
    with FICHIER_2026_BRUT.open(encoding="utf-8-sig", newline="") as f:
        _, imorte = lire_version(f.read().replace("\r", ""), "imorte")
    analyser_rupture(ily[-1]["paires"], imorte, v2026["paires"], codes,
                     sum(rythmes) / len(rythmes))

    print("\n=== Fichiers ===")
    for chemin in (SORTIE_COMPTES, SORTIE_JSON, SORTIE_ANNUEL, SORTIE_SOURCES):
        print(f"  {chemin.relative_to(RACINE)} : {chemin.stat().st_size / 1024:,.0f} Ko"
              .replace(",", " "))


if __name__ == "__main__":
    main()
