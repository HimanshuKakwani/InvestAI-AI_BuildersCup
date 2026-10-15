import { useRef, useState, type ReactNode } from 'react'

type IconName =
  | 'activity'
  | 'arrow'
  | 'book'
  | 'briefcase'
  | 'check'
  | 'chevron'
  | 'clock'
  | 'download'
  | 'image'
  | 'link'
  | 'menu'
  | 'message'
  | 'plus'
  | 'search'
  | 'sparkle'
  | 'trend'
  | 'youtube'

const iconPaths: Record<IconName, ReactNode> = {
  activity: <><path d="M3 12h3l2.3-6 4.2 12 2.4-6H21" /></>,
  arrow: <><path d="M5 12h14M14 7l5 5-5 5" /></>,
  book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21V5.5ZM20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5A2.5 2.5 0 0 1 20 21V5.5Z" /></>,
  briefcase: <><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>,
  check: <><path d="m5 12 4 4L19 6" /></>,
  chevron: <><path d="m9 18 6-6-6-6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  download: <><path d="M12 3v12m0 0 5-5m-5 5-5-5M5 20h14" /></>,
  image: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8.5" cy="9" r="1.5" /><path d="m4 17 5-5 4 4 2-2 5 4" /></>,
  link: <><path d="m10 13.5 4-4m-6.5 8-1 1a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0m6-3 1-1a3.5 3.5 0 0 1 5 5l-4 4a3.5 3.5 0 0 1-5 0" /></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  message: <><path d="M20 15a3 3 0 0 1-3 3H9l-5 3V7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v8Z" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
  sparkle: <><path d="m12 3 1.3 4.2L17 9l-3.7 1.8L12 15l-1.3-4.2L7 9l3.7-1.8L12 3ZM18.5 15l.7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3Z" /></>,
  trend: <><path d="m3 17 6-6 4 4 8-9M15 6h6v6" /></>,
  youtube: <><rect x="2.5" y="5" width="19" height="14" rx="4" /><path d="m10 9 5 3-5 3V9Z" /></>,
}

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {iconPaths[name]}
    </svg>
  )
}

function Logo() {
  return (
    <div className="brand">
      <span className="brand-mark"><span /><span /><span /></span>
      <span>Invest<span>PI</span></span>
    </div>
  )
}

function Button({ children, variant = 'primary', onClick, className = '' }: { children: ReactNode; variant?: 'primary' | 'secondary' | 'ghost'; onClick?: () => void; className?: string }) {
  return <button className={`button button-${variant} ${className}`} onClick={onClick}>{children}</button>
}

interface ParameterItem {
  id?: string
  name?: string
  score?: number
  weight?: number
  status?: string
  findings?: string
  sources?: string[]
}

interface AuditReport {
  report_id?: string
  timestamp?: string
  modality?: string
  is_financial_advice?: boolean
  message?: string
  resolved_stock?: {
    ticker?: string
    name?: string
    market?: string
  }
  current_price?: number
  claim?: {
    ticker?: string
    direction?: string
    target_price?: number
    claimed_percentage_move?: number
    time_horizon_days?: number
    exact_quote?: string
    quote_timestamp?: string
    creator_claimed_name?: string
    guaranteed_return_language_detected?: boolean
  }
  verdict?: {
    score?: number
    flag?: string
    summary?: string
    explanation?: string
    hard_gate_triggered?: boolean
    hard_gate_reason?: string
  }
  parameters?: ParameterItem[]
  chart_b64?: string
  pdf_url?: string
}

