"""
test_quiz.py
------------
Contrôle le quiz (data/quiz_questions.json) et écrit data/quiz_simulation.json, que la page lit
pour afficher ses limites. Le fichier n'est pas écrit si un contrôle échoue.

Contrôles bloquants :
  - chaque question ne promet que ce que les six critères mesurent : aucun mot interdit, et
    chaque effet d'une réponse est annoncé dans le texte de cette réponse (champ « dit ») ;
  - tous les parcours possibles, chaque réponse ayant la même probabilité : aucun pays ne gagne
    plus de 12 % des parties, et au moins 38 pays sur 41 peuvent entrer dans un top 3 ;
  - le moteur JavaScript du site (quiz-moteur.js, lancé avec Node) donne exactement les mêmes
    résultats que ce calcul Python, sur tous les parcours ;
  - les phrases « Le saviez-vous ? » annoncent le bon rang et les bonnes égalités.

Lancement depuis la racine :
    py scripts/test_quiz.py
"""

import csv
import datetime
import hashlib
import json
import math
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data"
FICHIER_QUESTIONS = DONNEES / "quiz_questions.json"
SORTIE = DONNEES / "quiz_simulation.json"

CRITERES = ["culture", "nature", "villes", "prix", "distance", "mer"]
POIDS_PLEIN = 1.5
PAYS_DE_TETE = 8
PART_MAX = 0.12
TOP3_MIN = 38
QUESTIONS_BANQUE = 15
# Ce que les données ne mesurent pas : le texte des questions ne doit pas le promettre.
MOTS_INTERDITS = r"\b(langues?|traducteur|plages?|sable|montagnes?|sommets?|cuisine|restaurants?|table|plats?|faune|animal|animaux|safari|réseau|climat|pull|vol|vols|avion|heures?|hôtels?|auberges?|festival|fêtes?|ambiance)\b"


def lire_csv(nom):
    with (DONNEES / nom).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def controler_questions(banque):
    erreurs = []
    questions = banque["questions"]
    if len(questions) != QUESTIONS_BANQUE:
        erreurs.append(f"{len(questions)} questions au lieu de {QUESTIONS_BANQUE}")
    if len({q["id"] for q in questions}) != len(questions):
        erreurs.append("identifiants de questions en double")
    for q in questions:
        textes = [q["theme"], q["question"]]
        if not 2 <= len(q["options"]) <= 3:
            erreurs.append(f"{q['id']} : 2 ou 3 réponses attendues")
        for o in q["options"]:
            texte = f"{o['titre']} {o['detail']}".lower()
            textes.append(texte)
            if not o["effets"]:
                erreurs.append(f"{q['id']} : réponse sans effet")
            for e in o["effets"]:
                if e["critere"] not in CRITERES or not 0 <= e["valeur"] <= 100 or e["poids"] <= 0:
                    erreurs.append(f"{q['id']} : effet invalide {e}")
                if e["dit"].lower() not in texte:
                    erreurs.append(f"{q['id']} : l'effet sur {e['critere']} n'est pas annoncé (« {e['dit']} »)")
        for t in textes:
            m = re.search(MOTS_INTERDITS, t, re.I)
            if m:
                erreurs.append(f"{q['id']} : « {m.group()} » promet une chose non mesurée")
    return erreurs


def classer(pays, somme, poids):
    valeurs = [s / w if w else 50 for s, w in zip(somme, poids)]
    imp = [min(1, w / POIDS_PLEIN) * abs(v - 50) / 50 for v, w in zip(valeurs, poids)]
    total = 0
    for i in imp:
        total += i
    maximum = total * 1e4
    lignes = []
    for iso3, notes in pays:
        if not maximum:
            lignes.append((0, iso3, notes))
            continue
        ecart = 0
        for i, v, n in zip(imp, valeurs, notes):
            ecart += i * (v - n) ** 2
        lignes.append((100 * (1 - math.sqrt(ecart / maximum)), iso3, notes))
    lignes.sort(key=lambda l: (-l[0], l[1]))
    return lignes


def prochaine(questions, restantes, classement, poids):
    tete = classement[:PAYS_DE_TETE]
    ecarts = []
    for a in range(len(CRITERES)):
        moyenne = 0
        for l in tete:
            moyenne += l[2][a]
        moyenne /= len(tete)
        somme = 0
        for l in tete:
            somme += (l[2][a] - moyenne) ** 2
        ecarts.append(math.sqrt(somme / len(tete)))
    meilleure, record = -1, -math.inf
    for q in sorted(restantes):
        note = 0
        for o in questions[q]:
            for a, _, w in o:
                note += w * ecarts[a] * (1 - min(1, poids[a] / POIDS_PLEIN))
        note /= len(questions[q])
        if note > record:
            meilleure, record = q, note
    return meilleure


def simuler(banque, pays):
    questions = [[[(CRITERES.index(e["critere"]), e["valeur"], e["poids"]) for e in o["effets"]]
                  for o in q["options"]] for q in banque["questions"]]
    nombre = banque["nombre_questions"]
    gagne, top3, dernier = defaultdict(float), defaultdict(float), defaultdict(float)
    empreinte = hashlib.sha256()
    compte = [0]

    def suivre(restantes, somme, poids, proba, chemin):
        classement = classer(pays, somme, poids)
        if len(chemin) == nombre:
            compte[0] += 1
            gagne[classement[0][1]] += proba
            dernier[classement[-1][1]] += proba
            for l in classement[:3]:
                top3[l[1]] += proba
            ligne = f"{'-'.join(chemin)}:{','.join(l[1] for l in classement[:3])}:{classement[-1][1]}\n"
            empreinte.update(ligne.encode())
            return
        q = prochaine(questions, restantes, classement, poids)
        for i, option in enumerate(questions[q]):
            s2, p2 = somme[:], poids[:]
            for a, v, w in option:
                s2[a] += v * w
                p2[a] += w
            suivre(restantes - {q}, s2, p2, proba / len(questions[q]), chemin + [f"{q}.{i}"])

    suivre(frozenset(range(len(questions))), [0] * 6, [0] * 6, 1.0, [])
    return gagne, top3, dernier, compte[0], empreinte.hexdigest()


