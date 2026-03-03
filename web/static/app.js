const form = document.getElementById("fetch-form");
const urlInput = document.getElementById("target-url");
const sendBtn = document.getElementById("send-btn");
const statusPill = document.getElementById("status-pill");
const upstreamPill = document.getElementById("upstream-pill");
const contentTypePill = document.getElementById("ctype-pill");
const htmlView = document.getElementById("html-view");

function setStatus(text, kind) {
  statusPill.textContent = text;
  statusPill.classList.remove("ok", "err", "idle");
  statusPill.classList.add(kind);
}

function prettyText(raw) {
  try {
    const parsed = JSON.parse(raw);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}

function escapeHtml(text) {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderPreview(body, contentType) {
  if (!htmlView) return;

  if ((contentType || "").toLowerCase().includes("text/html")) {
    htmlView.srcdoc = body;
    return;
  }

  htmlView.srcdoc =
    "<!doctype html><html><body style='font-family:monospace;padding:12px;white-space:pre-wrap'>" +
    escapeHtml(body) +
    "</body></html>";
}

async function runFetch(url) {
  sendBtn.disabled = true;
  sendBtn.textContent = "Fetching...";
  setStatus("working", "idle");
  upstreamPill.textContent = "upstream: resolving";
  contentTypePill.textContent = "content-type: -";
  renderPreview("Running backend request...", "text/plain");

  try {
    const res = await fetch("/api/webview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });

    const text = await res.text();
    const upstream = res.headers.get("X-Upstream-IP") || "unknown";
    const contentType = res.headers.get("Content-Type") || "unknown";
    upstreamPill.textContent = `upstream: ${upstream}`;
    contentTypePill.textContent = `content-type: ${contentType}`;
    renderPreview(prettyText(text), contentType);

    if (res.status === 401) {
      renderPreview("Session expired. Reload and login again.", "text/plain");
      setStatus("401 unauthorized", "err");
      return;
    }

    if (res.ok) {
      setStatus(`${res.status} ok`, "ok");
    } else {
      setStatus(`${res.status} error`, "err");
    }
  } catch (err) {
    upstreamPill.textContent = "upstream: unavailable";
    contentTypePill.textContent = "content-type: -";
    renderPreview(`Request failed: ${err}`, "text/plain");
    setStatus("client error", "err");
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Fetch";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const url = urlInput.value.trim();
  if (!url) {
    return;
  }
  await runFetch(url);
});
