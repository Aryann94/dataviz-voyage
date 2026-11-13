// ===== Nuages : génération de la scène =====
const CLOUD_IMGS = [
  'img/cloud-1.webp', 'img/cloud-2.webp', 'img/cloud-3.webp',
  'img/cloud-4.webp', 'img/cloud-5.webp'
];

// ===== Réglages de la scène =====
const SEED     = Math.floor(Math.random() * 1e9);   // nouvelle disposition à chaque visite
const COUNT    = 26;
const SIZE_L   = [260, 1250];   // largeur paysage : du plus loin au plus proche
const SIZE_P   = [200, 1000];   // largeur portrait
const HAZE_MAX = 0.7;           // brume : transparence du plus lointain
// ====================

const lerp = (a, b, k) => a + (b - a) * k;

function rng(seed) {
  return () => {
    seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function layout(seed) {
  const r = rng(seed), off = r(), n = CLOUD_IMGS.length, out = [];
  for (let i = 0; i < COUNT; i++) {
    const t  = Math.pow((i + r() * 0.9) / COUNT, 1.6);           // beaucoup au loin, peu (mais gros) devant
    const nx = (((i * 0.618034 + off) % 1) - 0.5) * 1.25 + (r() - 0.5) * 0.08;
    const ny = -0.47 + 0.95 * Math.pow(t, 0.85) + (r() - 0.5) * 0.06;
    const k  = lerp(0.8, 1.2, r());
    const s  = Math.pow(t, 1.4);
    out.push({
      t,
      z: SIZE_L[1] / lerp(SIZE_L[0], SIZE_L[1], s),   // profondeur déduite de la taille : 1 (devant) → ≈ 4,8 (au fond)
      o: 1 - HAZE_MAX * (1 - t),                       // opacité : les lointains se fondent dans le ciel
      src: CLOUD_IMGS[(i * 2 + Math.floor(off * n)) % n],
      lx: Math.round(nx * 1600), ly: Math.round(ny * 900),
      lw: Math.round(lerp(SIZE_L[0], SIZE_L[1], s) * k),
      px: Math.round(nx * 900),  py: Math.round(ny * 1600),
      pw: Math.round(lerp(SIZE_P[0], SIZE_P[1], s) * k),
    });
  }
  return out;
}

const pl = document.getElementById('preloader');
const counter = pl.querySelector('.pl-counter');
const isPortrait = () => matchMedia('(orientation: portrait)').matches;

// Unité de scène : une seule valeur, partagée par le CSS (--u) et par la dispersion
let U = 1;
function fit() {
  const w = pl.clientWidth, h = pl.clientHeight;
  U = isPortrait() ? Math.max(w / 900, h / 1600) : Math.max(w / 1600, h / 900);
  pl.style.setProperty('--u', U.toFixed(4) + 'px');
}

function build() {
  fit();
  const frag = document.createDocumentFragment();
  const list = layout(SEED).map(c => {
    const el = document.createElement('div');
    el.className = 'cloud' + (c.t > 0.5 ? ' near' : '');
    el.style.cssText =
      `--lx:${c.lx};--ly:${c.ly};--lw:${c.lw};--px:${c.px};--py:${c.py};--pw:${c.pw};--o:${c.o.toFixed(2)}`;
    const inner = document.createElement('div');
    inner.className = 'drift';
    inner.style.cssText =
      `--a:${lerp(3, 30, c.t).toFixed(1)};` +
      `animation-duration:${lerp(16, 10, c.t).toFixed(1)}s;animation-delay:-${(c.t * 7).toFixed(1)}s`;
    const im = new Image();
    im.alt = ''; im.decoding = 'async'; im.draggable = false;
    im.src = c.src;
    inner.appendChild(im);
    el.appendChild(inner);
    frag.appendChild(el);
    return { el, c };
  });
  pl.insertBefore(frag, counter);   // une seule insertion dans la page
  return list;
}
const clouds = build();

const onResize = () => pl.isConnected ? fit() : removeEventListener('resize', onResize);
addEventListener('resize', onResize);

window.Clouds = { imgs: CLOUD_IMGS };