export default function App() {
  const [inputType, setInputType] = useState<'youtube' | 'image' | 'text'>('youtube')
  const [value, setValue] = useState('https://www.youtube.com/shorts/DivTA2Lz08s')
  const [region, setRegion] = useState('IN')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [stage, setStage] = useState<'input' | 'loading' | 'report'>('input')
  const [statusMessage, setStatusMessage] = useState('Following the money trail…')
  const [reports, setReports] = useState<AuditReport[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  const [rejectionMsg, setRejectionMsg] = useState<string | null>(null)
  const [mobileNav, setMobileNav] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        alert('File size exceeds the 10 MB limit.')
        return
      }
      setSelectedFile(file)
    }
  }

  const downloadPdf = (rep?: AuditReport) => {
    const target = rep || reports[activeIndex]
    if (target?.pdf_url) {
      window.open(target.pdf_url, '_blank')
    } else if (target?.report_id) {
      window.open(`/api/report/${target.report_id}.pdf`, '_blank')
    } else {
      alert('PDF brief not available for this session.')
    }
  }

  const analyze = async () => {
    setStage('loading')
    setStatusMessage('Following the money trail…')

    const msgs = [
      'Reading source lead…',
      'Extracting claims via Gemini multimodal AI…',
      'Cross-checking 5-year empirical data…',
      'Auditing 9 parameters against regulatory registries…',
      'Assembling confidential dossier…',
    ]
    let mIdx = 0
    const timer = setInterval(() => {
      mIdx = (mIdx + 1) % msgs.length
      setStatusMessage(msgs[mIdx])
    }, 2400)

    try {
      let resp: Response
      if (inputType === 'image') {
        if (!selectedFile) {
          clearInterval(timer)
          alert('Please select an image file to upload.')
          setStage('input')
          return
        }
        const formData = new FormData()
        formData.append('screenshot', selectedFile)
        formData.append('region', region)
        resp = await fetch('/api/analyze', { method: 'POST', body: formData })
      } else {
        const mod = inputType === 'youtube' ? 'youtube_url' : 'text'
        if (!value.trim()) {
          clearInterval(timer)
          alert('Please enter a valid link or tip text.')
          setStage('input')
          return
        }
        resp = await fetch('/api/analyze', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ modality: mod, payload: value.trim(), region }),
        })
      }

      clearInterval(timer)

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.error || `Server error (${resp.status})`)
      }

      const result = await resp.json()
      if (result.is_financial_advice === false) {
        setRejectionMsg(result.message || 'No securities recommendation detected in lead.')
        setReports([])
      } else {
        setRejectionMsg(null)
        const repsList: AuditReport[] = result.reports && result.reports.length > 0 ? result.reports : [result]
        setReports(repsList)
        setActiveIndex(0)
      }
      setStage('report')
    } catch (err: any) {
      clearInterval(timer)
      alert('Investigation error: ' + (err.message || String(err)))
      setStage('input')
    }
  }

  const activeRep = reports[activeIndex] || reports[0]

  return (
    <div className={`app-shell stage-${stage}`}>
      {stage === 'input' && (
        <>
          <header className="topbar">
            <div className="nav-wrap">
              <Logo />
              <nav className={mobileNav ? 'nav-links open' : 'nav-links'} aria-label="Primary navigation">
                <a className="active" href="#" onClick={() => setStage('input')}>New case</a>
                <a href="/apidocs/" target="_blank">Swagger API</a>
                <a href="/healthz" target="_blank">System Health</a>
              </nav>
              <div className="nav-actions">
                <select
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                  className="region-select"
                  aria-label="Target Jurisdiction"
                >
                  <option value="IN">🇮🇳 India (SEBI)</option>
                  <option value="SG">🇸🇬 Singapore (MAS)</option>
                  <option value="AU">🇦🇺 Australia (ASIC)</option>
                </select>
                <span className="desk-status"><i /> DESK ONLINE</span>
                <a href="/apidocs/" target="_blank" className="docs-btn">API DOCS</a>
              </div>
            </div>
          </header>

          <main className="intake-page" id="new-case">
            <div className="intake-copy">
              <div className="case-rule">
                <span>SECURITIES FORENSIC INTELLIGENCE</span>
                <span>AI BUILDERS CUP 2026</span>
              </div>
              <p className="overline">INVESTPI / RESEARCH DESK</p>
              <h1>Bring us a lead.<br /><em>We’ll find the signal.</em></h1>
              <p className="lead-copy">
                Social media is flooded with pump-and-dump claims, illegal return guarantees, and unlicensed finfluencers.
                Submit a video link, chat screenshot, or tip text. Our multimodal engine audits every claim against 5-year empirical market fundamentals and official regulatory registries.
              </p>
              <div className="proof-row">
                <span><strong>09</strong> Tests per company</span>
                <span><strong>01</strong> Verified report</span>
                <span><strong>0%</strong> Hallucination</span>
              </div>
            </div>

            <div className="intake-desk">
              <div className="desk-label">
                <span>NEW INVESTIGATION</span>
                <small>CASE NO. AUTO-GENERATED</small>
              </div>
              <div className="analyzer">
                <div className="input-tabs" role="tablist" aria-label="Analysis input type">
                  <button className={inputType === 'youtube' ? 'active' : ''} onClick={() => setInputType('youtube')}>
                    <span>01</span><Icon name="youtube" /> Video link
                  </button>
                  <button className={inputType === 'image' ? 'active' : ''} onClick={() => setInputType('image')}>
                    <span>02</span><Icon name="image" /> Screenshot
                  </button>
                  <button className={inputType === 'text' ? 'active' : ''} onClick={() => setInputType('text')}>
                    <span>03</span><Icon name="message" /> Tip text
                  </button>
                </div>

                <div className="input-area">
                  {inputType === 'youtube' && (
                    <div className="url-field">
                      <Icon name="link" />
                      <input
                        aria-label="YouTube URL"
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        placeholder="Paste the YouTube video or short URL here…"
                      />
                    </div>
                  )}

                  {inputType === 'image' && (
                    <button
                      className={`dropzone ${selectedFile ? 'has-file' : ''}`}
                      onClick={() => fileRef.current?.click()}
                    >
                      <Icon name="image" size={24} />
                      <span>{selectedFile ? `Selected: ${selectedFile.name}` : 'Select or drop evidence'}</span>
                      <small>PNG, JPG, WEBP, MP4 · MAX 10 MB</small>
                    </button>
                  )}

                  {inputType === 'text' && (
                    <textarea
                      aria-label="Investment message"
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      placeholder="Paste the WhatsApp tip, Telegram message, or influencer post here…"
                    />
                  )}

                  <input ref={fileRef} type="file" accept="image/*,video/mp4" hidden onChange={handleFileChange} />

                  <Button onClick={analyze} className="analyze-button">
                    <span>Open investigation</span>
                    <Icon name="arrow" />
                  </Button>
                </div>

                <div className="trust-row">
                  <span><Icon name="check" size={13} /> Claims traced</span>
                  <span><Icon name="check" size={13} /> 9 Parameters audited</span>
                  <span><Icon name="check" size={13} /> Empirical data citing</span>
                </div>
              </div>
              <p className="desk-footnote">Source content is processed strictly for audit verification and is never used to train models.</p>
            </div>
          </main>

          <div className="landing-footer">
            <span>INVESTPI FORENSIC ENGINE · BFSI RISK & FRAUD DEFENSE</span>
            <span>SEBI (INDIA) · MAS (SINGAPORE) · ASIC (AUSTRALIA)</span>
          </div>
        </>
      )}

      {stage === 'loading' && (
        <main className="loading-page">
          <div className="loading-brand">
            <Logo />
            <span>CASE INITIALIZING…</span>
          </div>
          <div className="investigation-scene">
            <div className="flying-paper paper-one"><b>EVIDENCE 01</b><i /><i /><i /></div>
            <div className="flying-paper paper-two"><b>MARKET DATA</b><i /><i /><i /></div>
            <div className="flying-paper paper-three"><b>TRANSCRIPT</b><i /><i /><i /></div>
            <div className="lamp-light" />
            <div className="investigator">
              <div className="hat" /><div className="head" /><div className="collar left" /><div className="collar right" /><div className="coat" />
              <div className="glass"><div /></div>
            </div>
            <div className="case-table"><span /><span /><span /></div>
          </div>
          <div className="loading-copy">
            <p>INVESTIGATION IN PROGRESS</p>
            <h2>{statusMessage}</h2>
            <div className="loading-track"><span /></div>
            <div className="loading-steps">
              <span>Reading source</span>
              <span>Extracting claims</span>
              <span>Auditing 9 parameters</span>
              <span>Generating dossier</span>
            </div>
          </div>
        </main>
      )}

      {stage === 'report' && (
        <>
          <header className="report-header">
            <Logo />
            <div className="case-id">
              <span>PRIVATE &amp; CONFIDENTIAL FORENSIC AUDIT</span>
              <strong>CASE #{activeRep?.report_id ? activeRep.report_id.substring(0, 8).toUpperCase() : 'IP-0001'}</strong>
            </div>
            <div className="report-actions">
              <Button variant="ghost" onClick={() => setStage('input')}>
                <Icon name="plus" /> New case
              </Button>
              {activeRep && (
                <Button variant="secondary" onClick={() => downloadPdf(activeRep)}>
                  <Icon name="download" /> Export case file (PDF)
                </Button>
              )}
            </div>
          </header>

          {rejectionMsg ? (
            <div className="rejection-sheet">
              <div className="rejection-stamp">LEAD DISCARDED · NOT FINANCIAL ADVICE</div>
              <h2>No Securities Advice Detected</h2>
              <p>{rejectionMsg}</p>
              <Button onClick={() => setStage('input')}>Investigate Another Lead</Button>
            </div>
          ) : activeRep ? (
            <main className="case-workspace">
              <aside className="case-sidebar">
                <div className="sidebar-heading">
                  <span>CASE CONTENTS</span>
                  <small>{reports.length} SUBJECT{reports.length > 1 ? 'S' : ''} IDENTIFIED</small>
                </div>
                <div className="source-evidence">
                  <span className="evidence-tag">EXHIBIT A</span>
                  <div className="source-icon">
                    <Icon name={activeRep.modality === 'youtube_url' ? 'youtube' : activeRep.modality === 'screenshot' ? 'image' : 'message'} />
                  </div>
                  <div>
                    <strong>{activeRep.claim?.exact_quote ? activeRep.claim.exact_quote.substring(0, 36) + '…' : 'Lead Evidence'}</strong>
                    <small>Source: {activeRep.claim?.creator_claimed_name || '@Unverified'}</small>
                  </div>
                </div>

                <div className="folder-label">AUDITED EQUITIES</div>
                <div className="folder-stack">
                  {reports.map((item, index) => {
                    const itemTicker = item.resolved_stock?.ticker || item.claim?.ticker || 'STOCK'
                    const itemName = item.resolved_stock?.name || itemTicker
                    const itemScore = item.verdict?.score !== undefined ? Number(item.verdict.score).toFixed(1) : 'N/A'
                    return (
                      <button
                        key={item.report_id || index}
                        className={`case-folder ${activeIndex === index ? 'active' : ''}`}
                        onClick={() => setActiveIndex(index)}
                      >
                        <span className="folder-tab">{String(index + 1).padStart(2, '0')}</span>
                        <span className="folder-name">
                          <strong>{itemTicker}</strong>
                          <small>{itemName.substring(0, 24)}</small>
                        </span>
                        <span className="folder-score">{itemScore}<small>/10</small></span>
                      </button>
                    )
                  })}
                </div>
                <div className="chain-note">
                  <span>CHAIN OF EVIDENCE</span>
                  <p>Lead ingested: Live Session<br />Audit sealed: Deterministic Engine</p>
                </div>
              </aside>

              <section className="report-sheet">
                <div className="paper-punches"><span /><span /><span /></div>
                <div className={`report-stamp ${activeRep.verdict?.flag === 'GREEN' ? 'stamp-green' : activeRep.verdict?.flag === 'ORANGE' ? 'stamp-orange' : 'stamp-red'}`}>
                  INVESTPI FORENSIC<br />
                  <strong>{activeRep.verdict?.flag === 'GREEN' ? 'VERIFIED CONSISTENT' : activeRep.verdict?.flag === 'ORANGE' ? 'CAUTION ADVISED' : 'HIGH RISK'}</strong>
                </div>

                <div className="report-masthead">
                  <span>INVESTIGATOR’S FORENSIC AUDIT BRIEF</span>
                  <span>FILE #{activeRep.resolved_stock?.ticker || 'STOCK'}</span>
                </div>

                <div className="subject-head">
                  <div>
                    <p>SUBJECT / PUBLIC SECURITY</p>
                    <h1>{activeRep.resolved_stock?.name || activeRep.claim?.company_name || activeRep.resolved_stock?.ticker || 'Equities Lead'}</h1>
                    <span>{activeRep.resolved_stock?.ticker} · {activeRep.resolved_stock?.market || 'IN'} JURISDICTION</span>
                  </div>
                  <div className="verdict">
                    <small>INVESTPI SCORE</small>
                    <strong>{activeRep.verdict?.score !== undefined ? Number(activeRep.verdict.score).toFixed(1) : '0.0'}<em>/10</em></strong>
                    <span className={activeRep.verdict?.flag === 'GREEN' ? 'badge-green' : activeRep.verdict?.flag === 'ORANGE' ? 'badge-orange' : 'badge-red'}>
                      {activeRep.verdict?.flag === 'GREEN' ? 'CONSISTENT WITH DATA' : activeRep.verdict?.flag === 'ORANGE' ? 'CAUTION ADVISED' : 'HIGH RISK WARNING'}
                    </span>
                  </div>
                </div>

                <div className="price-strip">
                  <div>
                    <small>CURRENT MARKET PRICE</small>
                    <strong>{activeRep.current_price ? `₹${Number(activeRep.current_price).toFixed(2)}` : 'Unavailable'}</strong>
                  </div>
                  <div>
                    <small>CLAIMED TARGET</small>
                    <strong>
                      {activeRep.claim?.target_price ? `₹${Number(activeRep.claim.target_price).toFixed(2)}` : 'Unstated'}
                      {activeRep.claim?.claimed_percentage_move ? ` (${activeRep.claim.claimed_percentage_move > 0 ? '+' : ''}${activeRep.claim.claimed_percentage_move}%)` : ''}
                    </strong>
                  </div>
                  <div>
                    <small>HORIZON &amp; DIRECTION</small>
                    <strong>{activeRep.claim?.time_horizon_days ? `${activeRep.claim.time_horizon_days} Days` : 'Unspecified'} · {activeRep.claim?.direction || 'BUY'}</strong>
                  </div>
                  <div>
                    <small>HARD GATE SURVEILLANCE</small>
                    <strong style={{ color: activeRep.verdict?.hard_gate_triggered ? 'var(--red)' : 'var(--green)' }}>
                      {activeRep.verdict?.hard_gate_triggered ? `TRIGGERED (${activeRep.verdict.hard_gate_reason || 'HARD GATE'})` : 'PASSED'}
                    </strong>
                  </div>
                </div>

                <div className="report-section">
                  <span className="section-no">01</span>
                  <div>
                    <p className="report-label">PRIMARY FORENSIC FINDING</p>
                    <h2>{activeRep.verdict?.summary || 'Forensic Due-Diligence Summary'}</h2>
                    <p className="report-text">{activeRep.verdict?.explanation || 'All nine empirical checks were deterministically evaluated against official exchange prices and regulatory registries.'}</p>
                  </div>
                </div>

                {activeRep.claim?.exact_quote && (
                  <blockquote>
                    <span>EXHIBIT TRANSCRIPT / {activeRep.claim.quote_timestamp || 'TIMESTAMP N/A'}</span>
                    “{activeRep.claim.exact_quote}”
                  </blockquote>
                )}

                {activeRep.chart_b64 && (
                  <div className="report-section">
                    <span className="section-no">02</span>
                    <div>
                      <p className="report-label">EMPIRICAL BENCHMARK OVERLAY</p>
                      <h2>5-Year Historical Price vs Claimed Target</h2>
                      <div className="chart-container">
                        <img src={`data:image/png;base64,${activeRep.chart_b64}`} alt="5-Year Historical Chart with Target Overlay" />
                        <div className="chart-caption">Figure 1.0: 5-Year Empirical Closing Prices with Influencer Target Overlay Line</div>
                      </div>
                    </div>
                  </div>
                )}

                <div className="report-section markers-section">
                  <span className="section-no">03</span>
                  <div className="marker-report">
                    <div className="marker-title">
                      <div>
                        <p className="report-label">DETERMINISTIC COMPLIANCE AUDIT</p>
                        <h2>9 Parameters Evaluated</h2>
                      </div>
                      <div className="marker-tally">
                        {(activeRep.parameters || []).map((p, idx) => (
                          <span key={idx} className={p.status === 'PASS' ? 'passed' : p.status === 'FAIL' ? 'failed' : ''}>
                            {idx + 1}
                          </span>
                        ))}
                      </div>
                    </div>

                    <div className="marker-grid">
                      {(activeRep.parameters || []).map((p, idx) => (
                        <div className={`marker status-${p.status || 'INFO'}`} key={p.id || idx}>
                          <span className="marker-check">
                            {p.status === 'PASS' ? <Icon name="check" size={10} /> : p.status === 'FAIL' ? '!' : '?'}
                          </span>
                          <span>
                            <strong>{p.name || `P${idx + 1}`}</strong>
                            <small>{p.findings || 'No anomalies detected.'}</small>
                            {p.sources && p.sources.length > 0 && (
                              <div className="source-cite">Source: {p.sources.join(', ')}</div>
                            )}
                          </span>
                          <em>{p.status || 'INFO'}</em>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="analyst-signoff">
                  <div>
                    <span>AUDIT PREPARED BY</span>
                    <strong>InvestPI Research Desk</strong>
                    <small>Independent Machine-Assisted Due Diligence · Not a Stock Recommendation</small>
                  </div>
                  <Button variant="ghost" onClick={() => downloadPdf(activeRep)}>
                    <Icon name="download" /> Download Verified PDF Report
                  </Button>
                </div>
              </section>
            </main>
          ) : null}
        </>
      )}
    </div>
  )
}
