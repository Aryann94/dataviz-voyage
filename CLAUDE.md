# Consignes pour Claude

## À lire d'abord
`RECAPITULATIF.md`, surtout « Où on en est » (en haut) et la section 8 (prochaines étapes).

## Règles de travail
- **Proposer la méthode avant de coder**, et attendre la validation.
- **Une tâche à la fois.**
- **Contrôles bloquants dans les scripts** : un script s'arrête plutôt que d'écrire des données fausses.
- **Ne rien inventer** : chaque donnée a une source (lien, date), et une donnée manquante reste vide et signalée.
- **Commits sans aucune mention de Claude** (ni « Co-Authored-By », ni « Generated with »).
- **Expliquer simplement**, et finir chaque réponse par « Ce que tu dois faire », avec des étapes numérotées.

## Environnement
Windows, PowerShell, Python lancé avec `py` (par exemple `py scripts/build_carte.py`, depuis la racine du projet).
