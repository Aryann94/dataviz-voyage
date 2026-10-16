# Dataviz voyage : récapitulatif du projet (phase données terminée)

*Mis à jour le 16 octobre 2026. Document de passation pour les conversations suivantes et base de la section technique.*

## 1. Le projet en bref

- **Cours** : Web Graphique (DMA1EDA7), M1, Everardo Reyes. Rendu : lien GitHub, entre le 11 décembre 2026 et le 15 janvier 2027.
- **Barème /20** : présentation (5), explication technique (5), interactivité, avec 3 visualisations différentes et fonctionnelles (7), partage des données en CSV/XLS (3).
- **Contraintes** : HTML, CSS et JavaScript « vanilla », bibliothèques légères autorisées (D3, Chart.js, Leaflet), aucun CMS. Couleurs pas trop vives. Travail en solo. IA autorisée par le prof, à condition de savoir expliquer le travail.
- **Sujet** : le voyage. Trois activités sur la page :
  1. **Quiz « Quel pays pour moi ? »** : questions en cartes, puis le pays qui ressemble le plus au joueur, avec un **radar** de comparaison.
  2. **Carte des passeports** : choisir un passeport et voir le monde coloré selon les visas (199 pays).
  3. **Budget d'un voyage** : répartition du budget quotidien (hébergement, transport, repas, activités) et effort relatif (jours de revenu moyen).
- **Dépôt** : https://github.com/Aryann94/dataviz-voyage (public). Dossier local : `C:\Users\malik\Downloads\dataviz-voyage`. Futur site : `aryann94.github.io/dataviz-voyage`.

## 2. Les fichiers

```
dataviz-voyage/
├── data/
│   ├── pays.csv                 FINAL - 1 ligne par pays (41), 33 colonnes : faits bruts
│   ├── scores.csv               FINAL - notes du quiz 0-100 (5 axes) + distance depuis Paris
│   ├── visas.csv                FINAL - 39 402 paires passeport -> destination
│   ├── budget.csv               FINAL - format long : pays x niveau x catégorie (40 pays)
│   ├── pays_liste.csv           saisie manuelle : les 41 pays, nom, région, choix de capitale/photo
│   ├── descriptions_pays.csv    saisie manuelle : 41 textes de présentation
│   ├── saisie_budget.csv        relevé Budget Your Trip (format large)
│   ├── corrections_visas.csv    41 vérifications manuelles avec source et date
│   ├── corrections_unesco.csv   5 corrections justifiées du comptage UNESCO
│   ├── intermediaire/           sorties par source (Wikidata, Banque mondiale, ILOSTAT)
│   └── raw/                     réponses brutes des API et fichiers téléchargés (traçabilité)
└── scripts/                     Python, bibliothèque standard (+ certifi)
```

**Ordre d'exécution** (depuis la racine, `py` sous Windows) :
1. `build_visas.py` : télécharge Passport Index, convertit et applique `corrections_visas.csv` → `visas.csv`
2. `build_pays_wikidata.py` : SPARQL Wikidata (capitales, GPS, images, drapeaux, UNESCO) et API Commons (crédits photos)
3. `build_pays_banquemondiale.py` : API Banque mondiale, 7 indicateurs
4. `build_pays_ilostat.py` : salaires ILOSTAT. **Testé puis écarté**, gardé comme preuve.
5. `import_budget_collage.py` puis `build_budget.py` : budget Budget Your Trip → `budget.csv`
6. `build_pays.py` : assemble `pays.csv`, avec des contrôles bloquants
7. `build_scores.py` : calcule `scores.csv` et teste 5 profils de voyageurs

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
`iso3, iso2, nom_fr, region, capitale, lat, lon, description, image_url, image_auteur, image_licence, drapeau_url, unesco_culturel, unesco_naturel, unesco_mixte, unesco_total, zones_protegees_pct, densite_hab_km2, pop_urbaine_pct, pop_villes_1m_pct, rnb_hab_usd, niveau_prix, budget_dispo, budget_moyen_usd_jour, wikidata_qid, dans_quiz` (+ une colonne `annee_…` par indicateur).

### `visas.csv`
`passeport_iso3, destination_iso3, statut, jours, date_verification`. Valeurs de `statut` : `sans_visa`, `visa_arrivee`, `eta`, `e_visa`, `visa_requis`, `interdit`.

