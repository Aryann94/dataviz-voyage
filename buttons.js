// ===== Boutons : effet magnétique, et texte qui roule au survol =====
(() => {
  const STRENGTH = 0.2;                                              // force par défaut : 40 % de la distance au centre
  const canHover = matchMedia('(hover: hover) and (pointer: fine)').matches;
  const calm     = matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Aimant : le bouton suit la souris d'une partie de la distance, puis revient avec un rebond élastique
  if (canHover && !calm && window.gsap) {
    document.querySelectorAll('[data-magnetic]').forEach(b => {
      const k = parseFloat(b.dataset.magnetic) || STRENGTH;
      b.addEventListener('pointermove', e => {
        const r = b.getBoundingClientRect();
        const cx = r.left - gsap.getProperty(b, 'x') + r.width / 2;    // centre au repos (sans le déplacement en cours)
        const cy = r.top  - gsap.getProperty(b, 'y') + r.height / 2;
        gsap.to(b, { x: (e.clientX - cx) * k, y: (e.clientY - cy) * k, duration: 0.3, ease: 'power3.out', overwrite: 'auto' });
      });
      b.addEventListener('pointerleave', () => {
        gsap.to(b, { x: 0, y: 0, duration: 0.9, ease: 'elastic.out(1, 0.3)', overwrite: 'auto' });
      });
    });
  }

  // Texte qui roule : chaque lettre monte au survol, et une copie revient par le bas
  // (prêt pour le bouton « Scroll pour explorer » ; le texte complet reste lu par les lecteurs d'écran)
  document.querySelectorAll('[data-roll]').forEach(el => {
    const text = el.textContent.trim();
    el.setAttribute('aria-label', text);
    el.innerHTML = '<span class="roll" aria-hidden="true">' + [...text].map((ch, i) => {
      const c = ch === ' ' ? '&nbsp;' : ch;
      return `<span class="roll-ch" style="--i:${i}"><span>${c}</span><span>${c}</span></span>`;
    }).join('') + '</span>';
  });
})();