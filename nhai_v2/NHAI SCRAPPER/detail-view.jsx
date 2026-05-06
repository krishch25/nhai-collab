/* global React, Icons, Cite, fmtDate, fmtINRPlain, daysUntil, TypeTag, ConfTag */
const { useState: useStateD, useRef: useRefD, useEffect: useEffectD } = React;

// --- Citation jump panel (replaces fake PDF panel) ---
function CitationPanel({ snippet, page, file, docUrl }) {
  if (!snippet && !page) return null;
  return (
    <aside className="pdf-panel">
      <div className="pdf-head">
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-4)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{file || "Document"}</span>
        {docUrl && (
          <a href={docUrl} target="_blank" rel="noopener noreferrer" className="step" title="Open source document" style={{ textDecoration: "none" }}>
            {Icons.external}
          </a>
        )}
      </div>
      <div className="pdf-body" ref={null} style={{ padding: "24px 20px" }}>
        {page > 0 && (
          <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--ink-5)", letterSpacing: ".08em", textTransform: "uppercase", marginBottom: 12 }}>
            Page {page}
          </div>
        )}
        {snippet && (
          <blockquote style={{
            margin: 0,
            padding: "14px 16px",
            background: "var(--hi-soft)",
            borderLeft: "3px solid var(--hi)",
            fontSize: 13,
            lineHeight: 1.65,
            color: "var(--ink-2)",
            whiteSpace: "pre-wrap",
            fontStyle: "normal"
          }}>
            "{snippet}"
          </blockquote>
        )}
        {!snippet && (
          <p style={{ fontSize: 13, color: "var(--ink-4)", fontStyle: "italic" }}>
            Click any citation chip to see the source quote from the RFP.
          </p>
        )}
      </div>
    </aside>
  );
}

// --- Section components ---
function FieldRow({ label, value, page, snippet, onJump, na }) {
  return (
    <>
      <div className="flabel">{label}</div>
      <div className="fvalue">
        {na || !value || value === "N/A" ? <span className="na">—</span> : <span>{value}</span>}
        {page ? <Cite page={page} snippet={snippet} onJump={onJump} /> : null}
      </div>
    </>
  );
}

function sectionConf(obj, keys) {
  if (!obj) return "low";
  const filled = keys.filter(k => {
    const v = obj[k];
    if (!v) return false;
    const val = typeof v === "object" ? (v.value || "") : (v || "");
    if (Array.isArray(val)) return val.length > 0;
    return val && val !== "N/A" && val !== "";
  });
  const ratio = filled.length / Math.max(keys.length, 1);
  if (ratio >= 0.55) return "high";
  if (ratio >= 0.25) return "medium";
  return "low";
}

function Section({ id, num, title, conf = "high", info, children, side }) {
  const inner = side ? (
    <div className="annot">
      <div className="body">{children}</div>
      <div className="aside">{side}</div>
    </div>
  ) : children;
  return (
    <section className="section" id={id}>
      <div className="section-head">
        <span className="num">§ {num}</span>
        <h2>{title}</h2>
        {info && (
          <span className="section-info">
            i
            <span className="tip">{info}</span>
          </span>
        )}
        <span className={"conf " + conf}><span className="dot" /> {conf} confidence</span>
      </div>
      {inner}
    </section>
  );
}

// --- Deep-safe field accessor — never crashes on null/undefined ---
function safeVal(obj, ...keys) {
  let cur = obj;
  for (const k of keys) {
    if (cur == null) return "N/A";
    cur = cur[k];
  }
  return cur ?? "N/A";
}
function safeArr(obj, ...keys) {
  const v = safeVal(obj, ...keys);
  return Array.isArray(v) ? v : [];
}