### `budget.csv`
`iso3, niveau (petit|moyen|confort), categorie (hebergement|transport|repas|activites), montant_usd_jour, total_site_usd, source_url, date_releve, date_maj_site`.

### `scores.csv`
`iso3, score_culture, score_nature, score_villes, score_prix, score_distance, distance_paris_km`.

## 4. Sources et méthodes de collecte

| Donnée | Source | Méthode | Licence / remarque |
|---|---|---|---|
| Visas | Passport Index (dépôt GitHub imorte/passport-index-data, données du 18/02/2026) | téléchargement CSV + nettoyage | MIT |
| Vérification des visas | France Diplomatie, fiches « Entrée / séjour » (sept.-oct. 2026), europa.eu pour l'UE | vérification manuelle des 40 destinations du passeport français | 38/40 concordantes, 2 corrigées (Thaïlande 30 j, Sri Lanka ETA) |
| Capitales, GPS, images, drapeaux, UNESCO | Wikidata (SPARQL, query.wikidata.org) + Wikimedia Commons (API) | requêtes SPARQL | CC0 / licences des photos conservées |
| Indicateurs | Banque mondiale (API WDI) : `ER.LND.PTLD.ZS`, `EN.POP.DNST`, `SP.URB.TOTL.IN.ZS`, `EN.URB.MCTY.TL.ZS`, `NY.GNP.PCAP.CD`, `PA.NUS.PPP`, `PA.NUS.FCRF` | API REST JSON | CC BY 4.0, séries mises à jour le 08/10/2026 |
| Budget | Budget Your Trip (pages mises à jour en 2026) | copier-coller des tableaux, extraction par script (20 pays relevés via IA, 21 collés à la main) | relevé du 16/10/2026 |
| Salaires (écartés) | ILOSTAT `EAR_EHRA_SEX_CUR_NB_A` | téléchargement bulk | voir les décisions |

Quatre méthodes de collecte différentes : téléchargement, API REST, SPARQL, relevé manuel.

## 5. Décisions et justifications (à reprendre dans la section technique)

