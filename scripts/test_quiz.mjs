// Parcourt tous les chemins du quiz avec le moteur du site et imprime un résumé JSON.
// Lancé par scripts/test_quiz.py, qui compare le résultat au calcul Python.
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { CRITERES, construireFaits, etat, leSaviezVous, coderParcours, lireParcours } from '../quiz-moteur.js';

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
const faits = construireFaits(brut, scores, csv(lire('data/unesco_sites.csv')));

console.log(JSON.stringify({
  parcours, empreinte: empreinte.digest('hex'),
  parcours_relu: lireParcours(exemple, questions, pays, nombre)?.length ?? 0,
  parcours_faux_refuse: lireParcours('99.0', questions, pays, nombre) === null,
  faits: Object.fromEntries(brut.map(p => [p.iso3, leSaviezVous(faits, p.iso3, 99).map(({ cle, sens, rang, egaux }) => ({ cle, sens, rang, egaux }))])),
}));
