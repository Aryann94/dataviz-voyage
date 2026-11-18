// ===== Quiz « Quel pays pour toi ? » : déroulé, révélation et écran de résultat =====
import * as d3 from 'd3';
import {
  CRITERES, LIBELLES, SEUIL_EXPRIME, classer, coderParcours, construireFaits, etat, leSaviezVous, lireParcours,
} from './quiz-moteur.js';

const racine = document.getElementById('quiz');
const calme = matchMedia('(prefers-reduced-motion: reduce)').matches;
const entier = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 1 });
const prixFmt = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 3 });
const REGLAGES = { 0: 'Ignoré', 0.5: 'Moins', 1: 'Normal', 1.5: 'Plus', 2: 'Bien plus' };
const D = {};                     // données chargées
let minuteurs = [];

// Crée un élément. Le texte passe toujours par textContent : aucune donnée n'est lue comme du HTML.
function h(balise, proprietes = {}, ...enfants) {
  const e = document.createElement(balise);
  for (const [cle, valeur] of Object.entries(proprietes)) {
    if (valeur === undefined || valeur === null || valeur === false) continue;
    if (cle === 'class') e.className = valeur;
    else if (cle === 'text') e.textContent = valeur;
    else if (cle.startsWith('on')) e.addEventListener(cle.slice(2), valeur);
    else e.setAttribute(cle, valeur === true ? '' : valeur);
  }
  e.append(...enfants.flat().filter(x => x !== null && x !== undefined && x !== false));
  return e;
}

function ecran(...contenu) {
  minuteurs.forEach(clearTimeout);
  minuteurs = [];
  racine.replaceChildren(...contenu);
  scrollTo({ top: 0 });
}

function credit(auteur, licence, lien, prefixe = 'Photo') {
  return h('p', { class: 'credit' }, `${prefixe} : ${auteur}, ${licence}. `,
    h('a', { href: lien, target: '_blank', rel: 'noopener', text: 'Source' }));
}

async function charger() {
  const [scores, pays, sites, banque, photos, simulation] = await Promise.all([
    d3.csv('data/scores.csv'), d3.csv('data/pays.csv'), d3.csv('data/unesco_sites.csv'),
    d3.json('data/quiz_questions.json'), d3.csv('data/quiz_photos.csv'), d3.json('data/quiz_simulation.json'),
  ]);
  D.questions = banque.questions;
  D.nombre = banque.nombre_questions;
  D.simulation = simulation;
  D.brut = new Map(pays.map(p => [p.iso3, p]));
  D.pays = scores.map(s => ({
    iso3: s.iso3, nom: D.brut.get(s.iso3).nom_fr, distance: +s.distance_paris_km,
    scores: CRITERES.map(c => +s[`score_${c}`]),
  }));
  D.faits = construireFaits(pays, scores, sites);
  D.sites = d3.group(sites, s => s.iso3);
  D.photos = new Map(photos.map(p => [`${p.question}:${p.option}`, p]));
}

// ----- Intro et questions -----
function accueil() {
  history.replaceState(null, '', location.pathname);
  ecran(h('section', { class: 'intro' },
    h('p', { class: 'etiquette', text: 'Quiz · 41 pays' }),
    h('h1', { text: 'Quel pays pour toi ?' }),
    h('p', { text: 'Douze choix, parfois difficiles. Après chaque réponse, le quiz cherche la question qui départage le mieux les pays en tête.' }),
    h('button', { class: 'btn btn--primary', type: 'button', text: 'Commencer', onclick: () => poser([]) }),
    h('p', { class: 'discret', text: 'Tes réponses ne sont ni enregistrées ni envoyées.' })));
}

