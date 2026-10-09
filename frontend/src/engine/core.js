// JavaScript port of resume_scanner (skills.py, extractor.py, matcher.py, segregator.py).
// Pure functions on text, so the same file runs in the browser and in Node (parity tests).
import config from "./config.json" with { type: "json" };

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

// ---------------------------------------------------------------- skills
const SKILL_CATEGORY = {};
const PATTERNS = [];
for (const [cat, skills] of Object.entries(config.skills)) {
  for (const [canonical, aliases] of Object.entries(skills)) {
    SKILL_CATEGORY[canonical] = cat;
    const names = new Set(aliases);
    if (!config.no_canonical_match.includes(canonical)) names.add(canonical.toLowerCase());
    [...names].sort((a, b) => b.length - a.length).forEach((alias) => {
      PATTERNS.push([canonical, new RegExp(`(?<![a-z0-9+#])${esc(alias)}(?![a-z0-9+#])`, "i"), alias]);
    });
  }
}
const AMBIGUOUS = new Set(config.ambiguous);

export function findSkills(text) {
  const found = new Set();
  for (const [canonical, re] of PATTERNS) {
    if (found.has(canonical)) continue;
    const m = text.match(re);
    if (!m) continue;
    const alias = m[0].toLowerCase();
    if (AMBIGUOUS.has(alias)) {
      const all = text.match(new RegExp(re.source, "gi")) || [];
      const listed = new RegExp(`${esc(alias)}\\s*(,|/|\\||\\band\\b)`, "i").test(text);
      if (all.length < 2 && !listed) continue;
    }
    found.add(canonical);
  }
  return [...found].sort(cmp);
}

// Python sorts strings by code point; localeCompare would not.
export function cmp(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

export function expandImplied(skills) {
  const out = new Set(skills);
  const stack = [...out];
  while (stack.length) {
    for (const parent of config.implies[stack.pop()] || []) {
      if (!out.has(parent)) { out.add(parent); stack.push(parent); }
    }
  }
  return [...out].sort(cmp);
}

export function categorize(skills) {
  const out = {};
  for (const s of skills) (out[SKILL_CATEGORY[s] || "Other"] ||= []).push(s);
  return out;
}

// ---------------------------------------------------------------- extractor
const EMAIL_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;
const PHONE_RE = /(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,5}\)?[\s-]?)?\d{3,5}[\s-]?\d{4,5}/g;
const URL_RE = /(?:https?:\/\/)?(?:www\.)?(linkedin\.com\/in\/[\w-]+|github\.com\/[\w-]+)/gi;
const L = "(?<![a-z])", R = "(?![a-z])";
const DEGREES = [
  ["PhD", new RegExp(`${L}(ph\\.?d|doctorate)${R}`, "i")],
  ["Master's", new RegExp(`${L}(m\\.?tech|m\\.e\\.?|m\\.?sc|mca|mba|m\\.?des|master'?s?|m\\.s\\.)${R}`, "i")],
  ["Bachelor's", new RegExp(`${L}(b\\.?tech|b\\.e\\.?|b\\.?sc|bca|b\\.?com|b\\.?des|bachelor'?s?|b\\.s\\.|undergraduate)${R}`, "i")],
  ["Diploma", new RegExp(`${L}diploma${R}`, "i")],
];
const RANK = { PhD: 4, "Master's": 3, "Bachelor's": 2, Diploma: 1, null: 0 };
const MONTHS = { jan: 1, feb: 2, mar: 3, apr: 4, may: 5, jun: 6, jul: 7, aug: 8, sep: 9, oct: 10, nov: 11, dec: 12 };
const MON = "(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\\.?";
const DATE_RANGE_RE = new RegExp(
  `(?:${MON}\\s+)?((?:19|20)\\d{2})\\s*(?:-|to|until)\\s*(?:(?:${MON}\\s+)?((?:19|20)\\d{2})|(present|current|now|till date))`, "gi");
const YEARS_STATED_RE = /(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+|industry\s+|work\s+)?experience/gi;

export function cleanText(text) {
  return text.replace(/\u2022/g, "-").replace(/\u25cf/g, "-").replace(/\uf0b7/g, "-")
    .replace(/[\u2013\u2014]/g, "-").replace(/\xa0/g, " ")
    .replace(/[ \t]+/g, " ").replace(/\n\s*\n+/g, "\n\n").trim();
}

