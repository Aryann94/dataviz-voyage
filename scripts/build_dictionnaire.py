"""
build_dictionnaire.py
---------------------
Écrit data/documentation/dictionnaire_donnees.csv : une ligne par colonne de chaque CSV du
téléchargement, avec sa description, son unité, sa source, sa licence et son année.

Les descriptions sont écrites ici, à la main. Le type, les valeurs possibles, les années
calculées et le nombre de cases vides sont lus dans les données : ils ne peuvent pas dériver.

Contrôles bloquants (rien n'est écrit si l'un échoue) :
  - chaque colonne de chaque CSV est décrite, une seule fois, et aucune n'est en trop ;
  - chaque colonne a une description, une source connue et une année ou une date ;
  - chaque colonne numérique a une unité ;
  - une colonne avec des cases vides dit ce que le vide signifie ;
  - chaque source citée figure dans data/documentation/LICENCES.txt.

Lancement depuis la racine :
    py scripts/build_dictionnaire.py
"""

import csv
import re
import sys
from pathlib import Path

from build_excel import FICHIERS

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "data"
DOSSIER = DONNEES / "documentation"
SORTIE = DOSSIER / "dictionnaire_donnees.csv"
LICENCES = DOSSIER / "LICENCES.txt"

COLONNES = ["fichier", "colonne", "description", "type", "unite", "valeurs_ou_etendue",
            "source", "lien_source", "licence", "annee_ou_date", "cases_vides", "sens_case_vide"]
MAX_VALEURS = 8

BM = "https://data.worldbank.org/indicator/"
CC_BY = "CC BY 4.0"
CC0 = "CC0"
MIT = "MIT (notice dans LICENCES.txt)"
DERIVE = "dérivé : suit les licences des données utilisées"

# clé : (libellé, lien, licence, date par défaut, mot à retrouver dans LICENCES.txt)
SOURCES = {
    "projet": ("Saisie du projet Périple", "https://github.com/Aryann94/dataviz-voyage",
               "création du projet", "16/10/2026", ""),
    "projet_ia": ("Texte du projet Périple, rédigé avec l'aide d'une IA",
                  "https://github.com/Aryann94/dataviz-voyage", "création du projet", "16/10/2026", ""),
    "calcul": ("Calcul du projet Périple", "https://github.com/Aryann94/dataviz-voyage", DERIVE, "", ""),
    "wikidata": ("Wikidata", "https://www.wikidata.org", CC0, "relevé du 16/10/2026", "Wikidata"),
    "wikidata_monde": ("Wikidata", "https://www.wikidata.org", CC0, "relevé du 17/11/2026", "Wikidata"),
    "wikidata_unesco": ("Wikidata", "https://www.wikidata.org", CC0,
                        "relevés du 16/10/2026 et du 17/11/2026", "Wikidata"),
    "unesco_mixte": ("Wikidata ; Wikipédia en français quand source_nom ou source_annee est rempli",
                     "https://fr.wikipedia.org", f"{CC0} ; CC BY-SA 4.0",
                     "relevés du 16/10, du 17/11 et du 18/11/2026", "Wikipédia"),
    "wikipedia": ("Wikipédia en français", "https://fr.wikipedia.org", "CC BY-SA 4.0",
                  "relevé du 18/11/2026", "Wikipédia"),
    "unesco_lien": ("Lien vers la fiche du Centre du patrimoine mondial", "https://whc.unesco.org",
                    "lien seulement : aucun contenu repris", "16/10/2026", "UNESCO"),
    "commons": ("Wikimedia Commons", "https://commons.wikimedia.org",
                "licence propre à chaque fichier", "relevé du 16/10/2026", "Wikimedia Commons"),
    "factbook": ("CIA World Factbook, copie archivée", "https://github.com/factbook/factbook.json",
                 f"domaine public ; copie {CC0}", "relevé du 16/10/2026", "CIA World Factbook"),
    "byt": ("Budget Your Trip", "https://www.budgetyourtrip.com",
            "réservé : reproduction soumise à l'accord écrit du site", "relevé du 16/10/2026",
            "Budget Your Trip"),
    "imorte": ("Passport Index, dépôt imorte/passport-index-data, avec vérifications manuelles",
               "https://github.com/imorte/passport-index-data", MIT, "données du 18/02/2026",
               "imorte/passport-index-data"),
    "historique": ("Passport Index, dépôts ilyankou/passport-index-dataset et imorte/passport-index-data",
                   "https://github.com/ilyankou/passport-index-dataset", MIT,
                   "versions du 17/04/2019 au 18/02/2026", "ilyankou/passport-index-dataset"),
    "verif_visas": ("Vérification manuelle sur des pages officielles (lien dans source_url)",
                    "https://www.diplomatie.gouv.fr/fr/conseils-aux-voyageurs/",
                    "faits vérifiés, lien vers chaque page", "", "France Diplomatie"),
    "verif_unesco": ("Vérification sur les fiches du Centre du patrimoine mondial (lien dans source_url)",
                     "https://whc.unesco.org", "lien seulement : aucun contenu repris", "16/10/2026", "UNESCO"),
    "natural_earth": ("Natural Earth v5.1.2, point de vue de la France", "https://www.naturalearthdata.com",
                      "domaine public", "préparé le 17/11/2026", "Natural Earth"),
}
for code, libelle in (("ER.LND.PTLD.ZS", "aires terrestres protégées"), ("EN.POP.DNST", "densité de population"),
                      ("AG.LND.FRST.ZS", "surface forestière"), ("SP.URB.TOTL.IN.ZS", "population urbaine"),
                      ("EN.URB.MCTY.TL.ZS", "agglomérations de plus d'un million d'habitants"),
                      ("NY.GNP.PCAP.CD", "RNB par habitant, méthode Atlas")):
    SOURCES[code] = (f"Banque mondiale, WDI, {code} ({libelle})", BM + code, CC_BY,
                     "extraction du 16/10/2026", "Banque mondiale")
