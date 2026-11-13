// ===== Compteur de chargement réel =====
const Progress = (() => {
  const MIN_TIME = 1600;    // ms : le compteur ne va jamais plus vite (évite le flash)
  const MAX_TIME = 15000;   // ms : sécurité, on termine même si un fichier traîne
  const TAU      = 140;     // ms : douceur de l'affichage (plus grand = plus doux)

  const out  = document.getElementById('pl-value');
  const root = document.getElementById('preloader');
  const files = new Map();  // fichiers chargés par fetch, réutilisables ensuite (ex. l'astronaute)

  function loadImage(url, set) {
    const im = new Image();
    im.onload = im.onerror = () => set(1);
    im.src = url;
  }

  // Compte les octets reçus quand le serveur donne la taille du fichier
  async function loadFetch(url, set) {
    try {
      const resp = await fetch(url);
      const total = +resp.headers.get('Content-Length') || 0;
      if (!resp.body || !total) { files.set(url, await resp.blob()); set(1); return; }
      const reader = resp.body.getReader(), chunks = [];
      let got = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value); got += value.length;
        set(Math.min(got / total, 1));
      }
      files.set(url, new Blob(chunks));
      set(1);
    } catch (e) {
      console.warn('Preloader : échec du chargement', url, e);
      set(1);   // un fichier en échec ne doit pas bloquer le site
    }
  }

  // Faux chargement irrégulier, pour tester (index.html?sim=4000)
  function loadSim(ms, set) {
    const t0 = performance.now();
    (function tick() {
      const k = Math.min((performance.now() - t0) / ms, 1);
      set(k < 1 ? k * (0.8 + 0.2 * Math.random()) : 1);
      if (k < 1) setTimeout(tick, 80 + Math.random() * 160);
    })();
  }

  function run(list, { sim = 0 } = {}) {
    const items = list.map(it => ({ ...it, frac: 0 }));
    items.push({ type: 'page', weight: 1, frac: 0 });               // le reste de la page
    if (sim) items.push({ type: 'sim', ms: sim, weight: 8, frac: 0 });
    const total = items.reduce((s, it) => s + it.weight, 0);
    const real = () => items.reduce((s, it) => s + it.weight * it.frac, 0) / total;

    items.forEach(it => {
      const set = v => { it.frac = Math.max(it.frac, v); };          // ne recule jamais
      if (it.type === 'image') loadImage(it.url, set);
      else if (it.type === 'fetch') loadFetch(it.url, set);
      else if (it.type === 'sim') loadSim(it.ms, set);
      else if (it.type === 'task') {                 // tâche libre : reçoit set(0 → 1)
        Promise.resolve().then(() => it.run(set))
          .catch(e => console.warn('Preloader : tâche en échec', e))
          .then(() => set(1));                       // une tâche en échec ne bloque pas le site
      }
      else if (it.type === 'page') {
        if (document.readyState === 'complete') set(1);
        else addEventListener('load', () => set(1), { once: true });
      }
    });

    return new Promise(resolve => {
      let shown = 0, lastValue = -1, t0, prev;
      requestAnimationFrame(function frame(now) {
        if (t0 === undefined) { t0 = prev = now; }
        const dt = now - prev; prev = now;
        const elapsed = now - t0;
        let target = Math.min(real(), elapsed / MIN_TIME);
        if (elapsed > MAX_TIME) target = 1;
        shown += (target - shown) * (1 - Math.exp(-dt / TAU));     // lissage identique à 60 et 120 Hz
        if (target === 1 && 1 - shown < 0.004) shown = 1;
        const v = Math.floor(shown * 100);
        if (v !== lastValue) {
          lastValue = v;
          Counter.set(v);                          // dessine le nombre
          root.setAttribute('aria-valuenow', v);
        }
        shown < 1 ? requestAnimationFrame(frame) : resolve();
      });
    });
  }

  return { run, files };
})();