- **41 pays** : quotas par continent (10 Europe, 10 Asie, 3 Moyen-Orient, 7 Afrique, 9 Amériques, 2 Océanie) et diversité de prix. Biais assumé : moins de pays africains. Manquent des voisins très visités (Allemagne, Belgique, Pays-Bas), à ajouter en décembre si on est en avance, environ 10 min par pays. La carte des visas couvre, elle, 199 pays.
- **UNESCO** : comptage par numéro de site (les extensions `80bis`, `80ter` et les composantes `868-001`… ne comptent qu'une fois) et 5 corrections documentées. **Contrôle : 8 pays sur 8 identiques aux chiffres officiels** (France, Espagne, Italie, Japon, Chine, Afrique du Sud, Brésil, Australie). Seuls les **comptages** sont redistribués : les conditions de l'UNESCO interdisent de republier sa liste.
- **Arrivées touristiques retirées** : la série s'arrête en 2020 (Covid), les années ne sont pas comparables, et les définitions varient (la France compte les visiteurs à la journée).
- **Salaires ILOSTAT écartés** : 7 pays manquants (dont le Japon, la Chine et l'Australie), des sources mélangées (enquête ménages / registres), des années de 2017 à 2025, des incohérences (l'Espagne au-dessus de la France, l'Afrique du Sud à 1,38 $/h). Remplacés par le **revenu national brut par habitant** (Banque mondiale), complet et homogène. Sur la page, on parlera de « jours de revenu moyen », pas d'« heures de travail ».
- **Indice du niveau des prix** = PPA / taux de change (États-Unis = 1). Il sert à l'axe « prix » du quiz. **Corrélation de rang de 0,84** avec les budgets Budget Your Trip sur 41 pays : les deux sources indépendantes concordent. 3 pays mélangent 2024 et 2025 (Vietnam, Tanzanie, Émirats), effet négligeable.
- **Budget** : somme des 4 catégories utilisée, parce que les totaux du site ne s'additionnent pas (Sénégal -55 %, Turquie +29 %, Kenya +17 % ; vérifié mot pour mot). **Argentine exclue** de la visualisation 3 : repas à 5,71 $ par jour, invraisemblable (prix en pesos non actualisés après l'inflation). Elle reste dans le quiz.
- **Capitales** : Pretoria pour l'Afrique du Sud (siège du gouvernement), Colombo pour le Sri Lanka.
- **Descriptions** : 41 textes de 2 phrases, rédigés avec l'IA, à relire.

## 6. Formule du quiz

**5 axes, chacun ramené de 0 à 100 par rapport aux 41 pays** (le plus fort = 100) :

| Axe | Calcul |
|---|---|
| Culture | log(1 + sites UNESCO culturels + mixtes) |
| Nature | ½ faible densité (log) + ¼ UNESCO naturels et mixtes (log) + ¼ zones protégées, puis ramené à 0-100 |
| Villes | % de la population dans les villes de plus d'un million d'habitants |
| Prix | −log(niveau des prix) : 100 = le moins cher |
| Distance | distance à vol d'oiseau Paris → capitale (haversine) |

**Comparaison joueur / pays (« le pays qui te ressemble »)** :
- chaque réponse du quiz pousse un ou plusieurs axes vers une valeur souhaitée, avec un poids ;
- profil du joueur : valeur = moyenne pondérée ; importance = min(1, poids cumulé / 1,5) × |valeur − 50| / 50. Une envie tiède compte peu ;
- ressemblance (%) = 100 × (1 − √(Σ importance × écart² / Σ importance × 100²)).

**Tests effectués** :
- 5 profils types donnent 5 pays différents, tous logiques (villes et culture, loin → Japon ; nature → Islande ; petit budget → Indonésie ; culture, pas loin → Italie ; prix seul → Égypte) ;
- simulation des 27 648 combinaisons du prototype : le Brésil, « bon partout », gagnait 32 % des parties avec la formule de base. Avec le correctif, il en gagne 23 %, et 40 pays sur 41 peuvent apparaître dans le top 3 ;
- **prototype** : https://claude.ai/artifact/U5FEve1vN8HjjCZf1zpjH1 (8 questions en cartes, résultat avec radar). Le fichier est aussi dans `prototype/quiz-prototype.html` : il sert de référence pour la logique, pas pour le design.

## 7. Limites connues (à écrire sur la page)

- **La culture se limite aux monuments** : la cuisine, la culture populaire et les fêtes ne sont pas mesurées. C'est pour ça que le Japon (« grandes villes + monuments » pour nos chiffres) ne sort pas forcément pour quelqu'un qui l'aime pour d'autres raisons.
- **Pas de donnée sur la mer et les plages** : une réponse « plage » oriente vers des pays calmes et naturels. Piste : la longueur des côtes.
- **La nature est vue à travers la densité** : la Suisse, la Corée et le Japon, très peuplés, ont des notes de nature faibles malgré leurs montagnes.
- **Les zones protégées** sont gonflées en Europe par Natura 2000. **Les villes** : le Sri Lanka est à 0 à cause de sa définition statistique très étroite de Colombo.
- **Les visas** datent de février 2026, sauf pour le passeport français, vérifié en octobre 2026. Afficher la date sur la carte.
- **Les notes sont relatives** à la sélection de 41 pays.

## 8. Prochaines étapes (nouvelle conversation : le site)

1. Structure de la page : accueil et intro, quiz, carte des passeports, budget, section technique, téléchargement des données (ZIP : 4 CSV + dictionnaire des données).
2. Choix des bibliothèques : D3 pour le radar et la carte, Leaflet ou D3-geo pour la carte, Chart.js possible pour le budget. Fond de carte Natural Earth : faire la jointure sur `ADM0_A3`, car France et Norvège ont `ISO_A3 = -99`.
3. Réécrire les questions du quiz pour qu'elles soient plus amusantes (duels, situations, images), 10 à 12 questions, avec la même logique de calcul.
4. Une visualisation à la fois, testée avant de passer à la suivante.
5. Puis : relire les descriptions, choisir de meilleures photos pour 5 à 10 pays, rédiger l'introduction et la section technique, déployer sur GitHub Pages.

Questions ouvertes : ajouter la mer et les plages ? Ajouter l'Allemagne, la Belgique et les Pays-Bas ? Garder la France dans les résultats du quiz (décision actuelle : oui) ?