function poser(reponses) {
  const { suivante } = etat(D.questions, D.pays, reponses, D.nombre);
  const q = D.questions[suivante];
  const numero = reponses.length + 1;
  const titre = h('h1', { tabindex: '-1', text: q.question });
  const cartes = q.options.map((o, i) => {
    const photo = q.type === 'duel' ? D.photos.get(`${q.id}:${i}`) : null;
    return h('div', { class: 'carte-choix' },
      h('button', {
        class: 'bouton-choix', type: 'button',
        onclick: () => {
          const suite = [...reponses, { q: suivante, o: i }];
          if (suite.length === D.nombre) revelation(suite); else poser(suite);
        },
      },
      photo && h('img', { src: photo.image_url, alt: photo.description, width: 640, height: 400, decoding: 'async' }),
      h('span', { class: 'bouton-texte' }, h('strong', { text: o.titre }))),
      photo && credit(photo.auteur, photo.licence, photo.page));
  });
  ecran(h('section', { class: 'question', 'aria-labelledby': 'titre-question' },
    h('div', { class: 'progres' },
      h('div', { class: 'progres-haut' },
        h('p', { class: 'etiquette', text: q.theme }),
        h('p', { class: 'discret', text: `Question ${numero} sur ${D.nombre}` })),
      h('div', { class: 'progres-barre', 'aria-hidden': 'true' },
        h('i', { style: `width:${100 * (numero - 1) / D.nombre}%` }))),
    titre,
    h('div', { class: 'choix', style: `--n:${q.options.length}` }, cartes),
    h('div', { class: 'question-bas' },
      reponses.length
        ? h('button', { class: 'lien-bouton', type: 'button', text: 'Question précédente', onclick: () => poser(reponses.slice(0, -1)) })
        : h('button', { class: 'lien-bouton', type: 'button', text: 'Retour', onclick: accueil }))));
  titre.id = 'titre-question';
  titre.focus({ preventScroll: true });
}

// ----- Révélation : les pays se rangent, du dernier au premier -----
function revelation(reponses) {
  if (calme) return resultat(reponses);
  const { classement } = etat(D.questions, D.pays, reponses, D.nombre);
  const lignes = classement.map((l, i) => h('li', { class: i < 3 ? 'podium' : null },
    h('b', { text: i + 1 }), h('span', { text: l.pays.nom })));
  ecran(h('section', { class: 'revelation', 'aria-label': 'Classement en cours' },
    h('div', { class: 'revelation-haut' },
      h('h1', { text: 'Ton classement' }),
      h('button', { class: 'lien-bouton', type: 'button', text: 'Passer', onclick: () => resultat(reponses) })),
    h('ol', { 'aria-hidden': 'true' }, lignes)));
  let t = 150;
  for (let i = lignes.length - 1; i >= 0; i--) {
    minuteurs.push(setTimeout(() => lignes[i].classList.add('vu'), t));
    t += i > 3 ? 55 : i === 3 ? 320 : i === 2 ? 420 : 620;
  }
  minuteurs.push(setTimeout(() => resultat(reponses), t + 500));
}

