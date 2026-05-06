/* global React */
const { useState, useRef, useEffect } = React;

// --- Icons (stroke-1.5, line-art, 16px) ---
const Icon = ({ d, size = 16, fill = "none", stroke = "currentColor", style, ...rest }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill={fill} stroke={stroke}
       strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={style} {...rest}>
    {typeof d === "string" ? <path d={d} /> : d}
  </svg>
);

const Icons = {
  search: <Icon d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16-4-4" />,
  filter: <Icon d="M3 5h18M6 12h12M10 19h4" />,
  sort: <Icon d="M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4" />,
  download: <Icon d="M12 4v12m0 0-4-4m4 4 4-4M5 20h14" />,
  bell: <Icon d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2H4.5L6 16zm3 4a3 3 0 0 0 6 0" />,
  more: <Icon d="M5 12h.01M12 12h.01M19 12h.01" />,
  back: <Icon d="M15 6l-6 6 6 6" />,
  fwd: <Icon d="M9 6l6 6-6 6" />,
  close: <Icon d="M6 6l12 12M6 18L18 6" />,
  rows: <Icon d="M4 6h16M4 12h16M4 18h16" />,
  cards: <Icon d="M4 6h7v6H4zM13 6h7v6h-7zM4 14h7v4H4zM13 14h7v4h-7z" />,
  table: <Icon d="M4 6h16M4 12h16M4 18h16M9 4v16M15 4v16" />,
  clock: <Icon d="M12 6v6l4 2M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" />,
  doc: <Icon d="M7 3h7l4 4v14H7V3zM14 3v4h4M9 13h6M9 17h4" />,
  tag: <Icon d="M3 12V4h8l9 9-8 8-9-9zm5-5v.01" />,
  chev: <Icon d="M6 9l6 6 6-6" />,
  pdf: <Icon d="M7 3h8l4 4v14H7V3zM15 3v4h4M9 12h2a1.5 1.5 0 0 1 0 3H9v3M14 12v6M14 12h2.5M14 15h2" />,
  copy: <Icon d="M7 7h10v13H7zM5 5h10v2M5 5v13h2" />,
  share: <Icon d="M4 12v7h16v-7M12 4v12m0-12-4 4m4-4 4 4" />,
  star: <Icon d="M12 4l2.5 5 5.5.8-4 3.9 1 5.5L12 16.5 7 19.2l1-5.5-4-3.9 5.5-.8z" />,
  pin: <Icon d="M12 17v5M9 4h6l-1 6 4 3H6l4-3z" />,
  link: <Icon d="M10 14a4 4 0 0 1 0-6l3-3a4 4 0 0 1 6 6l-1.5 1.5M14 10a4 4 0 0 1 0 6l-3 3a4 4 0 0 1-6-6l1.5-1.5" />,
  check: <Icon d="M5 12l5 5 9-11" />,
  alert: <Icon d="M12 8v5m0 3v.01M3 19h18L12 4 3 19z" />,
  flag: <Icon d="M5 3v18M5 4h13l-2 4 2 4H5" />,
  map: <Icon d="M9 4l-6 3v13l6-3 6 3 6-3V4l-6 3-6-3zM9 4v13M15 7v13" />,
  rupee: <Icon d="M7 5h11M7 9h11M7 5c4 0 7 1 7 4s-3 4-7 4l8 6" />,
  layers: <Icon d="M12 3l9 5-9 5-9-5 9-5zM3 13l9 5 9-5M3 18l9 5 9-5" />,
  highlight: <Icon d="M9 11l5 5-7 4-2-2 4-7zM9 11l7-7 5 5-7 7" />,
  zoom_in: <Icon d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16-4-4M11 8v6M8 11h6" />,
  zoom_out: <Icon d="M11 4a7 7 0 1 1 0 14 7 7 0 0 1 0-14zm9 16-4-4M8 11h6" />,
  external: <Icon d="M14 4h6v6M20 4l-9 9M10 6H4v14h14v-6" />,
  refresh: <Icon d="M4 12a8 8 0 0 1 14-5.2M20 12a8 8 0 0 1-14 5.2M4 6v5h5M15 13h5v5" />,
};
window.Icons = Icons;
window.Icon = Icon;

// --- Tag helpers ---
function StatusTag({ s }) {
  const cls = s === "active" ? "tag active" : "tag closed";
  return <span className={cls}>● {s}</span>;
}

function TypeTag({ t }) {
  const map = { "2-stage": "two", "single-stage": "one" };
  return <span className={`tag ${map[t] || ""}`}>{t || "unknown"}</span>;
}

function ConfTag({ c }) {
  return <span className={`tag ${c || "low"}`}>{(c || "low")} conf.</span>;
}
window.StatusTag = StatusTag;
window.TypeTag = TypeTag;
window.ConfTag = ConfTag;

// --- Number formatters ---
function fmtINR(cr) {
  if (!cr || cr === 0) return "—";
  if (cr >= 100) return `₹${(cr / 100).toFixed(2)} Kcr`;
  return `₹${cr.toFixed(2)} Cr`;
}
function fmtINRPlain(n) {
  return "₹" + n.toLocaleString("en-IN");
}

// FIXED: uses real Date.now() not hardcoded date
function daysUntil(iso) {
  if (!iso) return 0;
  const d = (new Date(iso) - Date.now()) / 86400000;
  return Math.round(d);
}

function fmtDate(iso, withTime = false) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const timeStr = withTime
      ? ` · ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`
      : "";
    return `${String(d.getDate()).padStart(2,"0")} ${months[d.getMonth()]} ${d.getFullYear()}${timeStr}`;
  } catch(e) {
    return iso;
  }
}
window.fmtINR = fmtINR;
window.fmtINRPlain = fmtINRPlain;
window.daysUntil = daysUntil;
window.fmtDate = fmtDate;

// --- Sparkline (simple) ---
function Spark({ data, color = "currentColor" }) {
  const w = 120, h = 28;
  const max = Math.max(...data), min = Math.min(...data);
  const sx = w / (data.length - 1);
  const sy = (v) => h - 2 - ((v - min) / (max - min || 1)) * (h - 4);
  const path = data.map((v, i) => `${i ? "L" : "M"}${(i*sx).toFixed(1)},${sy(v).toFixed(1)}`).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%" }}>
      <path d={path} fill="none" stroke={color} strokeWidth="1.2" />
      <path d={`${path} L${w},${h} L0,${h} Z`} fill={color} opacity="0.07" />
    </svg>
  );
}
window.Spark = Spark;

// --- Citation pill (the showcase interaction) ---
function Cite({ page, snippet, source = "RFP_787.pdf", onJump, active }) {
  const [open, setOpen] = useState(false);
  if (!page || page === 0) return null;
  return (
    <span className="cite-wrap" style={{ position: "relative", display: "inline-block" }}
          onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        className={"cite" + (active ? " active" : "")}
        onClick={(e) => { e.stopPropagation(); onJump && onJump(page, snippet); }}
        title={`Jump to page ${page}`}
      >
        p. {page}
      </button>
      {open && snippet && (
        <span className="cite-tip">
          <span className="src"><span>{source}</span><span>page {page}</span></span>
          <blockquote>"{snippet}"</blockquote>
          <span className="hint">Click chip → jump to page · highlights snippet</span>
        </span>
      )}
    </span>
  );
}
window.Cite = Cite;
