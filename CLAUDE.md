# Consignes pour Claude

## À lire d'abord
`RECAPITULATIF.md`, surtout « Où on en est » (en haut) et la section 8 (prochaines étapes).

## Règles de travail
- **Décider seul** en suivant ces règles et le récap, et appliquer ses recommandations sans demander.
- **Ne poser une question que pour** : une action irréversible (réécrire l'historique Git, supprimer des fichiers), un choix de contenu visible sur le site (texte, design), ou deux options vraiment équivalentes. Dans ce cas : une seule question, avec une recommandation.
- **Une tâche à la fois.**
- **Contrôles bloquants dans les scripts** : un script s'arrête plutôt que d'écrire des données fausses.
- **Ne rien inventer** : chaque donnée a une source (lien, date), et une donnée manquante reste vide et signalée.
- **Commits sans aucune mention de Claude** (ni « Co-Authored-By », ni « Generated with »).
- **Fin de chaque tâche** : un résumé simple de 5 lignes maximum : ce qui est fait, ce qui a été décidé et pourquoi.

## Style d'écriture des textes du site
À appliquer à tout texte visible : questions, résultats, présentation, section technique, LISEZMOI.
- Écrire comme un humain : français simple, direct et naturel, sérieux sans être trop formel.
- Pas de tiret long (—).
- Pas de question rhétorique suivie de sa réponse, pas de « ce n'est pas X, c'est Y », pas de « non seulement… mais aussi ».
- Pas de règle de trois systématique, pas d'anaphore artificielle, pas de suspense forcé, pas de conclusion inspirante, pas de phrase de résumé automatique en fin de paragraphe.
- Pas de transitions mécaniques (par ailleurs, de plus, ainsi, néanmoins, en outre).
- Mots interdits : plonger, tirer parti, optimiser, révolutionner, libérer le potentiel, transcender, réinventer, naviguer, rationaliser, sublimer, crucial, incontournable, fluide, révolutionnaire, transformateur, à la pointe, nuancé, aux multiples facettes, robuste, vertigineux, « il est important de noter », « en conclusion », « joue un rôle central », « ouvrir la voie à », « au final », « en résumé », « cela m'a permis de », « il convient de souligner ». Reformuler plutôt que remplacer par un synonyme.
- Varier la longueur des phrases et des paragraphes, éviter les structures symétriques, ne pas répéter une idée.
- Ne jamais inventer un fait, un chiffre ou une citation.
- Relire chaque texte avec ces règles avant de le proposer.

## Environnement
Windows, PowerShell, Python lancé avec `py` (par exemple `py scripts/build_carte.py`, depuis la racine du projet).
