// Parcourt tous les chemins du quiz avec le moteur du site et imprime un résumé JSON.
// Lancé par scripts/test_quiz.py, qui compare le résultat au calcul Python.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { CRITERES, etat, leSaviezVous, coderParcours, lireParcours } from '../quiz-moteur.js';

const racine = new URL('../', import.meta.url);
const lire = f => readFileSync(new URL(f, racine), 'utf8');
const { questions, nombre_questions: nombre } = JSON.parse(lire('data/quiz_questions.json'));

function csv(texte) {
  const lignes = [];
  let ligne = [], champ = '', guillemets = false;
  for (let i = 0; i < texte.length; i++) {
    const c = texte[i];
    if (guillemets) {
      if (c === '"' && texte[i + 1] === '"') { champ += '"'; i++; }
      else if (c === '"') guillemets = false;
      else champ += c;
    } else if (c === '"') guillemets = true;
    else if (c === ',') { ligne.push(champ); champ = ''; }
    else if (c === '\n') { ligne.push(champ.replace(/\r$/, '')); lignes.push(ligne); ligne = []; champ = ''; }
    else champ += c;
  }
  const [entete, ...corps] = lignes;
  return corps.map(l => Object.fromEntries(entete.map((k, i) => [k, l[i]])));
}

const scores = csv(lire('data/scores.csv'));
const pays = scores.map(s => ({ iso3: s.iso3, scores: CRITERES.map(c => +s[`score_${c}`]) }));
const empreinte = createHash('sha256');
let parcours = 0, exemple = null;

function suivre(reponses) {
  const e = etat(questions, pays, reponses, nombre);
  if (reponses.length === nombre) {
    parcours++;
    const code = coderParcours(reponses);
    exemple ??= code;
    empreinte.update(`${code}:${e.classement.slice(0, 3).map(l => l.pays.iso3).join(',')}:${e.classement.at(-1).pays.iso3}\n`);
    return;
  }
  questions[e.suivante].options.forEach((_, o) => suivre([...reponses, { q: e.suivante, o }]));
}
suivre([]);

const brut = csv(lire('data/pays.csv'));
const distance = Object.fromEntries(scores.map(s => [s.iso3, +s.distance_paris_km]));
const premiere = {};
for (const l of csv(lire('data/unesco_sites.csv'))) premiere[l.iso3] = Math.min(premiere[l.iso3] ?? Infinity, +l.annee_inscription);
const faits = brut.map(p => ({
  iso3: p.iso3, nom: p.nom_fr, niveau_prix: +p.niveau_prix, unesco_total: +p.unesco_total, foret_pct: +p.foret_pct,
  densite_hab_km2: +p.densite_hab_km2, cotes_km: +p.cotes_km, pop_villes_1m_pct: +p.pop_villes_1m_pct,
  zones_protegees_pct: +p.zones_protegees_pct, distance_paris_km: distance[p.iso3],
  sans_littoral: p.sans_littoral === 'true', premiere_inscription: premiere[p.iso3],
}));

console.log(JSON.stringify({
  parcours, empreinte: empreinte.digest('hex'),
  parcours_relu: lireParcours(exemple, questions, pays, nombre)?.length ?? 0,
  parcours_faux_refuse: lireParcours('99.0', questions, pays, nombre) === null,
  faits: Object.fromEntries(brut.map(p => [p.iso3, leSaviezVous(faits, p.iso3, 99).map(({ cle, sens, rang, egaux }) => ({ cle, sens, rang, egaux }))])),
}));