def rang(valeurs, iso3, sens):
    moi = valeurs[iso3]
    return (sum(1 for v in valeurs.values() if sens * (v - moi) > 0) + 1,
            sum(1 for v in valeurs.values() if v == moi))


def controler_faits(faits_js):
    pays = lire_csv("pays.csv")
    scores = {l["iso3"]: float(l["distance_paris_km"]) for l in lire_csv("scores.csv")}
    premieres = {}
    for l in lire_csv("unesco_sites.csv"):
        premieres[l["iso3"]] = min(premieres.get(l["iso3"], 9999), int(l["annee_inscription"]))
    colonnes = {c: {p["iso3"]: float(p[c]) for p in pays}
                for c in ("niveau_prix", "unesco_total", "foret_pct", "densite_hab_km2", "cotes_km",
                          "pop_villes_1m_pct", "zones_protegees_pct")}
    colonnes["distance_paris_km"] = scores
    colonnes["premiere_inscription"] = {k: float(v) for k, v in premieres.items()}
    erreurs, nombre = [], 0
    sans_mer = sum(p["sans_littoral"] == "true" for p in pays)
    for iso3, faits in faits_js.items():
        for f in faits:
            nombre += 1
            if f["cle"] == "sans_littoral":
                attendu = (sans_mer, sans_mer)
            else:
                attendu = rang(colonnes[f["cle"]], iso3, f["sens"])
            if (f["rang"], f["egaux"]) != attendu:
                erreurs.append(f"{iso3} {f['cle']} : {f['rang']}/{f['egaux']} au lieu de {attendu}")
    return erreurs, nombre


def main():
    banque = json.loads(FICHIER_QUESTIONS.read_text(encoding="utf-8"))
    erreurs = controler_questions(banque)
    if erreurs:
        sys.exit("Questions refusées :\n  - " + "\n  - ".join(erreurs))
    lignes = lire_csv("scores.csv")
    noms = {p["iso3"]: p["nom_fr"] for p in lire_csv("pays.csv")}
    pays = [(l["iso3"], [float(l[f"score_{c}"]) for c in CRITERES]) for l in lignes]
    gagne, top3, dernier, parcours, empreinte = simuler(banque, pays)
    tri = sorted(gagne.items(), key=lambda x: -x[1])
    jamais_top3 = sorted((i for i, _ in pays if top3[i] == 0), key=lambda i: noms[i])
    print(f"{parcours} parcours, {len(gagne)} pays peuvent gagner, {len(pays) - len(jamais_top3)}/41 dans un top 3")
    print("les plus fréquents : " + ", ".join(f"{noms[i]} {100 * v:.1f} %" for i, v in tri[:6]))
    print("jamais dans un top 3 : " + (", ".join(noms[i] for i in jamais_top3) or "aucun"))
    print("jamais gagnants : " + ", ".join(noms[i] for i, _ in pays if i not in gagne))

    if tri[0][1] > PART_MAX:
        erreurs.append(f"{noms[tri[0][0]]} gagne {100 * tri[0][1]:.1f} % des parties (maximum 12 %)")
    if len(pays) - len(jamais_top3) < TOP3_MIN:
        erreurs.append(f"{len(pays) - len(jamais_top3)} pays dans un top 3 (minimum {TOP3_MIN})")

    sortie = subprocess.run(["node", str(RACINE / "scripts" / "test_quiz.mjs")], capture_output=True,
                            text=True, encoding="utf-8", cwd=RACINE)
    if sortie.returncode:
        sys.exit(f"Le moteur JavaScript a échoué :\n{sortie.stderr}")
    js = json.loads(sortie.stdout)
    if js["parcours"] != parcours or js["empreinte"] != empreinte:
        erreurs.append("le moteur JavaScript et le calcul Python ne donnent pas les mêmes résultats")
    if js["parcours_relu"] != banque["nombre_questions"] or not js["parcours_faux_refuse"]:
        erreurs.append("la lecture d'un parcours partagé ne fonctionne pas")
    erreurs_faits, nb_faits = controler_faits(js["faits"])
    erreurs += erreurs_faits
    if erreurs:
        sys.exit("Contrôles échoués, rien n'a été écrit :\n  - " + "\n  - ".join(erreurs[:30]))

    SORTIE.write_text(json.dumps({
        "date": datetime.date.today().isoformat(), "parcours": parcours,
        "hypothese": "chaque réponse a la même probabilité",
        "part_max_pct": round(100 * tri[0][1], 1), "pays_le_plus_frequent": noms[tri[0][0]],
        "pays_gagnants": len(gagne), "pays_top3": len(pays) - len(jamais_top3),
        "jamais_top3": [noms[i] for i in jamais_top3],
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"OK : moteur JavaScript identique, {nb_faits} faits contrôlés, {SORTIE.name} écrit.")


if __name__ == "__main__":
    main()
