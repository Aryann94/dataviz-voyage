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

## Environnement
Windows, PowerShell, Python lancé avec `py` (par exemple `py scripts/build_carte.py`, depuis la racine du projet).