export function splitSections(text) {
  const lookup = {};
  for (const [key, aliases] of Object.entries(config.section_headings)) aliases.forEach((a) => (lookup[a] = key));
  const sections = { header: [] };
  let current = "header";
  for (const line of text.split("\n")) {
    const stripped = line.toLowerCase().replace(/[^a-z ]/g, "").trim();
    if (stripped in lookup && line.trim().length < 40) {
      current = lookup[stripped];
      sections[current] ||= [];
      continue;
    }
    (sections[current] ||= []).push(line);
  }
  const out = {};
  for (const [k, v] of Object.entries(sections)) { const t = v.join("\n").trim(); if (t) out[k] = t; }
  return out;
}

const HEADING_WORDS = new Set(Object.values(config.section_headings).flat());
export function extractName(text) {
  for (let line of text.split("\n").slice(0, 6)) {
    line = line.trim();
    if (!line || EMAIL_RE.test(line) || /\d/.test(line)) continue;
    const words = line.replace(/\./g, " ").split(/\s+/).filter(Boolean);
    if (words.length >= 2 && words.length <= 4 &&
        words.every((w) => w[0] === w[0].toUpperCase() && w[0] !== w[0].toLowerCase() && /^[A-Za-z]+$/.test(w.replace(/-/g, "")))) {
      if (!HEADING_WORDS.has(line.toLowerCase())) {
        return line === line.toUpperCase() ? line.toLowerCase().replace(/(^|[\s-])([a-z])/g, (m, a, b) => a + b.toUpperCase()) : line;
      }
    }
  }
  return null;
}

export function extractPhone(text) {
  for (const m of text.matchAll(PHONE_RE)) {
    const digits = m[0].replace(/\D/g, "");
    if (digits.length >= 10 && digits.length <= 13 && !/^(19|20)\d{2}(19|20)\d{2}\d*$/.test(digits)) return m[0].trim();
  }
  return null;
}

export function extractEducation(text) {
  let best = null;
  for (const [label, re] of DEGREES) if (re.test(text) && RANK[label] > RANK[best]) best = label;
  return best;
}

export function extractExperienceYears(text, today = new Date()) {
  const scope = splitSections(text).experience || "";
  const intervals = [];
  for (const m of scope.matchAll(DATE_RANGE_RE)) {
    const [, sm, sy, em, ey, present] = m;
    const start = [+sy, MONTHS[(sm || "jan").slice(0, 3).toLowerCase()] || 1];
    const end = present ? [today.getFullYear(), today.getMonth() + 1]
      : [+ey, MONTHS[(em || "dec").slice(0, 3).toLowerCase()] || 12];
    if (end[0] > start[0] || (end[0] === start[0] && end[1] >= start[1])) intervals.push([start, end]);
  }
  const le = (a, b) => a[0] < b[0] || (a[0] === b[0] && a[1] <= b[1]);
  let total = 0;
  if (intervals.length) {
    intervals.sort((a, b) => a[0][0] - b[0][0] || a[0][1] - b[0][1] || a[1][0] - b[1][0] || a[1][1] - b[1][1]);
    const merged = [[...intervals[0]]];
    for (const [s, e] of intervals.slice(1)) {
      const last = merged[merged.length - 1];
      if (le(s, last[1])) { if (le(last[1], e)) last[1] = e; } else merged.push([s, e]);
    }
    total = merged.reduce((acc, [s, e]) => acc + Math.max(0, (e[0] - s[0]) * 12 + (e[1] - s[1])), 0);
  }
  let years = round(total / 12, 1);
  const stated = [...text.matchAll(YEARS_STATED_RE)].map((m) => parseFloat(m[1]));
  if (stated.length) years = Math.max(years, ...stated);
  return years;
}

export function extractProfile(text) {
  const sections = splitSections(text);
  const skills = findSkills(text);
  const links = [...new Set([...text.matchAll(URL_RE)].map((m) => m[1].toLowerCase()))].sort(cmp);
  const email = text.match(EMAIL_RE);
  return {
    name: extractName(text), email: email ? email[0] : null,
    phone: extractPhone(sections.header ?? text), links, skills,
    skills_by_category: categorize(skills),
    education: extractEducation(sections.education ?? text),
    experience_years: extractExperienceYears(text),
  };
}

// ---------------------------------------------------------------- TF-IDF (sklearn-compatible)
const STOP = new Set(config.stop_words);
function analyze(doc) {
  const toks = (doc.toLowerCase().match(/[\p{L}\p{N}_]{2,}/gu) || []).filter((t) => !STOP.has(t));
  const grams = [...toks];
  for (let i = 0; i + 1 < toks.length; i++) grams.push(`${toks[i]} ${toks[i + 1]}`);
  return grams;
}

