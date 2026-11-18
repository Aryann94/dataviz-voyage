// ===== Moteur du quiz : aucun accès à la page, testé par scripts/test_quiz.py =====
export const CRITERES = ['culture', 'nature', 'villes', 'prix', 'distance', 'mer'];
export const LIBELLES = { culture: 'Culture', nature: 'Nature', villes: 'Villes', prix: 'Prix bas', distance: 'Distance', mer: 'Mer' };
export const POIDS_PLEIN = 1.5;   // poids cumulé à partir duquel un critère compte pleinement
export const PAYS_DE_TETE = 8;    // la question suivante départage ces pays
export const SEUIL_EXPRIME = 0.05;   // en dessous, le joueur ne s'est pas vraiment prononcé

const INDICE = Object.fromEntries(CRITERES.map((c, i) => [c, i]));

function cumulVide() {
  return { somme: CRITERES.map(() => 0), poids: CRITERES.map(() => 0) };
}

function ajouter(cumul, option) {
  for (const e of option.effets) {
    const a = INDICE[e.critere];
    cumul.somme[a] += e.valeur * e.poids;
    cumul.poids[a] += e.poids;
  }
}

// reponses : [{ q: indice de la question, o: indice de l'option }, ...]
export function cumuler(questions, reponses) {
  const cumul = cumulVide();
  for (const r of reponses) ajouter(cumul, questions[r.q].options[r.o]);
  return cumul;
}

// Valeur souhaitée et importance de chaque critère. Une envie tiède (proche de 50) compte peu.
export function profil(cumul) {
  return CRITERES.map((_, a) => {
    const valeur = cumul.poids[a] ? cumul.somme[a] / cumul.poids[a] : 50;
    return { valeur, importance: Math.min(1, cumul.poids[a] / POIDS_PLEIN) * Math.abs(valeur - 50) / 50 };
  });
}

// pays : [{ iso3, scores: [6 notes] }]. facteurs : multiplicateurs du mode « Et si… ».
export function classer(pays, prof, facteurs = null) {
  const imp = prof.map((p, a) => p.importance * (facteurs ? facteurs[a] : 1));
  let total = 0;
  for (const i of imp) total += i;
  const maximum = total * 1e4;
  const lignes = pays.map(p => {
    if (!maximum) return { pays: p, ressemblance: 0 };
    let ecart = 0;
    for (let a = 0; a < imp.length; a++) ecart += imp[a] * (prof[a].valeur - p.scores[a]) ** 2;
    return { pays: p, ressemblance: 100 * (1 - Math.sqrt(ecart / maximum)) };
  });
  return lignes.sort((x, y) => y.ressemblance - x.ressemblance || (x.pays.iso3 < y.pays.iso3 ? -1 : 1));
}

// Question la plus utile : elle porte sur les critères qui séparent le plus les pays de tête
// et sur lesquels le joueur s'est encore peu exprimé.
export function prochaineQuestion(questions, restantes, classement, poids) {
  const tete = classement.slice(0, PAYS_DE_TETE);
  const ecarts = CRITERES.map((_, a) => {
    let moyenne = 0;
    for (const l of tete) moyenne += l.pays.scores[a];
    moyenne /= tete.length;
    let somme = 0;
    for (const l of tete) somme += (l.pays.scores[a] - moyenne) ** 2;
    return Math.sqrt(somme / tete.length);
  });
  let meilleure = -1, record = -Infinity;
  for (const q of [...restantes].sort((a, b) => a - b)) {
    let note = 0;
    for (const o of questions[q].options) {
      for (const e of o.effets) {
        const a = INDICE[e.critere];
        note += e.poids * ecarts[a] * (1 - Math.min(1, poids[a] / POIDS_PLEIN));
      }
    }
    note /= questions[q].options.length;
    if (note > record) { record = note; meilleure = q; }
  }
  return meilleure;
}

// État après une suite de réponses : profil, classement et question suivante.
export function etat(questions, pays, reponses, nombre) {
  const cumul = cumuler(questions, reponses);
  const prof = profil(cumul);
  const classement = classer(pays, prof);
  let suivante = null;
  if (reponses.length < nombre) {
    const posees = new Set(reponses.map(r => r.q));
    const restantes = questions.map((_, i) => i).filter(i => !posees.has(i));
    suivante = prochaineQuestion(questions, restantes, classement, cumul.poids);
  }
  return { cumul, profil: prof, classement, suivante };
}

// Parcours partagé : « 0.1-3.2-… ». Renvoie null s'il ne correspond pas au déroulé du quiz.
export const coderParcours = reponses => reponses.map(r => `${r.q}.${r.o}`).join('-');

export function lireParcours(texte, questions, pays, nombre) {
  const morceaux = String(texte || '').split('-');
  if (morceaux.length !== nombre) return null;
  const reponses = [];
  for (const m of morceaux) {
    const t = /^(\d+)\.(\d+)$/.exec(m);
    if (!t) return null;
    const r = { q: +t[1], o: +t[2] };
    if (etat(questions, pays, reponses, nombre).suivante !== r.q) return null;
    if (!questions[r.q].options[r.o]) return null;
    reponses.push(r);
  }
  return reponses;
}

