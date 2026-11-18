# Périple (dataviz voyage) : récapitulatif du projet

*Mis à jour le 18 novembre 2026. Données terminées, page d'accueil terminée, les trois visualisations restent à faire. Document de passation pour les conversations suivantes et base de la section technique.*

## Où on en est (18 novembre 2026)

**Décidé le 18/11 :**
- on n'ajoute aucun pays, la sélection reste à 41 pays (raison en section 5, trous connus en section 7) ;
- on ne republie plus de contenu venant de whc.unesco.org : les noms et années repris des fiches sont remplacés par Wikipédia en français, et `unesco_sites.csv` peut entrer dans le ZIP (section 5).

**Fait le 17/11 :**
- `pays_monde.csv` : les 199 pays (nom, ISO2, drapeau, revenu par habitant) ;
- le fond de carte (`data/carte/`) ;
- l'historique des visas 2019-2026 (57 versions) ;
- les noms et années des 735 sites UNESCO (`unesco_sites.csv`).

**Prochaines tâches, dans l'ordre :**
1. Téléchargement des données (section 8, tâche 5) : fichier Excel, dictionnaire, licences, citation de Budget Your Trip, crédit de la photo de Jakarta, ZIP.
2. Puis la suite de la section 8 : quiz final, puis le site, une visualisation à la fois.

## 1. Le projet en bref

- **Cours** : Web Graphique (DMA1EDA7), M1, Everardo Reyes. Rendu : lien GitHub, entre le 11 décembre 2026 et le 15 janvier 2027.
- **Barème /20** : présentation (5), explication technique (5), interactivité, avec 3 visualisations différentes et fonctionnelles (7), partage des données en CSV/XLS (3).
- **Contraintes** : HTML, CSS et JavaScript « vanilla », bibliothèques légères autorisées (D3, Chart.js, Leaflet), aucun CMS. Couleurs pas trop vives. Travail en solo. IA autorisée par le prof, à condition de savoir expliquer le travail.
- **Nom du site** : **Périple** (décidé en novembre 2026, logo dans `img/logo.svg`).
- **Sujet** : le voyage. Trois activités sur la page :
  1. **Quiz « Quel pays pour moi ? »** : questions en cartes, puis le pays qui ressemble le plus au joueur, avec un **radar** de comparaison.
  2. **Carte des passeports** : choisir un passeport et voir le monde coloré selon les visas (199 pays).
  3. **Budget d'un voyage** : répartition du budget quotidien (hébergement, transport, repas, activités) et effort relatif (jours de revenu moyen).
- **Dépôt** : https://github.com/Aryann94/dataviz-voyage (public). Dossier local : `C:\Users\malik\Downloads\dataviz-voyage`. Futur site : `aryann94.github.io/dataviz-voyage`.

## 2. Les fichiers

```
dataviz-voyage/
├── data/
│   ├── pays.csv                 FINAL - 1 ligne par pays (41), 39 colonnes : faits bruts
│   ├── pays_monde.csv           FINAL - les 199 pays de la carte : nom français, ISO2, drapeau, RNB par habitant
│   ├── scores.csv               FINAL - notes du quiz 0-100 (6 axes) + distance depuis Paris
│   ├── visas.csv                FINAL - 39 402 paires passeport -> destination
│   ├── visas_historique_comptes.csv FINAL - passeport x version (57 dates, 2019-2026) : nombre de pays par statut (courbe)
│   ├── visas_historique.json        FINAL - 8 photos annuelles (une matrice 199 x 199 par année) pour le curseur du globe
│   ├── visas_historique_annuel.csv  FINAL - les 8 photos en format long (8 Mo) : pour le ZIP, pas chargé par le site
│   ├── visas_historique_sources.csv une ligne par version : commit, format, empreinte SHA-256, photo, trou
│   ├── budget.csv               FINAL - format long : pays x niveau x catégorie (40 pays)
│   ├── carte/
│   │   ├── pays_carte.topojson      FINAL - fond de carte du globe et de la carte à plat (249 entités, 1,2 Mo)
│   │   └── correspondance_carte.csv une ligne par entité Natural Earth : code passeport, règle, repère, surface
│   ├── pays_liste.csv           saisie manuelle : les 41 pays, nom, région, choix de capitale/photo
│   ├── descriptions_pays.csv    saisie manuelle : 41 textes de présentation
│   ├── saisie_budget.csv        relevé Budget Your Trip (format large)
│   ├── corrections_visas.csv    41 vérifications manuelles avec source et date (40 pour le passeport français + Canada → Sénégal)
│   ├── corrections_unesco.csv   5 corrections justifiées du comptage UNESCO
│   ├── unesco_sites.csv         FINAL - 735 sites des 41 pays : nom (Wikidata ou Wikipédia), catégorie, année d'inscription, sources. Chargé par le site et mis dans le ZIP
│   ├── corrections_unesco_noms.csv 54 corrections : titre d'article et année de Wikipédia en français (lien permanent en source), élément imposé. La fiche UNESCO sert seulement à vérifier
│   ├── intermediaire/           sorties par source (Wikidata, Banque mondiale, CIA Factbook, ILOSTAT)
│   └── raw/                     réponses brutes des API et fichiers téléchargés (traçabilité)
├── scripts/                     Python, bibliothèque standard (+ certifi)
│
├── index.html                   la page (pour l'instant : préchargeur + hero)
├── style.css                    couleurs (encre #0D0D33, crème #FFF7E6, ciel), polices, hero, boutons
├── main.js                      chef d'orchestre : chargement → 100 % → choix du son → dispersion → chute → défilement
├── clouds.js, disperse.js       nuages du préchargeur et leur dispersion
├── counter.js, progress.js      compteur 0-100 % et suivi réel du chargement (images, Three.js, modèle)
├── gate.js                      « Entrer avec le son » / « sans le son »
├── sound.js                     Web Audio API : musique (intro + boucle), vent généré, souffles, étouffement dans le casque
├── scene.js                     scène 3D Three.js : astronaute en rendu toon, traits de vitesse, paysage en plans, plongée
├── hero.js                      textes du hero (arrivée, puis texte d'accueil dans la visière)
├── scroll.js                    Lenis + ScrollTrigger : avance de la plongée, déblocage, navigation au clavier
├── buttons.js                   boutons « magnétiques » et effet de roulement du texte
├── img/                         nuages, 4 plans du paysage, logo, favicons (WebP)
├── models/astronaute.glb        modèle 3D de l'astronaute
├── sounds/                      musique.mp3, whoosh.mp3 (et musique test.mp3, non utilisée)
├── fonts/Evori.ttf              police du titre
├── prototype/quiz-prototype.html  référence pour la logique du quiz (pas pour le design)
├── prototype/carte-test.html    page de vérification du fond de carte (D3, carte à plat)
└── .github/workflows/pages.yml  déploiement GitHub Pages à chaque push sur main
```

**Ordre d'exécution** (depuis la racine, `py` sous Windows) :
1. `build_visas.py` : télécharge Passport Index, convertit et applique `corrections_visas.csv` → `visas.csv`
2. `build_pays_wikidata.py` : SPARQL Wikidata (capitales, GPS, images, drapeaux, UNESCO) et API Commons (crédits photos)
3. `build_pays_banquemondiale.py` : API Banque mondiale, 8 indicateurs (dont la forêt)
3 bis. `build_pays_cotes.py` : CIA World Factbook (archive JSON sur GitHub) : côtes, surface des terres, latitude du centre
4. `build_pays_ilostat.py` : salaires ILOSTAT. **Testé puis écarté**, gardé comme preuve.
5. `import_budget_collage.py` puis `build_budget.py` : budget Budget Your Trip → `budget.csv`
6. `build_pays.py` : assemble `pays.csv`, avec des contrôles bloquants
7. `build_scores.py` : calcule `scores.csv` (6 axes) et teste 8 profils de voyageurs
8. `build_pays_monde.py` : les 199 pays de `visas.csv`. Wikidata donne les noms, ISO2 et drapeaux, et Data360 de la Banque mondiale donne le RNB. Résultat : `pays_monde.csv`. Le script réutilise les fonctions réseau des scripts 2 et 3, et il a besoin de `visas.csv`, `pays_liste.csv` et `pays.csv`.
9. `build_carte.py` : fond de carte Natural Earth (point de vue de la France, 10m), jointure avec `pays_monde.csv`, simplification par mapshaper → `data/carte/`. Il demande **Node.js** (installé le 17/11, v26 LTS) pour `npx mapshaper`. Le fichier brut de 13 Mo est téléchargé dans `data/raw/natural_earth/`, qui n'est pas commité.

