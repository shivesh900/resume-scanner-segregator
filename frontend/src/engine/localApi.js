// Browser-only implementation of the Flask REST API, used for the GitHub Pages demo.
// Same request/response shapes as resume_scanner/api.py; data lives in localStorage.
import { parseJob, screenText, thresholds } from "./core.js";
import { extractText } from "./parse.js";

const KEY = "rss-demo-v1";
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || { jobs: [], candidates: [] }; } catch { return { jobs: [], candidates: [] }; } };
let db = load();
const save = () => localStorage.setItem(KEY, JSON.stringify(db));
const id = () => Math.random().toString(16).slice(2, 14);
const now = () => new Date().toISOString().slice(0, 19) + "+00:00";

const withCounts = (job) => {
  const counts = { High: 0, Medium: 0, Low: 0 };
  db.candidates.filter((c) => c.job_id === job.id).forEach((c) => counts[c.priority]++);
  return { ...job, counts };
};

function createJob(title, description) {
  if (!title?.trim() || !description?.trim()) throw new Error("title and description are required");
  const { text, ...profile } = parseJob(title.trim(), description.trim());
  const job = { id: id(), title: title.trim(), description: description.trim(), profile, created_at: now() };
  db.jobs.unshift(job);
  save();
  return withCounts(job);
}

async function screenFiles(jobId, files) {
  const job = db.jobs.find((j) => j.id === jobId);
  if (!job) throw new Error("job not found");
  const jp = parseJob(job.title, job.description);
  const screened = [], failed = [];
  for (const f of files) {
    try {
      const text = await extractText(f);
      const c = { ...screenText(jp, text, f.name), id: id(), job_id: jobId, status: "new", created_at: now() };
      db.candidates.push(c);
      screened.push(c);
    } catch (e) {
      failed.push({ filename: f.name, error: e.message || "could not parse" });
    }
  }
  save();
  return { screened, failed };
}

const base = import.meta.env.BASE_URL;

export const localApi = {
  mode: "browser",
  health: async () => ({ status: "ok", version: "1.0.0", mode: "browser", thresholds }),
  jobs: async () => db.jobs.map(withCounts),
  createJob: async (t, d) => createJob(t, d),
  deleteJob: async (jobId) => { db.jobs = db.jobs.filter((j) => j.id !== jobId); db.candidates = db.candidates.filter((c) => c.job_id !== jobId); save(); return null; },
  candidates: async (jobId) => db.candidates.filter((c) => c.job_id === jobId).sort((a, b) => b.score - a.score),
  upload: (jobId, files) => screenFiles(jobId, [...files]),
  setStatus: async (cid, status) => {
    if (!["new", "shortlisted", "rejected"].includes(status)) throw new Error("bad status");
    const c = db.candidates.find((x) => x.id === cid);
    c.status = status; save(); return { ...c };
  },
  demo: async () => {
    const jd = (await (await fetch(`${base}samples/ml_engineer.txt`)).text()).split("\n");
    const job = createJob(jd[0].trim(), jd.slice(1).join("\n").trim());
    const names = await (await fetch(`${base}samples/index.json`)).json();
    const files = await Promise.all(names.map(async (n) => new File([await (await fetch(`${base}samples/${n}`)).blob()], n)));
    await screenFiles(job.id, files);
    return withCounts(db.jobs.find((j) => j.id === job.id));
  },
  exportCsv: (jobId) => {
    const job = db.jobs.find((j) => j.id === jobId);
    const rows = [["rank", "name", "email", "phone", "score", "priority", "status", "experience_years", "education", "matched_required", "missing_required", "filename"]];
    db.candidates.filter((c) => c.job_id === jobId).sort((a, b) => b.score - a.score).forEach((c, i) =>
      rows.push([i + 1, c.name, c.email, c.phone, c.score, c.priority, c.status, c.experience_years, c.education,
                 c.matched_required.join("; "), c.missing_required.join("; "), c.filename]));
    const csv = rows.map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = `${job.title.replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_shortlist.csv`;
    a.click();
  },
};
