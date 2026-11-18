"""
test_quiz.py
------------
Contrôle le quiz (data/quiz_questions.json) et écrit data/quiz_simulation.json, que la page lit
pour afficher ses limites. Le fichier n'est pas écrit si un contrôle échoue.

Contrôles bloquants :
  - une réponse peut évoquer une situation (un plat de rue, le bruit des vagues), mais ne promet
    aucun résultat que les données ne mesurent pas (langue, faune, sable, gastronomie…) ;
  - 15 angles différents, sans phrase sous les choix, et aucun texte répété ;
  - chaque effet d'une réponse a sa raison, écrite en une phrase et affichée sur le résultat ;
  - les textes du quiz respectent le style de CLAUDE.md (mots et tournures interdits) ;
  - au plus 3 questions par critère principal, et au plus 2 duels villes contre nature ;
  - tous les parcours possibles, chaque réponse ayant la même probabilité : aucun pays ne gagne
    plus de 12 % des parties, au moins 38 pays sur 41 peuvent entrer dans un top 3, et deux
    questions de suite n'ont jamais le même critère principal ;
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
MAX_PAR_PRINCIPAL = 3
MAX_DUELS_VILLES_NATURE = 2
# Résultats que les données ne mesurent pas : une réponse ne doit pas les promettre.
# Les images d'une situation (un plat de rue, un vol court) restent autorisées.
PROMESSES_INTERDITES = r"\b(langues?|traducteurs?|interprètes?|faune|animal|animaux|safari|sable|gastronomi\w*|sp[ée]cialit[ée]s?|meilleure? (cuisine|table|plage))\b"
# Style de CLAUDE.md, contrôlé sur les fichiers qui portent les textes du quiz.
FICHIERS_STYLE = ["data/quiz_questions.json", "quiz.js", "quiz-moteur.js", "destinations.html"]
STYLE_INTERDIT = (
    r"—|\b(plong\w+|tirer parti|optimis\w+|révolution\w*|libérer le potentiel|transcend\w+|réinvent\w+|"
    r"navigu\w+|rationalis\w+|sublim\w+|crucial\w*|incontournable\w*|fluide\w*|transformateur\w*|"
    r"à la pointe|nuancé\w*|aux multiples facettes|robuste\w*|vertigineu\w+|il est important de noter|"
    r"en conclusion|joue un rôle central|ouvrir la voie à|au final|en résumé|cela m'a permis de|"
    r"il convient de souligner|ce n'est pas .{1,60}, c'est|non seulement)\b"
    r"|(?:^|[.!?«\"'`]\s*)(par ailleurs|de plus|ainsi|néanmoins|en outre)\b"
)


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
    if len({q["angle"] for q in questions}) != len(questions):
        erreurs.append("deux questions ont le même angle")
    tous_textes = [q["question"] for q in questions] + [o["titre"] for q in questions for o in q["options"]]
    if len({t.lower() for t in tous_textes}) != len(tous_textes):
        erreurs.append("un texte de question ou de réponse est répété")
    par_principal, duels_villes_nature = defaultdict(list), []
    for q in questions:
        textes = [q["theme"], q["question"]]
        par_principal[q["principal"]].append(q["id"])
        if q["principal"] not in CRITERES:
            erreurs.append(f"{q['id']} : critère principal inconnu")
        if not 2 <= len(q["options"]) <= 3:
            erreurs.append(f"{q['id']} : 2 ou 3 réponses attendues")
        poids_question, tetes = defaultdict(float), set()
        for o in q["options"]:
            textes.append(o["titre"])
            if "detail" in o:
                erreurs.append(f"{q['id']} : pas de phrase sous les choix")
            if not o["effets"]:
                erreurs.append(f"{q['id']} : réponse sans effet")
                continue
            for e in o["effets"]:
                if e["critere"] not in CRITERES or not 0 <= e["valeur"] <= 100 or e["poids"] <= 0:
                    erreurs.append(f"{q['id']} : effet invalide {e}")
                raison = e.get("raison", "").strip()
                if not raison.endswith(".") or raison.count(".") != 1:
                    erreurs.append(f"{q['id']} : l'effet sur {e['critere']} doit s'expliquer en une phrase")
                textes.append(raison)
                poids_question[e["critere"]] += e["poids"]
            tetes.add(max(o["effets"], key=lambda e: e["poids"])["critere"])
        if poids_question and poids_question[q["principal"]] < max(poids_question.values()) - 1e-9:
            erreurs.append(f"{q['id']} : {q['principal']} n'est pas le critère le plus pesant")
        if tetes == {"villes", "nature"}:
            duels_villes_nature.append(q["id"])
        for t in textes:
            m = re.search(PROMESSES_INTERDITES, t, re.I)
            if m:
                erreurs.append(f"{q['id']} : « {m.group()} » promet un résultat non mesuré")
    for critere, ids in par_principal.items():
        if len(ids) > MAX_PAR_PRINCIPAL:
            erreurs.append(f"{critere} : {len(ids)} questions principales (maximum {MAX_PAR_PRINCIPAL})")
    if len(duels_villes_nature) > MAX_DUELS_VILLES_NATURE:
        erreurs.append(f"trop de duels villes contre nature : {duels_villes_nature}")
    for nom in FICHIERS_STYLE:
        for n, ligne in enumerate((RACINE / nom).read_text(encoding="utf-8").splitlines(), 1):
            m = re.search(STYLE_INTERDIT, ligne, re.I)
            if m:
                erreurs.append(f"{nom}, ligne {n} : style interdit (« {m.group().strip()} »)")
    photos = {(l["question"], int(l["option"])) for l in lire_csv("quiz_photos.csv")}
    duels = {(q["id"], i) for q in questions if q["type"] == "duel" for i in range(len(q["options"]))}
    if photos != duels:
        erreurs.append(f"photos et duels ne correspondent pas : {sorted(photos ^ duels)}")
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


def prochaine(questions, principaux, restantes, classement, poids, precedent):
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
        if principaux[q] == precedent:
            continue
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
    principaux = [q["principal"] for q in banque["questions"]]
    nombre = banque["nombre_questions"]
    gagne, top3, dernier = defaultdict(float), defaultdict(float), defaultdict(float)
    empreinte = hashlib.sha256()
    compte = [0]

    def suivre(restantes, somme, poids, proba, chemin, precedent):
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
        q = prochaine(questions, principaux, restantes, classement, poids, precedent)
        if q < 0 or principaux[q] == precedent:
            sys.exit(f"Parcours sans question possible : {'-'.join(chemin)}")
        for i, option in enumerate(questions[q]):
            s2, p2 = somme[:], poids[:]
            for a, v, w in option:
                s2[a] += v * w
                p2[a] += w
            suivre(restantes - {q}, s2, p2, proba / len(questions[q]), chemin + [f"{q}.{i}"], principaux[q])

    suivre(frozenset(range(len(questions))), [0] * 6, [0] * 6, 1.0, [], None)
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
