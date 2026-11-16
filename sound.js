// ===== Son : musique (intro + boucle), vent généré, souffles (Web Audio API) =====
// Rien ne joue avant un clic de l'utilisateur : les navigateurs l'interdisent.

// ----- Réglages -----
const SOUND = {
  files:  { music: 'sounds/musique.mp3', whoosh: 'sounds/whoosh.mp3' },   // pour changer un son : remplace le fichier en gardant le nom
  // La musique démarre à la fin de l'atterrissage, joue son intro une seule fois,
  // puis boucle entre start et end (en secondes), avec un fondu enchaîné à chaque raccord
  music:  {
    at:    0.9,     // quand elle démarre : 0 = début du freinage, 1 = astronaute posé
    start: 10,      // début du passage qui boucle (juste après l'intro)
    end:   42,     // fin du passage qui boucle (avant que le morceau ne se termine)
    rate:  0,   // décodage à 24 kHz : moitié moins de mémoire, aigus coupés au-dessus de 12 kHz (0 = qualité d'origine)
  },
  volume: { master: 0.8, music: 0.5, wind: 0.45, whoosh: 0.7, ui: 0.25 },
  wind:   { low: 250, high: 1400, rest: 0.1 },   // bande du vent (Hz) : au repos, à pleine vitesse ; part du vent au repos
  duck:   0.4,                                   // la musique baisse de 40 % si le vent souffle fort
  muffle: [16000, 450],                          // étouffement pendant la plongée (Hz) : avant, dans le casque
  xfade:  0,                                   // fondu enchaîné à chaque raccord de la boucle (secondes)
  fade:   0.6,                                   // fondu quand on active ou coupe le son (secondes)
  whooshAt: 0,                                   // début du souffle dans son fichier (secondes), si le fichier commence par un blanc
  startWait: 400,                                // au clic, on attend au plus 0,4 s que le son soit prêt avant de lancer l'image
};

