"""
build_excel.py
--------------
Classeur Excel du téléchargement : une feuille par CSV, en-têtes en gras, première ligne figée,
filtres et colonnes à une largeur lisible. Les CSV sont seulement lus, jamais modifiés.

visas_historique_annuel.csv (315 216 lignes) reste en CSV seulement : mesuré dans LibreOffice le
18/11/2026, le classeur se charge en 1,8 à 2,0 s sans cette feuille, en 4,5 à 8,2 s avec, et il
passe de 1,5 à 7,1 Mo.

Écrit avec la bibliothèque standard : un fichier .xlsx est un ZIP de fichiers XML.

Dans une feuille, une colonne est numérique si toutes ses valeurs sont des nombres ; le nombre
est écrit tel quel. Tout le reste (dates, codes, booléens) reste du texte, sans conversion.

Contrôles bloquants, avant de remplacer le fichier final :
  - chaque CSV est bien formé, avec le même nombre de colonnes sur chaque ligne ;
  - le classeur relu donne, cellule par cellule, exactement le texte des CSV ;
  - les CSV n'ont pas changé pendant le traitement (empreinte SHA-256).

Lancement depuis la racine :
    py scripts/build_excel.py
"""

import csv
import hashlib
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data"
SORTIE = DONNEES / "telechargement" / "periple_donnees.xlsx"

FICHIERS = [
    "pays.csv", "scores.csv", "pays_monde.csv", "budget.csv", "unesco_sites.csv", "visas.csv",
    "visas_historique_comptes.csv", "visas_historique_annuel.csv",
    "visas_historique_sources.csv", "corrections_visas.csv", "corrections_unesco.csv",
    "carte/correspondance_carte.csv", "documentation/dictionnaire_donnees.csv",
]
HORS_CLASSEUR = {"visas_historique_annuel.csv"}
FEUILLES = [f for f in FICHIERS if f not in HORS_CLASSEUR]

COLONNES_TEXTE = {"commit", "sha256"}          # identifiants, même s'ils ressemblent à des nombres
NOMBRE = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][-+]?\d+)?")
INTERDITS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\r￾￿]")
ECHAPPEMENT_EXCEL = re.compile(r"_x[0-9A-Fa-f]{4}_")      # Excel le lirait comme un caractère
MAX_CELLULE = 32767
MAX_LIGNES = 1048576
LARGEUR_MIN, LARGEUR_MAX = 9, 50
DATE_ZIP = (2026, 1, 1, 0, 0, 0)               # date fixe : même contenu, même fichier

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
ENTETE_XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'

