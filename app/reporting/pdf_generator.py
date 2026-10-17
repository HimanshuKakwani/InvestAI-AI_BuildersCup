"""InvestPI PDF Report Generator using ReportLab."""
import io
import base64
from typing import Dict, Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether, HRFlowable
)
from app.config import ROOT_DIR

# Colors matching InvestPI theme
DARK_BG = colors.HexColor("#0f172a")
PANEL_BG = colors.HexColor("#1e293b")
TEXT_LIGHT = colors.HexColor("#f8fafc")
TEXT_MUTED = colors.HexColor("#94a3b8")
ACCENT_BLUE = colors.HexColor("#38bdf8")
RED_FLAG = colors.HexColor("#ef4444")
ORANGE_FLAG = colors.HexColor("#f97316")
GREEN_FLAG = colors.HexColor("#22c55e")
BORDER_COLOR = colors.HexColor("#334155")

def build_pdf_report(data: Dict[str, Any], chart_b64: str = None) -> io.BytesIO:
    """
    Constructs a comprehensive, multi-page forensic audit PDF report containing:
    1. Header & Verdict Banner (with Traffic Light Flag & Score)
    2. Executive Summary of Audited Claim
    3. 5-Year Empirical Historical Price Chart with Target Overlay
    4. Detailed 9-Parameter Forensic Breakdown with Citing Sources
    5. Problematic AI Extractions & Regulatory Red Flags Section (Empty if clean green flag)
    6. Compliance Disclaimer & Official Regulatory Recourse Links
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0284c7")
    )

    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    table_body_style = ParagraphStyle(
        "TableBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#1e293b")
    )

    story = []

    # 1. Header
    report_id = data.get("report_id", "REP-001")
    region = data.get("region", "IN")
    market_name = data.get("market_name", "India")
    regulator = data.get("regulator", "SEBI")
    
    right_style = ParagraphStyle(
        "RightText",
        parent=body_style,
        alignment=2 # Right align
    )

    logo_file = ROOT_DIR / "static" / "investpi_logo.png"
    if logo_file.exists():
        logo_img = Image(str(logo_file), width=0.52*inch, height=0.52*inch)
        title_content = Table([
            [logo_img, Paragraph(f"<b>InvestPI Forensic Audit Report</b><br/><font size=8 color='#64748b'>Retail Investor Scam Defense Shield · AI Builder Cup</font>", title_style)]
        ], colWidths=[0.6*inch, 290])
        title_content.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        title_content = Paragraph(f"<b>InvestPI Forensic Audit Report</b><br/><font size=8 color='#64748b'>Retail Investor Scam Defense Shield · AI Builder Cup</font>", title_style)

    header_table = Table([
        [
            title_content,
            Paragraph(f"<font size=8><b>Report ID:</b> {report_id}<br/><b>Jurisdiction:</b> {market_name} ({regulator})<br/><b>Generated:</b> Automated Engine</font>", right_style)
        ]
    ], colWidths=[350, 190])
    header_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story.append(header_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=4, spaceAfter=10))

    # 2. Verdict Banner
    v = data.get("verdict", {})
    flag = v.get("flag", "HIGH_RISK")
    flag_label = v.get("flag_label", "High Risk")
    flag_badge = v.get("flag_badge", "🔴")
    score = v.get("score", 0.0)

    bg_color = colors.HexColor("#fee2e2") if flag == "HIGH_RISK" else (colors.HexColor("#dcfce7") if flag == "CONSISTENT" else colors.HexColor("#ffedd5"))
    border_col = RED_FLAG if flag == "HIGH_RISK" else (GREEN_FLAG if flag == "CONSISTENT" else ORANGE_FLAG)

    verdict_text = Paragraph(
        f"<font size=14><b>{flag_badge} {flag_label.upper()}</b></font><br/>"
        f"<font size=9 color='#475569'>Forensic Confidence Score: <b>{score:.1f} / 10</b> · Evaluated against 5-Year Empirical Distributions</font>",
        body_style
    )

    hard_gates = v.get("hard_gate_reasons", [])
    hg_html = ""
    if hard_gates:
        hg_html = "<br/><font color='#b91c1c'><b>Hard Gate Rejection Triggered:</b><br/>" + "<br/>".join([f"• {g}" for g in hard_gates]) + "</font>"

    verdict_card = Table([
        [
            verdict_text,
            Paragraph(f"<font size=20 color='{border_col.hexval()}'><b>{score:.1f}</b></font><font size=10 color='#64748b'>/10</font>", ParagraphStyle('ScoreR', parent=body_style, alignment=2))
        ],
        [
            Paragraph(hg_html, body_style) if hg_html else Paragraph("", body_style),
            ""
        ]
    ], colWidths=[420, 120])
    verdict_card.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), bg_color),
        ('BOX', (0, 0), (-1, -1), 1.5, border_col),
        ('PADDING', (0, 0), (-1, -1), 10),
        ('SPAN', (0, 1), (1, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(verdict_card)
    story.append(Spacer(1, 12))

    # 3. Audited Target Summary Table
    claim = data.get("claim", {})
    resolved = data.get("resolved_stock", {})
    target_price = claim.get("target_price")
    claimed_move = claim.get("claimed_percentage_move")
    horizon = claim.get("time_horizon_days", 14)
    creator = claim.get("creator_claimed_name") or "Unspecified Handle"
    quote = claim.get("exact_quote", "N/A")

    # Format claimed_move safely whether float, int, or string
    formatted_move = "Directional Breakout"
    if claimed_move is not None:
        try:
            val = float(str(claimed_move).replace("%", "").strip())
            formatted_move = f"+{val:.1f}% ({horizon} days horizon)"
        except Exception:
            formatted_move = f"{claimed_move} ({horizon} days horizon)"

    # Format target_price safely whether float, int, or string
    formatted_target = "Not explicit"
    if target_price is not None:
        try:
            t_val = float(str(target_price).replace(",", "").strip())
            formatted_target = f"{t_val:.2f}"
        except Exception:
            formatted_target = str(target_price)

    story.append(Paragraph("1. Audited Claim Overview", heading_style))
    summary_data = [
        [
            Paragraph("<b>Company / Security:</b>", table_body_style),
            Paragraph(f"{resolved.get('name', 'N/A')} ({resolved.get('ticker', 'N/A')})", table_body_style),
            Paragraph("<b>Claimed Move:</b>", table_body_style),
            Paragraph(formatted_move, table_body_style)
        ],
        [
            Paragraph("<b>Target Price:</b>", table_body_style),
            Paragraph(formatted_target, table_body_style),
            Paragraph("<b>Source / Handle:</b>", table_body_style),
            Paragraph(f"{creator}", table_body_style)
        ],
        [
            Paragraph("<b>Verbatim Quote:</b>", table_body_style),
            Paragraph(f"<i>\"{quote}\"</i>", table_body_style),
            Paragraph("<b>Timestamp:</b>", table_body_style),
            Paragraph(f"{claim.get('quote_timestamp', '00:00')}", table_body_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[110, 160, 110, 160])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP')
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # 4. Matplotlib Empirical Price Chart
    if chart_b64:
        story.append(Paragraph("2. 5-Year Empirical Historical Price & Target Verification", heading_style))
        img_data = base64.b64decode(chart_b64)
        img_buf = io.BytesIO(img_data)
        chart_img = Image(img_buf, width=7.2*inch, height=2.8*inch)
        story.append(chart_img)
        story.append(Spacer(1, 10))

    # 5. Full 9-Parameter Forensic Breakdown Table
    story.append(Paragraph("3. 9-Parameter Forensic Investigation Breakdown", heading_style))
    param_rows = [
        [
            Paragraph("<b>#</b>", table_header_style),
            Paragraph("<b>Parameter</b>", table_header_style),
            Paragraph("<b>Score</b>", table_header_style),
            Paragraph("<b>Status</b>", table_header_style),
            Paragraph("<b>Detailed Findings & Empirical Analysis</b>", table_header_style),
            Paragraph("<b>Authoritative Source</b>", table_header_style)
        ]
    ]

    source_map = {
        "price_move_realism": f"{market_name} EOD Daily Price Series (5-Yr Archive)",
        "valuation_range": "Exchange Quarterly & Annual Income Statements",
        "earnings_trajectory": "Quarterly Financial Disclosures & YoY Trajectory",
        "analyst_consensus": "Institutional Consensus Target Estimates",
        "promoter_holding": f"{regulator} Quarterly Shareholding Pattern Disclosures",
        "regulatory_orders": f"{regulator} Orders, Debarred List & Adjudications",
        "surveillance_volume": f"Exchange Daily Surveillance & ASM/GSM Lists",
        "licensing_check": f"{regulator} Official License Directory Snapshot",
        "hype_language": f"{market_name} Market Misconduct & Misleading Advice Lexicon"
    }

    params = data.get("parameters", [])
    for idx, p in enumerate(params, start=1):
        p_id = p.get("id", "")
        p_name = p.get("name", f"Param {idx}")
        score_val = f"{p['score']:.1f}/10" if p.get("score") is not None else "N/A"
        status_val = p.get("status", "N/A")
        explanation = p.get("explanation", "Evaluated based on empirical benchmarks.")
        source_name = source_map.get(p_id, f"Official {regulator} Public Records")

        status_color = "#16a34a" if status_val == "PASS" else ("#dc2626" if status_val == "FAIL" else "#d97706")

        param_rows.append([
            Paragraph(f"<b>P{idx}</b>", table_body_style),
            Paragraph(f"<b>{p_name}</b>", table_body_style),
            Paragraph(f"<b>{score_val}</b>", table_body_style),
            Paragraph(f"<font color='{status_color}'><b>{status_val}</b></font>", table_body_style),
            Paragraph(explanation, table_body_style),
            Paragraph(f"<font size=7 color='#64748b'>{source_name}</font>", table_body_style)
        ])

    param_table = Table(param_rows, colWidths=[24, 110, 42, 44, 210, 110])
    param_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")])
    ]))
    story.append(param_table)
    story.append(Spacer(1, 14))

    # 6. Flagged Problematic Findings Section (Empty if Green Flag)
    problematic_items = []
    
    # Check language hype phrases
    manipulative_phrases = claim.get("manipulative_phrases", [])
    for mp in manipulative_phrases:
        problematic_items.append(f"Manipulative Language: \"{mp.get('phrase')}\" ({mp.get('category')}) at {mp.get('timestamp', '00:00')}")

    if claim.get("guaranteed_return_language_detected"):
        problematic_items.append("Guaranteed Profit Claim: Video/text promises guaranteed returns, strictly prohibited under securities marketing regulations.")

    # Check hard gates and failed parameters
    for g in hard_gates:
        problematic_items.append(f"Hard Gate Breach: {g}")

    for p in params:
        if p.get("status") == "FAIL" and p.get("id") not in ["hype_language"]:
            problematic_items.append(f"{p['name']} Anomaly: {p['explanation']}")

    # Only render if NOT green / has problems
    if flag != "CONSISTENT" and len(problematic_items) > 0:
        story.append(Paragraph("4. Problematic Flags & Anomalies Picked Up by AI", heading_style))
        prob_rows = [[Paragraph("<b>The following deceptive, manipulative, or high-risk elements were flagged during forensic inspection:</b>", body_style)]]
        for pi in problematic_items:
            prob_rows.append([Paragraph(f"<font color='#b91c1c'><b>•</b></font> {pi}", body_style)])

        prob_table = Table(prob_rows, colWidths=[540])
        prob_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#fff1f2")),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#fca5a5")),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))
        story.append(prob_table)
        story.append(Spacer(1, 10))
    elif flag == "CONSISTENT":
        # Green Flag: Section omitted per requirement
        pass

    # 7. Regulatory Disclaimer & Official Reporting Links
    story.append(Paragraph("5. Regulatory Recourse & Legal Safe Harbor", heading_style))
    reporting_name = data.get("reporting_name", "Cybercrime Portal")
    reporting_url = data.get("reporting_url", "https://cybercrime.gov.in")
    disclaimer_text = (
        f"<b>Official Reporting Recourse:</b> If you suspect fraudulent market manipulation or unregistered solicitation, file an official complaint with <b>{reporting_name}</b> at <font color='#0284c7'><u>{reporting_url}</u></font>.<br/><br/>"
        "<b>Important Legal Disclaimer:</b> InvestPI is an AI-powered forensic research auditor designed to rate claim plausibility against publicly available regulatory and historical exchange data. InvestPI does not issue financial advice, stock recommendations, or buy/sell calls. All data points reflect historical distributions and public registries as of the report date."
    )
    story.append(Paragraph(disclaimer_text, ParagraphStyle("Disc", parent=body_style, fontSize=7.5, leading=10, textColor=colors.HexColor("#64748b"))))

    doc.build(story)
    buffer.seek(0)
    return buffer