// ===== « Le saviez-vous ? » : phrases construites depuis les rangs, égalités comprises =====
const MESURES = [
  { cle: 'niveau_prix', haut: 'le plus cher', bas: 'le moins cher', hautN: 'les plus chers', basN: 'les moins chers' },
  { cle: 'unesco_total', haut: 'le plus riche en sites du patrimoine mondial', bas: null, hautN: 'les plus riches en sites du patrimoine mondial' },
  { cle: 'foret_pct', haut: 'le plus couvert de forêt', bas: 'le moins couvert de forêt', hautN: 'les plus couverts de forêt', basN: 'les moins couverts de forêt' },
  { cle: 'densite_hab_km2', haut: 'le plus densément peuplé', bas: 'le moins densément peuplé', hautN: 'les plus densément peuplés', basN: 'les moins densément peuplés' },
  { cle: 'cotes_km', haut: 'avec le plus de kilomètres de côtes', bas: null, hautN: 'avec le plus de kilomètres de côtes' },
  { cle: 'pop_villes_1m_pct', haut: 'avec la plus forte part d\'habitants dans les très grandes villes', bas: null, hautN: 'avec la plus forte part d\'habitants dans les très grandes villes' },
  { cle: 'zones_protegees_pct', haut: 'avec la plus grande part de terres protégées', bas: 'avec la plus petite part de terres protégées', hautN: 'avec la plus grande part de terres protégées', basN: 'avec la plus petite part de terres protégées' },
  { cle: 'distance_paris_km', haut: 'le plus éloigné de Paris', bas: null, hautN: 'les plus éloignés de Paris' },
];
export const RANG_MAX_FAIT = 3;

// Faits bruts des pays, à partir des lignes (texte) de pays.csv, scores.csv et unesco_sites.csv
export function construireFaits(paysBruts, scores, sites) {
  const distance = Object.fromEntries(scores.map(s => [s.iso3, +s.distance_paris_km]));
  const premiere = {};
  for (const s of sites) premiere[s.iso3] = Math.min(premiere[s.iso3] ?? Infinity, +s.annee_inscription);
  return paysBruts.map(p => ({
    iso3: p.iso3, nom: p.nom_fr, niveau_prix: +p.niveau_prix, unesco_total: +p.unesco_total,
    foret_pct: +p.foret_pct, densite_hab_km2: +p.densite_hab_km2, cotes_km: +p.cotes_km,
    pop_villes_1m_pct: +p.pop_villes_1m_pct, zones_protegees_pct: +p.zones_protegees_pct,
    distance_paris_km: distance[p.iso3], sans_littoral: p.sans_littoral === 'true',
    premiere_inscription: premiere[p.iso3],
  }));
}

function rangDe(faits, cle, iso3, sens) {
  const valeurs = faits.map(f => ({ iso3: f.iso3, v: f[cle] })).filter(x => Number.isFinite(x.v));
  const moi = valeurs.find(x => x.iso3 === iso3);
  if (!moi) return null;
  const devant = valeurs.filter(x => sens * (x.v - moi.v) > 0).length;
  const egaux = valeurs.filter(x => x.v === moi.v).length;
  return { rang: devant + 1, egaux, total: valeurs.length };
}

// faits : [{ iso3, nom, niveau_prix, unesco_total, …, sans_littoral, premiere_inscription }]
export function leSaviezVous(faits, iso3, maximum = 3) {
  const moi = faits.find(f => f.iso3 === iso3);
  const candidats = [];
  for (const m of MESURES) {
    for (const sens of [1, -1]) {
      const adjectif = sens === 1 ? m.haut : m.bas;
      if (!adjectif) continue;
      const r = rangDe(faits, m.cle, iso3, sens);
      if (!r || r.rang > RANG_MAX_FAIT) continue;
      let texte;
      if (r.egaux > 1) {
        const pluriel = sens === 1 ? m.hautN : m.basN;
        texte = `${moi.nom} : parmi les ${r.rang + r.egaux - 1} pays ${pluriel} de notre sélection, à égalité avec ${r.egaux - 1} autre${r.egaux > 2 ? 's' : ''}.`;
      } else if (r.rang === 1) {
        texte = `${moi.nom} : le pays ${adjectif} de notre sélection de ${r.total}.`;
      } else {
        texte = `${moi.nom} : ${r.rang}ᵉ pays ${adjectif} de notre sélection de ${r.total}.`;
      }
      candidats.push({ cle: m.cle, sens, rang: r.rang, egaux: r.egaux, texte });
    }
  }
  if (moi.sans_littoral) {
    const n = faits.filter(f => f.sans_littoral).length;
    candidats.push({ cle: 'sans_littoral', sens: 0, rang: n, egaux: n, texte: `${moi.nom} : l'un des ${n} pays de notre sélection sans accès à la mer.` });
  }
  if (Number.isFinite(moi.premiere_inscription)) {
    const r = rangDe(faits, 'premiere_inscription', iso3, -1);
    if (r.rang <= RANG_MAX_FAIT) {
      const texte = r.egaux > 1
        ? `${moi.nom} : un site inscrit au patrimoine mondial dès ${moi.premiere_inscription}, comme ${r.egaux - 1} autre${r.egaux > 2 ? 's' : ''} pays de notre sélection.`
        : `${moi.nom} : le pays de notre sélection dont le premier site a été inscrit le plus tôt, en ${moi.premiere_inscription}.`;
      candidats.push({ cle: 'premiere_inscription', sens: -1, rang: r.rang, egaux: r.egaux, texte });
    }
  }
  candidats.sort((a, b) => a.rang - b.rang || a.egaux - b.egaux);
  return candidats.slice(0, maximum);
}