// ----- Radar -----
function dessinerRadar(zone, prof, ligne, axe, surAxe) {
  zone.replaceChildren();
  const W = 460, H = 410, cx = W / 2, cy = H / 2, R = 136;
  const angle = i => -Math.PI / 2 + i * Math.PI / 3;
  const point = (i, v) => [cx + R * v / 100 * Math.cos(angle(i)), cy + R * v / 100 * Math.sin(angle(i))];
  const exprime = prof.map(p => p.importance >= SEUIL_EXPRIME);
  const toi = prof.map((p, i) => (exprime[i] ? p.valeur : 50));
  const lui = ligne.pays.scores;
  const chemin = v => v.map((x, i) => point(i, x).join(',')).join(' ');
  const svg = d3.select(zone).append('svg').attr('viewBox', `0 0 ${W} ${H}`).attr('role', 'group')
    .attr('aria-label', `Radar : ton profil comparé à ${ligne.pays.nom}. Choisis un critère pour voir le détail.`);
  for (const n of [25, 50, 75, 100]) svg.append('polygon').attr('class', 'radar-grille').attr('points', chemin(CRITERES.map(() => n)));
  CRITERES.forEach((_, i) => {
    const [x, y] = point(i, 100);
    svg.append('line').attr('class', `radar-rayon${exprime[i] ? '' : ' sans-avis'}`)
      .attr('x1', cx).attr('y1', cy).attr('x2', x).attr('y2', y);
  });
  svg.append('polygon').attr('class', 'serie-pays').attr('points', chemin(lui));
  svg.append('polygon').attr('class', 'serie-toi').attr('points', chemin(toi));
  const losange = d3.symbol().type(d3.symbolDiamond).size(82);
  lui.forEach((v, i) => {
    const [x, y] = point(i, v);
    svg.append('path').attr('class', 'point-pays').attr('d', losange()).attr('transform', `translate(${x},${y})`);
  });
  toi.forEach((v, i) => {
    const [x, y] = point(i, v);
    svg.append('circle').attr('class', `point-toi${exprime[i] ? '' : ' sans-avis'}`).attr('cx', x).attr('cy', y).attr('r', 4.6);
  });

  // noms posés directement là où les deux profils s'écartent le plus
  let ecart = -1, k = -1;
  toi.forEach((v, i) => { if (exprime[i] && Math.abs(v - lui[i]) > ecart) { ecart = Math.abs(v - lui[i]); k = i; } });
  if (k >= 0 && ecart >= 12) {
    for (const [v, nom] of [[toi[k], 'Toi'], [lui[k], ligne.pays.nom]]) {
      const [x, y] = point(k, v);
      const droite = Math.cos(angle(k)) >= -0.01;
      svg.append('text').attr('class', 'radar-nom').attr('x', x + (droite ? 9 : -9)).attr('y', y - 7)
        .attr('text-anchor', droite ? 'start' : 'end').text(nom);
    }
  }

  const bulle = h('div', { class: 'bulle', hidden: true });
  zone.append(bulle);
  const texte = i => `${LIBELLES[CRITERES[i]]} : toi ${exprime[i] ? entier.format(toi[i]) : 'sans avis'}, ${ligne.pays.nom} ${entier.format(lui[i])}`;
  const montrer = (ev, i) => {
    const r = zone.getBoundingClientRect();
    bulle.textContent = texte(i);
    bulle.hidden = false;
    const demi = bulle.offsetWidth / 2;
    bulle.style.left = `${Math.max(demi, Math.min(r.width - demi, ev.clientX - r.left))}px`;
    bulle.style.top = `${Math.max(bulle.offsetHeight + 10, ev.clientY - r.top)}px`;
  };
  CRITERES.forEach((_, i) => {
    const a = point(i, 100), g = [cx + (R + 12) * Math.cos(angle(i) - Math.PI / 6), cy + (R + 12) * Math.sin(angle(i) - Math.PI / 6)];
    const d = [cx + (R + 12) * Math.cos(angle(i) + Math.PI / 6), cy + (R + 12) * Math.sin(angle(i) + Math.PI / 6)];
    svg.append('polygon').attr('class', 'radar-zone-axe').attr('points', [[cx, cy], g, a, d].map(p => p.join(',')).join(' '))
      .on('pointermove', ev => montrer(ev, i)).on('pointerleave', () => { bulle.hidden = true; })
      .on('click', () => surAxe(i));
  });
  CRITERES.forEach((c, i) => {
    const x = cx + (R + 33) * Math.cos(angle(i)), y = cy + (R + 29) * Math.sin(angle(i));
    const largeur = 82, hauteur = 30;
    const groupe = svg.append('g').attr('class', `radar-axe${i === axe ? ' actif' : ''}${exprime[i] ? '' : ' sans-avis'}`)
      .attr('role', 'button').attr('tabindex', 0).attr('aria-pressed', i === axe)
      .attr('aria-label', `${texte(i)}. Voir pourquoi.`)
      .on('click', () => surAxe(i))
      .on('keydown', ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); surAxe(i); } });
    groupe.append('rect').attr('x', x - largeur / 2).attr('y', y - hauteur / 2).attr('width', largeur).attr('height', hauteur);
    groupe.append('text').attr('x', x).attr('y', y).text(LIBELLES[c]);
  });
}

