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
│   ├── pays.csv                 FINAL - 1 ligne par pays (41), 39 colonnes : faits bruts
│   ├── scores.csv               FINAL - notes du quiz 0-100 (6 axes) + distance depuis Paris
│   ├── visas.csv                FINAL - 39 402 paires passeport -> destination
│   ├── budget.csv               FINAL - format long : pays x niveau x catégorie (40 pays)
│   ├── pays_liste.csv           saisie manuelle : les 41 pays, nom, région, choix de capitale/photo
│   ├── descriptions_pays.csv    saisie manuelle : 41 textes de présentation
│   ├── saisie_budget.csv        relevé Budget Your Trip (format large)
│   ├── corrections_visas.csv    41 vérifications manuelles avec source et date
│   ├── corrections_unesco.csv   5 corrections justifiées du comptage UNESCO
│   ├── intermediaire/           sorties par source (Wikidata, Banque mondiale, CIA Factbook, ILOSTAT)
│   └── raw/                     réponses brutes des API et fichiers téléchargés (traçabilité)
└── scripts/                     Python, bibliothèque standard (+ certifi)
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

### `budget.csv`
`iso3, niveau (petit|moyen|confort), categorie (hebergement|transport|repas|activites), montant_usd_jour, total_site_usd, source_url, date_releve, date_maj_site`.

### `scores.csv`
`iso3, score_culture, score_nature, score_villes, score_prix, score_distance, score_mer, distance_paris_km, date_calcul`.

## 4. Sources et méthodes de collecte

| Donnée | Source | Méthode | Licence / remarque |
|---|---|---|---|
| Visas | Passport Index (dépôt GitHub imorte/passport-index-data, données du 18/02/2026) | téléchargement CSV + nettoyage | MIT |
| Vérification des visas | France Diplomatie, fiches « Entrée / séjour » (sept.-oct. 2026), europa.eu pour l'UE | vérification manuelle des 40 destinations du passeport français | 38/40 concordantes, 2 corrigées (Thaïlande 30 j, Sri Lanka ETA) |
| Capitales, GPS, images, drapeaux, UNESCO | Wikidata (SPARQL, query.wikidata.org) + Wikimedia Commons (API) | requêtes SPARQL | CC0 / licences des photos conservées |
| Indicateurs | Banque mondiale (API WDI) : `ER.LND.PTLD.ZS`, `EN.POP.DNST`, `AG.LND.FRST.ZS`, `SP.URB.TOTL.IN.ZS`, `EN.URB.MCTY.TL.ZS`, `NY.GNP.PCAP.CD`, `PA.NUS.PPP`, `PA.NUS.FCRF` | API REST JSON | CC BY 4.0, séries mises à jour le 08/10/2026 |
| Budget | Budget Your Trip (pages mises à jour en 2026) | copier-coller des tableaux, extraction par script (20 pays relevés via IA, 21 collés à la main) | relevé du 16/10/2026 |
| Côtes, surface, latitude | CIA World Factbook, copie archivée github.com/factbook/factbook.json (la CIA a arrêté le Factbook en février 2026) | téléchargement JSON + lecture du texte (« 29,751 km ») | domaine public ; le Vietnam est compté sans ses îles |
| Salaires (écartés) | ILOSTAT `EAR_EHRA_SEX_CUR_NB_A` | téléchargement bulk | voir les décisions |

Quatre méthodes de collecte différentes (5 sources) : téléchargement, API REST, SPARQL, relevé manuel.

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

## 7. Limites connues (à écrire sur la page)

- **La culture se limite aux monuments** : la cuisine, la culture populaire et les fêtes ne sont pas mesurées. C'est pour ça que le Japon (« grandes villes + monuments » pour nos chiffres) ne sort pas forcément pour quelqu'un qui l'aime pour d'autres raisons.
- **La mer mesure un potentiel, pas des plages** : beaucoup de côtes et une latitude chaude. Pas de différence entre sable et falaises, pas de réputation : le Japon (88) et le Chili (74, courant froid) sont surévalués, la latitude du centre du pays ignore la Floride ou le Queensland.
- **La nature** compte autant les grands espaces vides que les forêts. Les déserts peuplés sont pénalisés (Maroc 0, Égypte 14), la montagne n'est pas mesurée (la Suisse reste à 37). La forêt de la FAO inclut les savanes boisées (Sénégal 45 %).
- **Les zones protégées** sont gonflées en Europe par Natura 2000. **Les villes** : le Sri Lanka est à 0 à cause de sa définition statistique très étroite de Colombo.
- **Les visas** datent de février 2026, sauf pour le passeport français, vérifié en octobre 2026. Afficher la date sur la carte.
- **Les notes sont relatives** à la sélection de 41 pays.

## 8. Prochaines étapes (nouvelle conversation : le site)

1. Structure de la page : accueil et intro, quiz, carte des passeports, budget, section technique, téléchargement des données (ZIP : 4 CSV + dictionnaire des données).
2. Choix des bibliothèques : D3 pour le radar et la carte, Leaflet ou D3-geo pour la carte, Chart.js possible pour le budget. Fond de carte Natural Earth : faire la jointure sur `ADM0_A3`, car France et Norvège ont `ISO_A3 = -99`.
3. Réécrire les questions du quiz pour qu'elles soient plus amusantes (duels, situations, images), 10 à 12 questions, avec la même logique de calcul.
4. Une visualisation à la fois, testée avant de passer à la suivante.
5. Puis : relire les descriptions, choisir de meilleures photos pour 5 à 10 pays, rédiger l'introduction et la section technique, déployer sur GitHub Pages.

**Décision du 16/10/2026 : on fige les 6 critères.** Langue et climat ont été étudiés puis écartés :
- **langue** : avec les langues officielles, l'Inde (anglais officiel, alphabet latin pour l'anglais) obtient le même dépaysement que les États-Unis, ce qui est absurde ; le Maroc, où le français est très parlé sans être officiel, serait compté comme très dépaysant ;
- **climat par mois** : une seule ville par pays ment pour les grands pays (Canberra en juillet est froide, le nord de l'Australie est chaud), et choisir plusieurs villes à la main serait subjectif ;
- **cuisine, culture pop** : aucune donnée objective et réutilisable.
Un critère approximatif qui produit des résultats absurdes coûte plus de crédibilité qu'il n'apporte de réalisme.

**Le Japon trop souvent gagnant (19,9 %) se corrige dans les questions, pas dans les données** : les réponses actuelles disent surtout ce qu'on veut, rarement ce qu'on ne veut pas, donc un pays fort partout gagne. Les nouvelles questions devront contenir des choix qui coûtent (« animé ou calme », « cher mais confortable ou simple et bon marché »). **Objectif à vérifier par la simulation : aucun pays ne gagne plus de 12 % des parties**, et au moins 38 pays sur 41 peuvent apparaître dans un top 3.

Choix validés pour le quiz final : questions fun (duels de photos, mises en situation), quiz qui s'adapte (mode rapide environ 8 questions, mode précis environ 15), révélation animée du classement à la fin (pas pendant : ça gâcherait le suspense), résultat partageable avec « le pays qui te ressemble le moins ». Pas de test avec la classe.

Questions ouvertes : Ajouter l'Allemagne, la Belgique et les Pays-Bas ? Garder la France dans les résultats du quiz (décision actuelle : oui) ?