SOURCES["prix_bm"] = ("Calcul du projet à partir de Banque mondiale, WDI, PA.NUS.PPP et PA.NUS.FCRF",
                      BM + "PA.NUS.PPP", CC_BY, "extraction du 16/10/2026", "Banque mondiale")
SOURCES["rnb_monde"] = ("Banque mondiale, WDI, NY.GNP.PCAP.CD, par l'API Data360", BM + "NY.GNP.PCAP.CD",
                        CC_BY, "extraction du 17/11/2026", "Banque mondiale")

ISO3 = "Code ISO 3166-1 alpha-3 du pays, clé commune aux fichiers"
AN = "Année de la valeur de la colonne "


def c(colonne, description, source, unite="", vide="", annee=""):
    return (colonne, description, source, unite, vide, annee)


DICTIONNAIRE = {
    "pays.csv": [
        c("iso3", ISO3, "projet"),
        c("iso2", "Code ISO 3166-1 alpha-2 du pays", "wikidata"),
        c("nom_fr", "Nom du pays en français", "projet"),
        c("region", "Grande région retenue pour répartir la sélection de 41 pays", "projet"),
        c("capitale", "Capitale retenue (Pretoria pour l'Afrique du Sud, Colombo pour le Sri Lanka)", "wikidata"),
        c("lat", "Latitude de la capitale", "wikidata", "degrés décimaux"),
        c("lon", "Longitude de la capitale", "wikidata", "degrés décimaux"),
        c("description", "Présentation du pays en deux phrases", "projet_ia"),
        c("image_url", "Lien vers la photo sur Wikimedia Commons (la photo n'est pas fournie)", "commons"),
        c("image_auteur", "Auteur de la photo", "commons", annee="relevés du 16/10/2026 et du 18/11/2026"),
        c("image_licence", "Licence de la photo", "commons", annee="relevés du 16/10/2026 et du 18/11/2026"),
        c("drapeau_url", "Lien vers le drapeau sur Wikimedia Commons", "commons"),
        c("unesco_culturel", "Nombre de sites culturels du patrimoine mondial, comptés par numéro de site", "wikidata", "sites"),
        c("unesco_naturel", "Nombre de sites naturels du patrimoine mondial", "wikidata", "sites"),
        c("unesco_mixte", "Nombre de sites mixtes du patrimoine mondial", "wikidata", "sites"),
        c("unesco_total", "Nombre total de sites du patrimoine mondial", "wikidata", "sites"),
        c("zones_protegees_pct", "Aires terrestres protégées, en part de la surface des terres", "ER.LND.PTLD.ZS", "% des terres", annee="col:annee_zones_protegees"),
        c("annee_zones_protegees", AN + "zones_protegees_pct", "ER.LND.PTLD.ZS", "année", annee="col:annee_zones_protegees"),
        c("densite_hab_km2", "Population au milieu de l'année divisée par la surface des terres", "EN.POP.DNST", "habitants par km²", annee="col:annee_densite"),
        c("annee_densite", AN + "densite_hab_km2", "EN.POP.DNST", "année", annee="col:annee_densite"),
        c("foret_pct", "Surface de forêt, en part de la surface des terres", "AG.LND.FRST.ZS", "% des terres", annee="col:annee_foret"),
        c("annee_foret", AN + "foret_pct", "AG.LND.FRST.ZS", "année", annee="col:annee_foret"),
        c("cotes_km", "Longueur des côtes (0 pour un pays sans accès à la mer)", "factbook", "km"),
        c("sans_littoral", "true si la longueur des côtes vaut 0", "factbook"),
        c("superficie_terres_km2", "Surface des terres", "factbook", "km²"),
        c("lat_centre", "Latitude du centre du pays", "factbook", "degrés"),
        c("pop_urbaine_pct", "Population urbaine, en part de la population totale", "SP.URB.TOTL.IN.ZS", "% de la population", annee="col:annee_pop_urbaine"),
        c("annee_pop_urbaine", AN + "pop_urbaine_pct", "SP.URB.TOTL.IN.ZS", "année", annee="col:annee_pop_urbaine"),
        c("pop_villes_1m_pct", "Population des agglomérations de plus d'un million d'habitants, en part de la population totale. 0 quand le pays n'apparaît pas dans la série", "EN.URB.MCTY.TL.ZS", "% de la population", annee="col:annee_pop_villes_1m"),
        c("annee_pop_villes_1m", AN + "pop_villes_1m_pct", "EN.URB.MCTY.TL.ZS", "année", "pays absent de la série : pop_villes_1m_pct vaut alors 0", annee="col:annee_pop_villes_1m"),
        c("rnb_hab_usd", "Revenu national brut par habitant, méthode Atlas", "NY.GNP.PCAP.CD", "dollars US courants", annee="col:annee_rnb"),
        c("annee_rnb", AN + "rnb_hab_usd", "NY.GNP.PCAP.CD", "année", annee="col:annee_rnb"),
        c("niveau_prix", "Indice du niveau des prix : parité de pouvoir d'achat divisée par le taux de change officiel", "prix_bm", "indice (États-Unis = 1)", annee="col:annee_niveau_prix"),
        c("annee_niveau_prix", "Plus ancienne des deux années utilisées pour niveau_prix", "prix_bm", "année", annee="col:annee_niveau_prix"),
        c("budget_dispo", "true si le pays a un budget détaillé dans budget.csv", "byt"),
        c("budget_moyen_usd_jour", "Somme des 4 catégories de budget au niveau moyen", "byt", "dollars US par personne et par jour", "pays exclu de budget.csv (Argentine : montants jugés invraisemblables)"),
        c("wikidata_qid", "Identifiant de l'élément Wikidata du pays", "wikidata"),
        c("dans_quiz", "true si le pays a toutes les données nécessaires au quiz", "calcul", annee="col:date_assemblage"),
        c("date_assemblage", "Date de construction du fichier", "calcul", annee="col:date_assemblage"),
    ],
    "scores.csv": [
        c("iso3", ISO3, "projet"),
        c("score_culture", "Sites culturels et mixtes (logarithme), ramenés de 0 à 100 sur les 41 pays", "calcul", "note de 0 à 100", annee="col:date_calcul"),
        c("score_nature", "½ espaces naturels (meilleur de la faible densité et de la forêt) + ¼ sites naturels et mixtes + ¼ zones protégées", "calcul", "note de 0 à 100", annee="col:date_calcul"),
        c("score_villes", "Part de la population dans les villes de plus d'un million d'habitants", "calcul", "note de 0 à 100", annee="col:date_calcul"),
        c("score_prix", "Niveau des prix inversé, en logarithme : 100 = le moins cher", "calcul", "note de 0 à 100", annee="col:date_calcul"),
        c("score_distance", "Distance depuis Paris : 100 = le plus loin", "calcul", "note de 0 à 100", annee="col:date_calcul"),
        c("score_mer", "Chaleur selon la latitude × longueur et densité des côtes. Mesure un potentiel, pas les plages", "calcul", "note de 0 à 100", annee="col:date_calcul"),
        c("distance_paris_km", "Distance à vol d'oiseau entre Paris et la capitale", "calcul", "km", annee="col:date_calcul"),
        c("date_calcul", "Date du calcul", "calcul", annee="col:date_calcul"),
    ],
    "pays_monde.csv": [
        c("iso3", "Code du pays ou du passeport, ISO 3166-1 alpha-3 (XKX pour le Kosovo)", "projet", annee="col:date_extraction"),
        c("iso2", "Code à deux lettres du pays (XK pour le Kosovo)", "wikidata_monde"),
        c("nom_fr", "Nom français (pays_liste.csv pour les 41 pays, Wikidata pour les autres)", "wikidata_monde"),
        c("dans_selection", "true si le pays fait partie des 41 pays du quiz", "projet", annee="col:date_extraction"),
        c("wikidata_qid", "Identifiant de l'élément Wikidata du pays", "wikidata_monde"),
        c("drapeau_url", "Lien vers le drapeau : celui reconnu par l'ONU quand il existe, sinon celui de Wikidata", "wikidata_monde"),
        c("rnb_hab_usd", "Dernier revenu national brut par habitant connu, méthode Atlas", "rnb_monde", "dollars US courants", "aucune valeur publiée pour ce pays", annee="col:annee_rnb"),
        c("annee_rnb", AN + "rnb_hab_usd", "rnb_monde", "année", "aucune valeur publiée pour ce pays", annee="col:annee_rnb"),
        c("rnb_statut", "ok = valeur récente ; ancien = plus de 5 ans ; absent = aucune valeur", "calcul", annee="col:date_extraction"),
        c("rnb_utilisable", "true seulement si rnb_statut vaut ok", "calcul", annee="col:date_extraction"),
        c("date_extraction", "Date de l'extraction", "calcul", annee="col:date_extraction"),
    ],
    "budget.csv": [
        c("iso3", ISO3, "projet"),
        c("niveau", "Niveau de budget : petit (Budget), moyen (Mid-Range), confort (Luxury)", "byt", annee="col:date_releve"),
        c("categorie", "hebergement, transport (local), repas ou activites", "byt", annee="col:date_releve"),
        c("montant_usd_jour", "Dépense affichée par le site. Hébergement : une personne en chambre double", "byt", "dollars US par personne et par jour", annee="col:date_releve"),
        c("total_site_usd", "Total affiché par le site pour ce niveau. Il ne vaut pas toujours la somme des catégories", "byt", "dollars US par personne et par jour", "total non relevé pour ce pays", annee="col:date_releve"),
        c("source_url", "Page du pays sur Budget Your Trip", "byt", annee="col:date_releve"),
        c("date_releve", "Date du relevé", "byt", annee="col:date_releve"),
        c("date_maj_site", "Date de mise à jour des coûts indiquée par le site", "byt", annee="col:date_maj_site"),
    ],
    "unesco_sites.csv": [
        c("iso3", ISO3, "projet"),
        c("id_unesco", "Numéro du site au patrimoine mondial, sans suffixe d'extension", "wikidata_unesco", "identifiant"),
        c("categorie", "Catégorie du site", "wikidata_unesco"),
        c("nom_fr", "Nom affiché. Ce n'est pas le nom officiel de l'UNESCO : libellé Wikidata ou titre d'article Wikipédia", "unesco_mixte"),
        c("langue_nom", "Origine du nom : fr (libellé français), mul (libellé multilingue), wikifr (titre Wikipédia), en (libellé anglais)", "calcul", annee="relevés du 16/10, du 17/11 et du 18/11/2026"),
        c("wikidata_qid", "Élément Wikidata retenu pour représenter le site", "wikidata_unesco", vide="aucun élément ne représente le site entier"),
        c("regle_choix", "Comment l'élément a été trouvé : numéro exact, révision ou extension", "calcul", annee="17/11/2026"),
        c("departage", "Choix entre plusieurs éléments : aucun, partie_de, titre_unesco (comparaison non publiée), douteux, correction", "calcul", annee="17/11/2026"),
        c("annee_inscription", "Année d'inscription. Pour un site partagé, elle suit l'élément du pays", "unesco_mixte", "année"),
        c("transfrontalier", "true si le site concerne plusieurs pays", "wikidata_unesco"),
        c("lien_unesco", "Lien vers la fiche du site, sans reprise de son contenu", "unesco_lien"),
        c("source_nom", "Lien permanent vers l'article Wikipédia dont vient le nom", "wikipedia", vide="le nom vient de l'élément Wikidata"),
        c("source_annee", "Lien permanent vers l'article Wikipédia dont vient l'année", "wikipedia", vide="l'année vient de Wikidata"),
    ],
    "visas.csv": [
        c("passeport_iso3", "Code du pays qui délivre le passeport", "imorte"),
        c("destination_iso3", "Code du pays de destination", "imorte"),
        c("statut", "Règle d'entrée : sans_visa, visa_arrivee, eta (autorisation électronique), e_visa, visa_requis, interdit", "imorte"),
        c("jours", "Durée de séjour autorisée sans visa", "imorte", "jours", "durée non précisée par la source, ou statut autre que sans_visa"),
        c("date_verification", "Date de la vérification manuelle", "verif_visas", vide="paire non vérifiée à la main", annee="col:date_verification"),
    ],
    "visas_historique_comptes.csv": [
        c("passeport_iso3", "Code du pays qui délivre le passeport", "historique"),
        c("date", "Date de la version du jeu de données", "historique", annee="col:date"),
        c("source", "Dépôt d'origine de la version", "historique"),
        c("format", "Format de la version (voir visas_historique_sources.csv)", "historique"),
        c("sans_visa", "Destinations sans visa", "historique", "destinations"),
        c("visa_arrivee", "Destinations avec visa à l'arrivée", "historique", "destinations"),
        c("eta", "Destinations avec autorisation électronique. Non comparable entre les formats", "historique", "destinations"),
        c("e_visa", "Destinations avec visa électronique. Non comparable entre les formats", "historique", "destinations"),
        c("visa_requis", "Destinations avec visa requis. Non comparable entre les formats", "historique", "destinations"),
        c("covid_ban", "Destinations fermées par une interdiction liée au Covid", "historique", "destinations"),
        c("interdit", "Destinations qui refusent l'entrée", "historique", "destinations"),
        c("sans_demarche", "sans_visa + visa_arrivee", "calcul", "destinations", annee="col:date"),
        c("demarche", "eta + e_visa + visa_requis", "calcul", "destinations", annee="col:date"),
        c("entree_interdite", "covid_ban + interdit", "calcul", "destinations", annee="col:date"),
        c("total", "Nombre de destinations comptées", "calcul", "destinations", annee="col:date"),
        c("ecart_jours", "Jours écoulés depuis la version précédente", "calcul", "jours", "première version, sans version précédente", annee="col:date"),
        c("trou_avant", "true si plus de 100 jours séparent cette version de la précédente", "calcul", annee="col:date"),
    ],
    "visas_historique_annuel.csv": [
        c("passeport_iso3", "Code du pays qui délivre le passeport", "historique"),
        c("destination_iso3", "Code du pays de destination", "historique"),
        c("annee", "Année de la photo : première version disponible de l'année", "historique", "année", annee="col:annee"),
        c("statut", "Règle d'entrée, avec covid_ban en plus des statuts de visas.csv", "historique", annee="col:annee"),
        c("jours", "Durée de séjour autorisée sans visa", "historique", "jours", "durée non précisée, ou statut autre que sans_visa", annee="col:annee"),
    ],
    "visas_historique_sources.csv": [
        c("date", "Date de la version", "historique", annee="col:date"),
        c("source", "Dépôt d'origine de la version", "historique"),
        c("commit", "Identifiant du commit Git de la version", "historique", vide="version 2026, qui vient de visas.csv"),
        c("format", "Code du format de la version", "calcul", annee="col:date"),
        c("description_format", "Explication du format", "calcul", annee="col:date"),
        c("sha256", "Empreinte SHA-256 de la version lue", "calcul", annee="col:date"),
        c("lignes", "Nombre de lignes de la version", "calcul", "lignes", annee="col:date"),
        c("photo_annuelle", "true si cette version sert de photo pour son année", "calcul", annee="col:date"),
        c("ecart_jours", "Jours écoulés depuis la version précédente", "calcul", "jours", "première version, sans version précédente", annee="col:date"),
        c("trou_avant", "true si plus de 100 jours séparent cette version de la précédente", "calcul", annee="col:date"),
    ],
    "corrections_visas.csv": [
        c("passeport_iso3", "Code du pays qui délivre le passeport", "verif_visas", annee="col:date_verification"),
        c("destination_iso3", "Code du pays de destination", "verif_visas", annee="col:date_verification"),
        c("statut", "Statut retenu après vérification", "verif_visas", annee="col:date_verification"),
        c("jours", "Durée de séjour retenue", "verif_visas", "jours", "pas de durée retenue pour cette paire", annee="col:date_verification"),
        c("source_url", "Page consultée pour la vérification", "verif_visas", annee="col:date_verification"),
        c("date_verification", "Date de la vérification", "verif_visas", annee="col:date_verification"),
        c("note", "Résultat de la vérification", "verif_visas", annee="col:date_verification"),
    ],
    "corrections_unesco.csv": [
        c("iso3", ISO3, "projet"),
        c("id_unesco", "Numéro du site concerné", "verif_unesco", "identifiant"),
        c("action", "exclure = site retiré du comptage de ce pays ; categorie = catégorie imposée", "verif_unesco"),
        c("categorie", "Catégorie imposée", "verif_unesco", vide="action exclure : pas de catégorie à imposer"),
        c("source_url", "Fiche consultée pour la vérification", "verif_unesco"),
        c("note", "Raison de la correction", "verif_unesco"),
    ],
    "carte/correspondance_carte.csv": [
        c("adm0_a3", "Code de l'entité dans Natural Earth", "natural_earth"),
        c("nom_ne", "Nom de l'entité dans Natural Earth", "natural_earth"),
        c("iso_a3_ne", "Code ISO donné par Natural Earth (-99 s'il n'y en a pas)", "natural_earth"),
        c("iso3_passeport", "Code du passeport associé à l'entité", "calcul", vide="territoire sans passeport dans les données de visas", annee="17/11/2026"),
        c("regle", "identique = même code ; table = code traduit ; sans_passeport = gris sur la carte", "calcul", annee="17/11/2026"),
        c("repere", "true si l'entité a un repère sur la carte (pays de moins de 3 000 km²)", "calcul", annee="17/11/2026"),
        c("surface_km2", "Surface calculée sur la forme Natural Earth, proche de la surface réelle", "calcul", "km²", annee="17/11/2026"),
        c("note", "Précision sur le code ou le statut du territoire", "calcul", vide="rien à signaler", annee="17/11/2026"),
    ],
}