function legende(nom) {
  const marque = (classe, dessin) => {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('viewBox', '-7 -7 14 14');
    s.setAttribute('aria-hidden', 'true');
    s.innerHTML = dessin;
    s.firstChild.setAttribute('class', classe);
    return s;
  };
  return h('div', { class: 'legende' },
    h('span', {}, marque('point-toi', '<circle r="5"/>'), 'Toi'),
    h('span', {}, marque('point-pays', '<path d="M0-6.4 6.4 0 0 6.4-6.4 0Z"/>'), nom));
}

function tableValeurs(prof, ligne) {
  return h('details', { class: 'table-valeurs' },
    h('summary', { text: 'Voir ces valeurs en tableau' }),
    h('table', {},
      h('thead', {}, h('tr', {}, h('th', { scope: 'col', text: 'Critère' }), h('th', { scope: 'col', text: 'Toi' }), h('th', { scope: 'col', text: ligne.pays.nom }))),
      h('tbody', {}, CRITERES.map((c, i) => h('tr', {},
        h('th', { scope: 'row', text: LIBELLES[c] }),
        h('td', { text: prof[i].importance >= SEUIL_EXPRIME ? entier.format(prof[i].valeur) : 'sans avis' }),
        h('td', { text: entier.format(ligne.pays.scores[i]) }))))));
}

// ----- « Pourquoi ce pays ? » : les faits derrière chaque note -----
function listeSites(iso3, categories) {
  const sites = (D.sites.get(iso3) || []).filter(s => categories.includes(s.categorie))
    .sort((a, b) => +a.annee_inscription - +b.annee_inscription || a.nom_fr.localeCompare(b.nom_fr, 'fr'));
  if (!sites.length) return h('p', { class: 'discret', text: 'Aucun site de cette catégorie dans nos données.' });
  return h('details', {},
    h('summary', { text: `Voir ${sites.length > 1 ? `les ${sites.length} sites` : 'le site'}` }),
    h('ul', { class: 'liste-sites' }, sites.map(s => h('li', {},
      `${s.nom_fr} (${s.annee_inscription}) · `,
      h('a', { href: s.lien_unesco, target: '_blank', rel: 'noopener', text: 'fiche' })))),
    h('p', { class: 'discret', text: 'Les noms viennent de Wikidata et de Wikipédia. Les intitulés officiels peuvent être différents.' }));
}

