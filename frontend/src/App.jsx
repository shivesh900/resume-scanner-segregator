import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api.js";

const PRIORITIES = ["High", "Medium", "Low"];
const COMPONENT_LABELS = {
  required_skills: "Required skills",
  preferred_skills: "Nice-to-have skills",
  text_similarity: "JD text similarity",
  experience_fit: "Experience fit",
};

function ScoreRing({ score, size = 52 }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const tone = score >= 70 ? "var(--high)" : score >= 45 ? "var(--medium)" : "var(--low)";
  return (
    <svg width={size} height={size} className="ring">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--track)" strokeWidth="6" fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={tone} strokeWidth="6" fill="none"
        strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} />
      <text x="50%" y="54%" textAnchor="middle" dominantBaseline="middle" fontSize={size / 3.6} fontWeight="700">
        {Math.round(score)}
      </text>
    </svg>
  );
}

const Chip = ({ children, tone = "" }) => <span className={`chip ${tone}`}>{children}</span>;

function NewJob({ onCreated, onCancel }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try { onCreated(await api.createJob(title, description)); } catch (err) { setError(err.message); }
  };
  return (
    <form className="card newjob" onSubmit={submit}>
      <h3>New job opening</h3>
      <input placeholder="Job title, e.g. ML Engineer" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea rows={9} value={description} onChange={(e) => setDescription(e.target.value)}
        placeholder={"Paste the job description.\nTip: put optional skills under a 'Nice to have' heading."} />
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button type="submit" className="primary" disabled={!title || !description}>Create</button>
        <button type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function Dropzone({ onFiles, busy }) {
  const input = useRef(null);
  const [over, setOver] = useState(false);
  return (
    <div className={`dropzone ${over ? "over" : ""}`}
      onClick={() => input.current.click()}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); onFiles(e.dataTransfer.files); }}>
      <input ref={input} type="file" multiple accept=".pdf,.docx,.txt" hidden
        onChange={(e) => { onFiles(e.target.files); e.target.value = ""; }} />
      <strong>{busy ? "Screening resumes…" : "Drop resumes here or click to upload"}</strong>
      <span>PDF, DOCX or TXT · multiple files at once</span>
    </div>
  );
}

function CandidateCard({ c, onOpen }) {
  return (
    <button className={`candidate ${c.status}`} onClick={() => onOpen(c)}>
      <ScoreRing score={c.score} />
      <div className="cinfo">
        <div className="cname">{c.name}{c.status !== "new" && <span className={`status ${c.status}`}>{c.status}</span>}</div>
        <div className="cmeta">{c.experience_years} yrs · {c.education || "Education n/a"}</div>
        <div className="chips">
          {c.matched_required.slice(0, 4).map((s) => <Chip key={s} tone="ok">{s}</Chip>)}
          {c.missing_required.slice(0, 2).map((s) => <Chip key={s} tone="miss">{s}</Chip>)}
        </div>
      </div>
    </button>
  );
}

