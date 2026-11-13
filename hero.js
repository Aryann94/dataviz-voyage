// ===== Hero : les petits textes montent ligne par ligne, sous un masque =====
const Hero = (() => {
  const DELAY = 0.7, DURATION = 1.4, STAGGER = 0.1;          // secondes, à partir du début du freinage
  const tags = [...document.querySelectorAll('.hero-tag')];

  // Chaque texte est enveloppé : un masque (qui coupe) et une ligne (qui monte)
  const lines = tags.map(el => {
    const line = document.createElement('span');
    line.className = 'line';
    line.append(...el.childNodes);
    const mask = document.createElement('span');
    mask.className = 'line-mask';
    mask.append(line);
    el.append(mask);
    return line;
  });

  const animated = !!window.gsap && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (animated) gsap.set(lines, { yPercent: 120, rotate: 6, transformOrigin: '0% 100%' });   // cachées sous le masque

  let done = false;
  function reveal() {
    if (done || !animated) return;
    done = true;
    gsap.to(lines, { yPercent: 0, rotate: 0, duration: DURATION, ease: 'expo.out', stagger: STAGGER, delay: DELAY });
  }
  return { reveal };
})();