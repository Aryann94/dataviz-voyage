// ===== Scène 3D : la chute de l'astronaute, puis la plongée au défilement =====
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ===== Réglages : cadrage (x en largeurs d'écran, y et taille en hauteurs ; y : 0 = centre, 0.5 = bord haut) =====
const MODEL_URL = 'models/astronaute.glb';
const FOV       = 35;
const CAM_Z     = 10;
const FALLING   = { x: 0, y: 0.02 };                 // où il se tient pendant la chute
const REST = {                     // où il se pose (y plus petit = plus bas, donc plus sur le titre)
  get x() { return innerWidth < innerHeight ? -0.02 : 0.02; },   // un peu plus à gauche en portrait
  y: 0.09,
  get size() { return innerWidth < innerHeight ? 0.34 : 0.44; },   // plus petit en portrait, pour qu'il tienne en largeur
};
const MAX_SIZE  = 0.95;                              // écran étroit : sa hauteur ne dépasse pas 95 % de la largeur
const MAX_DPR   = matchMedia('(pointer: coarse)').matches ? 1.5 : 2;

// ===== Réglages : le déroulé =====
const ENTER_MS    = 700;               // 1) il entre par le haut
const FALL_MS     = 1500;              // 2) durée de la chute, entrée comprise : ciel à pleine vitesse
const ARRIVE_MS   = 2600;              // 3) freinage : tout ralentit ensemble
const ARRIVE_TAIL = 1.5;               // 1 = freinage symétrique, 2 = ralentit tôt puis s'étire très longtemps
const ENTER_SPIN  = 1.4;               // culbute à l'entrée (radians)
const DRIFT       = [0.03, 0.035];     // dérive pendant la chute (largeurs, hauteurs d'écran)

// ===== Réglages : le corps (repère de l'écran : x = droite, y = haut, z = vers toi) =====
const BODY_FALL = { head: [-0.7, -0.45, 0.25], chest: [-0.3, 0.75, 0.6] };   // sur le dos, tête en bas à gauche
const BODY_REST = { head: [-0.7, 0.42, 0.15],  chest: [0.4, 0.55, 0.75] };   // renversé, tête en haut à gauche, jambes vers le titre
const BODY_FACE = { head: [0, 1, 0],           chest: [0, 0, 1] };           // en fin de plongée : droit, face à nous
const SWAY      = [0.2, 0.05];         // balancement du corps (radians) : en chute, au repos

// ===== Réglages : les membres (repère de l'astronaute : x = SA gauche, y = vers sa tête, z = devant lui) =====
// [os, os suivant, direction en chute, direction au repos, sens du geste]
const POSE = [
  ['Spine',        'Spine1',       [0, 0.97, 0.24],     [0, 0.98, 0.18],      [0, 0, 0.3]],
  ['Neck',         'Head',         [0, 0.8, 0.6],       [0.05, 0.9, 0.42],    [0.3, 0, 0.2]],
  ['LeftArm',      'LeftForeArm',  [0.5, 0.3, 0.8],     [0.7, 0, 0.7],        [0, 1, 0.3]],
  ['LeftForeArm',  'LeftHand',     [0.25, 0.5, 0.83],   [0.45, 0.3, 0.85],    [0, 1, 0]],
  ['RightArm',     'RightForeArm', [-0.6, 0.05, 0.8],   [-0.75, -0.25, 0.6],  [0, -1, 0.3]],
  ['RightForeArm', 'RightHand',    [-0.2, 0.45, 0.87],  [-0.4, 0.2, 0.9],     [0, -1, 0]],
  ['LeftUpLeg',    'LeftLeg',      [0.2, -0.45, 0.87],  [0.15, -0.8, 0.58],   [0, 0, 1]],
  ['LeftLeg',      'LeftFoot',     [0.15, -0.95, 0.25], [0.1, -0.97, 0],      [0, 0, 0.6]],
  ['RightUpLeg',   'RightLeg',     [-0.25, -0.75, 0.6], [-0.25, -0.6, 0.75],  [0, 0, -1]],
  ['RightLeg',     'RightFoot',    [-0.2, -0.98, -0.1], [-0.15, -0.9, -0.35], [0, 0, -0.6]],
];
const FLAIL      = 0.35;               // amplitude des gestes pendant la chute
const FLOAT      = 0.1;                // amplitude au repos
const FLAIL_RATE = 4.5;                // vitesse des gestes pendant la chute
const FLOAT_RATE = 1.2;                // vitesse au repos

// ===== Réglages : le toon =====
const TONES          = [125, 255];        // les 2 tons (0 à 255) : ombre, lumière
const SHADE_AT       = 0.56;              // où tombe la frontière : plus grand = plus d'ombre
const SHADE_SOFT     = 0.02;              // douceur de la frontière (0 = marche nette, qui scintille)
const NORMAL_BLUR    = 2;                 // lissage des ombres : 0 = aucun, 3 = très grandes formes
const LIGHT          = [2.3, 0.9];        // intensité du soleil, de la lumière d'ambiance
const SUN            = [2, 3, 6];         // d'où vient le soleil (droite, haut, vers toi)
const AMBIENT        = '#c9d6ff';         // teinte des ombres
const INK            = '#1c2452';         // couleur du contour
const OUTLINE        = 0.007;             // épaisseur du contour, en fraction de la taille du personnage (0 = aucun)
const OUTLINE_GROW   = 0.3;               // en gros plan : 0 = même épaisseur à l'écran, 1 = grossit avec l'approche (avant)
const SMOOTH_SHADING = true;              // true = ombres en grandes formes, false = facettes

// ===== Réglages : les traits de vitesse =====
const LINES      = 70;
const LINE_COLOR = '#1c2452';
const LINE_ALPHA = 0.55;
const LINE_RATE  = 2.4;                // hauteurs d'écran par seconde à pleine vitesse
const LINE_LEN   = 0.45;               // longueur à pleine vitesse (en hauteurs d'écran)
const IDLE_SPEED = 0.1;                // vitesse résiduelle une fois arrivé (0 = ciel calme)
const FAN        = 0.12;               // éventail : les traits s'écartent vers le haut
const IDLE_FPS   = 60;                 // plafond au repos

// ===== Réglages : le paysage =====
// drop : descente du plan (en hauteurs d'image) | depth : part de parallaxe et de zoom | rise : montée à l'arrivée
const LAYERS = [
  { file: 'img/plan-1.webp', drop: 0.04, depth: 1.00, rise: 0.34 },   // cabane et prairie
  { file: 'img/plan-2.webp', drop: 0.12, depth: 0.55, rise: 0.50 },   // collines
  { file: 'img/plan-3.webp', drop: 0.20, depth: 0.30, rise: 0.66 },   // montagne boisée
  { file: 'img/plan-4.webp', drop: 0.28, depth: 0.15, rise: 0.72 },   // pics
];
const LAND_ZOOM = innerWidth < innerHeight ? 1.08 : 1.03;   // zoom du paysage : plus de marge sur téléphone pour la parallaxe
const LAND_MIN_H   = 0.95;            // écran étroit : hauteur minimale du paysage (en hauteurs d'écran)
const PARALLAX = innerWidth < innerHeight ? [0.03, 0.018] : [0.008, 0.004];   // amplitude [horizontal, vertical] : téléphone en portrait, ordinateur
const TILT = { range: 10, recenter: 2.5, dir: [1, 1] };   // inclinaison : degrés pour aller au bout de la parallaxe, secondes pour recentrer, sens [horizontal, vertical]
const POINTER_EASE = 6;               // réactivité du suivi de la souris
const LAYER_MS     = 1200;            // durée de montée d'un plan
const LAYER_GAP    = 160;             // décalage entre deux plans

// ===== Réglages : le duotone =====
const DUO_SHADOW   = '#0D0D33';
const DUO_LIGHT    = '#FFF2D9';
const DUO_MIDTONE  = '#8f8676';        // ton moyen gris chaud
const DUO_CONTRAST = 1.0;
const DUO_MID      = 0.45;             // plus grand = image plus sombre
const DUO_MIX      = 1;                // 1 = duotone complet, 0 = vraies couleurs
const SKY_COLOR    = '#e8eef7';        // ciel en vraies couleurs
const HAZE_COLOR   = '#FFF9E5';
const HAZE         = [0.30, 1.0, 0.8]; // brume : totale au-dessus de 30 %, nulle à 100 %, force
const VIGNETTE     = [0.08, 0.5];      // bord crème : largeur, force

// ===== Réglages : le titre =====
const TITLE = {
  text: 'VOYAGE', font: '"Evori"', weight: 400,
  get width() { return innerWidth < innerHeight ? 0.9 : 0.62; },   // part de la largeur d'écran : 90 % en portrait, 62 % sur ordinateur                    // largeur à l'écran (en largeurs d'écran)
  y: -0.08,                         // centre (en hauteurs d'écran)
  fill: ['#FFFFFF', '#FDF1D7'],     // dégradé vertical : haut, bas
  bands: [[0.03, '#A39A8C'], [0.06, '#CFC6B5']],   // bandes d'ombre en bas : [hauteur, couleur]
  bandZone: 0.3,                    // les bandes n'apparaissent que dans le bas des lettres
  rim: ['#FFF9E5', 0],              // liseré clair (0 = aucun)
  spacing: 0,                       // espacement global entre les lettres
  nudge: [0, 0, 0, -0.05, 0, 0],        // décalage de chaque lettre, de V à E
  ink: '#0D0D33',                   // contour et extrusion
  stroke: 0.03,                     // épaisseur du contour
  depth: [-0.035, 0.07],            // extrusion : décalage horizontal, vertical
  delay: 0.4, duration: 1.3, stagger: 0.08,   // arrivée lettre par lettre, en secondes
};

// ===== Réglages : la révélation au curseur =====
const MASK_SIZE     = 256;
const REVEAL_RADIUS = 0.13;
const REVEAL_DECAY  = 0.975;
const REVEAL_FADE   = 0.002;
const REVEAL_EDGE   = [0.18, 0.5];

// ===== Réglages : la plongée au défilement (fractions de la course, de 0 à 1) =====
const ZOOM = {
  ease:  8,              // lissage : plus grand = suit le défilement de plus près
  calm:  [0.00, 0.40],   // ses gestes et son balancement s'éteignent
  face:  [0.00, 0.55],   // il se redresse et nous regarde
  dolly: [0.10, 0.90],   // la caméra plonge vers le casque
  title: [0.00, 0.35],   // les lettres redescendent sous la ligne
  lines: [0.00, 0.25],   // les traits de vitesse s'effacent
  land:  0.5,            // agrandissement du plan le plus proche en fin de plongée
  fill:  0.7,            // taille finale du casque : plus petit = plus gros (moins de 1 = déborde de l'écran)
  helmet: 0.75,          // rayon du casque, en fraction de la longueur de l'os de la tête
  aimY:  -0.2,           // visée verticale (en rayons de casque) : négatif = plus bas, pour centrer la visière
  fade:  [0.50, 0.85],   // le paysage s'efface en douceur dans le ciel crème (début, fin de la course)
};

// ===== Réglages : la visière =====
const VISOR = {
  material: 'transparent_mask',   // nom du matériau de la visière dans le modèle (la console liste les noms si introuvable)
  base:  '#05050f',               // verre noir
  rim:   '#3a3f6b',               // lueur sur les bords
  glint: '#ffffff',               // reflets
};

// ===== Réglages : le regard en fin de plongée =====
const GAZE = {
  turn: [0.22, 0.14],   // rotation maximale vers la souris ou l'inclinaison (radians) : gauche-droite, haut-bas
  text: [14, 9],        // le texte de la visière suit le regard (pixels) : horizontal, vertical
};
// ====================

const lerp    = (a, b, k) => a + (b - a) * k;
const clamp01 = v => Math.min(Math.max(v, 0), 1);
const ease5   = k => k * k * k * (k * (k * 6 - 15) + 10);          // départ et arrivée très doux
const span    = (r, v) => { const k = clamp01((v - r[0]) / (r[1] - r[0])); return k * k * (3 - 2 * k); };   // 0 → 1 sur une plage

// ----- Duotone : partagé par tous les shaders -----
const raw = hex => new THREE.Color().setStyle(hex, THREE.LinearSRGBColorSpace);   // valeurs telles qu'à l'écran
const DUO = {
  uShadow: { value: raw(DUO_SHADOW) }, uMidCol: { value: raw(DUO_MIDTONE) }, uLight: { value: raw(DUO_LIGHT) },
  uDuo: { value: DUO_MIX }, uContrast: { value: DUO_CONTRAST }, uMid: { value: DUO_MID },
  uMask: { value: null }, uScreen: { value: new THREE.Vector2(1, 1) }, uEdge: { value: new THREE.Vector2(...REVEAL_EDGE) }, uReveal: { value: 1 },
};
const DUO_GLSL = `
  uniform vec3 uShadow, uMidCol, uLight; uniform float uDuo, uContrast, uMid, uReveal;
  uniform sampler2D uMask; uniform vec2 uScreen, uEdge;
  vec3 duotone(vec3 c) {
    float l = dot(c, vec3(0.299, 0.587, 0.114));
    float t = clamp((l - uMid) * uContrast + 0.5, 0.0, 1.0);
    return t < 0.5 ? mix(uShadow, uMidCol, t * 2.0) : mix(uMidCol, uLight, t * 2.0 - 1.0);
  }
  // Part de duotone sous ce pixel : 1 = duotone, 0 = vraies couleurs là où le curseur est passé
  float hidden() {
    float m = texture2D(uMask, gl_FragCoord.xy / uScreen).r;
    return uDuo * (1.0 - smoothstep(uEdge.x, uEdge.y, m) * uReveal);
  }
`;
// Ajoute le duotone (et la révélation au curseur) à un matériau standard de three
function duoPatch(shader) {
  Object.assign(shader.uniforms, DUO);
  shader.fragmentShader = DUO_GLSL + shader.fragmentShader.replace('#include <colorspace_fragment>',
    '#include <colorspace_fragment>\n gl_FragColor.rgb = mix(gl_FragColor.rgb, duotone(gl_FragColor.rgb), hidden());');
}

// ----- Masque du curseur : une petite texture où la souris « peint », qui s'étale puis sèche -----
function makeMask(renderer) {
  const make = () => new THREE.WebGLRenderTarget(MASK_SIZE, MASK_SIZE, { depthBuffer: false });
  let a = make(), b = make();
  [a, b].forEach(t => { renderer.setRenderTarget(t); renderer.clear(); });
  renderer.setRenderTarget(null);
  const mat = new THREE.ShaderMaterial({
    depthTest: false, depthWrite: false,
    uniforms: {
      uPrev: { value: null }, uSeg: { value: new THREE.Vector4() }, uAsp: { value: 1 },
      uOn: { value: 0 }, uTime: { value: 0 }, uPx: { value: 1 / MASK_SIZE },
      uCfg: { value: new THREE.Vector3(REVEAL_RADIUS, REVEAL_DECAY, REVEAL_FADE) },
    },
    vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }`,
    fragmentShader: `
      uniform sampler2D uPrev; uniform vec4 uSeg; uniform vec3 uCfg;
      uniform float uAsp, uOn, uTime, uPx;
      varying vec2 vUv;
      void main() {
        vec2 flow = vec2(sin(vUv.y * 11.0 + uTime * 0.9), cos(vUv.x * 11.0 - uTime * 0.7)) * 0.0012;
        vec2 q = vUv - flow;
        float m = texture2D(uPrev, q).r * 0.6
          + (texture2D(uPrev, q + vec2(uPx, 0.0)).r + texture2D(uPrev, q - vec2(uPx, 0.0)).r
           + texture2D(uPrev, q + vec2(0.0, uPx)).r + texture2D(uPrev, q - vec2(0.0, uPx)).r) * 0.1;
        m = max(m * uCfg.y - uCfg.z, 0.0);
        vec2 pa = vUv - uSeg.xy, ba = uSeg.zw - uSeg.xy;
        pa.x *= uAsp; ba.x *= uAsp;
        float h = clamp(dot(pa, ba) / max(dot(ba, ba), 0.000001), 0.0, 1.0);
        float d = length(pa - ba * h);
        m = max(m, uOn * (1.0 - smoothstep(0.0, uCfg.x, d)));
        gl_FragColor = vec4(m, m, m, 1.0);
      }`,
  });
  const scn = new THREE.Scene(), cam = new THREE.Camera();
  const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  quad.frustumCulled = false;
  scn.add(quad);
  DUO.uMask.value = a.texture;
  return {
    step(time, x0, y0, x1, y1, on, aspect) {
      const u = mat.uniforms;
      u.uPrev.value = a.texture; u.uSeg.value.set(x0, y0, x1, y1);
      u.uOn.value = on; u.uTime.value = time; u.uAsp.value = aspect;
      renderer.setRenderTarget(b);
      renderer.render(scn, cam);
      renderer.setRenderTarget(null);
      [a, b] = [b, a];
      DUO.uMask.value = a.texture;
    },
  };
}

// ----- Visière : verre noir à reflets nets (une « matcap » : tout l'éclairage tient dans une petite image) -----
function visorMatcap() {
  const s = 512, c = document.createElement('canvas');
  c.width = c.height = s;
  const g = c.getContext('2d');
  g.fillStyle = VISOR.base; g.fillRect(0, 0, s, s);
  const rim = g.createRadialGradient(s / 2, s / 2, s * 0.3, s / 2, s / 2, s * 0.5);   // bords éclairés (incidence rasante)
  rim.addColorStop(0, 'rgba(0,0,0,0)'); rim.addColorStop(1, VISOR.rim);
  g.fillStyle = rim; g.fillRect(0, 0, s, s);
  g.fillStyle = VISOR.glint;                                                          // reflets nets, façon dessin animé
  g.save(); g.translate(s * 0.34, s * 0.3); g.rotate(-0.7);
  g.beginPath(); g.ellipse(0, 0, s * 0.14, s * 0.05, 0, 0, Math.PI * 2); g.fill();
  g.beginPath(); g.ellipse(s * 0.21, 0, s * 0.035, s * 0.018, 0, 0, Math.PI * 2); g.fill();
  g.restore();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

// ----- Toon : chaque matériau devient un matériau à 2 tons ; la visière devient du verre noir -----
function toonify(root) {
  const W = 64, data = new Uint8Array(W), soft = Math.max(SHADE_SOFT, 1e-4);
  for (let i = 0; i < W; i++) {
    const k = clamp01(((i + 0.5) / W - (SHADE_AT - soft)) / (2 * soft));
    data[i] = Math.round(lerp(TONES[0], TONES[1], k * k * (3 - 2 * k)));
  }
  const ramp = new THREE.DataTexture(data, W, 1, THREE.RedFormat);
  ramp.minFilter = ramp.magFilter = THREE.LinearFilter;
  ramp.needsUpdate = true;

  const visor = new THREE.MeshMatcapMaterial({ name: 'visor', matcap: visorMatcap() });
  const names = new Set();
  let foundVisor = false;
  const done = new Map();
  const convert = m => {
    names.add(m.name);
    if (m.name === VISOR.material) { foundVisor = true; return visor; }
    if (!done.has(m)) done.set(m, new THREE.MeshToonMaterial({
      name: m.name, color: m.color, map: m.map, gradientMap: ramp,
      transparent: m.transparent, opacity: m.opacity, alphaTest: m.alphaTest, side: m.side,
    }));
    return done.get(m);
  };
  root.traverse(o => {
    if (!o.isMesh) return;
    o.material = Array.isArray(o.material) ? o.material.map(convert) : convert(o.material);
    [].concat(o.material).forEach(m => { m.onBeforeCompile = duoPatch; });
  });
  if (!foundVisor) console.warn('Visière : matériau introuvable. Matériaux du modèle :', [...names]);
}

// ----- Normales et contour -----
function outline(root) {
  const meshes = [];
  root.traverse(o => { if (o.isMesh) meshes.push(o); });
  if (!meshes.length) return;

  const box = new THREE.Box3();
  meshes.forEach(m => { m.geometry.computeBoundingBox(); box.union(m.geometry.boundingBox); });
  const s = box.getSize(new THREE.Vector3());
  const tall = Math.max(s.x, s.y, s.z) || 1;

  const q = 1e4 / tall, verts = new Map();
  const key = (p, i) => `${Math.round(p.getX(i) * q)},${Math.round(p.getY(i) * q)},${Math.round(p.getZ(i) * q)}`;
  const at = k => verts.get(k) || verts.set(k, { n: new THREE.Vector3(), near: new Set() }).get(k);
  const A = new THREE.Vector3(), B = new THREE.Vector3(), C = new THREE.Vector3(), N = new THREE.Vector3();
  meshes.forEach(m => {
    const p = m.geometry.attributes.position, idx = m.geometry.index;
    const count = idx ? idx.count : p.count;
    for (let i = 0; i < count; i += 3) {
      const tri = idx ? [idx.getX(i), idx.getX(i + 1), idx.getX(i + 2)] : [i, i + 1, i + 2];
      A.fromBufferAttribute(p, tri[0]); B.fromBufferAttribute(p, tri[1]); C.fromBufferAttribute(p, tri[2]);
      N.subVectors(C, B).cross(A.sub(B));
      const keys = tri.map(v => key(p, v));
      keys.forEach((k, j) => {
        const v = at(k);
        v.n.add(N);
        v.near.add(keys[(j + 1) % 3]).add(keys[(j + 2) % 3]);
      });
    }
  });
  verts.forEach(v => v.n.normalize());

  let soft = new Map();
  verts.forEach((v, k) => soft.set(k, v.n.clone()));
  for (let pass = 0; pass < NORMAL_BLUR; pass++) {
    const next = new Map();
    verts.forEach((v, k) => {
      const sum = soft.get(k).clone();
      v.near.forEach(j => sum.add(soft.get(j)));
      next.set(k, sum.normalize());
    });
    soft = next;
  }

  meshes.forEach(m => {
    const p = m.geometry.attributes.position;
    const hullN = new Float32Array(p.count * 3), shadeN = new Float32Array(p.count * 3);
    for (let i = 0; i < p.count; i++) {
      const k = key(p, i), v = verts.get(k);
      if (!v) continue;
      v.n.toArray(hullN, i * 3);
      soft.get(k).toArray(shadeN, i * 3);
    }
    m.geometry.setAttribute('aSmooth', new THREE.BufferAttribute(hullN, 3));
    if (SMOOTH_SHADING) m.geometry.setAttribute('normal', new THREE.BufferAttribute(shadeN, 3));
  });
  if (!OUTLINE) return;

  const ink = new THREE.MeshBasicMaterial({
    color: INK, side: THREE.BackSide,
    polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2,
  });
  ink.onBeforeCompile = shader => {
    shader.uniforms.uThick = { value: OUTLINE * tall };
    shader.uniforms.uGrow  = { value: OUTLINE_GROW };
    shader.uniforms.uRef   = { value: CAM_Z };                       // distance de référence : la caméra au repos
    shader.vertexShader = 'attribute vec3 aSmooth;\nuniform float uThick, uGrow, uRef;\n' + shader.vertexShader
      .replace('#include <begin_vertex>',
        // plus la caméra est proche, plus on amincit la coque : le trait garde sa taille à l'écran
        'float camDist = -(modelViewMatrix * vec4(position, 1.0)).z;\n' +
        'float thin = pow(clamp(camDist / uRef, 0.02, 1.0), 1.0 - uGrow);\n' +
        'vec3 transformed = position + aSmooth * uThick * thin;');
    duoPatch(shader);
  };
  meshes.forEach(m => {
    const mat = [].concat(m.material)[0];
    if (mat.transparent || mat.alphaTest > 0) return;
    const hull = m.isSkinnedMesh ? new THREE.SkinnedMesh(m.geometry, ink) : new THREE.Mesh(m.geometry, ink);
    if (m.isSkinnedMesh) hull.bind(m.skeleton, m.bindMatrix);
    hull.position.copy(m.position);
    hull.quaternion.copy(m.quaternion);
    hull.scale.copy(m.scale);
    m.parent.add(hull);
  });
}

// ----- Orientation du corps : où pointe la tête, où regarde le torse -----
function facing({ head, chest }) {
  const y = new THREE.Vector3(...head).normalize();
  const z = new THREE.Vector3(...chest);
  const x = new THREE.Vector3().crossVectors(y, z).normalize();
  z.crossVectors(x, y);
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
}

// ----- Membres : on fait viser une direction à chaque os -----
const _a = new THREE.Vector3(), _b = new THREE.Vector3();
const _q = new THREE.Quaternion(), _pq = new THREE.Quaternion(), _wq = new THREE.Quaternion();
function aim(bone, child, dir) {
  const cur = child.getWorldPosition(_a).sub(bone.getWorldPosition(_b)).normalize();
  _q.setFromUnitVectors(cur, _b.copy(dir).normalize());
  bone.parent.getWorldQuaternion(_pq);
  bone.getWorldQuaternion(_wq);
  bone.quaternion.copy(_pq.invert()).multiply(_q).multiply(_wq);
}

function rig(root) {
  const find = n => root.getObjectByName('mixamorig' + n);
  const rows = POSE
    .map(([name, child, fall, rest, swing]) => ({ name, bone: find(name), child: find(child), fall, rest, swing }))
    .filter(r => r.bone && r.child);
  if (rows.length < POSE.length) console.warn('Astronaute : certains os sont introuvables');
  const bind = rows.map(r => r.bone.quaternion.clone());
  const snapshot = (key, amp) => {
    rows.forEach((r, i) => r.bone.quaternion.copy(bind[i]));
    return rows.map(r => {
      const dir = new THREE.Vector3(...r[key]).normalize()
        .addScaledVector(new THREE.Vector3(...r.swing), amp);
      aim(r.bone, r.child, dir);
      return r.bone.quaternion.clone();
    });
  };
  const fallA = snapshot('fall', FLAIL), fallB = snapshot('fall', -FLAIL);
  const restA = snapshot('rest', FLOAT), restB = snapshot('rest', -FLOAT);
  return rows.map((r, i) => ({
    bone: r.bone, fallA: fallA[i], fallB: fallB[i], restA: restA[i], restB: restB[i],
    bind: bind[i], straight: r.name === 'Spine' || r.name === 'Neck',   // dos et cou se redressent pour nous regarder
    rate: 0.8 + 0.4 * ((i * 0.618) % 1), phase: i * 1.7,
  }));
}

// ----- Traits de vitesse : une seule géométrie, un draw call -----
function makeLines() {
  const seed = new Float32Array(LINES * 12), corner = new Float32Array(LINES * 8), index = [];
  for (let i = 0; i < LINES; i++) {
    const s = [Math.random(), Math.random(), Math.random()];
    [[-1, 0], [1, 0], [1, 1], [-1, 1]].forEach((c, j) => {
      seed.set(s, (i * 4 + j) * 3);
      corner.set(c, (i * 4 + j) * 2);
    });
    index.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(LINES * 12), 3));
  geo.setAttribute('aSeed',    new THREE.BufferAttribute(seed, 3));
  geo.setAttribute('aCorner',  new THREE.BufferAttribute(corner, 2));
  geo.setIndex(index);

  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: {
      uTravel: { value: 0 }, uSpeed: { value: 0 },
      uLen: { value: LINE_LEN }, uFan: { value: FAN }, uAlpha: { value: LINE_ALPHA },
      uRes: { value: new THREE.Vector2(1, 1) }, uColor: { value: raw(LINE_COLOR) },
    },
    vertexShader: `
      attribute vec3 aSeed; attribute vec2 aCorner;
      uniform float uTravel, uSpeed, uLen, uFan; uniform vec2 uRes;
      varying float vAlpha, vAlong;
      float hash(float n) { return fract(sin(n) * 43758.5453); }
      void main() {
        float depth = mix(0.35, 1.0, aSeed.z);
        float run   = aSeed.y + uTravel * depth;
        float x     = hash(aSeed.x * 91.7 + floor(run) * 17.3) * 2.0 - 1.0;
        float len   = 2.0 * depth * mix(0.04, uLen, uSpeed);
        float head  = mix(-1.0, 1.0 + 2.0 * uLen, fract(run));
        float y     = head - (1.0 - aCorner.y) * len;
        float w     = mix(1.0, 2.6, aSeed.z) / uRes.x;
        gl_Position = vec4(x * 1.15 * (1.0 + uFan * y) + aCorner.x * w, y, 0.999, 1.0);
        vAlong = aCorner.y;
        vAlpha = mix(0.25, 1.0, aSeed.z) * mix(0.35, 1.0, uSpeed) * smoothstep(0.0, 0.08, uSpeed);
      }`,
    fragmentShader: `
      uniform vec3 uColor; uniform float uAlpha;
      varying float vAlpha, vAlong;
      void main() {
        float a = smoothstep(0.0, 0.7, vAlong) * (1.0 - smoothstep(0.92, 1.0, vAlong));
        gl_FragColor = vec4(uColor, a * vAlpha * uAlpha);
      }`,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1;
  return mesh;
}

// ----- Paysage : les 4 plans composés en une seule passe plein écran -----
async function makeLand(renderer, onLayer) {
  const empty = new THREE.DataTexture(new Uint8Array(4), 1, 1);
  empty.needsUpdate = true;
  const loader = new THREE.TextureLoader();
  const texs = await Promise.all(LAYERS.map(async l => {
    let t = empty;
    try {
      t = await loader.loadAsync(l.file);
      t.premultiplyAlpha = true;
      t.generateMipmaps = false;
      t.minFilter = THREE.LinearFilter;
      renderer.initTexture(t);
    } catch (e) {
      console.warn('Paysage : plan introuvable', l.file);
    }
    onLayer();
    return t;
  }));
  const first = texs.find(t => t !== empty);

  const mat = new THREE.ShaderMaterial({
    transparent: true, premultipliedAlpha: true, depthWrite: false,
    uniforms: {
      uT0: { value: texs[0] }, uT1: { value: texs[1] }, uT2: { value: texs[2] }, uT3: { value: texs[3] },
      uOff: { value: LAYERS.map(() => new THREE.Vector2()) },
      uFit: { value: new THREE.Vector2(1, 1) },
      uDep: { value: new THREE.Vector4(...LAYERS.map(l => l.depth)) },
      uZoom: { value: 0 }, uZoomC: { value: new THREE.Vector2(0.5, 0.5) },
      ...DUO, uSky: { value: 0 }, uSkyCol: { value: raw(SKY_COLOR) },
      uHazeCol: { value: raw(HAZE_COLOR) }, uHaze: { value: new THREE.Vector3(...HAZE) },
      uVig: { value: new THREE.Vector2(...VIGNETTE) }, uAsp: { value: 1 }, uFade: { value: 0 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = vec4(position.xy, 0.9995, 1.0); }`,
    fragmentShader: `
      ${DUO_GLSL}
      uniform float uSky; uniform vec3 uSkyCol;
      uniform vec3 uHazeCol, uHaze; uniform vec2 uVig; uniform float uAsp, uFade;
      uniform sampler2D uT0, uT1, uT2, uT3;
      uniform vec2 uOff[4], uFit, uZoomC; uniform vec4 uDep; uniform float uZoom;
      varying vec2 vUv;
      // Un plan : image centrée, ancrée en bas, décalée de o ; d = sa part de zoom quand la caméra avance
      vec4 plan(sampler2D t, vec2 o, float d) {
        vec2 uv = (vUv - uZoomC) / (1.0 + uZoom * d) + uZoomC;
        vec2 p = vec2((uv.x - 0.5) / uFit.x + 0.5, uv.y / uFit.y) - o;
        vec2 inside = step(vec2(0.0), p) * step(p, vec2(1.0));
        return texture2D(t, p) * inside.x * inside.y;
      }
      void main() {
        vec4 c = plan(uT3, uOff[3], uDep.w);
        vec4 n = plan(uT2, uOff[2], uDep.z); c = n + c * (1.0 - n.a);
        n = plan(uT1, uOff[1], uDep.y);      c = n + c * (1.0 - n.a);
        n = plan(uT0, uOff[0], uDep.x);      c = n + c * (1.0 - n.a);

        float a = c.a + uSky * (1.0 - c.a);
        vec3 col = (c.rgb + uSkyCol * uSky * (1.0 - c.a)) / max(a, 0.0001);
        col = mix(col, duotone(col), hidden());

        float top  = 1.0 - vUv.y;
        float haze = (1.0 - smoothstep(uHaze.x, uHaze.y, top)) * uHaze.z;
        float edge = min(min(vUv.x, 1.0 - vUv.x), min(vUv.y, 1.0 - vUv.y) / uAsp);
        float vig  = (1.0 - smoothstep(0.0, uVig.x, edge)) * uVig.y;
        col = mix(col, uHazeCol, max(haze, vig));

        gl_FragColor = vec4(col * a, a) * (1.0 - uFade);   // fondu vers le fond crème
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -2;
  return { mesh, uniforms: mat.uniforms, aspect: first ? first.image.width / first.image.height : 1.5 };
}

// ----- Titre : chaque lettre dans sa case (ombre comprise), monte à l'arrivée, redescend à la plongée -----
async function makeTitle() {
  const T = TITLE;
  try { await document.fonts.load(`${T.weight} 100px ${T.font}`, T.text); } catch (e) { console.warn('Titre : police introuvable'); }
  // Résolution du dessin : nette à la taille affichée, sans dépasser 4096 px de large
  const padK  = T.stroke + T.rim[1] + Math.max(Math.abs(T.depth[0]), Math.abs(T.depth[1])) + 0.02;
  const probe = document.createElement('canvas').getContext('2d');
  probe.font  = `${T.weight} 100px ${T.font}`;
  const textK = probe.measureText(T.text).width / 100;                                   // largeur du mot pour 1 px de police
  const shown = T.width * Math.max(innerWidth, screen.width) * Math.min(devicePixelRatio || 1, MAX_DPR);   // largeur affichée, en pixels réels
  const px = Math.round(Math.min(Math.max(shown / (textK + 2 * padK), 200), 4096 / (textK + 2 * padK * [...T.text].length)));
  const font = `${T.weight} ${px}px ${T.font}`;

  const cv = document.createElement('canvas'), g = cv.getContext('2d');
  g.font = font;
  g.fontKerning = 'normal';
  const m = g.measureText(T.text);
  const asc = m.actualBoundingBoxAscent, desc = m.actualBoundingBoxDescent;
  const pad = Math.ceil(px * (T.stroke + T.rim[1] + Math.max(Math.abs(T.depth[0]), Math.abs(T.depth[1])) + 0.02));
  const chars = [...T.text], last = chars.length - 1;
  const base = chars.map((_, i) => g.measureText(T.text.slice(0, i)).width);
  const adv  = chars.map((_, i) => g.measureText(T.text.slice(0, i + 1)).width - base[i]);
  const left = base.map((b, i) => b + px * (i * T.spacing + (T.nudge[i] || 0)));
  const wordW = left[last] + adv[last] + pad * 2;
  const H = Math.ceil(asc + desc + pad * 2);

  cv.width = Math.ceil(adv.reduce((s, a) => s + a + pad * 2, 0));
  cv.height = H;
  g.font = font; g.lineJoin = 'round';
  const grad = g.createLinearGradient(0, pad, 0, pad + asc + desc);
  grad.addColorStop(0, T.fill[0]); grad.addColorStop(1, T.fill[1]);
  const off = document.createElement('canvas'), o = off.getContext('2d');

  const pos = [], uv = [], idx = [], index = [];
  let x0 = 0;
  chars.forEach((ch, i) => {
    const cw = adv[i] + pad * 2, x = x0 + pad, y = pad + asc;
    g.save(); g.beginPath(); g.rect(x0, 0, cw, H); g.clip();

    g.fillStyle = g.strokeStyle = T.ink;
    g.lineWidth = px * T.stroke * 2;
    for (let k = 14; k >= 1; k--) {
      const ox = px * T.depth[0] * k / 14, oy = px * T.depth[1] * k / 14;
      g.strokeText(ch, x + ox, y + oy);
      g.fillText(ch, x + ox, y + oy);
    }
    if (T.rim[1] > 0) {
      g.strokeStyle = T.rim[0]; g.lineWidth = px * (T.stroke + T.rim[1]) * 2;
      g.strokeText(ch, x, y);
    }
    g.strokeStyle = T.ink; g.lineWidth = px * T.stroke * 2;
    g.strokeText(ch, x, y);

    off.width = Math.ceil(cw); off.height = H;
    o.font = font;
    o.fillStyle = grad;
    o.fillText(ch, pad, y);
    if (T.bands.length) {
      o.save();
      o.globalCompositeOperation = 'source-atop';
      o.beginPath(); o.rect(0, Math.round(y - (asc + desc) * T.bandZone), off.width, H); o.clip();
      o.fillStyle = T.bands[0][1]; o.fillText(ch, pad, y);
      T.bands.forEach((b, j) => {
        o.fillStyle = j + 1 < T.bands.length ? T.bands[j + 1][1] : grad;
        o.fillText(ch, pad, y - px * b[0]);
      });
      o.restore();
    }
    g.drawImage(off, x0, 0);
    g.restore();

    const X0 = left[i] / wordW * 2 - 1, X1 = (left[i] + cw) / wordW * 2 - 1;
    const U0 = x0 / cv.width, U1 = (x0 + cw) / cv.width;
    pos.push(X0, -1, 0, X1, -1, 0, X1, 1, 0, X0, 1, 0);
    uv.push(U0, 0, U1, 0, U1, 1, U0, 1);
    idx.push(i, i, i, i);
    x0 += cw;
  });
  for (let i = last; i >= 0; i--)
    index.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setAttribute('aIdx', new THREE.Float32BufferAttribute(idx, 1));
  geo.setIndex(index);

  const tex = new THREE.CanvasTexture(cv);
  tex.premultiplyAlpha = true;
  tex.generateMipmaps = false;                                      // affiché à sa taille : pas besoin des versions réduites (mémoire)
  tex.minFilter = THREE.LinearFilter;
  const mat = new THREE.ShaderMaterial({
    transparent: true, premultipliedAlpha: true, depthWrite: false,
    uniforms: {
      uMap: { value: tex }, uT: { value: -1 }, uOut: { value: 0 }, uCount: { value: chars.length },
      uRect: { value: new THREE.Vector4() },
      uAnim: { value: new THREE.Vector3(T.delay, T.duration, T.stagger) },
    },
    vertexShader: `
      attribute float aIdx;
      uniform vec4 uRect; uniform float uT, uOut, uCount; uniform vec3 uAnim;
      varying vec2 vUv; varying float vY;
      void main() {
        float t  = clamp((uT - uAnim.x - aIdx * uAnim.z) / uAnim.y, 0.0, 1.0);
        float up = 1.0 - pow(1.0 - t, 4.0);                         // arrivée : rapide puis très lent
        float o  = clamp(uOut * (1.0 + 0.1 * (uCount - 1.0)) - (uCount - 1.0 - aIdx) * 0.1, 0.0, 1.0);   // plongée : la dernière lettre part d'abord
        vec2 p = position.xy;
        p.y -= (1.0 - up) * 2.2 + o * o * 2.2;
        vUv = uv; vY = p.y;
        gl_Position = vec4(uRect.xy + p * uRect.zw, 0.9993, 1.0);
      }`,
    fragmentShader: `
      uniform sampler2D uMap;
      varying vec2 vUv; varying float vY;
      void main() {
        if (vY < -1.0) discard;
        gl_FragColor = texture2D(uMap, vUv);
      }`,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1.5;
  return { mesh, uniforms: mat.uniforms, ratio: H / wordW, wordW, px };
}

export async function init({ onProgress = () => {} } = {}) {
  const canvas = document.getElementById('scene');
  const still  = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, MAX_DPR));
  const mask = makeMask(renderer);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.05, 50);
  camera.position.z = CAM_Z;
  const sun = new THREE.DirectionalLight(0xffffff, LIGHT[0]);
  sun.position.set(...SUN);
  const lines = makeLines();
  lines.visible = !still;
  scene.add(new THREE.AmbientLight(AMBIENT, LIGHT[1]), sun, lines);

  // Chargement en parallèle : le modèle et les 4 plans du paysage
  let modelPart = 0, layersDone = 0;
  const report = () => onProgress(0.6 * modelPart + 0.3 * layersDone / LAYERS.length);
  const [gltf, land] = await Promise.all([
    new GLTFLoader().loadAsync(MODEL_URL, e => { if (e.total) { modelPart = e.loaded / e.total; report(); } }),
    makeLand(renderer, () => { layersDone++; report(); }),
  ]);
  modelPart = 1; report();
  scene.add(land.mesh);
  const title = await makeTitle();
  scene.add(title.mesh);

  // Normalisation : centré, 1 unité de haut
  const box    = new THREE.Box3().setFromObject(gltf.scene);
  const center = box.getCenter(new THREE.Vector3());
  const k      = 1 / (box.getSize(new THREE.Vector3()).y || 1);
  const norm   = new THREE.Group();
  norm.add(gltf.scene);
  norm.scale.setScalar(k);
  norm.position.copy(center).multiplyScalar(-k);
  const pivot = new THREE.Group();
  pivot.add(norm);
  scene.add(pivot);

  toonify(gltf.scene);
  outline(gltf.scene);
  gltf.scene.traverse(o => { if (o.isMesh) o.frustumCulled = false; });

  const limbs = rig(gltf.scene);
  const qFall = facing(BODY_FALL), qRest = facing(BODY_REST), qFace = facing(BODY_FACE);
  const headBone = gltf.scene.getObjectByName('mixamorigHead');
  const headTop  = gltf.scene.getObjectByName('mixamorigHeadTop_End');
  if (!headBone || !headTop) console.warn('Plongée : os de la tête introuvables');

  // ----- État -----
  let viewW = 1, viewH = 1, size = 1;
  let fallStart = null, ramp = 1, onArrive = null;
  let running = false, onScreen = true, raf = 0, last = 0, travel = 0, clock = 0;
  const SC = window.Scroll || { zoom: 0 };          // avance du défilement (scroll.js)
  let zs = 0;                                        // avance lissée
  const U = lines.material.uniforms;
  const L = land.uniforms;
  const titleEl = document.querySelector('.hero-title');   // calque HTML sélectionnable, posé sur le titre dessiné
  const visorEl = document.querySelector('.visor-content');   // texte et bouton de la visière
  const _g = new THREE.Quaternion(), _ge = new THREE.Euler();
  let lastShift = '';
  let tx = 0, ty = 0, px = 0, py = 0;
  let mx = -9, my = -9, pmx = -9, pmy = -9;
  let awake = 0, moved = false;
  let fx = 0, fy = 0;   // part de la parallaxe due à la souris ou au doigt (-1..1)
  let gx = 0, gy = 0;   // part due à l'inclinaison du téléphone (-1..1)

  // Position de la souris ou du doigt : parallaxe et pinceau du révélé
  const aim = (cx, cy) => {
    fx = cx / innerWidth * 2 - 1;
    fy = 1 - cy / innerHeight * 2;
    const r = canvas.getBoundingClientRect();
    mx = (cx - r.left) / r.width;
    my = 1 - (cy - r.top) / r.height;
    if (awake <= 0) { pmx = mx; pmy = my; }
    awake = 3; moved = true;
  };

  // Souris et stylet
  addEventListener('pointermove', e => {
    if (e.pointerType !== 'touch') aim(e.clientX, e.clientY);
  }, { passive: true });

  // Doigt : les événements tactiles continuent pendant le défilement. Passifs, ils ne le bloquent jamais.
  addEventListener('touchstart', e => {
    const t = e.touches[0]; if (!t) return;
    aim(t.clientX, t.clientY);
    pmx = mx; pmy = my;                            // nouveau toucher : on ne le relie pas au trait précédent
  }, { passive: true });
  addEventListener('touchmove', e => {
    const t = e.touches[0]; if (t) aim(t.clientX, t.clientY);
  }, { passive: true });
  addEventListener('touchend', e => {
    if (!e.touches.length) { fx = 0; fy = 0; }    // doigt levé : la parallaxe revient au gyroscope seul
  }, { passive: true });

  // Gyroscope : le décor suit l'inclinaison du téléphone (pages en HTTPS seulement)
  if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
    let nv = 0, nh = 0, lastT = 0;
    const onTilt = e => {
      if (e.beta == null || e.gamma == null) return;
      const a = (screen.orientation && screen.orientation.angle) || 0;   // téléphone tourné : on échange les axes
      let h = e.gamma, v = e.beta;
      if (a === 90)       { h = e.beta;  v = -e.gamma; }
      else if (a === 270) { h = -e.beta; v = e.gamma; }
      const now = performance.now();
      const k = 1 - Math.exp(-(now - lastT) / 1000 / TILT.recenter);     // premier relevé : k vaut 1, il devient la position neutre
      lastT = now;
      nh += (h - nh) * k;  nv += (v - nv) * k;                           // la position neutre suit lentement ta main
      gx = Math.max(-1, Math.min(1, TILT.dir[0] * (h - nh) / TILT.range));
      gy = Math.max(-1, Math.min(1, TILT.dir[1] * (v - nv) / TILT.range));
    };
    addEventListener('deviceorientation', onTilt);                        // on écoute tout de suite (Android : les relevés arrivent sans rien demander)
    if (typeof DeviceOrientationEvent !== 'undefined' && typeof DeviceOrientationEvent.requestPermission === 'function') {
      addEventListener('touchend', () => {                                // iPhone : les relevés n'arrivent qu'une fois l'autorisation accordée
        DeviceOrientationEvent.requestPermission().catch(() => {});
      }, { once: true, passive: true });
    }
  }
  const _e = new THREE.Euler(), _s = new THREE.Quaternion(), _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion();
  const _h0 = new THREE.Vector3(), _h1 = new THREE.Vector3(), _tgt = new THREE.Vector3(), _c = new THREE.Vector3();
  const render = () => renderer.render(scene, camera);

  function apply(ms, dt) {
    const since = fallStart === null ? -1 : ms - fallStart;
    const e = still ? 1 : 1 - Math.pow(1 - clamp01(since / ENTER_MS), 3);
    const a = still ? 1 : clamp01((since - FALL_MS) / ARRIVE_MS);
    const g = ease5(1 - Math.pow(1 - a, ARRIVE_TAIL));
    const t = still ? 0 : Math.max(since, 0) / 1000;

    if (a > 0 && onArrive) { const signal = onArrive; onArrive = null; signal(); }

    // Défilement : avance lissée, partagée avec hero.js (0 = hero, 1 = casque plein écran)
    if (dt > 0) zs += (SC.zoom - zs) * (1 - Math.exp(-dt * ZOOM.ease));
    SC.smooth = zs;
    const z  = still ? 0 : zs;
    const ck = span(ZOOM.calm, z);                                     // calme
    const fk = span(ZOOM.face, z);                                     // il nous regarde
    const dk = ease5(clamp01((z - ZOOM.dolly[0]) / (ZOOM.dolly[1] - ZOOM.dolly[0])));   // plongée
    DUO.uReveal.value = 1 - dk;                                        // le révélé s'efface pendant la plongée : visière nette pour lire

    // Vitesse du ciel
    const speed = still || fallStart === null ? 0
      : since < 0 ? Math.pow(1 - Math.min(-since / ramp, 1), 2)
      : IDLE_SPEED + (1 - IDLE_SPEED) * (1 - g);
    travel += speed * LINE_RATE * dt;
    U.uSpeed.value = speed;
    U.uTravel.value = travel;
    U.uAlpha.value = LINE_ALPHA * (1 - span(ZOOM.lines, z));
    lines.visible = !still && U.uAlpha.value > 0.001;

    // Position
    const startY = viewH / 2 + size;
    const drift  = e * (1 - g);
    pivot.position.set(
      lerp(FALLING.x, REST.x, g) * viewW + Math.sin(t * 1.3) * DRIFT[0] * viewW * drift,
      lerp(lerp(startY, FALLING.y * viewH, e), REST.y * viewH, g)
        + Math.sin(t * 1.9 + 1) * DRIFT[1] * viewH * drift
        + Math.sin(t * 0.8) * 0.03 * size * g * (1 - ck),
      0);

    // Corps : chute, repos, puis face à nous pendant la plongée
    const sway = lerp(SWAY[0], SWAY[1], g) * (1 - ck);
    _e.set(
      Math.sin(t * 1.1) * sway - (1 - e) * ENTER_SPIN,
      Math.sin(t * 0.7 + 1) * sway * 1.4,
      Math.sin(t * 0.9 + 2) * sway);
    pivot.quaternion.slerpQuaternions(qFall, qRest, g).premultiply(_s.setFromEuler(_e)).slerp(qFace, fk);
    // Regard : en fin de plongée, il se tourne un peu vers la souris (ou selon l'inclinaison du téléphone)
    if (dk > 0) pivot.quaternion.premultiply(_g.setFromEuler(_ge.set(-py * GAZE.turn[1] * dk, px * GAZE.turn[0] * dk, 0)));

    // Membres : les gestes s'éteignent, le dos et le cou se redressent
    clock += dt * lerp(FLAIL_RATE, FLOAT_RATE, g);
    for (const b of limbs) {
      const w = 0.5 + 0.5 * Math.sin(clock * b.rate + b.phase) * (1 - ck);
      _qa.slerpQuaternions(b.fallA, b.fallB, w);
      _qb.slerpQuaternions(b.restA, b.restB, w);
      b.bone.quaternion.slerpQuaternions(_qa, _qb, g);
      if (b.straight && fk > 0) b.bone.quaternion.slerp(b.bind, fk);
    }

    // Masque du curseur
    if (awake > 0 && dt > 0) {
      awake -= dt;
      mask.step(ms / 1000, pmx, pmy, mx, my, moved ? 1 : 0, camera.aspect);
      pmx = mx; pmy = my; moved = false;
    }

    // Ciel et titre
    L.uSky.value = still ? 1 : fallStart === null ? 0 : clamp01(1 + since / ramp);
    title.uniforms.uT.value = still ? 99 : (since - FALL_MS) / 1000;
    title.uniforms.uOut.value = span(ZOOM.title, z);
    title.mesh.visible = title.uniforms.uOut.value < 1;
    titleEl?.classList.toggle('is-shown',
    title.uniforms.uT.value > TITLE.delay + TITLE.duration * 0.5 && title.uniforms.uOut.value < 0.3);

    // Paysage : montée à l'arrivée, parallaxe à la souris
    tx = Math.max(-1, Math.min(1, fx + gx));   // parallaxe = doigt ou souris + inclinaison
    ty = Math.max(-1, Math.min(1, fy + gy));
    const follow = 1 - Math.exp(-dt * POINTER_EASE);
    px += (tx - px) * follow;
    py += (ty - py) * follow;
    LAYERS.forEach((l, i) => {
      const kk = still ? 1 : clamp01((since - FALL_MS - i * LAYER_GAP) / LAYER_MS);
      const up = 1 - Math.pow(1 - kk, 3);
      L.uOff.value[i].set(
        -px * PARALLAX[0] * l.depth,
        -l.drop - (1 - up) * l.rise - py * PARALLAX[1] * l.depth);
    });
    // Le texte de la visière suit le regard (uniquement quand la valeur change)
    const shift = dk > 0 ? `${(px * GAZE.text[0] * dk).toFixed(1)}px ${(-py * GAZE.text[1] * dk).toFixed(1)}px` : '';
    if (visorEl && shift !== lastShift) { visorEl.style.translate = shift; lastShift = shift; }

    // Caméra : plonge vers le casque en le gardant au centre
    camera.position.set(0, 0, CAM_Z);
    camera.lookAt(0, 0, 0);
    if (dk > 0 && headBone && headTop) {
      pivot.updateMatrixWorld(true);
      headBone.getWorldPosition(_h0);
      headTop.getWorldPosition(_h1);
      const R = _h0.distanceTo(_h1) * ZOOM.helmet;                    // rayon du casque
      _tgt.addVectors(_h0, _h1).multiplyScalar(0.5);
      _tgt.y += ZOOM.aimY * R;
      const tanMin = Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * Math.min(1, camera.aspect);   // écran étroit : on cadre sur la largeur
      const dist = R * ZOOM.fill / tanMin;
      camera.position.set(_tgt.x * dk, _tgt.y * dk, lerp(CAM_Z, _tgt.z + dist, dk));
      camera.lookAt(_tgt.x * dk, _tgt.y * dk, _tgt.z * dk);
      camera.updateMatrixWorld();
      _c.copy(_tgt).project(camera);                                   // le paysage grossit autour du casque
      L.uZoomC.value.set(_c.x * 0.5 + 0.5, _c.y * 0.5 + 0.5);
    }
    L.uZoom.value = ZOOM.land * dk;
    L.uFade.value = span(ZOOM.fade, z);                                // le paysage s'efface en douceur
    land.mesh.visible = L.uFade.value < 0.999;                         // entièrement effacé : plus dessiné
    window.Sound?.set(U.uSpeed.value, dk, g);                          // le son suit la scène : vitesse du vent, plongée, arrivée
  }

  function fit(draw = true) {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, MAX_DPR));   // suit le zoom du navigateur
    renderer.setSize(w, h, false);
    renderer.getDrawingBufferSize(DUO.uScreen.value);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    viewH = 2 * Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * CAM_Z;
    viewW = viewH * camera.aspect;
    size  = Math.min(REST.size * viewH, MAX_SIZE * viewW);
    pivot.scale.setScalar(size);
    U.uRes.value.set(w, h);
    const landH = Math.max(LAND_ZOOM * camera.aspect / land.aspect, LAND_MIN_H);
    L.uFit.value.set(landH * land.aspect / camera.aspect, landH);
    L.uAsp.value = camera.aspect;
    title.uniforms.uRect.value.set(0, TITLE.y * 2, TITLE.width, TITLE.width * title.ratio * camera.aspect);
    if (titleEl) {                                                       // le calque HTML prend la place et la taille du titre dessiné
      const scale = TITLE.width * w / title.wordW;
      titleEl.style.setProperty('--t-size', (title.px * scale).toFixed(2) + 'px');
      titleEl.style.setProperty('--t-y', (h / 2 - TITLE.y * h).toFixed(1) + 'px');
    }
    if (draw) { apply(performance.now(), 0); render(); }
  }

  function frame(ms) {
    raf = requestAnimationFrame(frame);
    const resting = ms - fallStart >= FALL_MS + ARRIVE_MS;
    if (resting && ms - last < 1000 / IDLE_FPS - 2) return;
    const dt = Math.min(Math.max(ms - last, 0) / 1000, 0.05);
    last = ms;
    apply(ms, dt);
    render();
  }
  function sync() {
    const should = running && onScreen;
    if (should && !raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
    if (!should && raf) { cancelAnimationFrame(raf); raf = 0; }
  }

  fit(false);
  apply(performance.now(), 0);
  await renderer.compileAsync(scene, camera);
  render();
  onProgress(1);

  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; sync(); }).observe(canvas);
  new ResizeObserver(() => fit()).observe(canvas);

  return {
    fall({ delay = 0, onArrive: signal } = {}) {
      if (fallStart !== null) return;
      if (still) { fallStart = 0; signal?.(); return; }
      onArrive = signal || null;
      ramp = Math.max(delay, 1);
      fallStart = performance.now() + Math.max(delay, 0);
      running = true;
      sync();
    },
  };
}