function detailsCritere(a, ligne) {
  const p = D.brut.get(ligne.pays.iso3);
  const n = c => +p[c];
  const puces = textes => h('ul', {}, textes.map(t => h('li', { text: t })));
  switch (CRITERES[a]) {
    case 'culture':
      return [puces([`${n('unesco_culturel') + n('unesco_mixte')} sites culturels ou mixtes au patrimoine mondial.`]), listeSites(p.iso3, ['culturel', 'mixte'])];
    case 'nature':
      return [puces([
        `${decimal.format(n('foret_pct'))} % des terres couvertes de forêt (${p.annee_foret}).`,
        `${decimal.format(n('densite_hab_km2'))} habitants par km² (${p.annee_densite}).`,
        `${decimal.format(n('zones_protegees_pct'))} % des terres protégées (${p.annee_zones_protegees}).`,
        `${n('unesco_naturel') + n('unesco_mixte')} sites naturels ou mixtes au patrimoine mondial.`,
      ]), listeSites(p.iso3, ['naturel', 'mixte'])];
    case 'villes':
      return [puces([p.annee_pop_villes_1m
        ? `${decimal.format(n('pop_villes_1m_pct'))} % de la population vit dans une agglomération de plus d'un million d'habitants (${p.annee_pop_villes_1m}).`
        : 'Le pays n\'apparaît pas dans la série des agglomérations de plus d\'un million d\'habitants : la valeur retenue est 0 %.'])];
    case 'prix': {
      const i = n('niveau_prix'), diff = Math.round(Math.abs(1 - i) * 100);
      return [puces([`Indice du niveau des prix : ${prixFmt.format(i)} (États-Unis = 1, ${p.annee_niveau_prix}).`,
        diff ? `Les prix y sont environ ${diff} % plus ${i < 1 ? 'bas' : 'hauts'} qu'aux États-Unis.` : 'Les prix y sont proches de ceux des États-Unis.'])];
    }
    case 'distance':
      return [puces([ligne.pays.distance ? `${entier.format(ligne.pays.distance)} km à vol d'oiseau entre Paris et ${p.capitale}.` : 'C\'est le point de départ de la mesure : Paris.'])];
    default:
      return [puces(p.sans_littoral === 'true'
        ? ['Pas d\'accès à la mer.']
        : [`${entier.format(n('cotes_km'))} km de côtes.`, `Latitude du centre du pays : ${decimal.format(Math.abs(n('lat_centre')))}° ${n('lat_centre') >= 0 ? 'nord' : 'sud'}.`]),
      h('p', { class: 'discret', text: 'Cette note combine la longueur des côtes et la chaleur selon la latitude. Elle ne dit rien des plages.' })];
  }
}

// ----- Ce que chaque réponse a changé dans le profil -----
function sensEffet(e) {
  const nom = LIBELLES[e.critere];
  if (e.valeur >= 60) return `${nom} : plus`;
  if (e.valeur <= 40) return `${nom} : moins`;
  return `${nom} : moyen`;
}

function detailReponses(reponses) {
  return h('details', { class: 'limites panneau effets-reponses' },
    h('summary', { text: 'Ce que chacune de tes réponses a changé' }),
    h('p', { class: 'discret', text: '« Prix bas : moins » veut dire que tu acceptes un pays plus cher.' }),
    h('div', { class: 'table-defile' }, h('table', {},
      h('thead', {}, h('tr', {}, h('th', { scope: 'col', text: 'Question' }), h('th', { scope: 'col', text: 'Ton choix' }), h('th', { scope: 'col', text: 'Effet' }))),
      h('tbody', {}, reponses.map(r => {
        const q = D.questions[r.q], o = q.options[r.o];
        return h('tr', {}, h('td', { text: q.question }), h('td', { text: o.titre }),
          h('td', {}, o.effets.map(e => h('p', {}, h('strong', { text: `${sensEffet(e)}. ` }), e.raison))));
      })))));
}

