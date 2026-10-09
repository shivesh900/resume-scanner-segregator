"""Check that the browser engine (frontend/src/engine/core.js) matches the Python engine.

Both engines get the same extracted resume text. Their scores, priorities,
skills and experience must agree. Requires Node 20+.

Run:  python scripts/check_web_parity.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from resume_scanner.matcher import parse_job  # noqa: E402
from resume_scanner.parser import extract_text  # noqa: E402
from resume_scanner.pipeline import screen_resume  # noqa: E402

NODE = """
import { readFileSync } from "node:fs";
import { parseJob, screenText } from "./frontend/src/engine/core.js";
const inp = JSON.parse(readFileSync(process.argv[2], "utf8"));
const job = parseJob(inp.title, inp.jd);
const out = inp.resumes.map((r) => screenText(job, r.text, r.filename));
console.log(JSON.stringify({ job, out }));
"""


def main():
    lines = (ROOT / "sample_data" / "job_descriptions" / "ml_engineer.txt").read_text().splitlines()
    title, jd = lines[0].strip(), "\n".join(lines[1:])
    job = parse_job(title, jd)
    files = sorted((ROOT / "sample_data" / "resumes").iterdir())
    resumes = [{"filename": p.name, "text": extract_text(p)} for p in files]
    py = {r["filename"]: screen_resume(job, p, p.name) for r, p in zip(resumes, files)}
    with tempfile.TemporaryDirectory() as td:
        inp = Path(td) / "in.json"
        inp.write_text(json.dumps({"title": title, "jd": jd, "resumes": resumes}))
        script = ROOT / "_parity.mjs"
        script.write_text(NODE)
        try:
            res = subprocess.run(["node", str(script), str(inp)], cwd=ROOT, capture_output=True, text=True, check=True)
        finally:
            script.unlink()
    js = json.loads(res.stdout)
    assert js["job"]["required_skills"] == job.required_skills, (js["job"]["required_skills"], job.required_skills)
    assert js["job"]["preferred_skills"] == job.preferred_skills
    bad = 0
    for c in js["out"]:
        p = py[c["filename"]]
        same = (abs(c["score"] - p["score"]) <= 0.1 and c["priority"] == p["priority"] and c["skills"] == p["skills"]
                and c["experience_years"] == p["experience_years"] and c["education"] == p["education"]
                and c["name"] == p["name"] and c["email"] == p["email"])
        bad += not same
        print(f"{'OK ' if same else 'DIFF'} {c['filename']:<22} py {p['score']:>5} {p['priority']:<6} | js {c['score']:>5} {c['priority']:<6}")
        if not same:
            for k in ("score", "skills", "experience_years", "education", "name", "email", "phone"):
                if c[k] != p[k]:
                    print(f"      {k}: py={p[k]!r} js={c[k]!r}")
    print(f"\n{len(js['out']) - bad}/{len(js['out'])} resumes identical between Python and the browser engine")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