// TfidfVectorizer(stop_words="english", ngram_range=(1,2), sublinear_tf=True) fitted on [a, b]
export function textSimilarity(a, b) {
  const docs = [a, b].map(analyze);
  if (!docs[0].length && !docs[1].length) return 0;
  const tfs = docs.map((d) => { const m = new Map(); d.forEach((t) => m.set(t, (m.get(t) || 0) + 1)); return m; });
  const vocab = new Set([...tfs[0].keys(), ...tfs[1].keys()]);
  const n = 2;
  const vecs = tfs.map((tf) => {
    const v = new Map();
    let norm = 0;
    for (const term of vocab) {
      const c = tf.get(term);
      if (!c) continue;
      const df = (tfs[0].has(term) ? 1 : 0) + (tfs[1].has(term) ? 1 : 0);
      const w = (1 + Math.log(c)) * (Math.log((1 + n) / (1 + df)) + 1);
      v.set(term, w);
      norm += w * w;
    }
    norm = Math.sqrt(norm) || 1;
    for (const [k, w] of v) v.set(k, w / norm);
    return v;
  });
  let dot = 0;
  for (const [k, w] of vecs[0]) if (vecs[1].has(k)) dot += w * vecs[1].get(k);
  return dot;
}

// ---------------------------------------------------------------- matcher
const PREFERRED_HEAD = /^\s*(nice[ -]to[ -]have|preferred|good to have|bonus|plus|desirable)\b.*$/im;
const MIN_YEARS_RE = /(\d{1,2})\+?\s*(?:-\s*\d+\s*)?(?:years?|yrs?)/gi;

export function parseJob(title, text) {
  const head = text.match(PREFERRED_HEAD);
  const req = head ? text.slice(0, head.index) : text;
  const pref = head ? text.slice(head.index) : "";
  const required = findSkills(req);
  const preferred = findSkills(pref).filter((s) => !required.includes(s));
  const years = [...req.matchAll(MIN_YEARS_RE)].map((m) => parseInt(m[1], 10));
  return { title, text, required_skills: required, preferred_skills: preferred,
           min_years: years.length ? Math.min(...years) : 0 };
}

// Python's round(): round-half-to-even, so both engines agree to the last digit
export function round(x, d = 0) {
  const m = x * 10 ** d;
  let r = Math.round(m);
  if (Math.abs(m - Math.trunc(m)) === 0.5) r = 2 * Math.round(m / 2);
  return r / 10 ** d;
}

export function scoreCandidate(job, profile, resumeText, w = config.weights) {
  const have = new Set(expandImplied(profile.skills));
  const matchedReq = job.required_skills.filter((s) => have.has(s));
  const missingReq = job.required_skills.filter((s) => !have.has(s));
  const matchedPref = job.preferred_skills.filter((s) => have.has(s));
  const reqCov = job.required_skills.length ? matchedReq.length / job.required_skills.length : 1;
  const prefCov = job.preferred_skills.length ? matchedPref.length / job.preferred_skills.length : 0;
  const sim = Math.min(1, textSimilarity(job.text, resumeText) / 0.5);
  const exp = job.min_years <= 0 ? 1 : Math.min(1, profile.experience_years / job.min_years);
  const prefW = job.preferred_skills.length ? w.preferred : 0;
  const totalW = w.required + prefW + w.similarity + w.experience;
  const raw = (w.required * reqCov + prefW * prefCov + w.similarity * sim + w.experience * exp) / totalW;
  const listed = new Set([...job.required_skills, ...job.preferred_skills]);
  return {
    score: round(100 * raw, 1),
    components: { required_skills: round(reqCov, 3), preferred_skills: round(prefCov, 3),
                  text_similarity: round(sim, 3), experience_fit: round(exp, 3) },
    matched_required: matchedReq, missing_required: missingReq, matched_preferred: matchedPref,
    extra_skills: profile.skills.filter((s) => !listed.has(s)).sort(cmp),
  };
}

export function priorityFor(score, t = config.thresholds) {
  return score >= t.high ? "High" : score >= t.medium ? "Medium" : "Low";
}

export function screenText(job, rawText, filename) {
  const started = (globalThis.performance || Date).now();
  const text = cleanText(rawText);
  const profile = extractProfile(text);
  const match = scoreCandidate(job, profile, text);
  return {
    filename, name: profile.name || filename.replace(/\.[^.]+$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    email: profile.email, phone: profile.phone, links: profile.links, education: profile.education,
    experience_years: profile.experience_years, skills: profile.skills, skills_by_category: profile.skills_by_category,
    score: match.score, priority: priorityFor(match.score), components: match.components,
    matched_required: match.matched_required, missing_required: match.missing_required,
    matched_preferred: match.matched_preferred, extra_skills: match.extra_skills,
    processing_ms: round((globalThis.performance || Date).now() - started, 1),
  };
}

export const thresholds = config.thresholds;