STYLES = ENTETE_XML + f"""<styleSheet xmlns="{NS}">
<fonts count="2"><font><sz val="10"/><name val="Arial"/><family val="2"/></font><font><b/><sz val="10"/><name val="Arial"/><family val="2"/></font></fonts>
<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFE8ECF1"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border><border><left/><right/><top/><bottom style="thin"><color rgb="FF8A94A3"/></bottom><diagonal/></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"/></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def empreinte(chemin):
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def lettre(indice):
    """0 -> A, 26 -> AA"""
    texte = ""
    indice += 1
    while indice:
        indice, reste = divmod(indice - 1, 26)
        texte = chr(65 + reste) + texte
    return texte


def indice_colonne(reference):
    n = 0
    for c in re.match(r"[A-Z]+", reference).group():
        n = n * 26 + ord(c) - 64
    return n - 1


def est_nombre(valeur):
    if not NOMBRE.fullmatch(valeur) or not math.isfinite(float(valeur)):
        return False
    chiffres = len(re.sub(r"\D", "", re.split(r"[eE]", valeur)[0]).lstrip("0"))
    entier = "." not in valeur and "e" not in valeur.lower()
    return chiffres <= (15 if entier else 17)


def lire_csv(relatif, erreurs):
    chemin = DONNEES / relatif
    if not chemin.exists():
        sys.exit(f"Fichier manquant : {chemin}")
    with chemin.open(encoding="utf-8", newline="") as f:
        lignes = list(csv.reader(f, strict=True))
    if not lignes or not all(lignes[0]) or len(set(lignes[0])) != len(lignes[0]):
        erreurs.append(f"{relatif} : en-tête vide ou en double")
        return [], []
    entete, corps = lignes[0], lignes[1:]
    if len(corps) + 1 > MAX_LIGNES:
        erreurs.append(f"{relatif} : trop de lignes pour Excel")
    for n, ligne in enumerate(corps, 2):
        if len(ligne) != len(entete):
            erreurs.append(f"{relatif}, ligne {n} : {len(ligne)} colonnes au lieu de {len(entete)}")
        for valeur in ligne:
            if (len(valeur) > MAX_CELLULE or INTERDITS.search(valeur)
                    or ECHAPPEMENT_EXCEL.search(valeur)):
                erreurs.append(f"{relatif}, ligne {n} : valeur impossible à écrire telle quelle")
    return entete, corps


def colonnes_numeriques(entete, corps):
    numeriques = set()
    for j, nom in enumerate(entete):
        valeurs = [l[j] for l in corps if l[j] != ""]
        if nom not in COLONNES_TEXTE and valeurs and all(est_nombre(v) for v in valeurs):
            numeriques.add(j)
    return numeriques


def largeurs(entete, corps):
    resultat = []
    for j, nom in enumerate(entete):
        contenu = max((len(l[j]) for l in corps), default=0)
        # l'en-tête est en gras et porte la flèche du filtre
        resultat.append(min(LARGEUR_MAX, max(LARGEUR_MIN, len(nom) + 5, contenu + 2)))
    return resultat


def nom_feuille(relatif):
    return Path(relatif).stem[:31]


def ecrire_feuille(zf, numero, entete, corps, chaines):
    numeriques = colonnes_numeriques(entete, corps)
    derniere = f"{lettre(len(entete) - 1)}{len(corps) + 1}"
    colonnes = "".join(f'<col min="{j + 1}" max="{j + 1}" width="{l}" customWidth="1"/>'
                       for j, l in enumerate(largeurs(entete, corps)))
    selection = ' tabSelected="1"' if numero == 1 else ""

    def indice_chaine(valeur):
        return chaines.setdefault(valeur, len(chaines))

    info = zipfile.ZipInfo(f"xl/worksheets/sheet{numero}.xml", DATE_ZIP)
    info.compress_type = zipfile.ZIP_DEFLATED
    with zf.open(info, "w") as sortie:
        sortie.write((ENTETE_XML + f'<worksheet xmlns="{NS}"><dimension ref="A1:{derniere}"/>'
                      f'<sheetViews><sheetView workbookViewId="0"{selection}>'
                      '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>'
                      '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView></sheetViews>'
                      f'<sheetFormatPr defaultRowHeight="13.5"/><cols>{colonnes}</cols><sheetData>').encode())
        cellules = "".join(f'<c r="{lettre(j)}1" s="1" t="s"><v>{indice_chaine(v)}</v></c>'
                           for j, v in enumerate(entete))
        sortie.write(f'<row r="1">{cellules}</row>'.encode())
        for i, ligne in enumerate(corps, 2):
            morceaux = []
            for j, v in enumerate(ligne):
                if v == "":
                    continue
                if j in numeriques:
                    morceaux.append(f'<c r="{lettre(j)}{i}"><v>{v}</v></c>')
                else:
                    morceaux.append(f'<c r="{lettre(j)}{i}" t="s"><v>{indice_chaine(v)}</v></c>')
            sortie.write(f'<row r="{i}">{"".join(morceaux)}</row>'.encode())
        sortie.write(f'</sheetData><autoFilter ref="A1:{derniere}"/></worksheet>'.encode())
    return derniere, len(numeriques)


def ecrire_partie(zf, nom, contenu):
    info = zipfile.ZipInfo(nom, DATE_ZIP)
    info.compress_type = zipfile.ZIP_DEFLATED
    zf.writestr(info, contenu.encode("utf-8"))


def ecrire_classeur(chemin, tableaux):
    chaines, plages, resume = {}, [], []
    with zipfile.ZipFile(chemin, "w", zipfile.ZIP_DEFLATED) as zf:
        for numero, (relatif, entete, corps) in enumerate(tableaux, 1):
            derniere, nb_num = ecrire_feuille(zf, numero, entete, corps, chaines)
            plages.append(derniere)
            resume.append((relatif, len(corps), len(entete), nb_num))
        n = len(tableaux)
        types = "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                        for i in range(1, n + 1))
        ecrire_partie(zf, "[Content_Types].xml", ENTETE_XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                      '<Default Extension="xml" ContentType="application/xml"/>'
                      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                      '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
                      f"{types}</Types>")
        ecrire_partie(zf, "_rels/.rels", ENTETE_XML + f'<Relationships xmlns="{NS_PKG}"><Relationship Id="rId1" '
                      f'Type="{NS_REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        feuilles = "".join(f'<sheet name={quoteattr(nom_feuille(t[0]))} sheetId="{i}" r:id="rId{i}"/>'
                           for i, t in enumerate(tableaux, 1))
        filtres = "".join(
            f'<definedName name="_xlnm._FilterDatabase" localSheetId="{i}" hidden="1">'
            f"{escape(chr(39) + nom_feuille(t[0]) + chr(39))}!$A$1:"
            f"${re.match('[A-Z]+', plages[i]).group()}${re.search(r'[0-9]+', plages[i]).group()}</definedName>"
            for i, t in enumerate(tableaux))
        ecrire_partie(zf, "xl/workbook.xml", ENTETE_XML + f'<workbook xmlns="{NS}" xmlns:r="{NS_REL}">'
                      f"<bookViews><workbookView/></bookViews><sheets>{feuilles}</sheets>"
                      f"<definedNames>{filtres}</definedNames></workbook>")
        liens = "".join(f'<Relationship Id="rId{i}" Type="{NS_REL}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                        for i in range(1, n + 1))
        ecrire_partie(zf, "xl/_rels/workbook.xml.rels", ENTETE_XML + f'<Relationships xmlns="{NS_PKG}">{liens}'
                      f'<Relationship Id="rId{n + 1}" Type="{NS_REL}/styles" Target="styles.xml"/>'
                      f'<Relationship Id="rId{n + 2}" Type="{NS_REL}/sharedStrings" Target="sharedStrings.xml"/>'
                      "</Relationships>")
        ecrire_partie(zf, "xl/styles.xml", STYLES)
        entrees = "".join(f'<si><t xml:space="preserve">{escape(c)}</t></si>' for c in chaines)
        ecrire_partie(zf, "xl/sharedStrings.xml", ENTETE_XML + f'<sst xmlns="{NS}" uniqueCount="{len(chaines)}">{entrees}</sst>')
    return resume


def relire_et_comparer(chemin, tableaux):
    """Relit le classeur écrit et compare chaque cellule au texte du CSV."""
    q = "{" + NS + "}"
    erreurs = []
    with zipfile.ZipFile(chemin) as zf:
        if zf.testzip() is not None:
            return ["archive .xlsx abîmée"]
        with zf.open("xl/sharedStrings.xml") as f:
            chaines = ["".join(si.itertext()) for si in ET.parse(f).getroot()]
        for numero, (relatif, entete, corps) in enumerate(tableaux, 1):
            attendu = [entete] + corps
            vues = 0
            with zf.open(f"xl/worksheets/sheet{numero}.xml") as f:
                for _, element in ET.iterparse(f):
                    if element.tag != q + "row":
                        continue
                    ligne = [""] * len(entete)
                    for c in element:
                        v = c.find(q + "v").text
                        ligne[indice_colonne(c.get("r"))] = chaines[int(v)] if c.get("t") == "s" else v
                    if vues >= len(attendu) or ligne != attendu[vues]:
                        erreurs.append(f"{relatif} : différence à la ligne {vues + 1}")
                        break
                    vues += 1
                    element.clear()
            if vues != len(attendu) and not any(e.startswith(relatif) for e in erreurs):
                erreurs.append(f"{relatif} : {vues} lignes relues sur {len(attendu)}")
    return erreurs


def main():
    avant = {r: empreinte(DONNEES / r) for r in FEUILLES if (DONNEES / r).exists()}
    erreurs, tableaux = [], []
    noms = [nom_feuille(r) for r in FEUILLES]
    if len(set(n.lower() for n in noms)) != len(noms):
        erreurs.append("deux feuilles auraient le même nom")
    for relatif in FEUILLES:
        entete, corps = lire_csv(relatif, erreurs)
        tableaux.append((relatif, entete, corps))
    if erreurs:
        sys.exit("Contrôles échoués, rien n'a été écrit :\n  - " + "\n  - ".join(erreurs[:30]))

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    temporaire = SORTIE.with_suffix(".tmp")
    try:
        resume = ecrire_classeur(temporaire, tableaux)
        erreurs = relire_et_comparer(temporaire, tableaux)
        for relatif, valeur in avant.items():
            if empreinte(DONNEES / relatif) != valeur:
                erreurs.append(f"{relatif} a changé pendant le traitement")
        if erreurs:
            sys.exit("Contrôles échoués, classeur non publié :\n  - " + "\n  - ".join(erreurs[:30]))
        os.replace(temporaire, SORTIE)
    finally:
        temporaire.unlink(missing_ok=True)

    print(f"Classeur écrit : {SORTIE.relative_to(RACINE)} ({SORTIE.stat().st_size / 1e6:.1f} Mo)")
    print(f"{'feuille':<28}{'lignes':>9}{'colonnes':>10}{'numériques':>12}")
    for relatif, lignes, colonnes, nb_num in resume:
        print(f"{nom_feuille(relatif):<28}{lignes:>9}{colonnes:>10}{nb_num:>12}")
    print("Contrôle : toutes les cellules relues sont identiques aux CSV ; CSV inchangés.")


if __name__ == "__main__":
    main()
