// ===== Scène 3D : la chute de l'astronaute =====
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ===== Réglages : cadrage (x en largeurs d'écran, y et taille en hauteurs ; y : 0 = centre, 0.5 = bord haut) =====
const MODEL_URL = 'models/astronaute.glb';
const FOV       = 35;
const CAM_Z     = 10;
const FALLING   = { x: 0, y: 0.02 };                 // où il se tient pendant la chute
const REST      = { x: 0.02, y: 0.09, size: 0.44 };  // où il se pose (y plus petit = plus bas, donc plus sur le titre)
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
const BODY_FALL = { head: [-0.7, -0.45, 0.25], chest: [-0.3, 0.75, 0.6] };   // sur le dos, tête en bas à gauche (ta référence)
const BODY_REST = { head: [-0.7, 0.42, 0.15],  chest: [0.4, 0.55, 0.75] };   // toujours renversé, tête en haut à gauche, jambes vers le titre
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
const SHADE_AT       = 0.56;              // où tombe la frontière : 0.5 = pile à mi-chemin, plus grand = plus d'ombre
const SHADE_SOFT     = 0.02;              // douceur de la frontière (0 = marche nette, qui scintille)
const NORMAL_BLUR    = 2;                 // lissage des ombres : 0 = aucun, 3 = très grandes formes
const LIGHT          = [2.3, 0.9];        // intensité du soleil, de la lumière d'ambiance
const SUN            = [2, 3, 6];         // d'où vient le soleil (droite, haut, vers toi) : plutôt de face
const AMBIENT        = '#c9d6ff';         // teinte des ombres : celle du ciel
const INK            = '#1c2452';         // couleur du contour
const OUTLINE        = 0.007;             // épaisseur du contour, en fraction de la taille du personnage (0 = aucun)
const SMOOTH_SHADING = true;              // true = ombres en grandes formes, false = facettes (elles clignotent)

// ===== Réglages : les traits de vitesse =====
const LINES      = 70;
const LINE_COLOR = '#1c2452';
const LINE_ALPHA = 0.55;
const LINE_RATE  = 2.4;                // hauteurs d'écran par seconde à pleine vitesse
const LINE_LEN   = 0.45;               // longueur à pleine vitesse (en hauteurs d'écran)
const IDLE_SPEED = 0.1;                // vitesse résiduelle une fois arrivé (0 = ciel calme)
const FAN        = 0.12;               // éventail : les traits s'écartent vers le haut (0 = parallèles)
const IDLE_FPS   = 60;                 // plafond au repos (30 = plus économe, un peu moins fluide)

// ===== Réglages : le paysage =====
// 4 plans, du plus proche au plus loin (le shader en attend exactement 4).
// drop  : descente du plan pour dégager le ciel (en hauteurs d'image)
// depth : part de parallaxe (1 = bouge le plus)
// rise  : distance de montée à l'arrivée (en hauteurs d'image)
const LAYERS = [
  { file: 'img/plan-1.webp', drop: 0.04, depth: 1.00, rise: 0.34 },   // cabane et prairie
  { file: 'img/plan-2.webp', drop: 0.12, depth: 0.55, rise: 0.50 },   // collines
  { file: 'img/plan-3.webp', drop: 0.20, depth: 0.30, rise: 0.66 },   // montagne boisée
  { file: 'img/plan-4.webp', drop: 0.28, depth: 0.15, rise: 0.72 },   // pics
];
const LAND_ZOOM    = 1.03;            // marge autour de l'écran, pour que les bords ne se voient jamais
const LAND_MIN_H   = 0.95;            // écran étroit : le paysage garde au moins cette hauteur (en hauteurs d'écran)
const PARALLAX     = [0.008, 0.004];  // amplitude à la souris : horizontale, verticale (en tailles d'image)
const POINTER_EASE = 6;               // réactivité du suivi de la souris (plus grand = plus nerveux)
const LAYER_MS     = 1200;            // durée de montée d'un plan
const LAYER_GAP    = 160;             // décalage entre deux plans

// ===== Réglages : le duotone =====
const DUO_SHADOW   = '#0D0D33';   // couleur des ombres
const DUO_LIGHT    = '#FFF2D9';   // couleur des lumières
const DUO_CONTRAST = 1.0;         // 1 = neutre, plus grand = plus tranché
const DUO_MID      = 0.45;         // point milieu : plus grand = image plus sombre
const DUO_MIX      = 1;           // 1 = duotone complet, 0 = vraies couleurs
const SKY_COLOR    = '#e8eef7';   // ciel en vraies couleurs
const DUO_MIDTONE  = '#8f8676';        // ton moyen gris chaud : évite le violet
const HAZE_COLOR   = '#FFF9E5';        // couleur de la brume et du bord
const HAZE         = [0.30, 1.0, 0.8]; // brume : totale au-dessus de 30 % (depuis le haut), nulle à 100 %, force
const VIGNETTE     = [0.08, 0.5];      // bord crème : largeur (en largeurs d'écran), force

// ===== Réglages : le titre =====
const TITLE = {
  text: 'VOYAGE', font: '"Evori"', weight: 400,
  width: 0.62,                      // largeur à l'écran (en largeurs d'écran)
  y: -0.08,                         // centre (en hauteurs d'écran : 0 = milieu, négatif = plus bas)
  fill: ['#FFFFFF', '#FDF1D7'],     // dégradé vertical : haut, bas
  bands: [[0.06, '#A39A8C'], [0.10, '#CFC6B5']],   // bandes d'ombre en bas : [hauteur, couleur], de la plus basse à la plus haute
  rim: ['#FFF9E5', 0],          // liseré clair autour du contour : couleur, épaisseur (0 = aucun)
  spacing: 0,                       // espacement global entre les lettres (fraction de la hauteur, négatif = plus serré)
  nudge: [0, 0, 0, -0.05, 0, 0],        // décalage de chaque lettre, de V à E (fraction de la hauteur, négatif = vers la gauche)
  ink: '#0D0D33',                   // contour et extrusion
  stroke: 0.03,                     // épaisseur du contour (fraction de la hauteur des lettres)
  depth: [-0.035, 0.07],            // extrusion : décalage horizontal, vertical (fraction de la hauteur)
  delay: 0.4, duration: 1.3, stagger: 0.08,   // arrivée lettre par lettre, en secondes
  bandZone: 0.3,                    // les bandes d'ombre n'apparaissent que dans le bas des lettres (fraction de leur hauteur)
};

// ===== Réglages : la révélation au curseur =====
const MASK_SIZE     = 256;          // résolution du masque (fixe, quel que soit l'écran)
const REVEAL_RADIUS = 0.13;         // taille du pinceau (en hauteurs d'écran)
const REVEAL_DECAY  = 0.975;        // persistance : plus proche de 1 = la couleur reste plus longtemps
const REVEAL_FADE   = 0.002;        // séchage minimal par image (garantit le retour à zéro)
const REVEAL_EDGE   = [0.18, 0.5];  // netteté du bord : deux valeurs proches = bord net
// ====================

const lerp    = (a, b, k) => a + (b - a) * k;
const clamp01 = v => Math.min(Math.max(v, 0), 1);
const ease5   = k => k * k * k * (k * (k * 6 - 15) + 10);          // départ et arrivée très doux
// ----- Duotone : partagé par tous les shaders -----
const raw = hex => new THREE.Color().setStyle(hex, THREE.LinearSRGBColorSpace);   // valeurs telles qu'à l'écran
const DUO = {
  uShadow: { value: raw(DUO_SHADOW) }, uMidCol: { value: raw(DUO_MIDTONE) }, uLight: { value: raw(DUO_LIGHT) },
  uDuo: { value: DUO_MIX }, uContrast: { value: DUO_CONTRAST }, uMid: { value: DUO_MID },
  uMask: { value: null }, uScreen: { value: new THREE.Vector2(1, 1) }, uEdge: { value: new THREE.Vector2(...REVEAL_EDGE) },
};
const DUO_GLSL = `
  uniform vec3 uShadow, uMidCol, uLight; uniform float uDuo, uContrast, uMid;
  uniform sampler2D uMask; uniform vec2 uScreen, uEdge;
  vec3 duotone(vec3 c) {
    float l = dot(c, vec3(0.299, 0.587, 0.114));                       // luminosité
    float t = clamp((l - uMid) * uContrast + 0.5, 0.0, 1.0);
    return t < 0.5 ? mix(uShadow, uMidCol, t * 2.0) : mix(uMidCol, uLight, t * 2.0 - 1.0);   // ombre → gris chaud → lumière
  }
  // Part de duotone sous ce pixel : 1 = duotone, 0 = vraies couleurs là où le curseur est passé
  float hidden() {
    float m = texture2D(uMask, gl_FragCoord.xy / uScreen).r;
    return uDuo * (1.0 - smoothstep(uEdge.x, uEdge.y, m));
  }
`;

// ----- Masque du curseur : une petite texture où la souris « peint », qui s'étale puis sèche -----
function makeMask(renderer) {
  const make = () => new THREE.WebGLRenderTarget(MASK_SIZE, MASK_SIZE, { depthBuffer: false });
  let a = make(), b = make();                                       // deux textures qu'on échange à chaque image
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
        vec2 flow = vec2(sin(vUv.y * 11.0 + uTime * 0.9), cos(vUv.x * 11.0 - uTime * 0.7)) * 0.0012;   // léger courant : le bord ondule
        vec2 q = vUv - flow;
        float m = texture2D(uPrev, q).r * 0.6                                                           // s'étale un peu
          + (texture2D(uPrev, q + vec2(uPx, 0.0)).r + texture2D(uPrev, q - vec2(uPx, 0.0)).r
           + texture2D(uPrev, q + vec2(0.0, uPx)).r + texture2D(uPrev, q - vec2(0.0, uPx)).r) * 0.1;
        m = max(m * uCfg.y - uCfg.z, 0.0);                                                              // sèche
        vec2 pa = vUv - uSeg.xy, ba = uSeg.zw - uSeg.xy;                                                // trait entre deux positions de la souris
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
// Ajoute le duotone à un matériau standard de three, après la conversion de couleur finale
function duoPatch(shader) {
  Object.assign(shader.uniforms, DUO);
  shader.fragmentShader = DUO_GLSL + shader.fragmentShader.replace('#include <colorspace_fragment>',
    '#include <colorspace_fragment>\n gl_FragColor.rgb = mix(gl_FragColor.rgb, duotone(gl_FragColor.rgb), uDuo);');
}

// ----- Toon : chaque matériau devient un matériau à 2 tons -----
function toonify(root) {
  // La rampe : ombre d'un côté, lumière de l'autre, frontière adoucie sur une bande étroite
  const W = 64, data = new Uint8Array(W), soft = Math.max(SHADE_SOFT, 1e-4);
  for (let i = 0; i < W; i++) {
    const k = clamp01(((i + 0.5) / W - (SHADE_AT - soft)) / (2 * soft));
    data[i] = Math.round(lerp(TONES[0], TONES[1], k * k * (3 - 2 * k)));
  }
  const ramp = new THREE.DataTexture(data, W, 1, THREE.RedFormat);
  ramp.minFilter = ramp.magFilter = THREE.LinearFilter;
  ramp.needsUpdate = true;

  const done = new Map();
  const convert = m => {
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
}

// ----- Normales et contour -----
// 1) Normales lissées (pour un contour sans déchirure) puis floutées (pour des ombres en grandes formes)
// 2) Contour : une copie de chaque pièce, gonflée, bleu nuit, dont on ne voit que les faces arrière
function outline(root) {
  const meshes = [];
  root.traverse(o => { if (o.isMesh) meshes.push(o); });
  if (!meshes.length) return;

  // Taille du personnage dans ses propres unités
  const box = new THREE.Box3();
  meshes.forEach(m => { m.geometry.computeBoundingBox(); box.union(m.geometry.boundingBox); });
  const s = box.getSize(new THREE.Vector3());
  const tall = Math.max(s.x, s.y, s.z) || 1;

  // Une entrée par position dans l'espace : normale moyenne + positions voisines
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
      N.subVectors(C, B).cross(A.sub(B));                          // normale de la face, pondérée par sa surface
      const keys = tri.map(v => key(p, v));
      keys.forEach((k, j) => {
        const v = at(k);
        v.n.add(N);
        v.near.add(keys[(j + 1) % 3]).add(keys[(j + 2) % 3]);
      });
    }
  });
  verts.forEach(v => v.n.normalize());

  // Flou : chaque normale se mélange à celles de ses voisines, NORMAL_BLUR fois
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

  // Le matériau du contour : on pousse chaque sommet le long de sa normale lissée, avant le squelette
  const ink = new THREE.MeshBasicMaterial({
    color: INK, side: THREE.BackSide,
    polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 2,   // reculé d'un cheveu : ne perce pas entre deux pièces
  });
  ink.onBeforeCompile = shader => {
    shader.uniforms.uThick = { value: OUTLINE * tall };
    shader.vertexShader = 'attribute vec3 aSmooth;\nuniform float uThick;\n' + shader.vertexShader
      .replace('#include <begin_vertex>', 'vec3 transformed = position + aSmooth * uThick;');
      duoPatch(shader);
  };
  meshes.forEach(m => {
    const mat = [].concat(m.material)[0];
    if (mat.transparent || mat.alphaTest > 0) return;              // pas de contour autour des parties transparentes
    const hull = m.isSkinnedMesh ? new THREE.SkinnedMesh(m.geometry, ink) : new THREE.Mesh(m.geometry, ink);
    if (m.isSkinnedMesh) hull.bind(m.skeleton, m.bindMatrix);      // même squelette : le contour suit les membres
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
  z.crossVectors(x, y);                                            // torse rendu perpendiculaire à la tête
  return new THREE.Quaternion().setFromRotationMatrix(new THREE.Matrix4().makeBasis(x, y, z));
}

// ----- Membres : on fait viser une direction à chaque os, sans dépendre des axes du rig -----
const _a = new THREE.Vector3(), _b = new THREE.Vector3();
const _q = new THREE.Quaternion(), _pq = new THREE.Quaternion(), _wq = new THREE.Quaternion();
function aim(bone, child, dir) {
  const cur = child.getWorldPosition(_a).sub(bone.getWorldPosition(_b)).normalize();   // direction actuelle de l'os
  _q.setFromUnitVectors(cur, _b.copy(dir).normalize());                                // rotation la plus courte vers la cible
  bone.parent.getWorldQuaternion(_pq);
  bone.getWorldQuaternion(_wq);
  bone.quaternion.copy(_pq.invert()).multiply(_q).multiply(_wq);
}

// Calcule une fois pour toutes 4 poses par os : chute A/B et repos A/B (A et B = les deux extrêmes du geste)
function rig(root) {
  const find = n => root.getObjectByName('mixamorig' + n);
  const rows = POSE
    .map(([name, child, fall, rest, swing]) => ({ bone: find(name), child: find(child), fall, rest, swing }))
    .filter(r => r.bone && r.child);
  if (rows.length < POSE.length) console.warn('Astronaute : certains os sont introuvables');
  const bind = rows.map(r => r.bone.quaternion.clone());
  const snapshot = (key, amp) => {
    rows.forEach((r, i) => r.bone.quaternion.copy(bind[i]));       // on repart toujours de la pose d'origine
    return rows.map(r => {
      const dir = new THREE.Vector3(...r[key]).normalize()
        .addScaledVector(new THREE.Vector3(...r.swing), amp);
      aim(r.bone, r.child, dir);                                    // parents d'abord : l'ordre de POSE compte
      return r.bone.quaternion.clone();
    });
  };
  const fallA = snapshot('fall', FLAIL), fallB = snapshot('fall', -FLAIL);
  const restA = snapshot('rest', FLOAT), restB = snapshot('rest', -FLOAT);
  return rows.map((r, i) => ({
    bone: r.bone, fallA: fallA[i], fallB: fallB[i], restA: restA[i], restB: restB[i],
    rate: 0.8 + 0.4 * ((i * 0.618) % 1), phase: i * 1.7,           // chaque membre a son rythme
  }));
}

// ----- Traits de vitesse : une seule géométrie, un draw call, animés dans le shader -----
function makeLines() {
  const seed = new Float32Array(LINES * 12), corner = new Float32Array(LINES * 8), index = [];
  for (let i = 0; i < LINES; i++) {
    const s = [Math.random(), Math.random(), Math.random()];      // colonne, phase, profondeur
    [[-1, 0], [1, 0], [1, 1], [-1, 1]].forEach((c, j) => {
      seed.set(s, (i * 4 + j) * 3);
      corner.set(c, (i * 4 + j) * 2);
    });
    index.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(LINES * 12), 3));   // inutilisé, exigé par three
  geo.setAttribute('aSeed',    new THREE.BufferAttribute(seed, 3));
  geo.setAttribute('aCorner',  new THREE.BufferAttribute(corner, 2));
  geo.setIndex(index);

  const mat = new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: {
      uTravel: { value: 0 }, uSpeed: { value: 0 },
      uLen: { value: LINE_LEN }, uFan: { value: FAN }, uAlpha: { value: LINE_ALPHA },
      uRes: { value: new THREE.Vector2(1, 1) }, uColor: { value: raw(LINE_COLOR) }
    },
    vertexShader: `
      attribute vec3 aSeed;      // colonne, phase, profondeur
      attribute vec2 aCorner;    // x : -1/+1 (bords), y : 0 (queue) / 1 (tête)
      uniform float uTravel, uSpeed, uLen, uFan;
      uniform vec2 uRes;
      varying float vAlpha, vAlong;
      float hash(float n) { return fract(sin(n) * 43758.5453); }
      void main() {
        float depth = mix(0.35, 1.0, aSeed.z);                        // lointain = lent, court, fin, pâle
        float run   = aSeed.y + uTravel * depth;
        float x     = hash(aSeed.x * 91.7 + floor(run) * 17.3) * 2.0 - 1.0;   // nouvelle colonne à chaque passage
        float len   = 2.0 * depth * mix(0.04, uLen, uSpeed);          // la longueur suit la vitesse
        float head  = mix(-1.0, 1.0 + 2.0 * uLen, fract(run));        // du bas vers le haut de l'écran
        float y     = head - (1.0 - aCorner.y) * len;
        float w     = mix(1.0, 2.6, aSeed.z) / uRes.x;                // épaisseur : 1 à 2,6 px
        gl_Position = vec4(x * 1.15 * (1.0 + uFan * y) + aCorner.x * w, y, 0.999, 1.0);   // tout au fond : l'astronaute passe devant
        vAlong = aCorner.y;
        vAlpha = mix(0.25, 1.0, aSeed.z) * mix(0.35, 1.0, uSpeed) * smoothstep(0.0, 0.08, uSpeed);
      }`,
    fragmentShader: `
      uniform vec3 uColor; uniform float uAlpha;
      varying float vAlpha, vAlong;
      void main() {
        float a = smoothstep(0.0, 0.7, vAlong) * (1.0 - smoothstep(0.92, 1.0, vAlong));   // queue qui s'efface, tête adoucie
        gl_FragColor = vec4(uColor, a * vAlpha * uAlpha);
      }`,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1;
  return mesh;
}

// ----- Paysage : les 4 plans composés en une seule passe plein écran -----
// ----- Paysage : les 4 plans composés en une seule passe plein écran -----
async function makeLand(renderer, onLayer) {
  const empty = new THREE.DataTexture(new Uint8Array(4), 1, 1);     // plan manquant : transparent
  empty.needsUpdate = true;
  const loader = new THREE.TextureLoader();
  const texs = await Promise.all(LAYERS.map(async l => {
    let t = empty;
    try {
      t = await loader.loadAsync(l.file);
      t.premultiplyAlpha = true;              // évite les liserés sur les bords détourés
      t.generateMipmaps = false;              // un tiers de mémoire en moins
      t.minFilter = THREE.LinearFilter;
      renderer.initTexture(t);                // envoyée à la carte graphique pendant le loader
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
      uOff: { value: LAYERS.map(() => new THREE.Vector2()) },       // décalage de chaque plan
      uFit: { value: new THREE.Vector2(1, 1) },                     // taille de l'image, en tailles d'écran
      ...DUO, uSky: { value: 0 }, uSkyCol: { value: raw(SKY_COLOR) },
      uHazeCol: { value: raw(HAZE_COLOR) }, uHaze: { value: new THREE.Vector3(...HAZE) },
      uVig: { value: new THREE.Vector2(...VIGNETTE) }, uAsp: { value: 1 },
    },
    vertexShader: `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = vec4(position.xy, 0.9995, 1.0); }   // tout au fond`,
    fragmentShader: `
      ${DUO_GLSL}
      uniform float uSky; uniform vec3 uSkyCol;
      uniform vec3 uHazeCol, uHaze; uniform vec2 uVig; uniform float uAsp;
      uniform sampler2D uT0, uT1, uT2, uT3;
      uniform vec2 uOff[4], uFit;
      varying vec2 vUv;
      // Un plan : image centrée, ancrée en bas, décalée de o (en tailles d'image)
      vec4 plan(sampler2D t, vec2 o) {
        vec2 p = vec2((vUv.x - 0.5) / uFit.x + 0.5, vUv.y / uFit.y) - o;
        vec2 inside = step(vec2(0.0), p) * step(p, vec2(1.0));
        return texture2D(t, p) * inside.x * inside.y;
      }
      void main() {
        vec4 c = plan(uT3, uOff[3]);                                 // du plus loin…
        vec4 n = plan(uT2, uOff[2]); c = n + c * (1.0 - n.a);
        n = plan(uT1, uOff[1]);      c = n + c * (1.0 - n.a);
        n = plan(uT0, uOff[0]);      c = n + c * (1.0 - n.a);        // …au plus proche

        float a = c.a + uSky * (1.0 - c.a);                          // le ciel remplit ce qui reste
        vec3 col = (c.rgb + uSkyCol * uSky * (1.0 - c.a)) / max(a, 0.0001);
        col = mix(col, duotone(col), hidden());

        float top  = 1.0 - vUv.y;                                            // 0 en haut de l'écran
        float haze = (1.0 - smoothstep(uHaze.x, uHaze.y, top)) * uHaze.z;    // brume : forte en haut, nulle en bas
        float edge = min(min(vUv.x, 1.0 - vUv.x), min(vUv.y, 1.0 - vUv.y) / uAsp);
        float vig  = (1.0 - smoothstep(0.0, uVig.x, edge)) * uVig.y;         // bord crème
        col = mix(col, uHazeCol, max(haze, vig));

        gl_FragColor = vec4(col * a, a);
      }`,
  });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -2;                       // avant les traits de vitesse
  return { mesh, uniforms: mat.uniforms, aspect: first ? first.image.width / first.image.height : 1.5 };
}

// ----- Titre : chaque lettre est dessinée dans sa case (ombre comprise) et monte d'un seul bloc -----
async function makeTitle() {
  const T = TITLE, px = 400;                                        // hauteur de dessin
  const font = `${T.weight} ${px}px ${T.font}`;
  try { await document.fonts.load(font, T.text); } catch (e) { console.warn('Titre : police introuvable'); }

  // 1) Mesures
  const cv = document.createElement('canvas'), g = cv.getContext('2d');
  g.font = font;
  g.fontKerning = 'normal';                                         // applique le crénage de la police (Y-A, A-G…)
  const m = g.measureText(T.text);
  const asc = m.actualBoundingBoxAscent, desc = m.actualBoundingBoxDescent;
  const pad = Math.ceil(px * (T.stroke + T.rim[1] + Math.max(Math.abs(T.depth[0]), Math.abs(T.depth[1])) + 0.02));
  const chars = [...T.text], last = chars.length - 1;
  const base = chars.map((_, i) => g.measureText(T.text.slice(0, i)).width);            // positions d'origine, crénage compris
  const adv  = chars.map((_, i) => g.measureText(T.text.slice(0, i + 1)).width - base[i]);
  const left = base.map((b, i) => b + px * (i * T.spacing + (T.nudge[i] || 0)));        // positions réglées
  const wordW = left[last] + adv[last] + pad * 2;
  const H = Math.ceil(asc + desc + pad * 2);

  // 2) Image : une case par lettre, côte à côte
  cv.width = Math.ceil(adv.reduce((s, a) => s + a + pad * 2, 0));
  cv.height = H;
  g.font = font; g.lineJoin = 'round';                              // angles arrondis : pas de pointes sur V, Y, A
  const grad = g.createLinearGradient(0, pad, 0, pad + asc + desc);
  grad.addColorStop(0, T.fill[0]); grad.addColorStop(1, T.fill[1]);
  const off = document.createElement('canvas'), o = off.getContext('2d');   // brouillon pour le remplissage d'une lettre

  const pos = [], uv = [], idx = [], index = [];
  let x0 = 0;
  chars.forEach((ch, i) => {
    const cw = adv[i] + pad * 2, x = x0 + pad, y = pad + asc;
    g.save(); g.beginPath(); g.rect(x0, 0, cw, H); g.clip();        // chaque lettre reste dans sa case

    g.fillStyle = g.strokeStyle = T.ink;                            // relief
    g.lineWidth = px * T.stroke * 2;
    for (let k = 14; k >= 1; k--) {
      const ox = px * T.depth[0] * k / 14, oy = px * T.depth[1] * k / 14;
      g.strokeText(ch, x + ox, y + oy);
      g.fillText(ch, x + ox, y + oy);
    }
    if (T.rim[1] > 0) {                                             // liseré clair entre relief et contour
      g.strokeStyle = T.rim[0]; g.lineWidth = px * (T.stroke + T.rim[1]) * 2;
      g.strokeText(ch, x, y);
    }
    g.strokeStyle = T.ink; g.lineWidth = px * T.stroke * 2;         // contour
    g.strokeText(ch, x, y);

    // Remplissage composé à part : dégradé, puis bandes d'ombre limitées au bas de la lettre
    off.width = Math.ceil(cw); off.height = H;                      // (redimensionner remet le brouillon à zéro)
    o.font = font;
    o.fillStyle = grad;
    o.fillText(ch, pad, y);
    if (T.bands.length) {
      o.save();
      o.globalCompositeOperation = 'source-atop';                   // ne peint que dans la lettre
      o.beginPath(); o.rect(0, Math.round(y - (asc + desc) * T.bandZone), off.width, H); o.clip();   // bord sur un pixel entier : pas de ligne
      o.fillStyle = T.bands[0][1]; o.fillText(ch, pad, y);
      T.bands.forEach((b, j) => {
        o.fillStyle = j + 1 < T.bands.length ? T.bands[j + 1][1] : grad;
        o.fillText(ch, pad, y - px * b[0]);
      });
      o.restore();
    }
    g.drawImage(off, x0, 0);
    g.restore();

    const X0 = left[i] / wordW * 2 - 1, X1 = (left[i] + cw) / wordW * 2 - 1;   // place dans le mot (-1 à 1)
    const U0 = x0 / cv.width, U1 = (x0 + cw) / cv.width;                       // place dans l'image
    pos.push(X0, -1, 0, X1, -1, 0, X1, 1, 0, X0, 1, 0);
    uv.push(U0, 0, U1, 0, U1, 1, U0, 1);
    idx.push(i, i, i, i);
    x0 += cw;
  });
  for (let i = last; i >= 0; i--)                                   // de droite à gauche : chaque lettre recouvre l'ombre de la suivante
    index.push(i * 4, i * 4 + 1, i * 4 + 2, i * 4, i * 4 + 2, i * 4 + 3);

  // 3) Géométrie et matériau
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  geo.setAttribute('aIdx', new THREE.Float32BufferAttribute(idx, 1));
  geo.setIndex(index);

  const tex = new THREE.CanvasTexture(cv);
  tex.premultiplyAlpha = true;
  const mat = new THREE.ShaderMaterial({
    transparent: true, premultipliedAlpha: true, depthWrite: false,
    uniforms: {
      uMap: { value: tex }, uT: { value: -1 },
      uRect: { value: new THREE.Vector4() },                        // centre x, y et demi-taille x, y (à l'écran)
      uAnim: { value: new THREE.Vector3(T.delay, T.duration, T.stagger) },
    },
    vertexShader: `
      attribute float aIdx;
      uniform vec4 uRect; uniform float uT; uniform vec3 uAnim;
      varying vec2 vUv; varying float vY;
      void main() {
        float t  = clamp((uT - uAnim.x - aIdx * uAnim.z) / uAnim.y, 0.0, 1.0);
        float up = 1.0 - pow(1.0 - t, 4.0);                         // rapide au début, très lent à la fin
        vec2 p = position.xy;
        p.y -= (1.0 - up) * 2.2;                                    // la lettre entière monte de sous la ligne
        vUv = uv; vY = p.y;
        gl_Position = vec4(uRect.xy + p * uRect.zw, 0.9993, 1.0);   // devant le paysage, derrière l'astronaute
      }`,
    fragmentShader: `
      uniform sampler2D uMap;
      varying vec2 vUv; varying float vY;
      void main() {
        if (vY < -1.0) discard;                                     // masque : rien sous la ligne de base
        gl_FragColor = texture2D(uMap, vUv);
      }`,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1.5;                                          // après le paysage, avant les traits
  return { mesh, uniforms: mat.uniforms, ratio: H / wordW };
}

export async function init({ onProgress = () => {} } = {}) {
  const canvas = document.getElementById('scene');
  const still  = matchMedia('(prefers-reduced-motion: reduce)').matches;   // mouvement réduit : image fixe
  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });   // un trait d'encre crénelé se voit
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, MAX_DPR));
  const mask = makeMask(renderer);

  const scene  = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 50);
  camera.position.z = CAM_Z;
  const sun = new THREE.DirectionalLight(0xffffff, LIGHT[0]);
  sun.position.set(...SUN);
  const lines = makeLines();
  lines.visible = !still;
  scene.add(new THREE.AmbientLight(AMBIENT, LIGHT[1]), sun, lines);

  // Chargement en parallèle : le modèle (60 % de la barre) et les 4 plans du paysage (30 %)
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

  // Normalisation : centré, 1 unité de haut, quel que soit le fichier
  const box    = new THREE.Box3().setFromObject(gltf.scene);
  const center = box.getCenter(new THREE.Vector3());
  const k      = 1 / (box.getSize(new THREE.Vector3()).y || 1);
  const norm   = new THREE.Group();
  norm.add(gltf.scene);
  norm.scale.setScalar(k);
  norm.position.copy(center).multiplyScalar(-k);
  const pivot = new THREE.Group();                 // tout ce qui bouge passe par ce pivot
  pivot.add(norm);
  scene.add(pivot);

  toonify(gltf.scene);
  outline(gltf.scene);
  gltf.scene.traverse(o => { if (o.isMesh) o.frustumCulled = false; });

  const limbs = rig(gltf.scene);                   // à faire tant que le pivot n'a pas tourné
  const qFall = facing(BODY_FALL), qRest = facing(BODY_REST);

  // ----- État -----
  let viewW = 1, viewH = 1, size = 1;              // dimensions visibles et taille de l'astronaute (unités 3D)
  let fallStart = null, ramp = 1, onArrive = null; // instant de son entrée (ms) ; montée des traits ; signal du freinage
  let running = false, onScreen = true, raf = 0, last = 0, travel = 0, clock = 0;
  const U = lines.material.uniforms;
  const L = land.uniforms;
  let tx = 0, ty = 0, px = 0, py = 0;              // souris : cible, puis position lissée (de -1 à 1)
  let mx = -9, my = -9, pmx = -9, pmy = -9;        // souris dans le canvas (0 à 1), pour le masque
  let awake = 0, moved = false;                    // le masque ne calcule que si la souris a bougé récemment
  addEventListener('pointermove', e => {
    tx = e.clientX / innerWidth * 2 - 1;
    ty = 1 - e.clientY / innerHeight * 2;
    const r = canvas.getBoundingClientRect();
    mx = (e.clientX - r.left) / r.width;
    my = 1 - (e.clientY - r.top) / r.height;
    if (awake <= 0) { pmx = mx; pmy = my; }        // reprise : pas de trait depuis l'ancienne position
    awake = 3; moved = true;
  }, { passive: true });
  const _e = new THREE.Euler(), _s = new THREE.Quaternion(), _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion();
  const render = () => renderer.render(scene, camera);

  // Place tout pour l'instant ms (dt = secondes écoulées depuis l'image précédente)
  function apply(ms, dt) {
    const since = fallStart === null ? -1 : ms - fallStart;                    // < 0 : il n'est pas encore entré
    const e = still ? 1 : 1 - Math.pow(1 - clamp01(since / ENTER_MS), 3);      // entrée : 0 → 1
    const a = still ? 1 : clamp01((since - FALL_MS) / ARRIVE_MS);              // temps du freinage : 0 → 1
    const g = ease5(1 - Math.pow(1 - a, ARRIVE_TAIL));                         // LA courbe du freinage : 0 = pleine vitesse, 1 = posé
    const t = still ? 0 : Math.max(since, 0) / 1000;

    if (a > 0 && onArrive) { const signal = onArrive; onArrive = null; signal(); }   // le freinage commence : le titre peut partir

    // Vitesse du ciel : monte avec les nuages, pleine pendant la chute, puis suit le freinage
    const speed = still || fallStart === null ? 0
      : since < 0 ? Math.pow(1 - Math.min(-since / ramp, 1), 2)
      : IDLE_SPEED + (1 - IDLE_SPEED) * (1 - g);
    travel += speed * LINE_RATE * dt;
    U.uSpeed.value = speed;
    U.uTravel.value = travel;

    // Position : bord haut → position de chute → position de repos
    const startY = viewH / 2 + size;                                // juste au-dessus du bord haut
    const drift  = e * (1 - g);                                     // la dérive s'éteint avec la vitesse
    pivot.position.set(
      lerp(FALLING.x, REST.x, g) * viewW + Math.sin(t * 1.3) * DRIFT[0] * viewW * drift,
      lerp(lerp(startY, FALLING.y * viewH, e), REST.y * viewH, g)
        + Math.sin(t * 1.9 + 1) * DRIFT[1] * viewH * drift
        + Math.sin(t * 0.8) * 0.03 * size * g,                      // léger flottement une fois posé
      0);

    // Corps : culbute à l'entrée, pose de chute, puis bascule lente vers la pose de repos
    const sway = lerp(SWAY[0], SWAY[1], g);
    _e.set(
      Math.sin(t * 1.1) * sway - (1 - e) * ENTER_SPIN,
      Math.sin(t * 0.7 + 1) * sway * 1.4,
      Math.sin(t * 0.9 + 2) * sway);
    pivot.quaternion.slerpQuaternions(qFall, qRest, g).premultiply(_s.setFromEuler(_e));

    // Membres : chacun oscille entre ses deux extrêmes ; rythme et amplitude suivent le freinage
    clock += dt * lerp(FLAIL_RATE, FLOAT_RATE, g);
    for (const b of limbs) {
      const w = 0.5 + 0.5 * Math.sin(clock * b.rate + b.phase);
      _qa.slerpQuaternions(b.fallA, b.fallB, w);
      _qb.slerpQuaternions(b.restA, b.restB, w);
      b.bone.quaternion.slerpQuaternions(_qa, _qb, g);
    }

    // Masque du curseur : s'endort 3 s après le dernier mouvement
    if (awake > 0 && dt > 0) {
      awake -= dt;
      mask.step(ms / 1000, pmx, pmy, mx, my, moved ? 1 : 0, camera.aspect);
      pmx = mx; pmy = my; moved = false;
    }

    // Le ciel du canvas apparaît pendant que les nuages s'écartent
    L.uSky.value = still ? 1 : fallStart === null ? 0 : clamp01(1 + since / ramp);
    // Titre : les lettres montent une à une quand le freinage commence
    title.uniforms.uT.value = still ? 99 : (since - FALL_MS) / 1000;

    // Paysage : chaque plan monte à l'arrivée (le plus proche d'abord), puis suit la souris
    const follow = 1 - Math.exp(-dt * POINTER_EASE);
    px += (tx - px) * follow;
    py += (ty - py) * follow;
    LAYERS.forEach((l, i) => {
      const k  = still ? 1 : clamp01((since - FALL_MS - i * LAYER_GAP) / LAYER_MS);
      const up = 1 - Math.pow(1 - k, 3);                           // rapide au début, lent à la fin
      L.uOff.value[i].set(
        -px * PARALLAX[0] * l.depth,
        -l.drop - (1 - up) * l.rise - py * PARALLAX[1] * l.depth);
    });
  }

  function fit(draw = true) {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    renderer.getDrawingBufferSize(DUO.uScreen.value);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    viewH = 2 * Math.tan(THREE.MathUtils.degToRad(FOV / 2)) * CAM_Z;
    viewW = viewH * camera.aspect;
    size  = Math.min(REST.size * viewH, MAX_SIZE * viewW);
    pivot.scale.setScalar(size);
    U.uRes.value.set(w, h);
    const landH = Math.max(LAND_ZOOM * camera.aspect / land.aspect, LAND_MIN_H);   // hauteur de l'image, en hauteurs d'écran
    L.uFit.value.set(landH * land.aspect / camera.aspect, landH);
    L.uAsp.value = camera.aspect;
    title.uniforms.uRect.value.set(0, TITLE.y * 2, TITLE.width, TITLE.width * title.ratio * camera.aspect);
    if (draw) { apply(performance.now(), 0); render(); }   // toujours : un changement de taille efface le canvas
  }

  // Boucle : ne tourne que si la chute est lancée ET le canvas visible
  function frame(ms) {
    raf = requestAnimationFrame(frame);
    const resting = ms - fallStart >= FALL_MS + ARRIVE_MS;
    if (resting && ms - last < 1000 / IDLE_FPS - 2) return;         // au repos : plafonné à IDLE_FPS
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

  // Préchauffage : shaders compilés pendant le loader, pas pendant la dispersion
  fit(false);
  apply(performance.now(), 0);
  await renderer.compileAsync(scene, camera);
  render();
  onProgress(1);

  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; sync(); }).observe(canvas);
  new ResizeObserver(() => fit()).observe(canvas);

  return {
    // delay : ms avant son entrée (les traits accélèrent pendant ce délai) ; onArrive : appelé quand le freinage commence
    fall({ delay = 0, onArrive: signal } = {}) {
      if (fallStart !== null) return;               // une seule fois
      if (still) { fallStart = 0; signal?.(); return; }
      onArrive = signal || null;
      ramp = Math.max(delay, 1);
      fallStart = performance.now() + Math.max(delay, 0);
      running = true;
      sync();
    },
  };
}