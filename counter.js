// ===== Compteur du loader : même style toon que le titre, dessiné dans un canvas 2D =====
const Counter = (() => {
  // Mêmes valeurs que TITLE dans scene.js (à garder identiques)
  const S = {
    font: '"Evori"', weight: 400,
    fill: ['#FFFFFF', '#FDF1D7'],
    bands: [[0.06, '#A39A8C'], [0.10, '#CFC6B5']],
    bandZone: 0.3,
    rim: ['#FFF9E5', 0],
    ink: '#0D0D33',
    stroke: 0.045,
    depth: [-0.025, 0.05],
    pct: 0.32,                 // taille du % (fraction de la hauteur des chiffres)
    gap: 0.04,                 // espace avant le %
  };

  const host = document.querySelector('.pl-num');
  const cv = document.createElement('canvas'), g = cv.getContext('2d');
  const off = document.createElement('canvas'), o = off.getContext('2d');   // brouillon pour le remplissage
  cv.className = 'pl-canvas';
  host.textContent = '';
  host.append(cv);

  let PX = 300, UNIT = 300, W = 1, H = 1, pad = 0, asc = 0, ready = false, want = 0, shown = null;
  const font = size => `${S.weight} ${size}px ${S.font}`;

  function setup() {
    PX = Math.min(Math.round(parseFloat(getComputedStyle(host).fontSize) * (devicePixelRatio || 1)), 700);
    g.font = font(PX);
    const m = g.measureText('100');
    asc = m.actualBoundingBoxAscent;
    // Unité du relief : à l'échelle de la hauteur des chiffres, dans la même proportion
    // que sur les capitales du titre (au cas où les chiffres sont plus petits que les lettres)
    const capRatio = g.measureText('VOYAGE').actualBoundingBoxAscent / PX;
    UNIT = asc / capRatio;
    pad = Math.ceil(UNIT * (S.stroke + S.rim[1] + Math.max(Math.abs(S.depth[0]), Math.abs(S.depth[1])) + 0.02));
    g.font = font(PX * S.pct);
    W = Math.ceil(m.width + PX * S.gap + g.measureText('%').width + pad * 2);
    H = Math.ceil(asc + pad * 2);
    cv.width = off.width = W;
    cv.height = off.height = H;
    cv.style.height = (H / PX) + 'em';            // affiché à la taille de la police du compteur
  }

  // Une chaîne au style toon : relief, liseré, contour, puis remplissage (dégradé + bandes en bas)
  function drawText(str, size, x, y, unit) {
    g.font = font(size); g.lineJoin = 'round';
    g.fillStyle = g.strokeStyle = S.ink;
    g.lineWidth = unit * S.stroke * 2;
    for (let k = 14; k >= 1; k--) {                                  // relief
      const ox = unit * S.depth[0] * k / 14, oy = unit * S.depth[1] * k / 14;
      g.strokeText(str, x + ox, y + oy);
      g.fillText(str, x + ox, y + oy);
    }
    if (S.rim[1] > 0) {                                              // liseré clair
      g.strokeStyle = S.rim[0]; g.lineWidth = unit * (S.stroke + S.rim[1]) * 2;
      g.strokeText(str, x, y);
    }
    g.strokeStyle = S.ink; g.lineWidth = unit * S.stroke * 2;        // contour
    g.strokeText(str, x, y);

    o.globalCompositeOperation = 'source-over';
    o.clearRect(0, 0, W, H);
    o.font = font(size);
    const a = o.measureText(str).actualBoundingBoxAscent;
    const grad = o.createLinearGradient(0, y - a, 0, y);
    grad.addColorStop(0, S.fill[0]); grad.addColorStop(1, S.fill[1]);
    o.fillStyle = grad; o.fillText(str, x, y);
    o.save();
    o.globalCompositeOperation = 'source-atop';                      // ne peint que dans les chiffres
    o.beginPath(); o.rect(0, Math.round(y - a * S.bandZone), W, H); o.clip();
    o.fillStyle = S.bands[0][1]; o.fillText(str, x, y);
    S.bands.forEach((b, j) => {
      o.fillStyle = j + 1 < S.bands.length ? S.bands[j + 1][1] : grad;
      o.fillText(str, x, y - unit * b[0]);
    });
    o.restore();
    g.drawImage(off, 0, 0);
  }

  function draw(v) {
    const str = String(v), ps = PX * S.pct;
    g.clearRect(0, 0, W, H);
    g.font = font(PX);  const nw = g.measureText(str).width;
    g.font = font(ps);  const pm = g.measureText('%');
    const x = (W - (nw + PX * S.gap + pm.width)) / 2, y = pad + asc;  // le tout centré
    drawText(str, PX, x, y, UNIT);
    drawText('%', ps, x + nw + PX * S.gap, y - asc + pm.actualBoundingBoxAscent, UNIT * S.pct);   // % aligné en haut des chiffres
  }

  function set(v) {
    want = v;
    if (!ready || v === shown) return;
    shown = v;
    draw(v);
  }

  // La police doit être chargée avant de dessiner
  document.fonts.load(font(100), '0123456789%VOYAGE').catch(() => {}).then(() => {
    setup();
    ready = true;
    set(want);
  });

  return { set };
})();