10. `build_visas_historique.py` : historique des visas (56 versions de l'historique Git d'ilyankou + la version 2026 du projet). Il demande **git** et `visas.csv`. Le clone d'ilyankou (8 Mo) est dans `data/raw/passport_index_historique/`, qui n'est pas commité, et il est figé au commit `e111423`.
11. `build_unesco_noms.py` : noms et années d'inscription des sites UNESCO des 41 pays → `unesco_sites.csv`. Il repart de `wikidata_unesco.json` (16/10) et de la même fonction `sites_unesco()` que le comptage. `--depuis-brut` relit le relevé Wikidata sans requête. `--verifier 10` compare 10 années tirées au hasard à whc.unesco.org (par curl : le site refuse urllib).
    - `build_unesco_wikipedia.py` (à lancer avant, si on refait les corrections) : cherche les articles de Wikipédia en français et écrit `corrections_unesco_noms.csv`, avec le relevé dans `data/raw/wikipedia_unesco.json`.
    - Garde-fou : `test_comptage_unesco.py` vérifie que le comptage recalculé depuis les données brutes retombe exactement sur `pays.csv`.

**Vérifier le fond de carte** : `py -m http.server 8000` depuis la racine, puis ouvrir http://localhost:8000/prototype/carte-test.html.

Le site charge directement les CSV de `data/` (par exemple avec `d3.csv()`). Les fichiers téléchargeables sont donc exactement ceux qui font tourner la page.

## 3. Modèle de données

Trois tables reliées par le **code ISO 3166 alpha-3** (`FRA`, `JPN`…) :
- `pays.csv` (1 ligne par pays) ←→ `scores.csv` (1 ligne par pays)
- `pays.csv` ←→ `budget.csv` (pays × niveau × catégorie)
- `pays.csv` ←→ `visas.csv` (passeport_iso3 → destination_iso3)

Les **faits bruts** sont dans `pays.csv`, les **choix de calcul** dans `scores.csv`.

Types de données présents :
- **texte** : nom, description ;
- **image** : photo et drapeau (URL Wikimedia Commons, avec auteur et licence) ;
- **spatial** : latitude et longitude de la capitale ;
- **date** : année de chaque indicateur, dates de relevé et de vérification ;
- **nombres** : indicateurs ;
- **booléen** : `dans_quiz`, `budget_dispo`.

### `pays.csv` : colonnes principales
`iso3, iso2, nom_fr, region, capitale, lat, lon, description, image_url, image_auteur, image_licence, drapeau_url, unesco_culturel, unesco_naturel, unesco_mixte, unesco_total, zones_protegees_pct, densite_hab_km2, foret_pct, cotes_km, sans_littoral, superficie_terres_km2, lat_centre, pop_urbaine_pct, pop_villes_1m_pct, rnb_hab_usd, niveau_prix, budget_dispo, budget_moyen_usd_jour, wikidata_qid, dans_quiz` (+ une colonne `annee_…` par indicateur).

### `visas.csv`
`passeport_iso3, destination_iso3, statut, jours, date_verification`. Valeurs de `statut` : `sans_visa`, `visa_arrivee`, `eta`, `e_visa`, `visa_requis`, `interdit`.

### Historique des visas
- `visas_historique_comptes.csv` : `passeport_iso3, date, source, format, sans_visa, visa_arrivee, eta, e_visa, visa_requis, covid_ban, interdit, sans_demarche, demarche, entree_interdite, total, ecart_jours, trou_avant`.
  - `sans_demarche` = `sans_visa` + `visa_arrivee`.
  - `demarche` = eTA + e-visa + visa requis.
  - `entree_interdite` = Covid + interdit.
  - `trou_avant = true` : plus de 100 jours depuis la version précédente, donc la courbe ne relie pas les deux points (pointillés).
- `visas_historique.json` : `codes` (199, ordre des lignes et des colonnes), `statuts` (lettre → statut et classe historique), `classes_historiques`, `photos` (`annee, date, source, commit, format, detail_fiable, matrice`). `matrice[i × 199 + j]` = passeport `codes[i]` vers `codes[j]`. Les lettres : S sans visa, A visa à l'arrivée, T eTA, E e-visa, R visa requis, C Covid, I interdit, - même pays.
- `visas_historique_annuel.csv` : `passeport_iso3, destination_iso3, annee, statut, jours`.

### `unesco_sites.csv`
`iso3, id_unesco, categorie (culturel | naturel | mixte), nom_fr, langue_nom (fr | mul | wikifr | en), wikidata_qid, regle_choix (exact | revision | extension | global_… | manuel), departage (aucun | partie_de | titre_unesco | douteux | correction), annee_inscription, transfrontalier, lien_unesco, source_nom, source_annee`. Une ligne par pays et par site : un site transfrontalier apparaît une fois par pays concerné (56 lignes). `source_nom` et `source_annee` donnent le lien permanent de l'article Wikipédia quand la valeur en vient. Vides : la valeur vient de l'élément Wikidata. `lien_unesco` est un simple lien vers la fiche.

### `budget.csv`
`iso3, niveau (petit|moyen|confort), categorie (hebergement|transport|repas|activites), montant_usd_jour, total_site_usd, source_url, date_releve, date_maj_site`.

### `scores.csv`
`iso3, score_culture, score_nature, score_villes, score_prix, score_distance, score_mer, distance_paris_km, date_calcul`.

## 4. Sources et méthodes de collecte

