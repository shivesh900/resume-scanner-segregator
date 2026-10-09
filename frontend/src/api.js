import { localApi } from "./engine/localApi.js";

const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).error || msg; } catch { /* not json */ }
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

const json = (method, body) => ({
  method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

const remoteApi = {
  mode: "server",
  health: () => request("/api/health"),
  jobs: () => request("/api/jobs"),
  createJob: (title, description) => request("/api/jobs", json("POST", { title, description })),
  deleteJob: (id) => request(`/api/jobs/${id}`, { method: "DELETE" }),
  candidates: (jobId) => request(`/api/jobs/${jobId}/candidates`),
  upload: (jobId, files) => {
    const fd = new FormData();
    [...files].forEach((f) => fd.append("files", f));
    return request(`/api/jobs/${jobId}/resumes`, { method: "POST", body: fd });
  },
  setStatus: (id, status) => request(`/api/candidates/${id}`, json("PATCH", { status })),
  demo: () => request("/api/demo", { method: "POST" }),
  exportUrl: (jobId) => `${BASE}/api/jobs/${jobId}/export.csv`,
};

// VITE_STATIC=1 (the GitHub Pages build) runs the whole pipeline in the browser.
export const api = import.meta.env.VITE_STATIC === "1" ? localApi : remoteApi;