const Sound = (() => {
  let ac = null, out, muffle, windBand, windGain, musicBus, white;
  let on = false, timer = 0, musicStarted = false;
  let speed = 0, dive = 0, arrive = 0;           // reçus de la scène 3D à chaque image
  const loops = [], bufs = {}, raw = {};

  // 1) Téléchargement des fichiers dès que la page est chargée (le décodage viendra avec le moteur audio)
  const fetchAll = () => {
    for (const [k, url] of Object.entries(SOUND.files)) {
      raw[k] = fetch(url)
        .then(r => { if (!r.ok) throw new Error(r.status); return r.arrayBuffer(); })
        .catch(() => { console.warn('Son : fichier introuvable', url); return null; });
    }
  };
  if (document.readyState === 'complete') fetchAll(); else addEventListener('load', fetchAll, { once: true });

  // Décodage ; avec rate, on décode à une fréquence plus basse pour économiser la mémoire
  async function decode(k, rate = 0) {
    const data = await raw[k];
    if (!data) return null;
    try {
      const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
      const ctx = rate && OAC ? new OAC(2, 1, rate) : ac;
      return (bufs[k] = await ctx.decodeAudioData(data));
    } catch (e) {
      console.warn('Son : fichier illisible', SOUND.files[k]);
      return null;
    }
  }

  // Bruit : du hasard (blanc), ou du hasard lissé, plus grave et plus doux (brun : le vent)
  function noise(seconds, brown) {
    const n = Math.floor(ac.sampleRate * seconds), b = ac.createBuffer(1, n, ac.sampleRate), d = b.getChannelData(0);
    let last = 0;
    for (let i = 0; i < n; i++) {
      const w = Math.random() * 2 - 1;
      d[i] = brown ? (last = (last + 0.02 * w) / 1.02) * 3.5 : w;
    }
    const drift = d[n - 1] - d[0];               // la fin rejoint le début : pas de clic quand la boucle repart
    for (let i = 0; i < n; i++) d[i] -= drift * i / (n - 1);
    return b;
  }

  // Boucle à intro : le premier tour joue depuis le tout début jusqu'à « end »,
  // les suivants rejouent « start → end », chacun commençant un peu avant la fin du précédent (fondu enchaîné)
  function loop(buf, bus, xf, from = 0, to = 0) {
    const end = to > from ? Math.min(to, buf.duration) : buf.duration;
    if (from >= end) from = 0;                   // réglages incohérents : on boucle le morceau entier
    loops.push({ buf, bus, from, end, xf: Math.min(xf, (end - from) / 3), next: 0, first: true });
    if (on) schedule();
  }
  function turn(l) {
    const t = l.next, off = l.first ? 0 : l.from, dur = l.end - off;
    const fadeIn = l.first ? 0.02 : l.xf;        // l'intro démarre nette, les raccords en fondu
    const src = ac.createBufferSource(), g = ac.createGain();
    src.buffer = l.buf;
    src.connect(g).connect(l.bus);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(1, t + fadeIn);
    g.gain.setValueAtTime(1, t + dur - l.xf);
    g.gain.linearRampToValueAtTime(0, t + dur);
    src.start(t, off, dur);
    l.next = t + dur - l.xf;
    l.first = false;
  }
  function schedule() {
    for (const l of loops) {
      if (l.next < ac.currentTime) l.next = ac.currentTime + 0.05;   // premier tour, ou retour après une pause
      while (l.next < ac.currentTime + 1) turn(l);                  // on programme toujours une seconde d'avance
    }
  }

  // 2) Le moteur audio, créé en pause quand les boutons apparaissent (la console peut le signaler : c'est normal)
  //    Circuit : musique et vent → étouffement (plongée) → volume général → haut-parleurs
  function prepare() {
    if (ac) return;
    ac = new (window.AudioContext || window.webkitAudioContext)();
    if ('audioSession' in navigator) { try { navigator.audioSession.type = 'playback'; } catch (e) {} }   // iPhone en mode silencieux
    out = ac.createGain(); out.gain.value = 0; out.connect(ac.destination);
    muffle = ac.createBiquadFilter(); muffle.type = 'lowpass'; muffle.frequency.value = SOUND.muffle[0]; muffle.Q.value = 0.3;
    muffle.connect(out);

    // Le vent : du bruit brun, filtré sur une bande qui suit la vitesse de chute
    windBand = ac.createBiquadFilter(); windBand.type = 'bandpass'; windBand.Q.value = 0.8;
    windGain = ac.createGain(); windGain.gain.value = 0;
    const wind = ac.createBufferSource(); wind.buffer = noise(4, true); wind.loop = true;
    wind.connect(windBand).connect(windGain).connect(muffle);
    wind.start();

    white = noise(1, false);                     // réserve de bruit blanc pour le souffle de secours
    musicBus = ac.createGain(); musicBus.gain.value = 0; musicBus.connect(muffle);
    decode('whoosh');
    decode('music', SOUND.music.rate);           // prête à l'avance, elle ne démarre qu'à l'atterrissage (voir tick)
  }

  // Toutes les 50 ms : la musique démarre au bon moment, les volumes et les filtres suivent la scène
  function tick() {
    if (!musicStarted && bufs.music && arrive >= SOUND.music.at) {   // fin de l'atterrissage : la musique commence
      musicStarted = true;
      loop(bufs.music, musicBus, SOUND.xfade, SOUND.music.start, SOUND.music.end);
    }
    schedule();
    const t = ac.currentTime, s = Math.min(Math.max(speed, 0), 1);
    const gust = 0.8 + 0.2 * Math.sin(t * 0.7) * Math.sin(t * 0.23 + 1);   // rafales lentes
    windGain.gain.setTargetAtTime(SOUND.volume.wind * (SOUND.wind.rest + (1 - SOUND.wind.rest) * s * s) * gust, t, 0.15);
    windBand.frequency.setTargetAtTime(SOUND.wind.low + (SOUND.wind.high - SOUND.wind.low) * s, t, 0.15);
    musicBus.gain.setTargetAtTime(SOUND.volume.music * (1 - SOUND.duck * s), t, 0.3);
    muffle.frequency.setTargetAtTime(SOUND.muffle[0] * Math.pow(SOUND.muffle[1] / SOUND.muffle[0], dive), t, 0.15);
  }

  // Souffle : le fichier s'il est là, sinon un souffle généré (bruit dont le filtre monte vite)
  function whoosh(vol = SOUND.volume.whoosh) {
    if (!on) return;
    const t = ac.currentTime;
    if (bufs.whoosh) {
      const s = ac.createBufferSource(), g = ac.createGain();
      s.buffer = bufs.whoosh; g.gain.value = vol;
      s.connect(g).connect(out);
      s.start(t, SOUND.whooshAt);
      return;
    }
    const s = ac.createBufferSource(), f = ac.createBiquadFilter(), g = ac.createGain();
    s.buffer = white; s.loop = true;
    f.type = 'bandpass'; f.Q.value = 0.9;
    f.frequency.setValueAtTime(180, t);
    f.frequency.exponentialRampToValueAtTime(2800, t + 0.9);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(vol, t + 0.7);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 1.2);
    s.connect(f).connect(g).connect(out);
    s.start(t); s.stop(t + 1.25);
  }

  // Petit « tic » : une note très courte qui glisse vers le grave et s'éteint aussitôt
  function tickSound() {
    if (!on) return;
    const t = ac.currentTime, o = ac.createOscillator(), g = ac.createGain();
    o.frequency.setValueAtTime(1400, t);
    o.frequency.exponentialRampToValueAtTime(900, t + 0.05);
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(SOUND.volume.ui, t + 0.005);
    g.gain.exponentialRampToValueAtTime(0.0001, t + 0.08);
    o.connect(g).connect(out);
    o.start(t); o.stop(t + 0.1);
  }

  // Activer ou couper ; instant = sans fondu (au clic d'entrée, pour ne pas étouffer le souffle)
  const btn = document.querySelector('.sound-toggle');
  function setOn(v, instant = false) {
    on = v;
    btn?.setAttribute('aria-pressed', String(on));
    if (on) {
      prepare();
      ac.resume();
      out.gain.cancelScheduledValues(ac.currentTime);
      if (instant) out.gain.setValueAtTime(SOUND.volume.master, ac.currentTime);
      else out.gain.setTargetAtTime(SOUND.volume.master, ac.currentTime, SOUND.fade / 3);
      if (!timer) timer = setInterval(tick, 50);
    } else if (ac) {
      out.gain.cancelScheduledValues(ac.currentTime);
      out.gain.setTargetAtTime(0, ac.currentTime, SOUND.fade / 3);
      clearInterval(timer); timer = 0;
      setTimeout(() => { if (!on) ac.suspend(); }, SOUND.fade * 1000 + 100);   // fondu terminé : moteur en pause
    }
  }
  btn?.addEventListener('click', () => setOn(!on));

  // 3) Au clic « avec le son » : on attend que le moteur tourne vraiment (au plus startWait), puis le souffle part
  async function start() {
    setOn(true, true);
    await Promise.race([ac.resume(), new Promise(r => setTimeout(r, SOUND.startWait))]);
    whoosh();
  }

  // Onglet en arrière-plan : silence
  document.addEventListener('visibilitychange', () => {
    if (!ac || !on) return;
    if (document.hidden) ac.suspend(); else ac.resume();
  });

  // Bouton de la visière : tic au survol, souffle plus discret au clic
  const cta = document.querySelector('.visor-btn');
  cta?.addEventListener('pointerenter', tickSound);
  cta?.addEventListener('click', () => whoosh(SOUND.volume.whoosh * 0.6));

  return {
    set(s, d, a) { speed = s; dive = d; arrive = a; },   // appelé par la scène 3D à chaque image
    prepare, start, setOn,
    get on() { return on; },
  };
})();
window.Sound = Sound;   // visible depuis scene.js et gate.js