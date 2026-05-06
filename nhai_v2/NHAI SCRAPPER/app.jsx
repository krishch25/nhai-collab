/* global React, ReactDOM, Icons, ListView, DetailView, useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakSelect, TweakColor, TweakToggle */
const { useState: useStateA, useEffect: useEffectA } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "warm",
  "density": "normal",
  "accentHue": 100,
  "showSpark": true,
  "citation": "chip"
}/*EDITMODE-END*/;

function App() {
  const [view, setView] = useStateA("list"); // "list" | "detail"
  const [activeTenderId, setActiveTenderId] = useStateA(null);
  const [activeTab, setActiveTab] = useStateA("tenders");
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [tenderCount, setTenderCount] = useStateA(window.TENDERS.length);

  useEffectA(() => {
    document.documentElement.setAttribute("data-theme",
      tweaks.theme === "warm" ? "" :
      tweaks.theme === "cool" ? "cool" :
      tweaks.theme === "ink" ? "ink" : "");
    // EY yellow at hue ~100; other hues use higher chroma for vibrancy
    const isYellow = tweaks.accentHue >= 90 && tweaks.accentHue <= 115;
    document.documentElement.style.setProperty("--accent",
      isYellow ? "#FFE600" : `oklch(0.78 0.16 ${tweaks.accentHue})`);
    document.documentElement.style.setProperty("--accent-2",
      isYellow ? "#B8A400" : `oklch(0.58 0.14 ${tweaks.accentHue})`);
    document.documentElement.style.setProperty("--accent-soft",
      isYellow ? "#FFFBE0" : `oklch(0.96 0.04 ${tweaks.accentHue})`);
  }, [tweaks.theme, tweaks.accentHue]);

  // Listen for live data loaded from API
  useEffectA(() => {
    const handler = (e) => setTenderCount(e.detail.length);
    window.addEventListener("tendersLoaded", handler);
    return () => window.removeEventListener("tendersLoaded", handler);
  }, []);

  const openTender = (id) => {
    setActiveTenderId(id);
    setView("detail");
    window.scrollTo(0, 0);
  };

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand" onClick={() => setView("list")}>
          <div className="brand-mark">EY</div>
          <div>
            <div className="brand-text">NHAI Intelligence</div>
            <div className="brand-sub">EY Advisory · India</div>
          </div>
        </div>
        <nav className="topnav">
          <button className={activeTab === "tenders" ? "active" : ""} onClick={() => { setActiveTab("tenders"); setView("list"); }}>
            Tenders <span className="count">{tenderCount}</span>
          </button>
          <button className={activeTab === "memos" ? "active" : ""} onClick={() => setActiveTab("memos")}>
            Memos
          </button>
          <button className={activeTab === "compare" ? "active" : ""} onClick={() => setActiveTab("compare")}>
            Compare
          </button>
          <button className={activeTab === "alerts" ? "active" : ""} onClick={() => setActiveTab("alerts")}>
            Alerts
          </button>
        </nav>
        <div className="top-spacer" />
        <div className="searchbar" style={{width:260}}>
          <span style={{display:"flex",color:"var(--ink-4)"}}>{Icons.search}</span>
          <input placeholder="Search tenders, NH numbers, states…" />
          <span className="kbd">⌘K</span>
        </div>
        <button className="icon-btn" title="Notifications">{Icons.bell}</button>
        {/* Live status indicator */}
        <div style={{
          display:"flex",alignItems:"center",gap:6,
          padding:"4px 10px",borderRadius:6,
          background:"rgba(255,255,255,0.08)",border:"1px solid rgba(255,255,255,0.15)",
          fontSize:11,fontFamily:"var(--mono)",color:"rgba(255,255,255,0.55)"
        }}>
          <span style={{
            width:6,height:6,borderRadius:3,
            background:"var(--ok)",display:"inline-block",
            boxShadow:"0 0 4px var(--ok)"
          }} />
          nhai.gov.in live
        </div>
      </header>

      {view === "list"
        ? <ListView tweaks={tweaks} onOpen={openTender} tenderCount={tenderCount} />
        : <DetailView tweaks={tweaks} tenderId={activeTenderId} onBack={() => setView("list")} />}

      <TweaksPanel title="Tweaks">
        <TweakSection title="Theme">
          <TweakRadio label="Tone" value={tweaks.theme}
                      onChange={(v) => setTweak("theme", v)}
                      options={[{value:"warm",label:"Warm"},{value:"cool",label:"Cool"},{value:"ink",label:"Ink"}]} />
          <TweakSelect label="Citation style" value={tweaks.citation}
                      onChange={(v) => setTweak("citation", v)}
                      options={[{value:"chip",label:"Pill chip · p. N"},{value:"footnote",label:"Footnote ¹²³"},{value:"margin",label:"Margin annotation"}]} />
        </TweakSection>
        <TweakSection title="Layout">
          <TweakRadio label="Density" value={tweaks.density}
                      onChange={(v) => setTweak("density", v)}
                      options={[{value:"compact",label:"Compact"},{value:"normal",label:"Normal"},{value:"roomy",label:"Roomy"}]} />
          <TweakToggle label="Show sparklines" value={tweaks.showSpark} onChange={(v) => setTweak("showSpark", v)} />
        </TweakSection>
        <TweakSection title="Accent">
          <div style={{display:"flex",gap:8,marginTop:6}}>
            {[ {h:100,n:"EY Yellow"}, {h:195,n:"Teal"}, {h:230,n:"Slate"}, {h:30,n:"Terra"}, {h:340,n:"Madder"} ].map(({h,n}) => (
              <button key={h} title={n} onClick={() => setTweak("accentHue", h)}
                style={{
                  width:26,height:26,borderRadius:13,
                  background: (h >= 90 && h <= 115) ? "#FFE600" : `oklch(0.78 0.16 ${h})`,
                  border: tweaks.accentHue === h ? "2px solid var(--ink)" : "1px solid var(--rule)",
                  cursor:"pointer"
                }} />
            ))}
          </div>
        </TweakSection>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