def lire(relatif):
    with (DONNEES / relatif).open(encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f)
        return lecteur.fieldnames, list(lecteur)


def est_nombre(v):
    try:
        float(v)
        return True
    except ValueError:
        return False


def type_colonne(valeurs):
    if not valeurs:
        return "vide"
    if all(v in ("true", "false") for v in valeurs):
        return "booléen"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in valeurs):
        return "date"
    if all(re.fullmatch(r"-?\d+", v) for v in valeurs):
        return "entier"
    if all(est_nombre(v) for v in valeurs):
        return "décimal"
    if all(v.startswith("http") for v in valeurs):
        return "lien"
    return "texte"


def etendue(valeurs, genre):
    if genre in ("entier", "décimal"):
        nombres = sorted(valeurs, key=float)
        return nombres[0] if nombres[0] == nombres[-1] else f"{nombres[0]} à {nombres[-1]}"
    if genre == "date":
        return min(valeurs) if min(valeurs) == max(valeurs) else f"{min(valeurs)} à {max(valeurs)}"
    distinctes = sorted(set(valeurs))
    if genre == "booléen" or (len(distinctes) <= MAX_VALEURS and max(map(len, distinctes)) <= 30):
        return " | ".join(distinctes)
    return f"{len(distinctes)} valeurs différentes"