// ----- Écran de résultat -----
function resultat(reponses) {
  const { profil: prof, classement: initial } = etat(D.questions, D.pays, reponses, D.nombre);
  history.replaceState(null, '', `#r=${coderParcours(reponses)}`);
  const gagnant = initial[0], dernier = initial[initial.length - 1];
  const importances = prof.map(p => p.importance);
  const e = {
    actif: gagnant.pays.iso3, axe: importances.indexOf(Math.max(...importances)),
    tri: 'ressemblance', facteurs: CRITERES.map(() => 1), courant: initial,
  };
  const ligneActive = () => e.courant.find(l => l.pays.iso3 === e.actif);

  const titreComparaison = h('h2');
  const sousComparaison = h('p', { class: 'discret' });
  const zoneRadar = h('div', { class: 'radar-zone' });
  const zoneLegende = h('div');
  const zoneTable = h('div');
  const zonePourquoi = h('div', { class: 'pourquoi', 'aria-live': 'polite' });
  const zoneFaits = h('div');

  const lignesDom = new Map();
  const liste = h('ol', { class: 'classement', 'aria-label': 'Classement des 41 pays' });
  for (const l of initial) {
    const barre = h('span', { class: 'ligne-barre' });
    const rang = h('span', { class: 'ligne-rang' }), valeur = h('span', { class: 'ligne-valeur' });
    const bouton = h('button', { class: 'ligne-pays', type: 'button', onclick: () => choisirPays(l.pays.iso3) },
      rang, h('span', { class: 'ligne-nom', text: l.pays.nom }), h('span', { class: 'ligne-rail' }, barre), valeur);
    const li = h('li', {}, bouton);
    lignesDom.set(l.pays.iso3, { li, bouton, barre, rang, valeur, nom: l.pays.nom });
    liste.append(li);
  }

  function majClassement(animer) {
    const avant = animer && !calme ? new Map([...lignesDom].map(([k, v]) => [k, v.li.offsetTop])) : null;
    e.courant = classer(D.pays, prof, e.facteurs);
    const rangs = new Map(e.courant.map((l, i) => [l.pays.iso3, i + 1]));
    let ordre = e.courant, note = l => l.ressemblance, unite = ' %';
    if (e.tri !== 'ressemblance') {
      const a = +e.tri;
      note = l => l.pays.scores[a];
      unite = '';
      ordre = [...e.courant].sort((x, y) => note(y) - note(x) || rangs.get(x.pays.iso3) - rangs.get(y.pays.iso3));
    }
    ordre.forEach((l, i) => {
      const d = lignesDom.get(l.pays.iso3), v = note(l), actif = l.pays.iso3 === e.actif;
      d.rang.textContent = i + 1;
      d.barre.style.width = `${Math.max(0, v)}%`;
      d.valeur.textContent = `${entier.format(v)}${unite}`;
      d.bouton.setAttribute('aria-pressed', actif);
      d.bouton.setAttribute('aria-label', `${i + 1}. ${d.nom}, ${entier.format(v)}${unite}`);
      liste.append(d.li);
    });
    if (avant) {
      for (const [k, d] of lignesDom) {
        const delta = avant.get(k) - d.li.offsetTop;
        if (delta) d.li.animate([{ transform: `translateY(${delta}px)` }, { transform: 'none' }], { duration: 280, easing: 'cubic-bezier(.2,.7,.2,1)' });
      }
    }
  }

  function majComparaison() {
    const l = ligneActive(), rang = e.courant.indexOf(l) + 1;
    titreComparaison.textContent = `${l.pays.nom} face à ton profil`;
    sousComparaison.textContent = `${entier.format(l.ressemblance)} % de ressemblance, ${rang === 1 ? '1er' : `${rang}e`} sur ${e.courant.length}.`;
    dessinerRadar(zoneRadar, prof, l, e.axe, a => { e.axe = a; majComparaison(); });
    zoneLegende.replaceChildren(legende(l.pays.nom));
    zoneTable.replaceChildren(tableValeurs(prof, l));
    const voeu = prof[e.axe].importance >= SEUIL_EXPRIME ? `${entier.format(prof[e.axe].valeur)} sur 100` : 'sans avis';
    zonePourquoi.replaceChildren(
      h('p', { class: 'etiquette', text: 'Pourquoi cette note ?' }),
      h('h3', { text: `${LIBELLES[CRITERES[e.axe]]} : ${entier.format(l.pays.scores[e.axe])} sur 100` }),
      h('p', { class: 'discret', text: `Ton souhait sur ce critère : ${voeu}.` }),
      ...detailsCritere(e.axe, l));
    const faits = leSaviezVous(D.faits, l.pays.iso3);
    zoneFaits.replaceChildren(faits.length
      ? h('ul', { class: 'faits' }, faits.map(f => h('li', { text: f.texte })))
      : h('p', { class: 'discret', text: `${l.pays.nom} n'arrive dans les trois premiers de la sélection sur aucune de nos mesures.` }));
  }

  function choisirPays(iso3) { e.actif = iso3; majClassement(false); majComparaison(); }

  const bilan = h('p', { 'aria-live': 'polite' });
  const reinit = h('button', { class: 'lien-bouton', type: 'button', text: 'Revenir à mes réponses', hidden: true });
  const curseurs = CRITERES.map((c, a) => {
    const inactif = prof[a].importance < SEUIL_EXPRIME;
    const sortie = h('output', { text: inactif ? 'Sans avis' : REGLAGES[1] });
    const entree = h('input', { id: `reglage-${c}`, type: 'range', min: 0, max: 2, step: 0.5, value: 1, disabled: inactif });
    entree.addEventListener('input', () => {
      e.facteurs[a] = +entree.value;
      sortie.textContent = REGLAGES[entree.value];
      majEtSi(true);
    });
    return { entree, sortie, inactif, bloc: h('div', { class: `reglage${inactif ? ' inactif' : ''}` }, h('label', { for: `reglage-${c}` }, LIBELLES[c], sortie), entree) };
  });
  function majEtSi(animer) {
    majClassement(animer);
    majComparaison();
    const modifie = e.facteurs.some(f => f !== 1);
    const tete = e.courant[0];
    bilan.textContent = !modifie ? `En tête avec tes réponses : ${tete.pays.nom}.`
      : tete.pays.iso3 === gagnant.pays.iso3 ? `Toujours en tête : ${tete.pays.nom}.`
        : `Nouveau pays en tête : ${tete.pays.nom} (au lieu de : ${gagnant.pays.nom}).`;
    reinit.hidden = !modifie;
  }
  reinit.addEventListener('click', () => {
    e.facteurs = CRITERES.map(() => 1);
    curseurs.forEach(c => { c.entree.value = 1; c.sortie.textContent = c.inactif ? 'Sans avis' : REGLAGES[1]; });
    majEtSi(true);
    curseurs.find(c => !c.inactif)?.entree.focus();
  });

  const tri = h('select', { id: 'tri-classement', onchange: ev => { e.tri = ev.target.value; majClassement(true); liste.scrollTop = 0; } },
    h('option', { value: 'ressemblance', text: 'Ressemblance' }),
    CRITERES.map((c, a) => h('option', { value: a, text: LIBELLES[c] })));

  const statutPartage = h('span', { class: 'discret', 'aria-live': 'polite' });
  const partager = async () => {
    try {
      await navigator.clipboard.writeText(location.href);
      statutPartage.textContent = 'Lien copié.';
    } catch {
      statutPartage.textContent = `Copie impossible. Lien : ${location.href}`;
    }
  };

  const brut = D.brut.get(gagnant.pays.iso3);
  const sim = D.simulation;
  const titre = h('h1', { tabindex: '-1', text: gagnant.pays.nom });
  ecran(h('div', { class: 'resultat' },
    h('section', { class: 'res-tete' },
      h('div', { class: 'res-photo' },
        h('img', { src: brut.image_url, alt: `Photo illustrant ${gagnant.pays.nom}`, width: 800, height: 533 }),
        credit(brut.image_auteur, brut.image_licence, brut.image_url)),
      h('div', { class: 'res-texte' },
        h('p', { class: 'etiquette', text: 'Le pays qui te ressemble le plus' }), titre,
        h('p', { class: 'score-principal', text: `${entier.format(gagnant.ressemblance)} % de ressemblance` }),
        h('p', { text: brut.description }),
        h('p', {}, 'Celui qui te ressemble le moins : ',
          h('button', { class: 'lien-bouton', type: 'button', text: `${dernier.pays.nom} (${entier.format(dernier.ressemblance)} %)`, onclick: () => { choisirPays(dernier.pays.iso3); titreComparaison.scrollIntoView({ behavior: calme ? 'auto' : 'smooth' }); } })))),
    h('div', { class: 'colonnes' },
      h('section', { class: 'panneau' },
        h('div', { class: 'bloc-titre' }, titreComparaison, sousComparaison),
        zoneRadar, zoneLegende, zoneTable),
      h('section', { class: 'panneau' }, zonePourquoi)),
    h('div', { class: 'colonnes' },
      h('section', { class: 'panneau' },
        h('div', { class: 'bloc-titre' }, h('h2', { text: 'Le classement' }),
          h('p', { class: 'discret', text: 'Choisis un pays pour le comparer à ton profil.' })),
        h('div', { class: 'tri' }, h('label', { for: 'tri-classement', text: 'Trier par' }), tri),
        liste),
      h('section', { class: 'panneau' },
        h('div', { class: 'bloc-titre' }, h('h2', { text: 'Et si…' }),
          h('p', { class: 'discret', text: 'Change l\'importance d\'un critère : le classement se réorganise.' })),
        h('div', { class: 'etsi-grille' }, curseurs.map(c => c.bloc)),
        h('div', { class: 'etsi-bilan' }, bilan, reinit))),
    h('section', { class: 'panneau' },
      h('div', { class: 'bloc-titre' }, h('h2', { text: 'Le saviez-vous ?' })), zoneFaits),
    h('div', { class: 'actions' },
      h('button', { class: 'btn btn--primary', type: 'button', text: 'Copier le lien du résultat', onclick: partager }),
      h('button', { class: 'btn btn--secondary', type: 'button', text: 'Recommencer', onclick: accueil }),
      statutPartage),
    detailReponses(reponses),
    h('details', { class: 'limites panneau' },
      h('summary', { text: 'Ce que ce quiz mesure, et ses limites' }),
      h('ul', {},
        h('li', { text: 'Il compare six critères : sites culturels du patrimoine mondial, espaces naturels, population des très grandes villes, niveau des prix, distance depuis Paris et potentiel de mer chaude.' }),
        h('li', { text: 'Il ne mesure ni les langues, ni la cuisine, ni la faune, ni la montagne, ni le climat mois par mois, ni la qualité des plages.' }),
        h('li', { text: '« Un plat de rue » compte pour le prix. Le quiz ne dit rien de la cuisine du pays, et les autres situations marchent de la même façon.' }),
        h('li', { text: 'Les notes sont relatives aux 41 pays choisis. Cette sélection n\'a aucun pays des Caraïbes, limite l\'Afrique du Nord au Maroc et à l\'Égypte, et ne compte pas l\'Allemagne, la Belgique ni les Pays-Bas.' }),
        h('li', { text: `Sur les ${entier.format(sim.parcours)} parcours possibles, si chaque réponse a la même probabilité, aucun pays ne gagne plus de ${decimal.format(sim.part_max_pct)} % des parties. ${new Intl.ListFormat('fr-FR').format(sim.jamais_top3)} n'atteignent jamais le top 3, mais restent dans le classement.` }),
        h('li', { text: 'Les photos des questions illustrent le choix et ne montrent aucun lieu célèbre, pour que personne ne reconnaisse une destination.' }),
        h('li', {}, 'Sources, licences et données : ', h('a', { href: 'data/telechargement/periple_donnees.zip', text: 'télécharger le fichier complet' }), '.')))));
  majEtSi(false);
  titre.focus({ preventScroll: true });
}

// ----- Démarrage -----
function ouvrirDepuisAdresse() {
  const t = /^#r=(.+)$/.exec(location.hash);
  const parcours = t && lireParcours(decodeURIComponent(t[1]), D.questions, D.pays, D.nombre);
  if (parcours) resultat(parcours); else accueil();
}

try {
  await charger();
  ouvrirDepuisAdresse();
  addEventListener('hashchange', ouvrirDepuisAdresse);
} catch (erreur) {
  console.error(erreur);
  racine.replaceChildren(h('p', { class: 'quiz-attente', text: 'Impossible de charger les données du quiz. Vérifie ta connexion, puis recharge la page.' }));
}
