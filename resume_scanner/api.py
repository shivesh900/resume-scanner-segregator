"""Flask REST API for the recruiter dashboard.

Run:  python -m resume_scanner.api   (serves the API and, if built, the React app)
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from . import __version__
from .matcher import parse_job
from .parser import SUPPORTED_EXTENSIONS, UnsupportedFileError
from .pipeline import screen_resume
from .segregator import Thresholds
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "sample_data"
FRONTEND_DIST = ROOT / "frontend" / "dist"
MAX_UPLOAD_MB = 10


def create_app(db_path: str | None = None, thresholds: Thresholds = Thresholds()) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024 * 5
    store = Store(db_path or os.environ.get("RSS_DB", ":memory:"))
    app.config["store"] = store

    @app.after_request
    def cors(resp):  # the Vite dev server runs on another port
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PATCH,DELETE,OPTIONS"
        return resp

    def err(msg, code=400):
        return jsonify({"error": msg}), code

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "version": __version__,
                        "thresholds": {"high": thresholds.high, "medium": thresholds.medium}})

    @app.get("/api/jobs")
    def list_jobs():
        return jsonify(store.list_jobs())

    @app.post("/api/jobs")
    def create_job():
        body = request.get_json(silent=True) or {}
        title, description = (body.get("title") or "").strip(), (body.get("description") or "").strip()
        if not title or not description:
            return err("title and description are required")
        profile = parse_job(title, description).to_dict()
        profile.pop("text", None)
        job = store.add_job(title, description, profile)
        return jsonify(store.get_job(job["id"])), 201

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id):
        job = store.get_job(job_id)
        return jsonify(job) if job else err("job not found", 404)

    @app.delete("/api/jobs/<job_id>")
    def delete_job(job_id):
        return ("", 204) if store.delete_job(job_id) else err("job not found", 404)

    @app.post("/api/jobs/<job_id>/resumes")
    def upload_resumes(job_id):
        job = store.get_job(job_id)
        if not job:
            return err("job not found", 404)
        files = request.files.getlist("files")
        if not files:
            return err("attach one or more resumes as multipart field 'files'")
        jp = parse_job(job["title"], job["description"])
        created, failed = [], []
        for f in files:
            name = Path(f.filename or "resume").name
            if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
                failed.append({"filename": name, "error": "unsupported file type"})
                continue
            try:
                result = screen_resume(jp, f.read(), name, thresholds=thresholds)
            except UnsupportedFileError as e:
                failed.append({"filename": name, "error": str(e)})
                continue
            except Exception as e:  # corrupt PDF etc.
                failed.append({"filename": name, "error": f"could not parse: {e.__class__.__name__}"})
                continue
            created.append(store.add_candidate(job_id, result))
        return jsonify({"screened": created, "failed": failed}), 201

    @app.get("/api/jobs/<job_id>/candidates")
    def list_candidates(job_id):
        if not store.get_job(job_id):
            return err("job not found", 404)
        priority = request.args.get("priority")
        return jsonify(store.list_candidates(job_id, priority))

    @app.get("/api/candidates/<cid>")
    def get_candidate(cid):
        c = store.get_candidate(cid)
        return jsonify(c) if c else err("candidate not found", 404)

    @app.patch("/api/candidates/<cid>")
    def update_candidate(cid):
        if not store.get_candidate(cid):
            return err("candidate not found", 404)
        try:
            return jsonify(store.set_status(cid, (request.get_json(silent=True) or {}).get("status", "")))
        except ValueError as e:
            return err(str(e))

    @app.get("/api/jobs/<job_id>/export.csv")
    def export_csv(job_id):
        job = store.get_job(job_id)
        if not job:
            return err("job not found", 404)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["rank", "name", "email", "phone", "score", "priority", "status",
                    "experience_years", "education", "matched_required", "missing_required", "filename"])
        for i, c in enumerate(store.list_candidates(job_id), 1):
            w.writerow([i, c["name"], c["email"], c["phone"], c["score"], c["priority"], c["status"],
                        c["experience_years"], c["education"], "; ".join(c["matched_required"]),
                        "; ".join(c["missing_required"]), c["filename"]])
        fname = "".join(ch if ch.isalnum() else "_" for ch in job["title"]).strip("_").lower()
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={fname}_shortlist.csv"})

    @app.post("/api/demo")
    def load_demo():
        """Create the sample job and screen all bundled synthetic resumes."""
        jd_path = SAMPLE_DIR / "job_descriptions" / "ml_engineer.txt"
        lines = jd_path.read_text().splitlines()
        title, description = lines[0].strip(), "\n".join(lines[1:]).strip()
        profile = parse_job(title, description).to_dict()
        profile.pop("text", None)
        job = store.add_job(title, description, profile)
        jp = parse_job(title, description)
        for p in sorted((SAMPLE_DIR / "resumes").iterdir()):
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                store.add_candidate(job["id"], screen_resume(jp, p, p.name, thresholds=thresholds))
        return jsonify(store.get_job(job["id"])), 201

    # React dashboard (production build) --------------------------------------
    @app.get("/")
    @app.get("/<path:path>")
    def spa(path="index.html"):
        if path.startswith("api/"):
            return err("not found", 404)
        if not FRONTEND_DIST.exists():
            return ("<h3>Resume Scanner Segregator API is running.</h3>"
                    "<p>Build the dashboard with <code>cd frontend && npm install && npm run build</code>, "
                    "or run <code>npm run dev</code> for the dev server.</p>"), 200
        target = FRONTEND_DIST / path
        if target.is_file():
            return send_from_directory(FRONTEND_DIST, path)
        return send_from_directory(FRONTEND_DIST, "index.html")

    return app


def main():
    port = int(os.environ.get("PORT", 5000))
    create_app().run(host="0.0.0.0", port=port, debug=bool(os.environ.get("FLASK_DEBUG")))


if __name__ == "__main__":
    main()
