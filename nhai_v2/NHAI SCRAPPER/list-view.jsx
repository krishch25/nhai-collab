/* global React, Icons, StatusTag, TypeTag, ConfTag, Spark, fmtINR, fmtINRPlain, daysUntil, fmtDate */
const { useState: useStateL, useEffect: useEffectL, useMemo } = React;

function ListView({ tweaks, onOpen, tenderCount }) {
  const [density, setDensity] = useStateL(tweaks.density || "normal");
  const [view, setView] = useStateL("table");
  const [query, setQuery] = useStateL("");
  const [showClosed, setShowClosed] = useStateL(false);
  const [typeFilter, setTypeFilter] = useStateL(null);
  const [stateFilter, setStateFilter] = useStateL(null);
  const [sortBy, setSortBy] = useStateL("deadline");
  const [tenders, setTenders] = useStateL(window.TENDERS || []);
  const [analyzingId, setAnalyzingId] = useStateL(null);
  const [analyzeMsg, setAnalyzeMsg] = useStateL(null);
  const [fetching, setFetching] = useStateL(false);

  // Update when live data arrives
  useEffectL(() => {
    const handler = (e) => setTenders(e.detail || []);
    window.addEventListener("tendersLoaded", handler);
    return () => window.removeEventListener("tendersLoaded", handler);
  }, []);

  // Split tenders by status
  const activeTenders = useMemo(() => tenders.filter(t => t.status === "active"), [tenders]);
  const closedTenders = useMemo(() => tenders.filter(t => t.status !== "active"), [tenders]);

  const applyFilters = (list) => {
    let r = list.filter(t => {
      if (typeFilter && t.type !== typeFilter) return false;
      if (stateFilter && t.state !== stateFilter) return false;
      if (query) {
        const q = query.toLowerCase();
        return (
          t.title.toLowerCase().includes(q) ||
          t.no.toLowerCase().includes(q) ||
          t.id.includes(q) ||
          t.nh.toLowerCase().includes(q) ||
          t.state.toLowerCase().includes(q)
        );
      }
      return true;
    });
    if (sortBy === "deadline") r.sort((a,b) => new Date(a.deadline) - new Date(b.deadline));
    if (sortBy === "value") r.sort((a,b) => b.estValue - a.estValue);
    if (sortBy === "match") r.sort((a,b) => b.match - a.match);
    return r;
  };

  const filteredActive = useMemo(() => applyFilters(activeTenders), [activeTenders, typeFilter, stateFilter, query, sortBy]);
  const filteredClosed = useMemo(() => applyFilters(closedTenders), [closedTenders, typeFilter, stateFilter, query, sortBy]);

  // Stats (always based on active tenders)
  const urgent = activeTenders.filter(t => daysUntil(t.deadline) <= 14).length;
  const analyzed = tenders.filter(t => t.analyzed).length;

  // Trigger analysis for a single tender
  async function runAnalysis(tenderId) {
    setAnalyzingId(tenderId);
    setAnalyzeMsg(null);
    try {
      const r = await fetch(`/api/tenders/${tenderId}/analyze`, { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        setAnalyzeMsg(`✓ Analysis queued for #${tenderId}. Refresh in ~60 seconds to see results.`);
      } else {
        setAnalyzeMsg(`✗ Failed to queue analysis for #${tenderId}.`);
      }
    } catch(e) {
      setAnalyzeMsg(`✗ Error: ${e.message}`);
    }
    setAnalyzingId(null);
    setTimeout(() => setAnalyzeMsg(null), 8000);
  }

  // Fetch latest tenders from NHAI API
  async function fetchFromNHAI() {
    setFetching(true);
    setAnalyzeMsg("Fetching latest tenders from nhai.gov.in…");
    try {
      const r = await fetch("/api/fetch", { method: "POST" });
      const d = await r.json();
      if (r.ok) {
        setAnalyzeMsg(`✓ Fetched ${d.fetched} tenders (${d.new} new). Refreshing list…`);
        const r2 = await fetch("/api/tenders");
        const data = await r2.json();
        setTenders(data || []);
        window.TENDERS = data || [];
        if (d.new > 0) {
          setTimeout(() => setAnalyzeMsg(`✓ ${d.new} new tender${d.new > 1 ? "s" : ""} added. ${d.analysis_queued} queued for AI analysis.`), 500);
        } else {
          setTimeout(() => setAnalyzeMsg("✓ Tender list is up to date."), 500);
        }
      } else {
        setAnalyzeMsg("✗ Fetch failed — check server connection.");
      }
    } catch(e) {
      setAnalyzeMsg(`✗ Error: ${e.message}`);
    }
    setFetching(false);
    setTimeout(() => setAnalyzeMsg(null), 8000);
  }

  // Run analysis on all unanalyzed active tenders
  async function runAllAnalysis() {
    const unanalyzed = activeTenders.filter(t => !t.analyzed).slice(0, 5); // batch max 5
    if (unanalyzed.length === 0) {
      setAnalyzeMsg("All active tenders are already analyzed.");
      setTimeout(() => setAnalyzeMsg(null), 4000);
      return;
    }
    setAnalyzeMsg(`Queuing analysis for ${unanalyzed.length} tenders…`);
    for (const t of unanalyzed) {
      await runAnalysis(t.id);
    }
  }

  const TenderTable = ({ items, closed = false }) => (
    <table className={"tlist " + density}>
      <colgroup>
        <col style={{ width: 90 }} />
        <col style={{ width: "auto" }} />
        <col style={{ width: 96 }} />
        <col style={{ width: 110 }} />
        <col style={{ width: 110 }} />
        <col style={{ width: 140 }} />
        <col style={{ width: 90 }} />
        <col style={{ width: 110 }} />
        <col style={{ width: 60 }} />
      </colgroup>
      <thead>
        <tr>
          <th>ID</th>
          <th>Tender</th>
          <th>Type</th>
          <th>NH · Length</th>
          <th>Est. value</th>
          <th>Deadline <span className="sort">▼</span></th>
          <th>Confidence</th>
          <th>Status</th>
          <th>AI</th>
        </tr>
      </thead>
      <tbody>
        {items.map(t => {
          const d = daysUntil(t.deadline);
          const isUrgent = d <= 7 && d >= 0;
          return (
            <tr key={t.id} onClick={() => onOpen(t.id)} style={closed ? { opacity: 0.65 } : {}}>
              <td className="id">{t.id}</td>
              <td className="title-cell">
                {t.title}
                <span className="sub">
                  <span className="mono" style={{color:"var(--ink-3)"}}>{t.no}</span> · {t.state}
                </span>
              </td>
              <td><TypeTag t={t.type} /> </td>
              <td className="num">
                {t.nh}
                <div style={{fontSize:11,color:"var(--ink-4)",marginTop:3}}>{t.length} km</div>
              </td>
              <td className="num">{t.estValue > 0 ? fmtINR(t.estValue) : <span style={{color:"var(--ink-5)"}}>—</span>}</td>
              <td className={"deadline " + (isUrgent ? "urgent" : "")}>
                {fmtDate(t.deadline)}
                <span className="days">{d > 0 ? `in ${d} days` : d === 0 ? "Today" : `${-d}d ago`}</span>
              </td>
              <td><ConfTag c={t.confidence} /></td>
              <td>
                <span style={{
                  display:"inline-flex",alignItems:"center",gap:4,
                  fontSize:10.5,padding:"2px 7px",borderRadius:4,fontFamily:"var(--mono)",
                  background: t.status === "active" ? "rgba(34,197,94,0.12)" : "var(--paper-2)",
                  color: t.status === "active" ? "var(--ok)" : "var(--ink-4)",
                  border: `1px solid ${t.status === "active" ? "rgba(34,197,94,0.3)" : "var(--rule)"}`,
                }}>
                  {t.status === "active" ? "● Active" : "○ Closed"}
                </span>
              </td>
              <td>
                {t.analyzed ? (
                  <span style={{color:"var(--ok)",fontSize:11,fontFamily:"var(--mono)"}}>✓</span>
                ) : (
                  <button
                    className="btn ghost"
                    style={{fontSize:10,padding:"2px 6px",whiteSpace:"nowrap"}}
                    onClick={(e) => { e.stopPropagation(); runAnalysis(t.id); }}
                    disabled={analyzingId === t.id}
                  >
                    {analyzingId === t.id ? "…" : "Analyze"}
                  </button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );

  const TenderCards = ({ items, closed = false }) => (
    <div className="cardgrid">
      {items.map(t => {
        const d = daysUntil(t.deadline);
        return (
          <div key={t.id} className="tcard" onClick={() => onOpen(t.id)} style={closed ? { opacity: 0.65 } : {}}>
            <div className="row1">
              <div>
                <div className="id">#{t.id} · <span className="mono">{t.no}</span></div>
                <h3>{t.title}</h3>
              </div>
              <ConfTag c={t.confidence} />
            </div>
            <div className="meta">
              <span><b>{t.nh}</b> · {t.state}</span>
              <span><b>{t.length} km</b></span>
              {t.estValue > 0 && <span><b>{fmtINR(t.estValue)}</b></span>}
            </div>
            <div className="footer">
              <TypeTag t={t.type} />
              <span className="mono" style={{fontSize:11.5,color: d <= 7 && d >= 0 ? "var(--danger)" : "var(--ink-4)"}}>
                {fmtDate(t.deadline)} · {d > 0 ? `${d}d left` : d === 0 ? "Today" : `${-d}d ago`}
              </span>
              {!t.analyzed && (
                <button
                  className="btn ghost"
                  style={{fontSize:10,padding:"2px 6px"}}
                  onClick={(e) => { e.stopPropagation(); runAnalysis(t.id); }}
                  disabled={analyzingId === t.id}
                >
                  {analyzingId === t.id ? "Analyzing…" : "Run AI"}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      {/* Page head */}
      <div className="page-head">
        <div>
          <div className="crumb">Workspace · Tenders</div>
          <h1>Active tenders — {new Date().toLocaleDateString("en-IN", {day:"numeric",month:"long",year:"numeric"})}</h1>
        </div>
        <div className="right">
          <button className="btn" onClick={fetchFromNHAI} disabled={fetching}
            title="Pull latest tenders from nhai.gov.in">
            <span style={{display:"flex"}}>{Icons.refresh}</span>
            {fetching ? "Fetching…" : "Fetch from NHAI"}
          </button>
          <button className="btn"><span style={{display:"flex"}}>{Icons.download}</span> Export CSV</button>
          <button className="btn"><span style={{display:"flex"}}>{Icons.bell}</span> Saved alerts</button>
          <button className="btn primary" onClick={runAllAnalysis}>
            <span style={{display:"flex"}}>{Icons.layers}</span> Run analysis
          </button>
        </div>
      </div>

      {/* Analysis feedback message */}
      {analyzeMsg && (
        <div style={{
          padding:"10px 24px",
          background:"var(--accent-soft)",
          borderBottom:"1px solid var(--accent)",
          fontSize:13,color:"var(--ink)",
          display:"flex",alignItems:"center",gap:8
        }}>
          <span style={{fontFamily:"var(--mono)",fontSize:11}}>ℹ</span>
          <span>{analyzeMsg}</span>
        </div>
      )}

      {/* Stats */}
      <div className="stat-row">
        <div className="stat">
          <div className="label">Active tenders</div>
          <div className="value">{activeTenders.length}<span className="unit">on portal</span></div>
          <div className="meta">{activeTenders.filter(t=>t.analyzed).length} analyzed · {activeTenders.filter(t=>!t.analyzed).length} pending</div>
        </div>
        <div className="stat">
          <div className="label">Closing in ≤ 14 days</div>
          <div className="value">{urgent}<span className="unit">tenders</span></div>
          <div className="meta">
            {urgent > 0
              ? <span style={{ color: "var(--danger)" }}>● {urgent} closing soon</span>
              : <span style={{ color: "var(--ok)" }}>● No urgent deadlines</span>}
          </div>
        </div>
        <div className="stat">
          <div className="label">Analysis coverage</div>
          <div className="value">{tenders.length > 0 ? Math.round(analyzed / tenders.length * 100) : 0}<span className="unit">% analyzed</span></div>
          <div className="pipebar" style={{marginTop:8}}>
            <span style={{ width: `${tenders.length > 0 ? analyzed/tenders.length*100 : 0}%`, background: "var(--ok)" }} />
          </div>
        </div>
        <div className="stat">
          <div className="label">Closed / archived</div>
          <div className="value">{closedTenders.length}<span className="unit">tenders</span></div>
          <div className="meta">
            <button
              className="chip"
              style={{fontSize:11,padding:"1px 8px",marginTop:2}}
              onClick={() => setShowClosed(v => !v)}
            >
              {showClosed ? "Hide closed" : "View closed tenders"}
            </button>
          </div>
        </div>
      </div>

      {/* Tools / Filters */}
      <div className="tools">
        <div className="searchbar" style={{ width: 380 }}>
          <span style={{ display: "flex", color: "var(--ink-4)" }}>{Icons.search}</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)}
                 placeholder="Search tender no., title, NH-number, state, ID…" />
          {!query && <span className="kbd">⌘K</span>}
        </div>
        <span className="sep" />
        {[
          { k: "type", v: "2-stage", label: "2-stage" },
          { k: "type", v: "single-stage", label: "Single-stage" },
        ].map(c => (
          <button key={c.label}
                  className={"chip" + (typeFilter === c.v ? " on" : "")}
                  onClick={() => setTypeFilter(f => f === c.v ? null : c.v)}>
            {c.label}
          </button>
        ))}
        <button className="chip">+ Add filter</button>
        <div style={{ flex: 1 }} />
        <select className="chip" value={sortBy} onChange={(e) => setSortBy(e.target.value)}
                style={{ background: "var(--paper)", paddingRight: 8 }}>
          <option value="deadline">Sort: Deadline</option>
          <option value="value">Sort: Est. value</option>
          <option value="match">Sort: Match score</option>
        </select>
        <span className="density-toggle">
          <button className={view === "table" ? "on" : ""} onClick={() => setView("table")} title="Table">
            {Icons.table}
          </button>
          <button className={view === "cards" ? "on" : ""} onClick={() => setView("cards")} title="Cards">
            {Icons.cards}
          </button>
        </span>
        {view === "table" && (
          <span className="density-toggle">
            <button className={density === "compact" ? "on" : ""} onClick={() => setDensity("compact")} title="Compact">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 7h16M4 12h16M4 17h16"/></svg>
            </button>
            <button className={density === "normal" ? "on" : ""} onClick={() => setDensity("normal")} title="Normal">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
            </button>
            <button className={density === "roomy" ? "on" : ""} onClick={() => setDensity("roomy")} title="Roomy">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M4 5h16M4 12h16M4 19h16"/></svg>
            </button>
          </span>
        )}
      </div>

      {/* ── ACTIVE TENDERS ── */}
      <div className="list-wrap">
        {tenders.length === 0 && (
          <div style={{padding:"60px 0",textAlign:"center",color:"var(--ink-4)"}}>
            <div style={{fontSize:28,marginBottom:12}}>⟳</div>
            <div style={{fontFamily:"var(--mono)",fontSize:13}}>Loading tenders from NHAI portal…</div>
          </div>
        )}

        {tenders.length > 0 && activeTenders.length === 0 && (
          <div style={{padding:"60px 0",textAlign:"center",color:"var(--ink-4)"}}>
            <div style={{fontFamily:"var(--mono)",fontSize:13}}>No active tenders found.</div>
          </div>
        )}

        {/* Active section header */}
        {activeTenders.length > 0 && (
          <div style={{
            display:"flex",alignItems:"center",gap:12,
            padding:"10px 0 6px",
            borderBottom:"2px solid var(--accent)",marginBottom:0
          }}>
            <span style={{
              fontFamily:"var(--mono)",fontSize:10,letterSpacing:".12em",
              textTransform:"uppercase",color:"var(--accent-2)",fontWeight:600
            }}>Active Tenders</span>
            <span style={{
              background:"var(--accent-soft)",color:"var(--accent-2)",
              borderRadius:10,padding:"0 8px",fontSize:11,fontWeight:600
            }}>{filteredActive.length}</span>
          </div>
        )}

        {activeTenders.length > 0 && filteredActive.length === 0 && (
          <div style={{padding:"40px 0",textAlign:"center",color:"var(--ink-4)"}}>
            <div style={{fontFamily:"var(--mono)",fontSize:13}}>No active tenders match the current filters.</div>
          </div>
        )}

        {activeTenders.length > 0 && filteredActive.length > 0 && (
          view === "table"
            ? <TenderTable items={filteredActive} />
            : <TenderCards items={filteredActive} />
        )}

        {/* ── CLOSED TENDERS (collapsible) ── */}
        {closedTenders.length > 0 && (
          <div style={{marginTop:32}}>
            <div
              style={{
                display:"flex",alignItems:"center",gap:12,
                padding:"10px 14px 10px",
                background:"var(--paper-2)",
                border:"1px solid var(--rule)",
                cursor:"pointer",
                userSelect:"none",
              }}
              onClick={() => setShowClosed(v => !v)}
            >
              <span style={{
                fontFamily:"var(--mono)",fontSize:10,letterSpacing:".12em",
                textTransform:"uppercase",color:"var(--ink-3)",fontWeight:600
              }}>
                {showClosed ? "▼" : "▶"} Closed / Archived Tenders
              </span>
              <span style={{
                background:"var(--paper)",color:"var(--ink-3)",
                border:"1px solid var(--rule)",
                borderRadius:10,padding:"0 8px",fontSize:11,fontWeight:600
              }}>{closedTenders.length}</span>
              <span style={{flex:1}} />
              <span style={{fontSize:12,color:"var(--ink-4)"}}>
                {showClosed ? "Click to hide" : "Click to expand"}
              </span>
            </div>

            {showClosed && (
              <div style={{marginTop:1}}>
                {filteredClosed.length === 0 ? (
                  <div style={{padding:"24px",textAlign:"center",color:"var(--ink-4)",fontFamily:"var(--mono)",fontSize:13}}>
                    No closed tenders match the current filters.
                  </div>
                ) : (
                  view === "table"
                    ? <TenderTable items={filteredClosed} closed />
                    : <TenderCards items={filteredClosed} closed />
                )}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="pager">
        <span>
          Showing {filteredActive.length} active
          {showClosed ? ` + ${filteredClosed.length} closed` : ""}
          {" "}of {tenders.length} total tenders from <span className="mono">nhai.gov.in</span>
        </span>
        <div className="pager-actions">
          <button className="btn ghost" disabled>← Prev</button>
          <button className="btn ghost">Next →</button>
        </div>
      </div>
    </div>
  );
}
window.ListView = ListView;
