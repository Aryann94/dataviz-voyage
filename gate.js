// ===== Entrée : avec ou sans le son. Le chargement attend ce choix, et ce clic débloque l'audio. =====
const Gate = {
  ask() {
    const el = document.querySelector('.pl-gate');
    if (!el) return Promise.resolve(false);                          // pas d'écran de choix : on entre sans le son
    window.Sound?.prepare();                                          // le moteur audio se prépare pendant qu'on choisit
    return new Promise(resolve => {
      const yes = el.querySelector('[data-sound="on"]'), no = el.querySelector('[data-sound="off"]');
      el.hidden = false;
      requestAnimationFrame(() => requestAnimationFrame(() => el.classList.add('is-open')));   // apparition en douceur
      let done = false;
      const pick = async withSound => {
        if (done) return;
        done = true;
        el.inert = true;                                              // plus cliquable
        if (withSound && window.Sound) await Sound.start();           // au plus 0,4 s : son et nuages partent ensemble
        el.classList.remove('is-open');
        setTimeout(() => el.remove(), 700);                           // disparu : on le retire de la page
        resolve(withSound);
      };
      yes.addEventListener('click', () => pick(true));
      no.addEventListener('click', () => pick(false));
    });
  },
};
window.Gate = Gate;