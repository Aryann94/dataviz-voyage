// ===== Enchaînement : chargement → 100 → dispersion → chute → titre → défilement =====
const REVEAL_AT = 0.4;    // le site devient visible à 40 % de la dispersion
const FALL_AT   = 0.55;   // l'astronaute entre à 55 % de la dispersion

(async () => {
  const root = document.documentElement;
  let scene = null, failed = false, fallAt = 0;
  const arrived = () => { Hero.reveal(); window.Scroll?.unlock(); };   // il freine : textes et défilement
  const startScene = () => {
    if (!fallAt) return;
    if (scene) scene.fall({ delay: fallAt - performance.now(), onArrive: arrived });
    else if (failed) arrived();                                         // pas d'astronaute : on débloque quand même
  };

  try {
    // Test : index.html?sim=4000 simule un chargement de 4 s
    const sim = Number(new URLSearchParams(location.search).get('sim')) || 0;

    const assets = [
      ...Clouds.imgs.map(url => ({ type: 'image', url, weight: 1 })),
      { type: 'task', weight: 30, run: async set => {                  // three.js + modèle + shaders
          try {
            const { init } = await import('./scene.js');
            set(0.3);
            scene = await init({ onProgress: k => set(0.3 + 0.7 * k) });
          } catch (e) {
            failed = true;
            throw e;
          } finally {
            startScene();
          }
      } },
    ];

    await Progress.run(assets, { sim });
    await new Promise(r => setTimeout(r, 150));                         // un court instant sur « 100 »
    await window.Gate?.ask();                                            // à 100 % : « avec ou sans le son », puis on entre

    const leaving = Clouds.disperse();
    fallAt = performance.now() + Clouds.leaveMs * FALL_AT;
    startScene();
    setTimeout(() => root.classList.remove('is-loading'), Clouds.leaveMs * REVEAL_AT);
    await leaving;
  } finally {
    root.classList.remove('is-loading');                                // sécurité : le site s'affiche quoi qu'il arrive
    document.getElementById('preloader')?.remove();
    document.dispatchEvent(new Event('preloader:done'));
    if (!fallAt) fallAt = performance.now();
    startScene();
  }
})();