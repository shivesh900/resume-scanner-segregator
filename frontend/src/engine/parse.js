// In-browser text extraction: pdf.js for PDF, mammoth for DOCX.
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import mammoth from "mammoth/mammoth.browser.js";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

async function pdfText(buf) {
  const doc = await pdfjs.getDocument({ data: buf }).promise;
  const pages = [];
  for (let i = 1; i <= doc.numPages; i++) {
    const content = await (await doc.getPage(i)).getTextContent();
    let line = "";
    const lines = [];
    for (const item of content.items) {
      line += item.str;
      if (item.hasEOL) { lines.push(line); line = ""; }
    }
    if (line) lines.push(line);
    pages.push(lines.join("\n"));
  }
  return pages.join("\n");
}

export async function extractText(file) {
  const name = file.name.toLowerCase();
  const buf = await file.arrayBuffer();
  if (name.endsWith(".pdf")) return pdfText(buf);
  if (name.endsWith(".docx")) return (await mammoth.extractRawText({ arrayBuffer: buf })).value;
  if (name.endsWith(".txt")) return new TextDecoder().decode(buf);
  throw new Error("Unsupported file type. Use PDF, DOCX or TXT.");
}
