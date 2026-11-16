// ===== Défilement : Lenis (défilement doux) + ScrollTrigger (avance de la plongée) =====
const Scroll = (() => {
  const LENIS_LERP = 0.1;                                     // douceur : plus petit = plus doux, plus long
  const DIVE_TIME  = 2.8;                                     // durée du défilement automatique (aller ou retour), en secondes
  const state = { zoom: 0, smooth: undefined, unlock() {}, dive() {}, back() {} };   // zoom : 0 = hero, 1 = casque plein écran

  history.scrollRestoration = 'manual';                       // un rechargement repart toujours du haut
  scrollTo(0, 0);

  if (!window.gsap || !window.ScrollTrigger) {
    console.warn('Défilement : GSAP ou ScrollTrigger introuvable');
    return state;
  }
  gsap.registerPlugin(ScrollTrigger);
  ScrollTrigger.config({ ignoreMobileResize: true });         // la barre d'adresse mobile ne recalcule rien

  let lenis = null;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (window.Lenis && !reduce) {
    lenis = new Lenis({ lerp: LENIS_LERP });
    lenis.on('scroll', ScrollTrigger.update);                 // ScrollTrigger suit la position lissée
    gsap.ticker.add(time => lenis.raf(time * 1000));          // une seule horloge pour tout
    gsap.ticker.lagSmoothing(0);
    lenis.stop();                                             // bloqué jusqu'au freinage de l'astronaute
  }

  const track = ScrollTrigger.create({
    trigger: '.hero-track', start: 'top top', end: 'bottom bottom',
    onUpdate: self => { state.zoom = self.progress; },
  });

  let unlocked = false;
  state.unlock = () => {
    if (unlocked) return;
    unlocked = true;
    ScrollTrigger.refresh();                                  // positions recalculées une fois tout en place
    lenis?.start();
  };

  // ----- Défilement automatique : la scène suit, l'animation se rejoue (aller) ou se rembobine (retour) -----
  const easeInOut = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);   // départ et arrivée en douceur
  function glide(to, onDone) {
    if (!unlocked) return;                                    // pas avant l'atterrissage
    if (lenis) lenis.scrollTo(to, { duration: DIVE_TIME, easing: easeInOut, onComplete: onDone });
    else { scrollTo({ top: to, behavior: reduce ? 'auto' : 'smooth' }); setTimeout(onDone, reduce ? 0 : 1200); }
  }
  state.dive = (onDone = () => {}) => glide(track.end, onDone);    // jusqu'à la visière
  state.back = (onDone = () => {}) => glide(track.start, onDone);  // retour au hero

  // ----- Clavier : Explorer → Son → Embarquer → navigateur → Explorer -----
  const cta   = document.querySelector('.scroll-cta');
  const sound = document.querySelector('.sound-toggle');
  const board = document.querySelector('.visor-btn');
  const shown = el => !!el && getComputedStyle(el).visibility === 'visible';
  // Un élément caché ne peut pas recevoir le focus : on attend qu'il apparaisse (vérifié toutes les 50 ms, 2 s au plus)
  const focusWhen = (el, tries = 40) => {
    if (!el) return;
    if (shown(el)) el.focus({ preventScroll: true });
    else if (tries > 0) setTimeout(() => focusWhen(el, tries - 1), 50);
  };
  const toExplorer = () => (shown(cta) && state.zoom < 0.01 ? cta.focus() : state.back(() => focusWhen(cta)));
  const toBoard    = () => (shown(board) && state.zoom > 0.99 ? board.focus() : state.dive(() => focusWhen(board)));

  cta?.addEventListener('click', () => state.dive(() => focusWhen(board)));   // clic ou Entrée : on plonge, puis focus sur « Embarquer »

  document.addEventListener('keydown', e => {
    if (e.key !== 'Tab' || !unlocked) return;
    const a = document.activeElement, back = e.shiftKey;
    if (a === cta && !back)       { e.preventDefault(); sound?.focus(); }
    else if (a === sound && !back) { e.preventDefault(); toBoard(); }
    else if (a === sound && back)  { e.preventDefault(); toExplorer(); }
    else if (a === board && back)  { e.preventDefault(); sound?.focus(); }
    else if (a === board && !back && sound) {                 // vers le navigateur : on saute le bouton son, placé après dans la page
      sound.tabIndex = -1;
      setTimeout(() => sound.removeAttribute('tabindex'), 0);
    }
  });

  // Retour dans la page depuis le navigateur (au clavier) alors qu'on est sur la visière : on remonte jusqu'à Explorer
  let outside = false, pointer = false;
  addEventListener('blur', () => { outside = true; });                         // le focus est parti dans le navigateur
  addEventListener('pointerdown', () => { pointer = true; setTimeout(() => { pointer = false; }, 500); }, true);
  document.addEventListener('focusin', () => {
    const wasOutside = outside;
    outside = false;
    if (wasOutside && !pointer && unlocked && document.activeElement === board) toExplorer();
  });

  return state;
})();
window.Scroll = Scroll;   // rend l'objet accessible partout, y compris depuis scene.js (module)