| Donnée | Source | Méthode | Licence / remarque |
|---|---|---|---|
| Visas | Passport Index (dépôt GitHub imorte/passport-index-data, données du 18/02/2026) | téléchargement CSV + nettoyage | MIT |
| Historique des visas | Passport Index : historique Git d'ilyankou/passport-index-dataset (56 versions, 17/04/2019 → 12/01/2025, commit figé `e111423`) | `git show` de chaque version + décodage de 4 formats | MIT ; dépôt archivé |
| Vérification des visas | France Diplomatie, fiches « Entrée / séjour » (sept.-oct. 2026), europa.eu pour l'UE | vérification manuelle des 40 destinations du passeport français | 38/40 concordantes, 2 corrigées (Thaïlande 30 j, Sri Lanka ETA). S'y ajoute 1 correction hors passeport français : Canada → Sénégal = visa requis (réciprocité annoncée en août 2025) |
| Capitales, GPS, images, drapeaux, UNESCO | Wikidata (SPARQL, query.wikidata.org) + Wikimedia Commons (API) | requêtes SPARQL | CC0 / licences des photos conservées |
| Indicateurs | Banque mondiale (API WDI) : `ER.LND.PTLD.ZS`, `EN.POP.DNST`, `AG.LND.FRST.ZS`, `SP.URB.TOTL.IN.ZS`, `EN.URB.MCTY.TL.ZS`, `NY.GNP.PCAP.CD`, `PA.NUS.PPP`, `PA.NUS.FCRF` | API REST JSON | CC BY 4.0, séries mises à jour le 08/10/2026 |
| Noms, ISO2, drapeaux et RNB des 199 pays | Wikidata (SPARQL) + Banque mondiale via **Data360** (data360api.worldbank.org, même série `NY.GNP.PCAP.CD`) | requête SPARQL + API REST paginée | CC0 / CC BY 4.0 ; extraction du 17/11/2026. Drapeaux : règle ONU (section 5) |
| Noms et années des sites UNESCO | Wikidata : libellés (fr, puis multilingue, puis titre Wikipédia en français, puis en) et désignation « patrimoine mondial » (P1435 = Q9259, date de début P580) | SPARQL sur les éléments déjà relevés le 16/10 | CC0 ; années contrôlées sur deux échantillons de whc.unesco.org (2 × 10/10 identiques le 17/11) |
| Corrections des sites UNESCO | Wikipédia en français : titres d'articles (liens Wikidata, listes « Patrimoine mondial en… »), infobox, catégories « inscrit en <année> » | API MediaWiki, relevé du 18/11/2026, lien permanent par valeur | CC BY-SA, attribution à mettre dans les licences. 37 noms et 15 années. Les fiches whc.unesco.org servent seulement à vérifier (15 années sur 15 identiques) et à départager des éléments Wikidata : rien n'en est publié (cache non commité) |
| Budget | Budget Your Trip (pages mises à jour en 2026) | copier-coller des tableaux, extraction par script (20 pays relevés via IA, 21 collés à la main) | relevé du 16/10/2026 |
| Fond de carte | Natural Earth v5.1.2, `ne_10m_admin_0_countries_fra` (point de vue de la France), dépôt nvkelso/natural-earth-vector | téléchargement (URL figée + SHA-256) + jointure + mapshaper | domaine public ; préparé le 17/11/2026 |
| Côtes, surface, latitude | CIA World Factbook, copie archivée github.com/factbook/factbook.json (la CIA a arrêté le Factbook en février 2026) | téléchargement JSON + lecture du texte (« 29,751 km ») | domaine public ; le Vietnam est compté sans ses îles |
| Salaires (écartés) | ILOSTAT `EAR_EHRA_SEX_CUR_NB_A` | téléchargement bulk | voir les décisions |

Quatre méthodes de collecte différentes (5 sources) : téléchargement, API REST, SPARQL, relevé manuel.

### Fond de carte : la commande mapshaper et ses réglages (`build_carte.py`)

```
npx --yes mapshaper@0.7.101 -i data/raw/natural_earth/carte_avant_simplification.geojson
    -clean
    -simplify visvalingam weighted 25% keep-shapes
    -rename-layers pays
    -o format=topojson quantization=400000 data/carte/pays_carte.topojson
```

Avant mapshaper, le script Python fait :
- le téléchargement, avec contrôle de l'empreinte SHA-256 ;
- la jointure sur `ADM0_A3` ;
- les propriétés de chaque entité (`iso3`, `adm0_a3`, `nom_fr`, `couvert`, `souverain`, repère).

Après mapshaper, il relit la TopoJSON pour les contrôles et regroupe le repère en un seul champ `[lon, lat]`. Voici ce que fait chaque réglage, et pourquoi :

| Réglage | Ce qu'il fait | Pourquoi cette valeur |
|---|---|---|
| `mapshaper@0.7.101` | version figée (29/10/2026) | la série 0.8 date de la semaine du 15/11 : trop récente pour s'y fier |
| `-clean` | répare la géométrie : supprime les fines bandes vides entre voisins (« slivers »), les chevauchements et les auto-intersections | ici, 4 bandes sur 9 supprimées, et les 249 entités gardées |
| `-simplify visvalingam` | retire d'abord les points qui forment les plus petits triangles avec leurs voisins, c'est-à-dire les détails les moins visibles | garde mieux l'allure des côtes que Douglas-Peucker |
| `weighted` | pénalise les angles aigus, pour des contours plus lisses | réglage conseillé par mapshaper pour les cartes |
| `25%` | garde 25 % des points (547 351 → 123 924) | **mesuré** : à 6 %, des îles de plus de 500 km² disparaissaient ; à 25 %, toutes les îles de plus de 100 km² restent, pour environ 1 Mo |
| `keep-shapes` | empêche un **pays** de disparaître entièrement (au moins une forme gardée par entité) | ça ne protège pas chaque **île** : 1 495 îlots sur 4 253 polygones sont retirés, tous de moins de 100 km² (contrôle bloquant au-delà) |
| simplification **topologique** | mapshaper simplifie une seule fois chaque frontière commune à deux pays | donc ni trou ni chevauchement entre voisins, contrairement à une simplification pays par pays |
| `format=topojson` | chaque frontière n'est stockée qu'une fois (« arcs » partagés), avec des coordonnées entières codées en différences | fichier beaucoup plus léger que le GeoJSON |
| `quantization=400000` | arrondit les coordonnées à une grille de 1/400 000 de l'étendue (environ 100 m) | à 100 000 (environ 400 m), le Vatican était écrasé en un segment d'aire nulle, que D3 peut dessiner comme « le globe entier » |

**Taille** : 12 916 Ko brut / 4 618 Ko compressé (gzip) avant, **1 246 Ko brut / 418 Ko compressé** après.

**Contrôles bloquants du script** :
- les 199 codes sont présents, une seule fois ;
- aucune entité n'est vide après simplification ;
- aucune île de 100 km² ou plus n'est perdue ;
- tous les contours extérieurs sont dans le sens horaire, comme D3 l'attend ;
- l'empreinte SHA-256 de la source est conforme.

## 5. Décisions et justifications (à reprendre dans la section technique)

