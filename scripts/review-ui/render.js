#!/usr/bin/env node
/**
 * Sentinel Review UI Renderer
 *
 * Usage: node render.js <input.json> <output.html>
 *
 * Reads a Sentinel review/scan JSON file and generates a fully self-contained
 * HTML file that works offline. On first run, downloads diff2html from CDN
 * and caches it in the vendor/ directory. Subsequent runs use the cached copy.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const https = require("https");

const [, , inputJson, outputHtml] = process.argv;

if (!inputJson || !outputHtml) {
  console.error("Usage: node render.js <input.json> <output.html>");
  process.exit(1);
}

// ── Paths ──────────────────────────────────────────────────────────────────

const VENDOR_DIR = path.join(__dirname, "vendor");
const TEMPLATE_PATH = path.join(__dirname, "template.html");

const VENDOR_CSS_PATH = path.join(VENDOR_DIR, "diff2html.min.css");
const VENDOR_JS_PATH = path.join(VENDOR_DIR, "diff2html-ui.min.js");

const CDN_CSS = "https://cdn.jsdelivr.net/npm/diff2html/bundles/css/diff2html.min.css";
const CDN_JS = "https://cdn.jsdelivr.net/npm/diff2html/bundles/js/diff2html-ui.min.js";

// ── Main ───────────────────────────────────────────────────────────────────

async function main() {
  // Read and validate input JSON
  let review;
  try {
    const raw = fs.readFileSync(inputJson, "utf8");
    review = JSON.parse(raw);
  } catch (err) {
    console.error(`Error reading input JSON: ${err.message}`);
    process.exit(1);
  }

  // Read template
  let template;
  try {
    template = fs.readFileSync(TEMPLATE_PATH, "utf8");
  } catch (err) {
    console.error(`Error reading template.html: ${err.message}`);
    process.exit(1);
  }

  // Get vendor files (from cache or CDN)
  const { css, js } = await getVendorFiles();

  // Build the final HTML
  let html = template;

  // ── Safe injection helper ────────────────────────────────────────────────
  // String.replace(pattern, string) interprets $' $` $& as special sequences.
  // Using a function replacement avoids all backreference expansion, and we
  // also escape any literal </script> / </style> the minified bundles may contain.
  const safeInjectJs  = (src) => src.replace(/<\/script>/gi, "<\\/script>");
  const safeInjectCss = (src) => src.replace(/<\/style>/gi,  "<\\/style>");

  // Inject vendor CSS
  if (css) {
    const safeCss = safeInjectCss(css);
    html = html.replace("/* INJECT_VENDOR_CSS */", () => safeCss);
  } else {
    html = html.replace(
      "/* INJECT_VENDOR_CSS */",
      () => `/* CDN fallback — open with internet connection for diffs */`
    );
    html = html.replace(
      '<link rel="stylesheet" id="diff2html-css-placeholder">',
      () => `<link rel="stylesheet" href="${CDN_CSS}">`
    );
  }

  // Inject vendor JS
  if (js) {
    const safeJs = safeInjectJs(js);
    html = html.replace("/* INJECT_VENDOR_JS */", () => safeJs);
  } else {
    html = html.replace("/* INJECT_VENDOR_JS */", () => `/* CDN fallback */`);
    html = html.replace(
      '<script id="diff2html-js-placeholder"></script>',
      () => `<script src="${CDN_JS}"></script>`
    );
  }

  // Inject review data
  const dataScript = `window.__REVIEW_DATA__ = ${JSON.stringify(review, null, 2)};`;
  html = html.replace("/* INJECT_DATA */", () => dataScript);

  // Write output HTML
  try {
    fs.writeFileSync(outputHtml, html, "utf8");
    console.log(`Generated: ${outputHtml}`);
  } catch (err) {
    console.error(`Error writing output HTML: ${err.message}`);
    process.exit(1);
  }
}

// ── Vendor file management ─────────────────────────────────────────────────

async function getVendorFiles() {
  // Try to use cached vendor files first
  const cssExists = fs.existsSync(VENDOR_CSS_PATH);
  const jsExists = fs.existsSync(VENDOR_JS_PATH);

  if (cssExists && jsExists) {
    return {
      css: fs.readFileSync(VENDOR_CSS_PATH, "utf8"),
      js: fs.readFileSync(VENDOR_JS_PATH, "utf8"),
    };
  }

  // Try to download from CDN
  console.log("Downloading diff2html for offline use (one-time setup)...");

  try {
    fs.mkdirSync(VENDOR_DIR, { recursive: true });

    const [css, js] = await Promise.all([
      download(CDN_CSS),
      download(CDN_JS),
    ]);

    // Save to vendor cache
    fs.writeFileSync(VENDOR_CSS_PATH, css, "utf8");
    fs.writeFileSync(VENDOR_JS_PATH, js, "utf8");
    console.log("diff2html cached to vendor/ — future renders work offline.");

    return { css, js };
  } catch (err) {
    console.warn(`Warning: Could not download diff2html (${err.message}). Diffs will require internet.`);
    return { css: null, js: null };
  }
}

function download(url) {
  return new Promise((resolve, reject) => {
    const handleResponse = (res) => {
      // Follow redirects
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return https.get(res.headers.location, handleResponse).on("error", reject);
      }

      if (res.statusCode !== 200) {
        return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
      }

      const chunks = [];
      res.on("data", (chunk) => chunks.push(chunk));
      res.on("end", () => resolve(Buffer.concat(chunks).toString("utf8")));
      res.on("error", reject);
    };

    https.get(url, handleResponse).on("error", reject);
  });
}

// ── Run ────────────────────────────────────────────────────────────────────

main().catch((err) => {
  console.error(`Fatal error: ${err.message}`);
  process.exit(1);
});