function Drawer({ c, onClose, onStatus }) {
  if (!c) return null;
  return (
    <div className="overlay" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose} aria-label="Close">×</button>
        <div className="dhead">
          <ScoreRing score={c.score} size={72} />
          <div>
            <h2>{c.name}</h2>
            <span className={`badge ${c.priority}`}>{c.priority} priority</span>
          </div>
        </div>
        <dl className="contact">
          <dt>Email</dt><dd>{c.email || "—"}</dd>
          <dt>Phone</dt><dd>{c.phone || "—"}</dd>
          <dt>Links</dt><dd>{c.links.join(", ") || "—"}</dd>
          <dt>Experience</dt><dd>{c.experience_years} years</dd>
          <dt>Education</dt><dd>{c.education || "—"}</dd>
          <dt>File</dt><dd>{c.filename}</dd>
        </dl>
        <h4>Why this score</h4>
        {Object.keys(COMPONENT_LABELS).map((k) => [k, c.components[k] ?? 0]).map(([k, v]) => (
          <div className="bar" key={k}>
            <span>{COMPONENT_LABELS[k]}</span>
            <div className="track"><div style={{ width: `${v * 100}%` }} /></div>
            <b>{Math.round(v * 100)}%</b>
          </div>
        ))}
        <h4>Matched required skills</h4>
        <div className="chips">{c.matched_required.map((s) => <Chip key={s} tone="ok">{s}</Chip>)}{!c.matched_required.length && "—"}</div>
        <h4>Missing required skills</h4>
        <div className="chips">{c.missing_required.map((s) => <Chip key={s} tone="miss">{s}</Chip>)}{!c.missing_required.length && "None 🎉"}</div>
        <h4>Nice-to-have matched</h4>
        <div className="chips">{c.matched_preferred.map((s) => <Chip key={s} tone="pref">{s}</Chip>)}{!c.matched_preferred.length && "—"}</div>
        <h4>Other skills</h4>
        <div className="chips">{c.extra_skills.map((s) => <Chip key={s}>{s}</Chip>)}{!c.extra_skills.length && "—"}</div>
        <div className="actions">
          <button className="primary" onClick={() => onStatus(c, "shortlisted")}>Shortlist</button>
          <button className="danger" onClick={() => onStatus(c, "rejected")}>Reject</button>
          {c.status !== "new" && <button onClick={() => onStatus(c, "new")}>Reset</button>}
        </div>
        <p className="muted small">Screened in {c.processing_ms} ms</p>
      </aside>
    </div>
  );
}

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [jobId, setJobId] = useState(null);
  const [candidates, setCandidates] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(null);
  const [online, setOnline] = useState(null);

  const job = jobs.find((j) => j.id === jobId);

  const refreshJobs = async (selectId) => {
    const list = await api.jobs();
    setJobs(list);
    if (selectId) setJobId(selectId);
    else if (!jobId && list.length) setJobId(list[0].id);
  };

  useEffect(() => {
    api.health().then(() => setOnline(true)).catch(() => setOnline(false));
    refreshJobs().catch(() => {});
  }, []);

  useEffect(() => {
    if (jobId) api.candidates(jobId).then(setCandidates).catch((e) => setNotice(e.message));
    else setCandidates([]);
  }, [jobId]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter((c) =>
      [c.name, c.email, ...c.skills].filter(Boolean).some((v) => v.toLowerCase().includes(q)));
  }, [candidates, query]);

  const stats = useMemo(() => {
    const n = candidates.length;
    const avg = n ? candidates.reduce((s, c) => s + c.score, 0) / n : 0;
    const by = Object.fromEntries(PRIORITIES.map((p) => [p, candidates.filter((c) => c.priority === p).length]));
    return { n, avg, by, shortlisted: candidates.filter((c) => c.status === "shortlisted").length };
  }, [candidates]);

  const loadDemo = async () => {
    setBusy(true);
    try { const j = await api.demo(); await refreshJobs(j.id); setNotice("Loaded the demo job with 12 synthetic resumes."); }
    catch (e) { setNotice(e.message); } finally { setBusy(false); }
  };

  const upload = async (files) => {
    if (!jobId || !files.length) return;
    setBusy(true);
    try {
      const r = await api.upload(jobId, files);
      setNotice(`Screened ${r.screened.length} resume(s)` + (r.failed.length ? `, ${r.failed.length} skipped (${r.failed.map((f) => f.filename).join(", ")})` : "."));
      setCandidates(await api.candidates(jobId));
      refreshJobs(jobId);
    } catch (e) { setNotice(e.message); } finally { setBusy(false); }
  };

  const setStatus = async (c, status) => {
    const updated = await api.setStatus(c.id, status);
    setCandidates((cs) => cs.map((x) => (x.id === c.id ? updated : x)));
    setOpen(updated);
  };

  const removeJob = async () => {
    if (!job || !confirm(`Delete "${job.title}" and its candidates?`)) return;
    await api.deleteJob(job.id);
    setJobId(null);
    refreshJobs();
  };

  return (
    <div className="app">
      <header>
        <div className="brand"><span className="logo">RS</span><div><h1>Resume Scanner Segregator</h1><p>AI-assisted resume parsing & candidate shortlisting</p></div></div>
        <div className="row">
          <span className={`dot ${online ? "on" : online === false ? "off" : ""}`}>{online ? "API online" : online === false ? "API offline" : "…"}</span>
          <button onClick={loadDemo} disabled={busy}>Load demo data</button>
          <button className="primary" onClick={() => setShowNew(true)}>+ New job</button>
        </div>
      </header>

      <div className="layout">
        <nav className="jobs">
          <h3>Job openings</h3>
          {!jobs.length && <p className="muted">No jobs yet. Create one or load the demo.</p>}
          {jobs.map((j) => (
            <button key={j.id} className={`job ${j.id === jobId ? "active" : ""}`} onClick={() => setJobId(j.id)}>
              <span>{j.title}</span>
              <small><b className="h">{j.counts.High}</b> · <b className="m">{j.counts.Medium}</b> · <b className="l">{j.counts.Low}</b></small>
            </button>
          ))}
        </nav>

        <main>
          {showNew && <NewJob onCancel={() => setShowNew(false)} onCreated={(j) => { setShowNew(false); refreshJobs(j.id); }} />}
          {notice && <div className="notice" onClick={() => setNotice("")}>{notice}</div>}
          {!job && !showNew && (
            <div className="empty card">
              <h2>Screen resumes in seconds</h2>
              <p>Create a job opening, drop in PDF/DOCX resumes, and candidates are parsed, scored against the job description and sorted into High, Medium and Low priority.</p>
              <button className="primary" onClick={loadDemo} disabled={busy}>Try it with demo data</button>
            </div>
          )}
          {job && (
            <>
              <section className="card jobhead">
                <div className="row spread">
                  <h2>{job.title}</h2>
                  <div className="row">
                    <a className="button" href={api.exportUrl(job.id)}>Export CSV</a>
                    <button className="ghost" onClick={removeJob}>Delete</button>
                  </div>
                </div>
                <div className="reqs">
                  <span className="muted">Required</span>
                  {job.profile.required_skills.map((s) => <Chip key={s} tone="req">{s}</Chip>)}
                </div>
                {!!job.profile.preferred_skills.length && (
                  <div className="reqs"><span className="muted">Nice to have</span>
                    {job.profile.preferred_skills.map((s) => <Chip key={s} tone="pref">{s}</Chip>)}</div>
                )}
                {job.profile.min_years > 0 && <p className="muted small">Minimum experience: {job.profile.min_years} {job.profile.min_years === 1 ? "year" : "years"}</p>}
              </section>

              <Dropzone onFiles={upload} busy={busy} />

              <section className="stats">
                <div className="stat"><b>{stats.n}</b><span>Screened</span></div>
                <div className="stat high"><b>{stats.by.High}</b><span>High priority</span></div>
                <div className="stat medium"><b>{stats.by.Medium}</b><span>Medium priority</span></div>
                <div className="stat low"><b>{stats.by.Low}</b><span>Low priority</span></div>
                <div className="stat"><b>{stats.avg.toFixed(1)}</b><span>Avg score</span></div>
                <div className="stat"><b>{stats.shortlisted}</b><span>Shortlisted</span></div>
              </section>

              <input className="search" placeholder="Search by name, email or skill…" value={query} onChange={(e) => setQuery(e.target.value)} />

              <section className="board">
                {PRIORITIES.map((p) => {
                  const list = filtered.filter((c) => c.priority === p);
                  return (
                    <div className={`column ${p}`} key={p}>
                      <h3><span className={`badge ${p}`}>{p}</span> <small>{list.length}</small></h3>
                      {list.map((c) => <CandidateCard key={c.id} c={c} onOpen={setOpen} />)}
                      {!list.length && <p className="muted small">No candidates</p>}
                    </div>
                  );
                })}
              </section>
            </>
          )}
        </main>
      </div>
      <Drawer c={open} onClose={() => setOpen(null)} onStatus={setStatus} />
    </div>
  );
}