- **41 pays, sélection figée (décision du 18/11) : on n'ajoute aucun pays.** Les 41 pays ont été choisis pour couvrir tous les continents et tous les types de voyage, pas pour suivre un classement de popularité. Ils sont répartis par quotas par continent (10 Europe, 10 Asie, 3 Moyen-Orient, 7 Afrique, 9 Amériques, 2 Océanie), avec une diversité de prix. Biais assumé : moins de pays africains. Les trous connus sont listés en section 7. La carte des visas couvre, elle, 199 pays.
- **UNESCO** : comptage par numéro de site (les extensions `80bis`, `80ter` et les composantes `868-001`… ne comptent qu'une fois) et 5 corrections documentées. **Contrôle : 8 pays sur 8 identiques aux chiffres officiels** (France, Espagne, Italie, Japon, Chine, Afrique du Sud, Brésil, Australie). 
- **Aucun contenu repris de whc.unesco.org (décision du 18/11).** Les conditions de l'UNESCO réservent la réutilisation d'une partie substantielle de sa base à un accord écrit. Les noms viennent donc de Wikidata (CC0) ou de Wikipédia en français (CC BY-SA, avec le lien de l'article), et les fiches servent seulement à vérifier et comme lien. `unesco_sites.csv` peut ainsi entrer dans le ZIP. Les anciens titres restent dans l'historique Git : on ne le réécrit pas.
- **Arrivées touristiques retirées** : la série s'arrête en 2020 (Covid), les années ne sont pas comparables, et les définitions varient (la France compte les visiteurs à la journée).
- **Salaires ILOSTAT écartés** : 7 pays manquants (dont le Japon, la Chine et l'Australie), des sources mélangées (enquête ménages / registres), des années de 2017 à 2025, des incohérences (l'Espagne au-dessus de la France, l'Afrique du Sud à 1,38 $/h). Remplacés par le **revenu national brut par habitant** (Banque mondiale), complet et homogène. Sur la page, on parlera de « jours de revenu moyen », pas d'« heures de travail ».
- **Indice du niveau des prix** = PPA / taux de change (États-Unis = 1). Il sert à l'axe « prix » du quiz. **Corrélation de rang de 0,84** avec les budgets Budget Your Trip sur 41 pays : les deux sources indépendantes concordent. 3 pays mélangent 2024 et 2025 (Vietnam, Tanzanie, Émirats), effet négligeable.
- **Budget** : somme des 4 catégories utilisée, parce que les totaux du site ne s'additionnent pas (Sénégal -55 %, Turquie +29 %, Kenya +17 % ; vérifié mot pour mot). **Argentine exclue** de la visualisation 3 : repas à 5,71 $ par jour, invraisemblable (prix en pesos non actualisés après l'inflation). Elle reste dans le quiz.
- **Capitales** : Pretoria pour l'Afrique du Sud (siège du gouvernement), Colombo pour le Sri Lanka.
- **Drapeaux (17/11) : le drapeau reconnu par l'ONU quand il existe, sinon celui de Wikidata.**
  - Wikidata donne le drapeau en usage. Il ne diffère de celui de l'ONU que pour l'**Afghanistan** : Wikidata donne celui des talibans, alors que le siège à l'ONU reste à la République islamique. On impose donc le drapeau de 2013-2021 (`DRAPEAUX_IMPOSES` dans `build_pays_monde.py`). Piège : sur Commons, « Flag of Afghanistan.svg » redirige vers le drapeau des talibans, donc il faut le nom exact du fichier.
  - Les pays qui ne sont pas membres de l'ONU (Taïwan, Kosovo) gardent le drapeau de Wikidata.
  - Les observateurs (Palestine, Vatican) gardent aussi celui de Wikidata, qui est leur drapeau officiel.

  On ne prend pas position : on suit l'institution de référence, et on retombe sur l'usage quand elle ne dit rien.
- **Revenus anciens = indisponibles (17/11).** Une valeur de plus de 5 ans n'est **pas** comparée aux valeurs de 2025 : guerres (Yémen, Soudan du Sud), crises monétaires et inflation (Cuba) la rendent trompeuse. Ces 5 pays sont traités comme les 4 pays sans valeur : « revenu indisponible », pas de grille. On garde la dernière valeur connue et son année pour l'infobulle, par transparence. Colonne `rnb_utilisable` dans `pays_monde.csv`.
- **« Pays sans démarche avant le départ » (17/11) = sans visa + visa à l'arrivée.** C'est la même définition partout : le compteur du globe en 2026, la courbe, l'historique.
  - C'est la seule mesure stable dans les quatre formats du jeu de données. La frontière entre eTA, e-visa et visa requis, elle, change avec le format : pas d'e-visa avant novembre 2020, et les eTA sont comptées avec les e-visas jusqu'en décembre 2024.
  - Le libellé n'est pas « sans visa », parce que le visa à l'arrivée est souvent payant.
  - Le compte strict « sans visa » reste dans l'infobulle.
- **Couleurs du globe en mode historique (17/11) : des classes comparables sur toute la période.**
  - sans visa ;
  - visa à l'arrivée ;
  - démarche avant le départ (eTA, e-visa et visa requis regroupés) ;
  - **plus une classe « entrée interdite »** (interdiction Covid, « no admission »). Elle ne pouvait entrer dans aucune des trois : jusqu'à 12 362 paires en janvier 2021.
    - La **raison** est dans l'infobulle : « restrictions Covid » ou « entrée interdite par le pays » (champ `raison` du JSON). En 2026, les 48 cas ne sont pas le Covid.
    - Sur le globe, elle aura **une couleur bien distincte du gris des territoires non couverts**, pour ne pas confondre « interdit » et « pas de données ».

  Le détail en 5 classes (sans visa, visa à l'arrivée, eTA, e-visa, visa requis) ne s'affiche que pour 2026 : champ `detail_fiable` du JSON.
- **Une photo par année pour le curseur du globe** : la première version de chaque année (17/04/2019, 13/01/2020, 25/01/2021, 05/01/2022, 11/01/2023, 05/01/2024, 02/01/2025, 18/02/2026). La courbe, elle, utilise les 57 versions.
- **Fond de carte (17/11) : point de vue de la France de Natural Earth, échelle 10m, simplifiée.** La vue par défaut suit les frontières de fait (Crimée dans la Russie, Somaliland séparé), et il n'existe pas de vue « ONU ». La vue de la France est cohérente avec un site en français et avec les vérifications faites sur France Diplomatie : Crimée en Ukraine, Somaliland dans la Somalie, Kosovo et Taïwan présents. **Limite à écrire sur la page** : le Sahara occidental y est rattaché au Maroc, ce qui suit la position française et non celle de l'ONU.
- **Descriptions** : 41 textes de 2 phrases, rédigés avec l'IA, à relire.

## 6. Formule du quiz

**6 axes, chacun ramené de 0 à 100 par rapport aux 41 pays** (le plus fort = 100) :

| Axe | Calcul |
|---|---|
| Culture | log(1 + sites UNESCO culturels + mixtes) |
| Nature | ½ « espaces naturels » + ¼ UNESCO naturels et mixtes (log) + ¼ zones protégées. « Espaces naturels » = le meilleur des deux entre faible densité (log) et forêt (% des terres) : grands espaces vides (Islande) **ou** pays peuplé mais très vert (Japon) |
| Villes | % de la population dans les villes de plus d'un million d'habitants |
| Prix | −log(niveau des prix) : 100 = le moins cher |
| Distance | distance à vol d'oiseau Paris → capitale (haversine) |
| Mer | chaleur × (½ log longueur des côtes + ½ log côtes par km² de terres). Chaleur : 1 jusqu'à 30° de latitude, 0 à partir de 60°, proportionnel entre les deux. Sans accès à la mer → 0 |

**Comparaison joueur / pays (« le pays qui te ressemble »)** :
- chaque réponse du quiz pousse un ou plusieurs axes vers une valeur souhaitée, avec un poids ;
- profil du joueur : valeur = moyenne pondérée ; importance = min(1, poids cumulé / 1,5) × |valeur − 50| / 50. Une envie tiède compte peu ;
- ressemblance (%) = 100 × (1 − √(Σ importance × écart² / Σ importance × 100²)).

**Tests effectués** :
- 8 profils types donnent 6 pays différents, tous logiques (villes et culture, loin → Japon ; nature sauvage → Islande ; petit budget → Indonésie ; culture, pas loin → Italie ; prix seul → Égypte ; plage et petit budget → Indonésie, Sri Lanka, Vietnam ; plage pas loin → Grèce ; villes et campagne verte → Japon) ;
- simulation des 27 648 combinaisons du prototype : le Brésil, « bon partout », gagnait 32 % des parties avec la formule de base. Avec le correctif, il en gagne 23 %, et 40 pays sur 41 peuvent apparaître dans le top 3 ;
- **avec 6 axes et 9 questions** (110 592 combinaisons, 16/10/2026) : le Japon gagne 19,9 % des parties, le Brésil 12,4 %, l'Indonésie et la Grèce 7,5 % ; 35 pays peuvent gagner, 37/41 apparaissent dans un top 3 (jamais : Suisse, Jordanie, Kenya, Ghana). Le Japon gagne surtout quand on combine les grandes villes avec autre chose (gratte-ciel + musées : 44 %), rarement en nature pure (lac + randonnée : 7,5 %). **À surveiller** : c'est le nouveau pays « bon partout » (villes 100, nature 95, mer 88). Variantes testées et rejetées : densité + forêt en moyenne (l'Islande tombe à 53 en nature), longueur des côtes seule (la Grèce passe derrière le Maroc et l'Égypte) ;
- **prototype** : https://claude.ai/artifact/U5FEve1vN8HjjCZf1zpjH1 (9 questions en cartes, dont une sur la mer, résultat avec radar à 6 axes). Le fichier est aussi dans `prototype/quiz-prototype.html` : il sert de référence pour la logique, pas pour le design.

## 6 bis. Projets similaires (vérifiés le 22/10/2026, à citer dans la présentation)

| Site | Fonctionnement | Différence avec notre quiz |
|---|---|---|
| [Voyasee](https://voyasee.com/destination-quiz/) | 12 questions fixes (6 en mode rapide), 600 destinations (villes, îles, régions), climat par mois via NASA POWER, formule affichée, radar et comparaison du top 3 | Le plus proche du nôtre. Questions non adaptatives, données de destination « curated » sans source publique, pas de téléchargement |
| [LOCALS Insider – Country Matcher](https://localsinsider.com/travel-tools/country-matcher/) | 6 questions fixes, 50 ou 53 pays (la page se contredit), le climat pèse le plus | Sources non citées, pas d'explication du calcul |
| [Odisé](https://www.odise.io/ou-partir-test) | 12 questions de personnalité, plus de 60 destinations, archétype + 3 destinations avec un texte explicatif | Profils sans source, test de personnalité |
| [Atlas Guide](https://www.atlas-guide.com/find-your-destination/) | 9 questions fixes, plus de 190 pays, explication écrite par une IA | Sources non nommées |

**Ce qui nous différencie vraiment** : questions adaptatives (aucun des 4 ne l'est), sources publiques citées et données téléchargeables en CSV, et le quiz relié à deux autres visualisations (visas, budget). Ne pas dire « personne ne l'a fait » : Voyasee fait déjà un quiz transparent avec radar.

Avis de ChatGPT reçu le 22/10 (« Akinator des pays », 100-150 pays × 30-50 critères, collecte des réponses des utilisateurs, modèle statistique) : **non retenu** pour ce projet. Trop grand pour un projet seul d'ici janvier, critères subjectifs (anime, ambiance), besoin d'un serveur et du consentement RGPD pour stocker des réponses, sources inadaptées (JNTO = Japon seulement ; arrivées touristiques déjà écartées). Idées gardées : expliquer chaque résultat, séparer faits et choix de calcul, questions adaptatives (déjà prévues).

## 7. Limites connues (à écrire sur la page)

- **La culture se limite aux monuments** : la cuisine, la culture populaire et les fêtes ne sont pas mesurées. C'est pour ça que le Japon (« grandes villes + monuments » pour nos chiffres) ne sort pas forcément pour quelqu'un qui l'aime pour d'autres raisons.
- **La mer mesure un potentiel, pas des plages** : beaucoup de côtes et une latitude chaude. Pas de différence entre sable et falaises, pas de réputation : le Japon (88) et le Chili (74, courant froid) sont surévalués, la latitude du centre du pays ignore la Floride ou le Queensland.
- **La nature** compte autant les grands espaces vides que les forêts. Les déserts peuplés sont pénalisés (Maroc 0, Égypte 14), la montagne n'est pas mesurée (la Suisse reste à 37). La forêt de la FAO inclut les savanes boisées (Sénégal 45 %).
- **Les zones protégées** sont gonflées en Europe par Natura 2000. **Les villes** : le Sri Lanka est à 0 à cause de sa définition statistique très étroite de Colombo.
- **Les visas** datent de février 2026, sauf pour le passeport français, vérifié en octobre 2026. Afficher la date sur la carte.
- **L'historique des visas a quatre formats successifs**. Deux pièges sont corrigés dans le script : en 2019, les codes 1 et 2 changent de sens entre deux formats ; et de février à mai 2020, les étiquettes « VOA » et « ETA » sont inversées dans les données elles-mêmes (France → États-Unis valait « visa à l'arrivée »). Six tests de bon sens bloquants vérifient chaque version. Les catégories eTA, e-visa et visa requis ne sont pas comparables d'une période à l'autre : d'où les classes regroupées.
- **Trois trous dans l'historique** : juin-octobre 2020 (194 jours sans version), mai-juillet 2023 (131 jours), janvier 2025-février 2026 (402 jours). La courbe les montre en pointillés.
- **Rupture de source en 2026** : ilyankou jusqu'en janvier 2025, puis imorte (février 2026) avec les corrections France Diplomatie. Mesuré le 17/11 :
  - imorte reprend exactement le vocabulaire d'ilyankou (même site source, mêmes 199 codes, eTA séparée) ;
  - en 13,2 mois, 2 761 paires changent de statut, soit 209 par mois, **moins** que le rythme habituel entre deux versions d'ilyankou en 2023-2024 (284 par mois). Rien n'indique donc une rupture de méthode ;
  - pour la France, on passe de 157 à 148 pays sans démarche. −8 viennent du temps et de la source : ce sont des changements réels et vérifiables, comme l'ETA britannique (avril 2025), l'ETA israélienne, l'e-visa en Mauritanie ou en Somalie, et le visa à l'arrivée en Namibie. −1 vient des corrections France Diplomatie (Sri Lanka : ETA).
  - Ce qu'on ne peut pas séparer : les deux sources n'ont aucune date en commun, donc un petit effet de méthode reste possible.
- **Les noms des sites UNESCO ne sont pas les noms officiels.** Ce sont les libellés de Wikidata (694 en français, 2 multilingues : Las Médulas, Caral) ou, pour 37 lignes, le titre d'un article de Wikipédia en français. Ces titres sont parfois plus courts ou plus larges que le site :
  - 17 articles portent sur le site lui-même ;
  - 10 portent sur son lieu ou son élément principal (Mycènes ne dit pas Tirynthe) ;
  - 10 sites n'ont pas d'article propre et prennent le titre de l'article de leur lieu (Diamantina, Yogyakarta…) ;
  - le monastère Sainte-Catherine (n° 954) est plus petit que la zone inscrite, et l'élément Wikidata de l'article sur Peruaçu (n° 1747) porte un autre numéro UNESCO (1035). Ces deux noms sont gardés.

  2 noms restent en anglais (libellés Wikidata, CC0) : le n° 1732 au Vietnam, sans article, et Hin Nam No pour la ligne du Laos du n° 951.
- **Les années d'inscription** : 15 manquaient dans Wikidata. Elles viennent de Wikipédia en français, avec le lien, et concordent toutes avec les fiches UNESCO. Une date antérieure à 1978 (la première liste) est écartée comme erreur : le Serengeti « 1960 » est en réalité inscrit en 1981. Pour un site partagé, l'année suit l'élément du pays : le n° 951 vaut 2003 pour le Vietnam et 2025 pour le Laos, qui l'a rejoint avec Hin Nam No.
- **Le fond de carte** suit le point de vue de la France : le Sahara occidental est rattaché au Maroc, ce qui suit la position française et non celle de l'ONU. Les départements d'outre-mer ont la couleur de la France, alors que leurs règles d'entrée diffèrent un peu. Les îlots de moins de 100 km² peuvent manquer, à cause de la simplification. Les 50 territoires sans passeport (Groenland, Porto Rico, Nouvelle-Calédonie…) sont en gris : Passport Index ne les couvre pas.
- **La sélection de 41 pays a des trous connus** (décision en section 5) : aucun pays des Caraïbes (le Mexique, la Colombie et le Costa Rica ont seulement une côte sur cette mer), une Afrique du Nord limitée au Maroc et à l'Égypte, et pas d'Allemagne (ni de Belgique, ni de Pays-Bas). Le quiz ne peut donc pas proposer ces pays. La carte des visas, elle, les couvre.
- **Les notes sont relatives** à la sélection de 41 pays.

## 7 bis. Le site : fil conducteur et visualisations (décidé le 03/11/2026, complété le 17/11/2026)

**Fil conducteur : « Où partir, et à quel prix selon d'où tu viens ».** Le passeport choisi par le visiteur change la carte des visas et le budget (en jours de revenu). Les trois visualisations restent **séparées** (une par section, chacune avec son interaction propre) et sont seulement reliées par des liens : sous le résultat du quiz, « Voir ce qu'il faut pour aller en [pays] » ouvre le globe avec ce pays déjà choisi, et « Voir le budget » ouvre le budget sur ce pays.

**Nom du site : Périple**, choisi parmi les noms courts proposés le 15/11 (Cap, Sésame, Escale, Départ, Périple, D'ici). Écartés : Atlas, Globe (trop courants), Tampon (double sens).

**Texte d'accueil retenu (version B, 17/11)** :
```html
<h2 class="visor-line visor-title">Où partir, et à quel prix ?</h2>
<p class="visor-line visor-text">Selon le passeport que tu as en poche, le même voyage ne demande ni les mêmes papiers ni le même effort. Trouve ton pays, regarde ce qu'il faut pour y entrer, puis ce qu'il te coûte vraiment.</p>
<div class="visor-line visor-cta"><a class="visor-btn btn btn--primary" href="destinations.html" data-magnetic="0.15">Trouver mon pays</a></div>
```
`destinations.html` est un nom provisoire : la page ouvre le quiz. **En attendant, le bouton pointe vers `prototype/quiz-prototype.html`.**

**Types de visualisation (5)** : radar, classement en barres, globe 3D, courbe dans le temps, grille de carrés + barres empilées.

### 1. Quiz → radar + classement
- Radar à 6 pointes (hexagone, un par critère) : profil du joueur contre profil du pays.
- **Révélation sur le classement lui-même** à la fin : les pays se rangent un par un jusqu'au résultat. Le globe n'est plus utilisé ici (décision du 17/11 : séparer le quiz et le globe). Pas de classement en direct pendant le quiz (ça gâcherait le suspense).
- Clic sur un pays du classement = radar mis à jour. **Classement triable par critère** après le résultat.
- **Mode « Et si… »** (après le résultat) : couper un critère (« et si le prix ne comptait pas ? ») ou changer son importance ; le classement se réorganise en direct avec une animation. Les curseurs n'apparaissent qu'après le quiz, jamais pendant.
- **« Pourquoi ce pays ? » : chaque pointe du radar est cliquable** et affiche le fait brut derrière la note : culture = nombre de sites UNESCO et leurs noms (`unesco_sites.csv` : sites culturels et mixtes ; pour la nature, sites naturels et mixtes) ; nature = % de forêt, densité, zones protégées ; villes = % de la population dans des villes de plus d'un million d'habitants ; prix = niveau des prix ; distance = km depuis Paris ; mer = km de côtes et latitude.
- **« Le saviez-vous ? » générés à partir des données**, jamais écrits à la main (pour ne rien inventer). Exemples tirés des données du 16/10 : « La Suisse est le 2ᵉ pays le plus cher de la liste, juste après l'Islande » ; « La Suisse fait partie des 4 pays sans accès à la mer ». Ce sont des phrases construites à partir des rangs et des seuils (le plus, le moins, parmi les N…), donc vraies par construction. **Elles devront gérer les égalités** : beaucoup de sites sont inscrits la même année (36 en 1987, 34 en 1997, 22 en 1979…), et plusieurs pays peuvent avoir le même nombre de sites. Par exemple, « parmi les plus anciens sites inscrits (1978) », jamais « le plus ancien » quand il y en a plusieurs. Les sites sans année sont exclus de ces phrases.
- Idées non retenues pour l'instant : « ce qui t'a rapproché / éloigné » (contributions de chaque critère) et photos supplémentaires des sites UNESCO.

### 2. Visas → globe 3D en WebGL (Three.js écrit à la main)
- **Three.js codé soi-même, pas globe.gl** : le but est d'apprendre (sélection des pays au clic par raycasting, couleurs par statut, transitions animées). Feu vert du prof pour les bibliothèques.
- **Accessibilité et performances obligatoires** : si WebGL n'est pas disponible, carte à plat en D3 à la place ; tout doit marcher au clavier avec une recherche de pays ; `prefers-reduced-motion` respecté (pas de rotation automatique).
- Le globe est sa propre section, séparée du quiz (on y arrive par le menu ou par le lien sous le résultat du quiz).
- On fait tourner le globe à la souris ; un clic sur un pays prend son passeport (on voit que les règles ne sont pas réciproques) ; au survol, statut et jours autorisés ; compteur « X pays sans démarche avant le départ » (sans visa + visa à l'arrivée ; le nombre strict « sans visa » est dans l'infobulle). Bouton « carte à plat ».
- **Fiche pays au clic** :
  - règles dans les deux sens (« toi chez eux », « eux chez toi ») ;
  - pour le passeport français, la note vérifiée sur France Diplomatie avec le lien et la date (`corrections_visas.csv`) ;
  - photo et description (41 pays) ;
  - courbe du nombre de pays sans visa pour ce passeport de 2019 à 2026.
- **Historique des visas 2019-2026** (fait le 17/11, `build_visas_historique.py`) : 56 versions de l'historique Git d'ilyankou (17/04/2019 → 12/01/2025) + la version 2026 du projet, soit 57 dates. **Passeport français, pays sans démarche avant le départ (dont sans visa)** : 159 (120) en avril 2019 ; 163 (120) en janvier 2020 ; 123 (95) en novembre 2020, avec 37 destinations interdites par le Covid ; 123 (98) en août 2021 ; 153 (122) en avril 2023 ; 157 (127) en janvier 2025 ; 148 (123) en février 2026. Usage : un curseur d'années sous le globe (8 photos, en classes comparables) et une courbe par passeport (57 points, en pointillés sur les trous). Ça corrige aussi le point faible « dates » du jeu de données.
- **Tampon de passeport stylisé** à la place d'une image de visa : dessiné en SVG à partir des données (pays, statut, durée), visiblement illustratif. Chaque pays cliqué ajoute un tampon au passeport virtuel du visiteur. Pas d'images de vrais visas : introuvables pour 199 pays, droits d'auteur, et imiter un document officiel ne se fait pas.

### 3. Budget → « combien de jours de revenu pour ce voyage »
- Grille de carrés : **un carré = un jour de revenu moyen** (RNB par habitant / 365) du pays de départ. Les carrés se remplissent quand on change les réglages.
- Réglages : pays de départ, destination, nombre de jours (curseur), niveau (petit, moyen, confort), nombre de voyageurs. Deux voyageurs côte à côte pour le même voyage.
- Détail au survol et en barres empilées (logement, transport, repas, activités), triables.
- Phrase calculée automatiquement, par exemple « Pour toi, ce voyage = 11 jours. Pour un habitant du Népal = presque un an. »
- Exemple vérifié sur nos données : 10 jours au Japon en budget moyen = 1 400 $ (140 $ par jour). France (RNB 48 630 $, 2025) : environ 11 jours ; Inde (2 760 $) : environ 185 jours ; Népal (1 570 $) : environ 326 jours.
- Limites à écrire sur la page : **billet d'avion non compté** (dépenses sur place seulement) ; **revenu moyen par habitant**, pas un salaire réel.
- RNB des 199 pays : fait (`pays_monde.csv`). Le pays de départ peut être n'importe lequel des 199. **Quand `rnb_utilisable = false` (9 pays), on affiche « revenu indisponible », sans grille de carrés.** L'infobulle donne « dernière valeur connue : X $ (année) » quand il y en a une (Cuba, Érythrée, Liechtenstein, Soudan du Sud, Yémen), sinon « aucune donnée » (Monaco, Corée du Nord, Taïwan, Vatican).

## 7 ter. Le site : ce qui est fait (accueil, novembre 2026)

**Déroulé de la page d'accueil** (orchestré par `main.js`) :
1. **Préchargeur** : des nuages couvrent l'écran, un compteur va de 0 à 100 % en suivant le vrai chargement (images, Three.js, modèle 3D). Test : `index.html?sim=4000` simule un chargement de 4 s.
2. **Choix d'entrée** à 100 % : « Entrer avec le son » ou « Entrer sans le son » (les navigateurs interdisent le son sans clic).
3. **Dispersion des nuages**, puis **chute de l'astronaute** (entrée par le haut, culbute, gestes, traits de vitesse) et freinage. Le paysage (4 plans) monte en parallaxe, qui suit la souris ou l'inclinaison du téléphone.
4. **Arrivée** : les petits textes apparaissent (« Periple » à gauche, « Scroll pour explorer » à droite), et le défilement est débloqué.
5. **Plongée au défilement** : la caméra entre dans la visière du casque, et le texte d'accueil (version B) apparaît dedans, avec le bouton « Trouver mon pays ».

**Choix techniques** :
- Three.js 0.187 (import map, CDN jsDelivr) avec un rendu toon écrit à la main : 2 tons, contour, ombres lissées, duotone. GSAP 3.15 et ScrollTrigger pour les animations, Lenis pour le défilement doux.
- Son en Web Audio API : la musique démarre à l'atterrissage et boucle entre 10 s et 42 s. Le vent est généré (bruit filtré selon la vitesse), la musique baisse quand le vent souffle fort, et le son est étouffé pendant la plongée dans le casque.
- **Accessibilité** : `prefers-reduced-motion` respecté (pas de Lenis ni d'animations des textes), parcours au clavier (Tab entre « Scroll pour explorer », le bouton son et « Trouver mon pays »), préchargeur en `role="progressbar"`, site visible même sans JavaScript.
- **Sécurité** : si la 3D échoue, le site se débloque quand même. Le préchargeur est retiré quoi qu'il arrive.
- **Déploiement** : la GitHub Action publie à chaque push sur `main`, sans `scripts/`, `data/raw/`, `data/intermediaire/` ni les `.md`.

**Reste à faire sur l'accueil** : `<main class="site">` est vide (les sections viendront ici) ; le tag affiche « Periple » sans accent (à vérifier : police ou choix voulu ?) ; `sounds/musique test.mp3` n'est pas utilisée mais elle est déployée (à supprimer ou à exclure).

## 8. Prochaines étapes (liste unique, mise à jour le 18/11/2026)

**Fait**
- [x] **Accueil du site** (voir 7 ter).
- [x] **Noms français, ISO2 et drapeaux des 199 pays** (Wikidata) → `pays_monde.csv`, avec `build_pays_monde.py`, le 17/11.
  - Les 199 pays ont un nom, un ISO2 et un drapeau. Ces deux colonnes sont sans doublon (contrôle bloquant).
  - Pour les 41 pays du quiz, le nom vient de `pays_liste.csv`.
  - Trois noms Wikidata sont raccourcis à la main : Pays-Bas (« Royaume des Pays-Bas »), Palestine (« État de Palestine »), Micronésie.
  - Le Kosovo est imposé (`Q1246`, ISO2 `XK`) parce qu'il n'a pas de code ISO officiel.
  - Drapeaux : règle ONU (voir section 5). L'Afghanistan a le drapeau de 2013-2021.
- [x] **RNB par habitant des 199 pays** (Banque mondiale, `NY.GNP.PCAP.CD`), dans le même fichier, le 17/11.
  - **Récupéré par Data360** (data360api.worldbank.org), la nouvelle API de la Banque mondiale, parce que l'ancienne API v2 renvoyait des erreurs 502 et des délais dépassés ce jour-là. C'est la même série WDI.
  - **Contrôle : les 41 pays du quiz ont exactement la même valeur et la même année que dans `pays.csv`.**
  - 190 pays sont utilisables (2022 à 2025). 9 sont « revenu indisponible » (`rnb_utilisable = false`) :
    - 5 valeurs de plus de 5 ans : Cuba 2019, Érythrée 2011, Liechtenstein 2009, Soudan du Sud 2015, Yémen 2018 ;
    - 4 sans valeur : Monaco, Corée du Nord, Taïwan, Vatican.

    Le Kosovo et la Palestine sont couverts. La règle d'affichage est dans la section 5.

**1. Fond de carte** (fait et validé le 17/11 avec `build_carte.py`)
- [x] Natural Earth v5.1.2, **point de vue de la France, échelle 10m** (`ne_10m_admin_0_countries_fra`). URL figée et empreinte SHA-256 vérifiée. Le fichier brut de 13 Mo n'est pas commité.
- [x] Jointure sur `ADM0_A3` : 196 codes identiques, 3 réglés par une table (`PSX`→`PSE`, `SDS`→`SSD`, `KOS`→`XKX`). **Aucun des 199 passeports ne manque sur la carte.**
- [x] 50 territoires sans passeport (Groenland, Porto Rico, Nouvelle-Calédonie…) et l'Antarctique sont en gris, avec le pays souverain dans les propriétés. Les noms faux de Natural Earth sont corrigés : les îles Spratleys s'appelaient « Wake ».
- [x] Simplification et nettoyage par mapshaper : la commande et ses réglages sont dans la section 4. **Les îles de plus de 100 km² sont toutes gardées.** Les îlots plus petits peuvent disparaître : `keep-shapes` protège chaque pays, pas chaque île.
- [x] **31 repères** pour les pays de **moins de 3 000 km²** sur la carte. Le seuil était de 2 500 km², il a été relevé le 17/11 pour inclure le Luxembourg et Samoa, comme prévu au départ. Les repères sont placés sur `LABEL_X` et `LABEL_Y`. La surface est mesurée sur la forme Natural Earth 10m, elle est donc proche de la surface réelle sans être identique (le Vatican y fait moins de 0,1 km²).

  | Pays | km² | Pays | km² | Pays | km² |
  |---|---:|---|---:|---|---:|
  | Vatican | < 0,1 | Saint-Christophe-et-Niévès | 265 | Tonga | 605 |
  | Monaco | 19 | Malte | 326 | Sainte-Lucie | 607 |
  | Tuvalu | 23 | Grenade | 349 | Micronésie | 637 |
  | Nauru | 29 | Saint-Vincent-et-les-Grenadines | 369 | Bahreïn | 689 |
  | Macao | 30 | Seychelles | 438 | Dominique | 733 |
  | Saint-Marin | 60 | Barbade | 446 | Kiribati | 954 |
  | Maldives | 109 | Andorre | 452 | Hong Kong | 1 039 |
  | Liechtenstein | 137 | Antigua-et-Barbuda | 453 | Sao Tomé-et-Principe | 1 042 |
  | Îles Marshall | 166 | Palaos | 494 | Comores | 1 679 |
  | | | Singapour | 513 | Maurice | 2 020 |
  | | | | | Luxembourg | 2 600 |
  | | | | | Samoa | 2 791 |

  **À régler sur le globe** : en vue entière, les repères européens (Monaco, Vatican, Saint-Marin, Liechtenstein, et aussi Andorre, le Luxembourg et Malte) se chevauchent. Ceux des Petites Antilles aussi. Deux pistes : les **regrouper** en un seul point qui s'ouvre au clic ou au zoom, ou les **afficher selon le zoom** (un repère n'apparaît que lorsqu'il est assez loin de ses voisins à l'écran). La recherche au clavier reste toujours possible.
- [x] `data/carte/correspondance_carte.csv` et le rapport.
- [x] Page de test `prototype/carte-test.html` vérifiée par Aryann le 17/11.

**2. Historique des visas 2019-2026** (fait le 17/11)
- [x] `build_visas_historique.py` : 56 versions d'ilyankou (le commit du 28/10/2019, qui supprime le fichier, est ignoré) + 2026. Quatre formats décodés, et les deux inversions de codes corrigées. **Six tests de bon sens et le contrôle des 39 402 paires passent sur les 57 versions.**
- [x] Définition unique : « pays sans démarche avant le départ » = sans visa + visa à l'arrivée (section 5).
- [x] Classes du globe en mode historique (sans visa, visa à l'arrivée, démarche, entrée interdite), et le détail en 5 classes seulement pour 2026 (`detail_fiable`).
- [x] Les trous sont repérés (`trou_avant`, au-delà de 100 jours) : 19/11/2020, 15/08/2023, 18/02/2026.
- [x] Rupture de source 2025 → 2026 mesurée (section 7).
- [x] Fichiers : `visas_historique_comptes.csv` (859 Ko), `visas_historique.json` (312 Ko), `visas_historique_annuel.csv` (8 Mo, pour le ZIP), `visas_historique_sources.csv`.

**3. Noms français des sites UNESCO**, pour « Pourquoi ce pays ? » (fait le 17/11, à finir)
- [x] Réorganisation de `build_pays_wikidata.py` : `sites_unesco()` donne le détail des sites, et `compter_unesco()` s'appuie dessus. `test_comptage_unesco.py` retombe exactement sur `pays.csv` (41 pays, 735 sites), avant et après (commit séparé).
- [x] `build_unesco_noms.py` → `unesco_sites.csv` : 735 sites nommés, des comptes identiques à `pays.csv` (contrôle bloquant).
  - Choix de l'élément : 680 avec l'identifiant exact, 46 avec une révision (`228rev`), 9 avec une extension (`311bis`). Aucun n'a eu besoin de la recherche dans tout Wikidata.
- [x] Années d'inscription : la plus ancienne date de « patrimoine mondial » parmi les éléments du site. Elles vont de 1978 à 2026. **10/10 identiques** à whc.unesco.org sur un échantillon tiré au hasard. 15 sites sans année.
- [x] **Départage des 49 sites qui ont plusieurs éléments avec l'identifiant exact**, en trois étapes. On avait relevé 28 vraies erreurs (le monument célèbre choisi au lieu de l'ensemble inscrit) :
  1. **Règle Wikidata « fait partie de » (P361) / « contient » (P527)** : on écarte le candidat qui fait partie d'un autre. Elle corrige **13 erreurs** (Versailles, Acropole, Stonehenge-Avebury, Venise et sa lagune, Zones historiques d'Istanbul…, plus l'atoll das Rocas, qui n'était pas repéré). Mais elle **se trompe de sens dans 2 cas** : Lamu et l'ESMA, où Wikidata range le site inscrit comme une partie du lieu célèbre.
  2. **Ressemblance avec le titre de la fiche UNESCO** (anglais et français, seuil 0,6) pour les sites où il reste plusieurs candidats. Elle corrige **12 erreurs** de plus (Vézelay, Carnac, Macao, Mompox, Cilento…). Le titre n'est jamais publié.
  3. **`corrections_unesco_noms.csv`** pour la fin : Lamu et l'ESMA (élément imposé), Bali (aucun élément ne représente le site), et les 2 départages douteux (Bath, Budj Bim).

  Les 28 erreurs sont donc corrigées. Vérone et Brasilia, que j'avais prises pour des erreurs, sont justes : les titres officiels sont « City of Verona » et « Brasilia ».
- [x] **Remplacement des contenus UNESCO par Wikipédia en français (18/11)**, avec `build_unesco_wikipedia.py`. `corrections_unesco_noms.csv` garde 54 lignes : 37 noms, 15 années et 3 éléments imposés ou retirés, chacun avec un lien permanent vers l'article. Aryann a validé les titres de lieux et les cas particuliers.
- [x] Contrôles du 18/11 : seuls les sites visés changent, aucune année ne bouge, le comptage retombe sur `pays.csv`, les 15 années concordent avec les fiches et les 52 liens permanents sont valides.
- [x] Résultat : 735 sites, **tous avec un nom et une année** (de 1978 à 2026). Les noms : 694 libellés français de Wikidata, 37 titres de Wikipédia, 2 libellés multilingues, 2 libellés anglais.
- [ ] La page et le fichier des licences diront que les noms viennent de Wikidata et, pour 37 d'entre eux, de Wikipédia (CC BY-SA).

**4. Allemagne, Belgique, Pays-Bas** (tranché le 18/11 : on ne les ajoute pas)
- [x] La sélection reste à 41 pays (raison en section 5, trous connus en section 7).

**5. Téléchargement des données (3 points)**
- [ ] Un **dictionnaire des données** : chaque colonne, avec son unité, sa source et son année.
- [ ] Un **fichier des licences et crédits**. Passport Index est sous licence MIT, qui oblige à joindre la notice de copyright. La Banque mondiale (CC BY 4.0) demande une attribution. Les photos ont un auteur et une licence. Le CIA Factbook est dans le domaine public. Il faut aussi les crédits de Natural Earth (domaine public) et de Wikipédia (CC BY-SA, pour les 37 noms et les 15 années des sites UNESCO).
- [ ] **Budget Your Trip : vérifier leurs conditions d'utilisation** avant de redistribuer `budget.csv` et `saisie_budget.csv`. Au minimum, citer clairement la source dans le fichier.
- [ ] Le **ZIP** des CSV.

**6. Quiz final**
- [ ] Réécrire les questions pour qu'elles soient plus amusantes : 10 à 12 questions (duels, situations, images), avec des choix qui coûtent, et la même logique de calcul.
- [ ] Les photos des duels, prises sur Wikimedia Commons, avec l'auteur et la licence.
- [ ] La simulation de toutes les combinaisons : aucun pays au-dessus de 12 % des parties, et au moins 38 pays sur 41 dans un top 3.

**7. Le site**
- [ ] La structure de `<main>` : quiz, globe des passeports, budget, section technique, téléchargement.
- [ ] Bibliothèques : Three.js pour le globe ; D3 pour le radar, le classement, la courbe, la grille de carrés et la carte de secours ; topojson-client pour lire le fond de carte.
- [ ] Une visualisation à la fois, testée avant de passer à la suivante.
- [ ] L'introduction et la section technique à rédiger, puis le déploiement sur GitHub Pages.

**8. À faire à la main (Aryann)**
- [ ] Relire les 41 descriptions.
- [ ] Choisir de meilleures photos pour 5 à 10 pays.

**9. Prépositions des noms de pays : en dernier**
- [ ] D'abord **tourner les phrases pour s'en passer** (« Départ : Népal », « Destination : Japon »). Un tableau de 199 prépositions écrit à la main (« au Japon », « aux Philippines », « à Singapour »…) risque de contenir des erreurs. On ne le fera que si une phrase ne peut vraiment pas s'écrire autrement.

**Secondaire**
- [ ] Monnaie du budget : si on affiche les montants en euros, il faut un taux USD → EUR daté, noté dans le dictionnaire.
- [ ] Visas : regarder si une version de Passport Index plus récente que février 2026 existe. La mise à jour obligerait à refaire les vérifications sur France Diplomatie, donc ce n'est pas prioritaire.

**Rien à collecter** : les « Le saviez-vous ? » et le mode « Et si… » utilisent les données qu'on a déjà.

**Décision du 16/10/2026 : on fige les 6 critères.** Langue et climat ont été étudiés puis écartés :
- **langue** : avec les langues officielles, l'Inde (anglais officiel, alphabet latin pour l'anglais) obtient le même dépaysement que les États-Unis, ce qui est absurde ; le Maroc, où le français est très parlé sans être officiel, serait compté comme très dépaysant ;
- **climat par mois** : une seule ville par pays ment pour les grands pays (Canberra en juillet est froide, le nord de l'Australie est chaud), et choisir plusieurs villes à la main serait subjectif ;
- **cuisine, culture pop** : aucune donnée objective et réutilisable.
Un critère approximatif qui produit des résultats absurdes coûte plus de crédibilité qu'il n'apporte de réalisme.

**Le Japon trop souvent gagnant (19,9 %) se corrige dans les questions, pas dans les données** : les réponses actuelles disent surtout ce qu'on veut, rarement ce qu'on ne veut pas, donc un pays fort partout gagne. Les nouvelles questions devront contenir des choix qui coûtent (« animé ou calme », « cher mais confortable ou simple et bon marché »). **Objectif à vérifier par la simulation : aucun pays ne gagne plus de 12 % des parties**, et au moins 38 pays sur 41 peuvent apparaître dans un top 3.

Choix validés pour le quiz final : questions fun (duels de photos, mises en situation), quiz qui s'adapte (mode rapide environ 8 questions, mode précis environ 15), révélation animée du classement à la fin (pas pendant : ça gâcherait le suspense), résultat partageable avec « le pays qui te ressemble le moins ». Pas de test avec la classe.

Question ouverte : garder la France dans les résultats du quiz (décision actuelle : oui) ?
