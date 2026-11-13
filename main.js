// ===== Enchaînement : chargement → 100 → dispersion → chute → titre =====
const REVEAL_AT = 0.4;    // le site (encore vide) devient visible à 40 % de la dispersion
const FALL_AT   = 0.55;   // l'astronaute entre à 55 % de la dispersion

(async () => {
  const root = document.documentElement;
  let scene = null, failed = false, fallAt = 0;              // fallAt : instant prévu de son entrée
  const startScene = () => {
    if (!fallAt) return;
    if (scene) scene.fall({ delay: fallAt - performance.now(), onArrive: Hero.reveal });
    else if (failed) Hero.reveal();                           // pas d'astronaute : le titre arrive seul
  };

  try {
    // Test : index.html?sim=4000 simule un chargement de 4 s
    const sim = Number(new URLSearchParams(location.search).get('sim')) || 0;

    const assets = [
      ...Clouds.imgs.map(url => ({ type: 'image', url, weight: 1 })),
      { type: 'task', weight: 30, run: async set => {        // three.js + modèle + shaders
          try {
            const { init } = await import('./scene.js');
            set(0.3);
            scene = await init({ onProgress: k => set(0.3 + 0.7 * k) });
          } catch (e) {
            failed = true;
            throw e;
          } finally {
            startScene();                                     // cas rare : la scène arrive (ou échoue) après le loader
          }
      } },
    ];

    await Progress.run(assets, { sim });
    await new Promise(r => setTimeout(r, 150));               // un court instant sur « 100 »

    const leaving = Clouds.disperse();
    fallAt = performance.now() + Clouds.leaveMs * FALL_AT;
    startScene();                                             // les traits accélèrent avec les nuages
    setTimeout(() => root.classList.remove('is-loading'), Clouds.leaveMs * REVEAL_AT);
    await leaving;
  } finally {
    root.classList.remove('is-loading');                      // sécurité : le site s'affiche quoi qu'il arrive
    document.getElementById('preloader')?.remove();
    document.dispatchEvent(new Event('preloader:done'));
    if (!fallAt) fallAt = performance.now();
    startScene();
  }
})();