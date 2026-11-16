// ===== Hero : les textes HTML, à l'arrivée et pendant la plongée =====
const Hero = (() => {
  const INTRO = { delay: 0.7, duration: 1.4, stagger: 0.1 };          // arrivée, en secondes après le début du freinage
  const animated = !!window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Enveloppe le contenu d'un élément : un masque (qui coupe) et une ligne (qui bouge)
  function wrap(el) {
    const line = document.createElement('span');
    line.className = 'line';
    line.append(...el.childNodes);
    const mask = document.createElement('span');
    mask.className = 'line-mask';
    mask.append(line);
    el.append(mask);
    return line;
  }

  const tags = [...document.querySelectorAll('.hero-tag')];
  const tagLines = tags.map(wrap);
  const visor = document.querySelector('.visor-content');
  const visorLines = visor ? [...visor.querySelectorAll('.visor-line')].map(wrap) : [];

  // 1) Arrivée : les petits textes montent de sous leur masque
  if (animated) gsap.set(tagLines, { yPercent: 120, rotate: 6, transformOrigin: '0% 100%' });
  let done = false;
  function reveal() {
    if (done || !animated) return;
    done = true;
    gsap.to(tagLines, { yPercent: 0, rotate: 0, duration: INTRO.duration, ease: 'expo.out', stagger: INTRO.stagger, delay: INTRO.delay });
  }

  // 2) Plongée : une timeline en pause, pilotée par l'avance lissée du défilement (0 → 1)
  if (window.gsap) {
    const zoom = gsap.timeline({ paused: true });
    zoom.fromTo(tags, { yPercent: 0, autoAlpha: 1 }, { yPercent: -80, autoAlpha: 0, duration: 0.12, ease: 'power2.in' }, 0);
    if (visor) zoom
      .fromTo(visor, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.03, ease: 'none' }, 0.8)
      .fromTo(visorLines, { yPercent: 120, rotate: 6, transformOrigin: '0% 100%' },
                          { yPercent: 0, rotate: 0, duration: 0.12, stagger: 0.03, ease: 'power3.out' }, 0.8);
    zoom.set({}, {}, 1);                                              // durée totale = 1 (comme l'avance)

    let last = -1;
    gsap.ticker.add(() => {
      const z = window.Scroll ? (Scroll.smooth ?? Scroll.zoom) : 0;   // même valeur que la scène 3D : tout reste synchronisé
      if (Math.abs(z - last) < 1e-4) return;
      last = z;
      zoom.progress(z);
    });
  }

  return { reveal };
})();