// --- Detail view ---
function DetailView({ tweaks, tenderId, onBack }) {
  const [t, setT] = useStateD(null);
  const [loading, setLoading] = useStateD(true);
  const [loadError, setLoadError] = useStateD(null);
  const [page, setPage] = useStateD(1);
  const [snippet, setSnippet] = useStateD(null);
  const [activeSection, setActiveSection] = useStateD("dates");
  const [analyzeStatus, setAnalyzeStatus] = useStateD(null);
  const [analyzeMsg, setAnalyzeMsg] = useStateD("");
  const [polling, setPolling] = useStateD(false);
  const mainRef = useRefD(null);
  const pollRef = useRefD(null);

  async function fetchDetail(id) {
    try {
      delete window.TENDER_CACHE[id];
      const data = await loadTenderDetail(id);
      if (data) {
        setT(data);
        setLoadError(null);
        setPage(1);
        return data;
      } else {
        setLoadError("Could not load tender data. Check server connection.");
        return null;
      }
    } catch (e) {
      setLoadError(`Error: ${e.message}`);
      return null;
    }
  }

  useEffectD(() => {
    if (!tenderId) return;
    setLoading(true);
    setLoadError(null);
    setT(null);
    fetchDetail(tenderId).then(data => {
      setLoading(false);
      // Auto-poll if not yet analyzed
      if (data && !data.analyzed) {
        setPolling(true);
      }
    });
    return () => { clearInterval(pollRef.current); };
  }, [tenderId]);

  // Poll every 15s while unanalyzed — auto-refresh when analysis completes
  useEffectD(() => {
    if (!polling) { clearInterval(pollRef.current); return; }
    pollRef.current = setInterval(async () => {
      const data = await fetchDetail(tenderId);
      if (data && data.analyzed) {
        setPolling(false);
        clearInterval(pollRef.current);
        setAnalyzeMsg("✓ Analysis complete! Data has been updated.");
        setTimeout(() => setAnalyzeMsg(""), 5000);
      }
    }, 15000);
    return () => clearInterval(pollRef.current);
  }, [polling, tenderId]);

  async function triggerAnalysis() {
    if (!tenderId) return;
    setAnalyzeStatus('queuing');
    setAnalyzeMsg('Queuing AI analysis…');
    try {
      const r = await fetch(`/api/tenders/${tenderId}/analyze`, { method: 'POST' });
      if (r.ok) {
        setAnalyzeStatus('queued');
        setAnalyzeMsg('✓ Analysis queued. The AI is processing the tender document. Refresh this page in ~60 seconds to see results.');
      } else {
        const err = await r.text();
        setAnalyzeStatus('error');
        setAnalyzeMsg(`✗ Failed to queue: ${err}`);
      }
    } catch (e) {
      setAnalyzeStatus('error');
      setAnalyzeMsg(`✗ Error: ${e.message}`);
    }
  }

  async function refreshAnalysis() {
    if (!tenderId) return;
    setLoading(true);
    const data = await fetchDetail(tenderId);
    setLoading(false);
    if (data && !data.analyzed) setPolling(true);
  }

  const jump = (p, s) => {
    setPage(p);
    setSnippet(s || null);
  };

  // Section nav scrollspy
  useEffectD(() => {
    const sections = ["dates", "fees", "elig", "eval", "scope", "sub", "contact", "pay", "risk", "forms"];
    const onScroll = () => {
      if (!mainRef.current) return;
      let cur = sections[0];
      for (const s of sections) {
        const el = document.getElementById(s);
        if (el && el.getBoundingClientRect().top < 120) cur = s;
      }
      setActiveSection(cur);
    };
    const el = mainRef.current;
    el && el.addEventListener("scroll", onScroll);
    return () => el && el.removeEventListener("scroll", onScroll);
  }, []);

  const navTo = (id) => {
    const el = document.getElementById(id);
    if (el && mainRef.current) {
      const container = mainRef.current;
      const top = el.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop - 24;
      container.scrollTo({ top, behavior: "smooth" });
    }
  };

  // Show loading spinner
  if (loading) {
    return (
      <div className="detail-wrap" style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "80vh", flexDirection: "column", gap: 12 }}>
        <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--ink-4)", animation: "pulse 1.5s infinite" }}>Loading tender data…</div>
      </div>
    );
  }

  // Show error state
  if (loadError || !t) {
    return (
      <div className="detail-wrap" style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "80vh", flexDirection: "column", gap: 16 }}>
        <div style={{ fontSize: 32, color: "var(--ink-5)" }}>⚠</div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--danger)" }}>{loadError || "Tender not found"}</div>
        <button className="btn" onClick={onBack}>← Back to list</button>
      </div>
    );
  }

  const sections = [
    { id: "dates", num: "01", label: "Key Dates", count: 7 },
    { id: "fees", num: "02", label: "RFP Fees & Securities", count: 4 },
    { id: "elig", num: "03", label: "Eligibility", count: 11 },
    { id: "eval", num: "04", label: "Evaluation Criteria", count: 6 },
    { id: "scope", num: "05", label: "Scope of RFP", count: 18 },
    { id: "sub", num: "06", label: "Submission Mechanisms", count: 12 },
    { id: "contact", num: "07", label: "Contact / SPOC", count: 1 },
    { id: "pay", num: "08", label: "Payment Terms", count: 5 },
    { id: "risk", num: "09", label: "Risk & Regulatory", count: 7 },
    { id: "forms", num: "10", label: "Documents & Forms", count: 14 },
  ];

  const dCount = daysUntil(t.deadline);
  const kd = t.key_dates || {};
  const fees = t.rfp_fees || {};
  const elig = t.eligibility || {};
  const tech = elig.technical || {};
  const fin = elig.financial || {};
  const ev = t.evaluation || {};
  const sc = t.scope || {};
  const sub = t.submission || {};
  const rsk = t.risk || {};
  const docs = t.documents || [];

  return (
    <div className="detail-wrap">
      {/* Section nav */}
      <nav className="section-nav">
        <div className="nav-label">Analysis Sections</div>
        {sections.map(s => (
          <a key={s.id}
            className={activeSection === s.id ? "active" : ""}
            onClick={() => navTo(s.id)}>
            <span className="num">{s.num}</span>
            <span style={{ flex: 1 }}>{s.label}</span>
            <span className="badge">{s.count}</span>
          </a>
        ))}
        <div className="group">
          <div className="nav-label">Tools</div>
          <a><span className="num">▸</span><span>Compare to similar</span></a>
          <a><span className="num">▸</span><span>Bid/no-bid memo</span></a>
          <a style={{ cursor: "pointer" }} onClick={triggerAnalysis}>
            <span className="num">▸</span>
            <span>{analyzeStatus === 'queuing' ? 'Queuing…' : 'Re-run analysis'}</span>
          </a>
          <a style={{ cursor: "pointer" }} onClick={refreshAnalysis}>
            <span className="num">↺</span>
            <span>Refresh data</span>
          </a>
        </div>
      </nav>

      {/* Main */}
      <main className="detail-main" ref={mainRef}>
        {/* Header */}
        <div className="detail-head">
          <div className="crumb">
            <a onClick={onBack} style={{ cursor: "pointer", textDecoration: "underline", textUnderlineOffset: 3 }}>Tenders</a>
            <span className="sep">/</span>
            <span>{t.no}</span>
            <span className="sep">/</span>
            <span>#{t.id}</span>
          </div>
          <h1>{t.title}</h1>
          <div className="meta-line">
            <span><b>{t.nh}</b> · {t.chainage}</span>
            <span><b>{t.length} km</b> · {t.state}</span>
            {t.duration && t.duration !== "N/A" && <span><b>Duration:</b> {t.duration}</span>}
            <TypeTag t={t.type} />
            <ConfTag c={t.confidence} />
          </div>

          {/* Analysis status banner */}
          {!t.analyzed && (
            <div style={{
              marginTop: 16, padding: "10px 16px",
              background: "rgba(234,179,8,0.08)", border: "1px solid rgba(234,179,8,0.3)",
              display: "flex", alignItems: "center", gap: 12, borderRadius: 4
            }}>
              <span style={{ fontSize: 13, color: "#b45309" }}>⚠ This tender has not been AI-analyzed yet.</span>
              <button className="btn" style={{ fontSize: 12 }} onClick={triggerAnalysis}
                disabled={analyzeStatus === 'queuing'}>
                {analyzeStatus === 'queuing' ? 'Queuing…' : 'Run AI Analysis Now'}
              </button>
            </div>
          )}

          {/* Analyze feedback */}
          {analyzeMsg && (
            <div style={{
              marginTop: 8, padding: "8px 14px", fontSize: 12.5,
              background: analyzeStatus === 'error' ? "rgba(239,68,68,0.08)" : "rgba(34,197,94,0.08)",
              border: `1px solid ${analyzeStatus === 'error' ? "rgba(239,68,68,0.3)" : "rgba(34,197,94,0.3)"}`,
              color: analyzeStatus === 'error' ? "#b91c1c" : "#15803d",
              borderRadius: 4
            }}>
              {analyzeMsg}
              {analyzeStatus === 'queued' && (
                <button className="btn ghost" style={{ fontSize: 11, marginLeft: 12 }} onClick={refreshAnalysis}>Refresh now</button>
              )}
            </div>
          )}

          <div style={{
            marginTop: 22,
            padding: "14px 16px",
            borderLeft: "2px solid var(--accent)",
            background: "var(--paper-2)",
            display: "flex",
            gap: 24,
            alignItems: "center"
          }}>
            <div>
              <div style={{ fontFamily: "var(--mono)", fontSize: 9.5, letterSpacing: ".1em", textTransform: "uppercase", color: "var(--ink-4)" }}>Bid due in</div>
              <div style={{ fontFamily: "var(--sans)", fontSize: 32, fontWeight: 700, letterSpacing: "-.02em", lineHeight: 1, marginTop: 2 }}>
                {dCount}<span style={{ fontFamily: "var(--mono)", fontSize: 13, color: "var(--ink-4)", marginLeft: 6 }}>days</span>
              </div>
            </div>
            <div style={{ width: 1, height: 36, background: "var(--rule)" }} />
            <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5, color: "var(--ink-2)" }}>
              {t.analyzed
                ? (t.summary || <span style={{ color: "var(--ink-4)", fontStyle: "italic" }}>No summary extracted — re-run analysis.</span>)
                : <span style={{ color: "var(--ink-4)", fontStyle: "italic" }}>AI summary will appear here after analysis is complete.</span>
              }
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn"><span style={{ display: "flex" }}>{Icons.flag}</span> Track</button>
              <button className="btn primary">Generate memo</button>
            </div>
          </div>
        </div>

        {/* Section 1 — Key Dates */}
        <Section id="dates" num="01" title="Key Dates" conf={sectionConf(kd, ["pre_bid_meeting","proposal_submission_deadline","technical_bid_opening","financial_bid_opening"])}
          info="Critical timeline milestones extracted from the RFP — pre-bid meeting, clarification deadline, proposal submission, bid opening dates, and validity period."
        >
          <div className="deadlines" style={{ marginBottom: 24 }}>
            {[
              { lbl: "Pre-bid meeting", val: kd.pre_bid_meeting || { value: "N/A", page: 0 }, isPrimary: false },
              { lbl: "Clarification deadline", val: kd.last_date_clarification || { value: "N/A", page: 0 }, isPrimary: false },
              { lbl: "Submission deadline", val: kd.proposal_submission_deadline || { value: "N/A", page: 0 }, isPrimary: true },
              { lbl: "Technical bid opening", val: kd.technical_bid_opening || { value: "N/A", page: 0 }, isPrimary: false },
              { lbl: "Financial bid opening", val: kd.financial_bid_opening || { value: "N/A", page: 0 }, isPrimary: false },
            ].map(({ lbl, val, isPrimary }, i) => (
              <div key={i} className="dline"
                style={isPrimary ? { borderColor: "var(--accent)", background: "var(--accent-soft)" } : {}}
                onClick={() => val.page && jump(val.page, val.snippet)}
              >
                <div className="lbl" style={isPrimary ? { color: "var(--accent-2)" } : {}}>{lbl}</div>
                <div className="day" style={{ fontSize: 13, fontWeight: 500, lineHeight: 1.3, margin: "4px 0" }}>
                  {val.value && val.value !== "N/A" ? val.value : <span style={{ color: "var(--ink-5)" }}>N/A</span>}
                </div>
                {val.page > 0 && <div className="tx" style={{ fontSize: 10, color: "var(--ink-5)" }}>p. {val.page}</div>}
              </div>
            ))}
          </div>

          <div className="fgrid">
            <FieldRow label="Pre-bid meeting" {...(kd.pre_bid_meeting || {})} onJump={jump} />
            <FieldRow label="Last date for clarification" value={(kd.last_date_clarification || {}).value} page={(kd.last_date_clarification || {}).page} snippet={(kd.last_date_clarification || {}).snippet} onJump={jump} />
            <FieldRow label="Proposal submission deadline" value={(kd.proposal_submission_deadline || {}).value} page={(kd.proposal_submission_deadline || {}).page} snippet={(kd.proposal_submission_deadline || {}).snippet} onJump={jump} />
            <FieldRow label="Technical bid opening" value={(kd.technical_bid_opening || {}).value} page={(kd.technical_bid_opening || {}).page} snippet={(kd.technical_bid_opening || {}).snippet} onJump={jump} />
            <FieldRow label="Financial bid opening" value={(kd.financial_bid_opening || {}).value} page={(kd.financial_bid_opening || {}).page} snippet={(kd.financial_bid_opening || {}).snippet} onJump={jump} />
            <FieldRow label="Bid validity period" value={(kd.bid_validity || {}).value} page={(kd.bid_validity || {}).page} snippet={(kd.bid_validity || {}).snippet} onJump={jump} />
            <FieldRow label="Document download period" value={(kd.document_download || {}).value} page={(kd.document_download || {}).page} snippet={(kd.document_download || {}).snippet} onJump={jump} />
          </div>
        </Section>

        {/* Section 2 — RFP Fees */}
        <Section id="fees" num="02" title="RFP Fees & Securities" conf={sectionConf(fees, ["rfp_fee_amount","payment_mode","emd_amount"])}
          info="Upfront costs to participate — document fee, bank details for payment, EMD (refundable security), and performance security (retained on contract award).">
          <div className="fgrid">
            <FieldRow label="RFP document fee" value={(fees.rfp_fee_amount || {}).value} page={(fees.rfp_fee_amount || {}).page} snippet={(fees.rfp_fee_amount || {}).snippet} onJump={jump} />
            <FieldRow label="Payment mode" value={(fees.payment_mode || {}).value} onJump={jump} />
            <div className="flabel">Bank account details</div>
            <div className="fvalue" style={{ flexDirection: "column", alignItems: "flex-start", gap: 6 }}>
              <div style={{ display: "grid", gridTemplateColumns: "110px 1fr", rowGap: 4, fontSize: 13.5 }}>
                <span style={{ color: "var(--ink-4)" }}>Beneficiary</span><span>{(fees.bank || {}).beneficiary || "N/A"}</span>
                <span style={{ color: "var(--ink-4)" }}>A/c No.</span><span className="mono">{(fees.bank || {}).account || "N/A"}</span>
                <span style={{ color: "var(--ink-4)" }}>IFSC</span><span className="mono">{(fees.bank || {}).ifsc || "N/A"}</span>
                <span style={{ color: "var(--ink-4)" }}>Bank</span><span>{(fees.bank || {}).bank || "N/A"}</span>
              </div>
              <Cite page={(fees.bank || {}).page} snippet={(fees.bank || {}).snippet} onJump={jump} />
            </div>
            <FieldRow label="Earnest money deposit" value={(fees.emd_amount || {}).value} page={(fees.emd_amount || {}).page} snippet={(fees.emd_amount || {}).snippet} onJump={jump} />
            <FieldRow label="Performance security" value={(fees.performance_security || {}).value} page={(fees.performance_security || {}).page} snippet={(fees.performance_security || {}).snippet} onJump={jump} />
          </div>
        </Section>

        {/* Section 3 — Eligibility */}
        <Section id="elig" num="03" title="Eligibility Criteria" conf={sectionConf(tech, ["min_annual_turnover","similar_project_experience","jv","key_personnel"])}
          info="Minimum qualifications required to bid. Technical: past experience, key personnel, JV rules. Financial: minimum turnover and net worth thresholds.">
          <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 6px", letterSpacing: "-.005em" }}>Technical Eligibility</h3>
          <div className="fgrid" style={{ marginBottom: 28 }}>
            <FieldRow label="Min. annual turnover" value={(tech.min_annual_turnover || {}).value} page={(tech.min_annual_turnover || {}).page} snippet={(tech.min_annual_turnover || {}).snippet} onJump={jump} />
            <FieldRow label="Similar project experience" value={(tech.similar_project_experience || {}).value} page={(tech.similar_project_experience || {}).page} snippet={(tech.similar_project_experience || {}).snippet} onJump={jump} />
            <FieldRow label="JV conditions" value={(tech.jv || {}).value} page={(tech.jv || {}).page} snippet={(tech.jv || {}).snippet} onJump={jump} />
            <FieldRow label="Ongoing assignment cap" value={(tech.ongoing_cap || {}).value} page={(tech.ongoing_cap || {}).page} snippet={(tech.ongoing_cap || {}).snippet} onJump={jump} />
            {(tech.key_personnel || []).length > 0 && <>
              <div className="flabel">Key personnel required</div>
              <div className="fvalue" style={{ flexDirection: "column", alignItems: "flex-start", padding: "10px 0" }}>
                <ul className="bulletlist" style={{ width: "100%" }}>
                  {(tech.key_personnel || []).map((kp, i) => (
                    <li key={i}>
                      <span className="marker">{String(i + 1).padStart(2, "0")}</span>
                      <div className="body">
                        {typeof kp === "string" ? kp : kp.role}
                        {kp.page ? <Cite page={kp.page} onJump={jump} snippet={typeof kp === "string" ? kp : kp.role} /> : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </>}
            {(tech.other_conditions || []).length > 0 && <>
              <div className="flabel">Other conditions</div>
              <div className="fvalue" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
                {(tech.other_conditions || []).map((c, i) => (
                  <div key={i} style={{ fontSize: 13, color: "var(--ink-3)", padding: "2px 0", borderBottom: "1px solid var(--rule)", width: "100%" }}>· {c}</div>
                ))}
              </div>
            </>}
          </div>
          <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 6px", letterSpacing: "-.005em" }}>Financial Eligibility</h3>
          <div className="fgrid">
            <FieldRow label="Min. annual turnover" value={(fin.min_annual_turnover || {}).value} page={(fin.min_annual_turnover || {}).page} snippet={(fin.min_annual_turnover || {}).snippet} onJump={jump} />
            <FieldRow label="Net worth requirement" value={(fin.net_worth || {}).value} page={(fin.net_worth || {}).page} snippet={(fin.net_worth || {}).snippet} onJump={jump} />
            <FieldRow label="Financial years considered" value={(fin.financial_years || {}).value} page={(fin.financial_years || {}).page} snippet={(fin.financial_years || {}).snippet} onJump={jump} />
          </div>
        </Section>

        {/* Section 4 — Evaluation */}
        <Section id="eval" num="04" title="Evaluation Criteria" conf={sectionConf(ev, ["method","technical_weight","financial_weight","technical_min_qualifying"])}
          info="How bids are scored and ranked. QCBS assigns separate weights to technical and financial proposals (e.g. 80/20). Technical proposals below the minimum qualifying score are disqualified before financial proposals are opened.">
          <div className="fgrid" style={{ marginBottom: 20 }}>
            <FieldRow label="Selection method" value={t.evaluation.method.value} page={t.evaluation.method.page} snippet={t.evaluation.method.snippet} onJump={jump} />
            <div className="flabel">Weightage</div>
            <div className="fvalue">
              <span className="num">Technical {t.evaluation.technical_weight.value}</span>
              <span style={{ color: "var(--ink-5)" }}>+</span>
              <span className="num">Financial {t.evaluation.financial_weight.value}</span>
              {t.evaluation.financial_weight.page ? <Cite page={t.evaluation.financial_weight.page} snippet={t.evaluation.formula} onJump={jump} /> : null}
            </div>
            <FieldRow label="Min. technical qualifying" value={t.evaluation.technical_min_qualifying.value} page={t.evaluation.technical_min_qualifying.page} snippet={t.evaluation.technical_min_qualifying.snippet} onJump={jump} />
          </div>

          {t.evaluation.criteria && t.evaluation.criteria.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "22px 0 6px", letterSpacing: "-.005em" }}>Evaluation criteria</h3>
            <table className="dtable">
              <thead><tr><th>Criterion</th><th style={{ width: 100, textAlign: "right" }}>Max marks</th><th style={{ width: 60 }}></th></tr></thead>
              <tbody>
                {t.evaluation.criteria.map((c, i) => (
                  <tr key={i}>
                    <td>{c.criterion}</td>
                    <td className="num" style={{ textAlign: "right" }}>{c.marks}</td>
                    <td>{c.page ? <Cite page={c.page} snippet={`${c.criterion} — ${c.marks} marks max`} onJump={jump} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>}

          {t.evaluation.pass_fail && t.evaluation.pass_fail.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "22px 0 6px", letterSpacing: "-.005em" }}>Pass / fail criteria</h3>
            <ul className="bulletlist">
              {t.evaluation.pass_fail.map((c, i) => (
                <li key={i}><span className="marker">{String(i + 1).padStart(2, "0")}</span><div className="body">{c}</div></li>
              ))}
            </ul>
          </>}

          <p style={{ marginTop: 14, fontSize: 13, color: "var(--ink-3)", fontStyle: "italic" }}>Formula: {t.evaluation.formula}</p>
        </Section>

        {/* Section 5 — Scope */}
        <Section id="scope" num="05" title="Scope of RFP" conf={sectionConf(sc, ["location","contract_duration","in_scope","deliverables"])}
          info="What the winning consultant must deliver — the exact tasks, deliverables, and milestones. Out-of-scope items are provided by NHAI/client. Use this to estimate staffing and timeline before deciding to bid.">
          <div className="fgrid" style={{ marginBottom: 24 }}>
            <FieldRow label="Project location" value={t.scope.location.value} page={t.scope.location.page} snippet={t.scope.location.snippet} onJump={jump} />
            <FieldRow label="Contract duration" value={t.scope.contract_duration.value} page={t.scope.contract_duration.page} snippet={t.scope.contract_duration.snippet} onJump={jump} />
          </div>
          {t.scope.in_scope && t.scope.in_scope.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 10px" }}>In-scope tasks</h3>
            <ul className="bulletlist" style={{ marginBottom: 24 }}>
              {t.scope.in_scope.map((s, i) => (
                <li key={i}>
                  <span className="marker">{String(i + 1).padStart(2, "0")}</span>
                  <div className="body">
                    {s.d}
                    {s.page ? <Cite page={s.page} onJump={jump} snippet={s.d} /> : null}
                  </div>
                </li>
              ))}
            </ul>
          </>}
          {t.scope.deliverables && t.scope.deliverables.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 10px" }}>Deliverables</h3>
            <table className="dtable">
              <thead><tr><th>Deliverable</th><th style={{ width: 200 }}>Timeline</th><th style={{ width: 60 }}></th></tr></thead>
              <tbody>
                {t.scope.deliverables.map((d, i) => (
                  <tr key={i}>
                    <td>{d.name}</td>
                    <td className="num">{d.timeline || "—"}</td>
                    <td>{d.page ? <Cite page={d.page} onJump={jump} snippet={`${d.name} — ${d.timeline}`} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>}
          {t.scope.out_of_scope && t.scope.out_of_scope.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "22px 0 10px" }}>Client obligations / out-of-scope</h3>
            <ul className="bulletlist">
              {t.scope.out_of_scope.map((s, i) => (
                <li key={i}><span className="marker">{String(i + 1).padStart(2, "0")}</span><div className="body">{s.d}{s.page ? <Cite page={s.page} onJump={jump} snippet={s.d} /> : null}</div></li>
              ))}
            </ul>
          </>}
        </Section>

        {/* Section 6 — Submission */}
        <Section id="sub" num="06" title="Submission Mechanisms" conf="high"
          info="How to physically submit the bid — the portal, all required forms, annexures, certifications, who must sign each document, how many copies, and the submission language. Missing any mandatory form disqualifies the bid.">
          <div className="fgrid" style={{ marginBottom: 24 }}>
            <FieldRow label="Submission mode" value={t.submission.mode.value} page={t.submission.mode.page} snippet={t.submission.mode.snippet} onJump={jump} />
            <FieldRow label="Portal" value={t.submission.portal.value} page={t.submission.portal.page} snippet={`Submission via ${t.submission.portal.value}`} onJump={jump} />
            <FieldRow label="Number of copies" value={t.submission.copies.value} onJump={jump} />
            <FieldRow label="Language" value={t.submission.language.value} onJump={jump} />
          </div>
          {t.submission.forms && t.submission.forms.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 10px" }}>Required forms ({t.submission.forms.length})</h3>
            <table className="dtable">
              <thead><tr><th>Form / document</th><th style={{ width: 220 }}>Signing authority</th><th style={{ width: 60 }}>Mand.</th><th style={{ width: 60 }}></th></tr></thead>
              <tbody>
                {t.submission.forms.map((f, i) => (
                  <tr key={i}>
                    <td>{f.name}</td>
                    <td style={{ color: "var(--ink-3)" }}>{f.auth || "—"}</td>
                    <td>{f.mandatory ? <span className="tag high" style={{ padding: "0 5px" }}>Yes</span> : <span className="tag" style={{ padding: "0 5px" }}>Opt.</span>}</td>
                    <td>{f.page ? <Cite page={f.page} onJump={jump} snippet={f.name} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>}
          {t.submission.certifications && t.submission.certifications.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "22px 0 10px" }}>Certifications required</h3>
            <ul className="bulletlist">
              {t.submission.certifications.map((c, i) => (
                <li key={i}><span className="marker">{String(i + 1).padStart(2, "0")}</span>
                  <div className="body">{typeof c === "string" ? c : c.description || JSON.stringify(c)}</div></li>
              ))}
            </ul>
          </>}
        </Section>

        {/* Section 7 — Contact */}
        <Section id="contact" num="07" title="Contact / SPOC" conf="high"
          info="Single Point of Contact at NHAI for this tender. All pre-bid clarification queries must be sent to this address in writing. Verbal queries are not accepted.">
          {t.all_contacts && t.all_contacts.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {t.all_contacts.map((c, i) => (
                <div key={i} style={{ padding: "18px 20px", background: "var(--paper-2)", border: "1px solid var(--rule)" }}>
                  {(c.name && c.name !== "N/A") && (
                    <div style={{ fontFamily: "var(--serif)", fontSize: 17, fontWeight: 500, lineHeight: 1.4, marginBottom: 8 }}>{c.name}</div>
                  )}
                  {(c.designation && c.designation !== "N/A") && (
                    <div style={{ fontSize: 13, color: "var(--ink-3)", marginBottom: 4 }}>{c.designation}{c.department ? ` · ${c.department}` : ""}</div>
                  )}
                  {c.address && (
                    <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.55, marginTop: 10, whiteSpace: "pre-line" }}>{c.address}</div>
                  )}
                  <div style={{ display: "flex", gap: 16, marginTop: 10, flexWrap: "wrap" }}>
                    {c.phone && <span className="mono" style={{ fontSize: 12, color: "var(--ink-3)" }}>{c.phone}</span>}
                    {c.email && <a href={`mailto:${c.email}`} className="mono" style={{ fontSize: 12, color: "var(--accent-2)" }}>{c.email}</a>}
                  </div>
                  {(c.source && c.source[0]) && <div style={{ marginTop: 10 }}><Cite page={c.source[0].page} onJump={jump} snippet={c.source[0].snippet} /></div>}
                </div>
              ))}
            </div>
          ) : (
            <span className="na">N/A — no contact information found in document</span>
          )}
        </Section>

        {/* Section 8 — Payment */}
        <Section id="pay" num="08" title="Payment Terms" conf="medium"
          info="When and how much NHAI pays — milestone-linked payment percentages, conditions for release, GST treatment, and any rate escalation clauses. Medium confidence means some payment language may require pre-bid verification.">
          {t.payment && t.payment.length > 0 ? (
            <table className="dtable">
              <thead><tr><th>Milestone / condition</th><th style={{ width: 80, textAlign: "right" }}>%</th><th>Details</th><th style={{ width: 60 }}></th></tr></thead>
              <tbody>
                {t.payment.map((p, i) => (
                  <tr key={i}>
                    <td><b>{p.milestone}</b></td>
                    <td className="num" style={{ textAlign: "right" }}>{p.pct || "—"}</td>
                    <td style={{ color: "var(--ink-3)" }}>{p.cond}</td>
                    <td>{p.page ? <Cite page={p.page} snippet={`${p.milestone}: ${p.cond}`} onJump={jump} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <span className="na">N/A — no payment schedule found in document</span>
          )}
        </Section>

        {/* Section 9 — Risk */}
        <Section id="risk" num="09" title="Risk & Regulatory" conf="medium"
          info="Contract risk exposure — liquidated damages for delays, force majeure events, termination triggers, dispute resolution mechanism, and specific penalty clauses. Extracted from the General Conditions of Contract section of the RFP.">
          <div className="fgrid" style={{ marginBottom: 24 }}>
            <FieldRow label="Liquidated damages" value={t.risk.liquidated_damages.value} page={t.risk.liquidated_damages.page} snippet={t.risk.liquidated_damages.snippet} onJump={jump} />
            <FieldRow label="Force majeure" value={t.risk.force_majeure.value} page={t.risk.force_majeure.page} snippet={t.risk.force_majeure.snippet} onJump={jump} />
            <FieldRow label="Dispute resolution" value={t.risk.dispute.value} page={t.risk.dispute.page} snippet={t.risk.dispute.snippet} onJump={jump} />
            <FieldRow label="Integrity pact" value={t.risk.integrity_pact.value} page={t.risk.integrity_pact.page} snippet={t.risk.integrity_pact.snippet} onJump={jump} />
          </div>
          {t.risk.termination && t.risk.termination.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 10px" }}>Termination conditions ({t.risk.termination.length})</h3>
            <ul className="bulletlist" style={{ marginBottom: 24 }}>
              {t.risk.termination.map((c, i) => (
                <li key={i}><span className="marker">{String(i + 1).padStart(2, "0")}</span>
                  <div className="body">{typeof c === "string" ? c : c.condition || JSON.stringify(c)}</div></li>
              ))}
            </ul>
          </>}
          {t.risk.penalty_clauses && t.risk.penalty_clauses.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "4px 0 10px" }}>Penalty clauses</h3>
            <table className="dtable">
              <thead><tr><th>Risk</th><th style={{ width: 90 }}>Category</th><th style={{ width: 60 }}></th></tr></thead>
              <tbody>
                {t.risk.penalty_clauses.map((p, i) => (
                  <tr key={i}>
                    <td>
                      <div style={{ marginBottom: 4 }}>{p.risk || (typeof p === "string" ? p : JSON.stringify(p))}</div>
                      {p.mitigation && p.mitigation !== "N/A" && <div style={{ fontSize: 12, color: "var(--ink-4)", fontStyle: "italic" }}>Mitigation: {p.mitigation}</div>}
                    </td>
                    <td><span className="tag" style={{ padding: "0 5px", fontSize: 10 }}>{p.category || "—"}</span></td>
                    <td>{p.source && p.source[0] ? <Cite page={p.source[0].page} snippet={p.source[0].snippet} onJump={jump} /> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>}
          {t.risk.insurance && t.risk.insurance.length > 0 && <>
            <h3 style={{ fontFamily: "var(--serif)", fontSize: 15, fontWeight: 500, margin: "22px 0 10px" }}>Insurance requirements</h3>
            <ul className="bulletlist">
              {t.risk.insurance.map((c, i) => (
                <li key={i}><span className="marker">{String(i + 1).padStart(2, "0")}</span>
                  <div className="body">{typeof c === "string" ? c : c.description || JSON.stringify(c)}</div></li>
              ))}
            </ul>
          </>}
        </Section>

        {/* Section 10 — Documents */}
        <Section id="forms" num="10" title="Documents & Forms" conf="high"
          info="All files attached to this tender by NHAI — the main RFP, Notice Inviting Tender, Bill of Quantities, drawings, corrigenda, and pre-bid query replies. Click any file to open or download from the NHAI portal.">
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 1,
            background: "var(--rule)",
            border: "1px solid var(--rule)"
          }}>
            {(t.documents && t.documents.length > 0 ? t.documents : []).map((f, i) => {
              const isPrimary = f.description === "RFP" || i === 0;
              const isForm = f.is_form;
              const ext = (f.extension || "").toLowerCase();
              const isExcel = ext === ".xlsx" || ext === ".xls";
              return (
                <a key={i} href={f.url || `/api/documents/${t.id}/${f.filename}`} target="_blank" rel="noopener noreferrer" style={{
                  background: "var(--paper)",
                  padding: "12px 14px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  cursor: "pointer",
                  textDecoration: "none",
                  color: "inherit"
                }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8 }}>
                    <div className="mono" style={{ fontSize: 11.5, color: isPrimary ? "var(--accent-2)" : "var(--ink-2)", fontWeight: isPrimary ? 600 : 500, wordBreak: "break-all" }}>{f.filename}</div>
                    {isForm && <span className="tag" style={{ height: 14, padding: "0 4px", fontSize: 8.5 }}>FORM</span>}
                    {isPrimary && <span className="tag" style={{ height: 14, padding: "0 4px", fontSize: 8.5, borderColor: "var(--accent)", color: "var(--accent-2)" }}>PRIMARY</span>}
                    {isExcel && <span className="tag" style={{ height: 14, padding: "0 4px", fontSize: 8.5 }}>XLS</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--ink-3)" }}>{f.description}</div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--ink-4)", marginTop: 4 }}>{f.filesize}</div>
                </a>
              );
            })}
          </div>
        </Section>

        <div style={{ marginTop: 80, paddingTop: 24, borderTop: "1px solid var(--rule)", fontFamily: "var(--mono)", fontSize: 11, color: "var(--ink-4)", display: "flex", justifyContent: "space-between" }}>
          <span>Analysis v1.0 · AI model · {t.documents ? t.documents.length : 0} documents indexed</span>
          <span>Tender #{t.id} · {t.no}</span>
        </div>
      </main>

      {/* PDF panel */}
      <CitationPanel
        snippet={snippet}
        page={page}
        file={t.sourcePdf || (t.documents && t.documents[0] ? t.documents[0].filename : "")}
        docUrl={t.documents && t.documents[0] ? t.documents[0].url : ""}
      />
    </div>
  );
}
window.DetailView = DetailView;
