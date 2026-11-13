## Plan technique détaillé (ce que l'assistant comptait faire)

### Principe d'architecture
- Un seul canvas WebGL, pas de post-traitement, pas de cible de rendu plein écran :
  duotone et révélation sont calculés dans le shader de chaque élément
  (paysage, titre, astronaute, traits). L'anticrénelage natif est conservé.
- Les valeurs de couleur restent en sRGB (textures en NoColorSpace, sortie directe).
- Budget : simulation à taille fixe, textures envoyées au GPU pendant le loader,
  tout mouvement piloté par des uniforms.

### Étape 1 : parallaxe et composition du paysage
- Diagnostiquer d'abord le symptôme (rien ne bouge, sens inversé, bords visibles,
  saccades, amplitude trop faible).
- Pistes : amplitude PARALLAX trop faible (0.012), écoute `pointermove` sur window,
  lissage POINTER_EASE, marge LAND_ZOOM 1.06, signe des décalages dans `uOff`.
- Régler les `drop` des 4 plans sur capture pour dégager le tiers haut de l'écran.
- Ajouter ensuite une légère parallaxe à l'astronaute (plan le plus proche) et au titre.
- Option : parallaxe au scroll en plus de la souris.

### Étape 2 : duotone
- Fonction GLSL commune : luminance (0.299, 0.587, 0.114), réglage contraste et point milieu,
  puis mix(ombre #0D0D33, lumière #FFF2D9). Réglé à l'œil pour approcher Figma
  (contraste 50, point milieu 50, mélange 100).
- Paysage : appliqué en fin du shader des plans. Le ciel est dessiné dans ce shader
  (crème en duotone, clair en couleur) et remplace le dégradé CSS.
- Astronaute : injecté dans MeshToonMaterial et dans le matériau du contour par
  onBeforeCompile, juste avant la conversion de couleur de sortie.
- Traits de vitesse : couleur bleu nuit, car le blanc est invisible sur fond crème.
- Un uniform global uReveal (0 = duotone, 1 = couleur) prépare l'étape 4.

### Étape 3 : titre dans le canvas
- Dessiner chaque lettre dans un canvas 2D (police Evori chargée par document.fonts),
  avec contour à angles arrondis (lineJoin round), ombre portée dure et deux tons.
  Cela règle aussi le risque de pointes sur V, Y, A du contour CSS.
- Une texture atlas, un quad par lettre placé entre le paysage et l'astronaute.
- GSAP anime directement position et rotation des quads (même montée lettre par lettre),
  le masque est fait par découpe dans le shader.
- Le <h1> reste dans la page, masqué visuellement, pour l'accessibilité et le référencement.
- Supprimer alors le z-index 3 provisoire : l'astronaute repasse devant le titre.

### Étape 4 : révélation au curseur, version légère
- Une petite texture masque (environ 256 px de large, un seul canal) en ping-pong :
  à chaque image, le masque précédent est repris avec une légère atténuation
  et un léger étalement, puis le curseur y ajoute une tache en cloche.
- Une seule tache par image, interpolée le long du trajet de la souris.
- Dans chaque shader : lecture du masque en coordonnées écran (gl_FragCoord / résolution),
  seuil adouci (smoothstep) plus un peu de bruit pour un bord net et organique,
  puis mix(duotone, couleur, masque).
- Mise en sommeil : si le curseur est immobile et le masque revenu à zéro,
  plus aucune passe de simulation.

### Étape 5 : vrai fluide, seulement si l'étape 4 ne suffit pas
- Méthode Stable Fluids (comme l'exemple fourni), mais : grille fixe d'environ 128 de côté,
  indépendante de l'écran ; textures demi-flottantes ; 8 à 12 itérations de pression
  avec reprise de la pression précédente (facteur 0.8) ; pas de temps réel plafonné.
- Le masque de l'étape 4 devient l'encre transportée par la vitesse.
- Alternative prête à l'emploi à évaluer : bibliothèque three-fluid-fx (démo « reveal mask »).

### Étape 6 : finitions
- Loader : fond crème, nuages et compteur aux couleurs du duotone.
- Mobile : mêmes événements pointeur, `touch-action: pan-y` sur le hero
  (glissé horizontal = fluide et parallaxe, vertical = défilement), grille et textures réduites.
- Polices : intégrer Evori (titre) et Bricolage Grotesque (texte, largeur normale).
- Optimisations restantes si les mesures le demandent : rogner chaque plan à sa bande utile,
  jeu de textures demi-taille pour mobile, prolongement automatique des bords des plans.
- Crédits à afficher : J-Toastie (astronaute), auteur de la photo.

### Pièges déjà rencontrés
- Un ease-out pur part à pleine vitesse : utiliser une courbe douce aux deux bouts.
- Toon sur facettes : les tons clignotent, il faut lisser les normales.
- Ordre d'arrivée des plans : le plus proche d'abord, sinon les zones rebouchées se voient.
- Les objets transparents sont dessinés après les opaques : gérer l'ordre par la profondeur.

## Consignes pour l'assistant qui reprend
- Répondre en français, en tutoyant. Ne coder que sur demande explicite.
- Lire tous les fichiers joints avant de proposer quoi que ce soit.
- Ne jamais réécrire un fichier entier sans raison : donner des remplacements ciblés
  (« remplace la fonction X », « ajoute après la ligne Y ») pour préserver mes réglages.
- Dire clairement ce qui est supposé et non vérifié, et ce qui est provisoire.
- Vérifier sur internet tout ce qui peut avoir changé (versions, licences, API).

## Structure de scene.js (à respecter)
- Réglages en constantes en tête, par blocs : cadrage, déroulé, corps, membres, toon,
  traits de vitesse, paysage.
- Fonctions : toonify, outline, facing, aim, rig, makeLines, makeLand, puis init.
- Dans init : `apply(ms, dt)` place tout pour un instant donné, `fit()` gère la taille,
  `frame()` est la boucle, `sync()` la démarre ou l'arrête. L'API renvoyée est `fall()`.
- Tout est exprimé en fractions d'écran ou d'image, jamais en pixels fixes.

## Budget de performance
- Cible : 60 images par seconde sur un portable à carte graphique intégrée, en 1080p.
- Environ 12 draw calls aujourd'hui (astronaute 5, contour 5, traits 1, paysage 1).
- Aucune passe plein écran en dehors du paysage. Simulation future : moins d'une demi-passe.
- Mémoire des plans : environ 45 Mo sans mipmaps (2 plans à 2560 px, 2 à 1280 px).
- Vérifier après chaque étape : piste « Frames » de l'onglet Performance (CPU ralenti x4),
  Performance monitor au repos, poids dans l'onglet Réseau.

## Références utiles
- Tutoriel Codrops (mars 2026) : « Dual-Scene Fluid X-Ray Reveal Effect in Three.js ».
- WebGL Fluid Simulation de Pavel Dobryakov (réglages par défaut : grille 128, 20 itérations).
- Article « Realistic Watercolor Reveal Effect » (masque gris vers couleur, version légère).