// ===== Dispersion : la caméra traverse la couche de nuages =====
// Chaque nuage a une profondeur z (1 = devant, ≈ 4,8 = au fond). La caméra avance de d.
// Perspective : tout s'écarte du point de fuite d'un facteur F = z / (z − d).
// Un nuage qui arrive sur la caméra grossit, s'efface, et laisse voir le plan suivant.

// ===== Réglages =====
const LEAVE_MS  = 1100;         // durée totale
const ACCEL     = 2.4;          // courbe de la caméra : 1 = vitesse constante, 3 = départ très lent puis ruée
const RECOIL    = 0.06;         // léger recul avant le départ (0 = aucun)
const SPREAD    = 0.16;         // écartement gauche/droite ajouté à la perspective (en largeurs d'écran)
const VERTICAL  = 1;            // écartement vertical (1 = perspective réelle, 0 = horizontal pur)
const SMEAR     = 0.25;         // étirement horizontal en fin de course (remplace le flou)
const FADE      = [0.5, 0.2];   // un nuage s'efface entre 50 % et 20 % de sa distance de départ
const VANISH    = [0, 1.5];       // décalage du point de fuite, en demi-écrans ([0, 1.5] = sous l'écran : les nuages filent vers le haut)
const COUNTER_Z = 1.5;          // profondeur du compteur
const STEPS     = 40;           // points calculés par trajectoire
// ====================

const clamp01 = v => Math.min(Math.max(v, 0), 1);
const smooth  = (a, b, v) => { const k = clamp01((v - a) / (b - a)); return k * k * (3 - 2 * k); };

// Distance parcourue par la caméra à l'instant tau (0 → 1)
function camera(tau, travel) {
  const recoil = tau < 0.3 ? Math.sin(Math.PI * tau / 0.3) ** 2 : 0;
  return travel * Math.pow(tau, ACCEL) - RECOIL * recoil;
}

// Trajectoire d'un objet placé à (rx, ry) du point de fuite, à la profondeur z
function track({ rx = 0, ry = 0, z, side = 0, opacity = 1, fade = FADE, smear = SMEAR }, travel, spreadPx) {
  const frames = [];
  for (let j = 0; j <= STEPS; j++) {
    const d = camera(j / STEPS, travel);
    const p = Math.max(1 - d / z, fade[1]);            // part de la distance restante
    const F = 1 / p;                                    // facteur de perspective
    const x = (rx + side * spreadPx) * (F - 1);
    const y = ry * (F - 1) * VERTICAL;
    const sx = F * (1 + smear * smooth(1, 1 / fade[1], F));
    frames.push({
      transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${sx.toFixed(4)}, ${F.toFixed(4)})`,
      opacity: (opacity * smooth(fade[1], fade[0], p)).toFixed(3),
    });
  }
  return frames;
}

async function disperse() {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    return pl.animate({ opacity: [1, 0] }, { duration: 300, fill: 'forwards' }).finished;
  }

  // 1) Lectures : une seule mesure, avant toute écriture
  const W = pl.clientWidth, H = pl.clientHeight;
  const cb = counter.getBoundingClientRect();
  const vx = cb.left + cb.width / 2 - W / 2 + VANISH[0] * W / 2;    // point de fuite, par rapport au centre
  const vy = cb.top + cb.height / 2 - H / 2 + VANISH[1] * H / 2;
  const portrait = isPortrait();
  const r = rng(SEED + 1);

  // 2) Calculs : position de chaque nuage déduite de la disposition (aucune mesure)
  const items = clouds.map(({ el, c }) => {
    const rx = (portrait ? c.px : c.lx) * U - vx;
    const ry = (portrait ? c.py : c.ly) * U - vy;
    return {
      el, rx, ry,
      z: c.z * lerp(0.92, 1.08, r()),                                // deux nuages de même taille ne partent pas ensemble
      side: Math.abs(rx) < W * 0.04 ? (r() < 0.5 ? -1 : 1) : Math.sign(rx),
      opacity: c.o,
    };
  });
  const travel = Math.max(...items.map(it => it.z)) * (1 - FADE[1]) * 1.02;   // le dernier nuage s'efface juste à la fin

  // 3) Écritures : une animation par nuage, transform + opacity uniquement
  const timing = { duration: LEAVE_MS, easing: 'linear', fill: 'forwards' };
  const anims = items.map(it => it.el.animate(track(it, travel, SPREAD * W), timing));

  // Le compteur est au point de fuite : il grossit sur place et s'efface tôt
  anims.push(counter.animate(
    track({ z: COUNTER_Z, fade: [0.85, 0.45], smear: 0 }, travel, 0), timing));

  return Promise.all(anims.map(a => a.finished));
}

Clouds.disperse = disperse;
Clouds.leaveMs  = LEAVE_MS;