def date_colonne(spec, source, lignes, erreurs, nom):
    if spec.startswith("col:"):
        valeurs = sorted({l[spec[4:]] for l in lignes if l[spec[4:]]})
        if not valeurs:
            erreurs.append(f"{nom} : colonne d'année vide")
            return ""
        return valeurs[0] if len(valeurs) == 1 else f"{valeurs[0]} à {valeurs[-1]}"
    return spec or SOURCES[source][3]


def main():
    erreurs, sorties = [], []
    fichiers = [f for f in FICHIERS if not f.startswith("documentation/")]
    if set(fichiers) != set(DICTIONNAIRE):
        erreurs.append(f"fichiers différents de build_excel.py : {sorted(set(fichiers) ^ set(DICTIONNAIRE))}")
    texte_licences = LICENCES.read_text(encoding="utf-8") if LICENCES.exists() else ""
    if not texte_licences:
        erreurs.append(f"{LICENCES.name} absent ou vide")
    for fichier in fichiers:
        if fichier not in DICTIONNAIRE:
            continue
        entete, lignes = lire(fichier)
        decrites = [d[0] for d in DICTIONNAIRE[fichier]]
        if len(decrites) != len(set(decrites)):
            erreurs.append(f"{fichier} : colonne décrite deux fois")
        if set(decrites) != set(entete):
            erreurs.append(f"{fichier} : non décrites {sorted(set(entete) - set(decrites))}, "
                           f"en trop {sorted(set(decrites) - set(entete))}")
            continue
        par_nom = {d[0]: d for d in DICTIONNAIRE[fichier]}
        for colonne in entete:
            _, description, source, unite, vide, annee = par_nom[colonne]
            nom = f"{fichier}:{colonne}"
            if source not in SOURCES:
                erreurs.append(f"{nom} : source inconnue {source}")
                continue
            libelle, lien, licence, _, repere = SOURCES[source]
            if repere and repere.casefold() not in texte_licences.casefold():
                erreurs.append(f"{nom} : « {repere} » absent de {LICENCES.name}")
            valeurs = [l[colonne] for l in lignes if l[colonne] != ""]
            genre = type_colonne(valeurs)
            nb_vides = len(lignes) - len(valeurs)
            quand = date_colonne(annee, source, lignes, erreurs, nom)
            if not description:
                erreurs.append(f"{nom} : description vide")
            if not quand:
                erreurs.append(f"{nom} : ni année ni date")
            if genre in ("entier", "décimal") and not unite:
                erreurs.append(f"{nom} : colonne numérique sans unité")
            if nb_vides and not vide:
                erreurs.append(f"{nom} : {nb_vides} cases vides sans explication")
            if vide and not nb_vides:
                erreurs.append(f"{nom} : explication du vide alors qu'aucune case n'est vide")
            sorties.append({
                "fichier": fichier, "colonne": colonne, "description": description, "type": genre,
                "unite": unite, "valeurs_ou_etendue": etendue(valeurs, genre) if valeurs else "",
                "source": libelle, "lien_source": lien, "licence": licence, "annee_ou_date": quand,
                "cases_vides": nb_vides, "sens_case_vide": vide,
            })
    if erreurs:
        sys.exit("Contrôles échoués, rien n'a été écrit :\n  - " + "\n  - ".join(erreurs))
    DOSSIER.mkdir(parents=True, exist_ok=True)
    with SORTIE.open("w", encoding="utf-8", newline="") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
        ecrivain.writeheader()
        ecrivain.writerows(sorties)
    print(f"Fichier écrit : {SORTIE.relative_to(RACINE)} ({len(sorties)} colonnes décrites, "
          f"{len(fichiers)} fichiers)")


if __name__ == "__main__":
    main()
