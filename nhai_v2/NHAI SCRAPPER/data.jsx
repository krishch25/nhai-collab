// Live data only — no mock fallback.
// All tender data is loaded from /api/tenders and /api/tenders/:id

window.TENDERS = [];
window.TENDER_CACHE = {};

async function loadLiveTenders() {
  try {
    const r = await fetch("/api/tenders");
    if (!r.ok) return;
    const data = await r.json();
    window.TENDERS = data || [];
    window.dispatchEvent(new CustomEvent("tendersLoaded", { detail: window.TENDERS }));
  } catch(e) {
    console.warn("Tender API unavailable:", e.message);
    window.dispatchEvent(new CustomEvent("tendersLoaded", { detail: [] }));
  }
}

async function loadTenderDetail(id) {
  if (window.TENDER_CACHE[id]) return window.TENDER_CACHE[id];
  try {
    const r = await fetch(`/api/tenders/${id}`);
    if (!r.ok) return null;
    const data = await r.json();
    window.TENDER_CACHE[id] = data;
    return data;
  } catch(e) {
    return null;
  }
}

loadLiveTenders();
