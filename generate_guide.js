// Commander Recovery Screener — User Guide Generator
// Run: node generate_guide.js

const docxPath = 'C:/Users/jayra/AppData/Roaming/npm/node_modules/docx';
const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    Header, Footer, AlignmentType, HeadingLevel, LevelFormat,
    BorderStyle, WidthType, ShadingType, VerticalAlign,
    PageNumber, PageBreak, ExternalHyperlink
} = require(docxPath);
const fs = require('fs');

// ─── Colour palette ───────────────────────────────────────────────────────────
const NAVY  = "1B3A6B";   // primary heading
const TEAL  = "0D6E6E";   // accent
const AMBER = "B45309";   // warning
const GREEN = "166534";   // success / callout
const LGRAY = "F3F4F6";   // table zebra
const MGRAY = "E5E7EB";   // table header bg
const DKGRAY= "6B7280";   // muted text

// ─── Border helpers ───────────────────────────────────────────────────────────
function bdr(color="CCCCCC", size=4) {
    return { style: BorderStyle.SINGLE, size, color };
}
const NO_BORDER = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const ALL_NONE = { top: NO_BORDER, bottom: NO_BORDER, left: NO_BORDER, right: NO_BORDER };

// ─── Paragraph helpers ────────────────────────────────────────────────────────
function h1(text) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_1,
        spacing: { before: 300, after: 120 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: NAVY, space: 4 } },
        children: [new TextRun({ text, font: "Arial", size: 28, bold: true, color: NAVY })]
    });
}

function h2(text) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 240, after: 80 },
        children: [new TextRun({ text, font: "Arial", size: 24, bold: true, color: TEAL })]
    });
}

function h3(text) {
    return new Paragraph({
        heading: HeadingLevel.HEADING_3,
        spacing: { before: 180, after: 60 },
        children: [new TextRun({ text, font: "Arial", size: 22, bold: true, color: NAVY })]
    });
}

function body(text, opts={}) {
    return new Paragraph({
        spacing: { before: opts.before || 60, after: opts.after || 80 },
        children: [new TextRun({ text, font: "Arial", size: 20, color: opts.color || "000000", bold: opts.bold || false, italics: opts.italic || false })]
    });
}

function bodyRuns(runs, opts={}) {
    return new Paragraph({
        spacing: { before: opts.before || 60, after: opts.after || 80 },
        children: runs
    });
}

function run(text, opts={}) {
    return new TextRun({ text, font: "Arial", size: opts.size || 20,
        bold: opts.bold || false, italics: opts.italic || false,
        color: opts.color || "000000" });
}

function bullet(text, level=0) {
    const indent = level === 0 ? { left: 600, hanging: 300 } : { left: 1000, hanging: 300 };
    return new Paragraph({
        numbering: { reference: "bullets", level },
        spacing: { before: 40, after: 40 },
        indent,
        children: [new TextRun({ text, font: "Arial", size: 20 })]
    });
}

function numbered(text, level=0) {
    return new Paragraph({
        numbering: { reference: "numbers", level },
        spacing: { before: 60, after: 60 },
        indent: { left: 600, hanging: 300 },
        children: [new TextRun({ text, font: "Arial", size: 20 })]
    });
}

function numberedRuns(runs, level=0) {
    return new Paragraph({
        numbering: { reference: "numbers", level },
        spacing: { before: 60, after: 60 },
        indent: { left: 600, hanging: 300 },
        children: runs
    });
}

function space(n=1) {
    return new Paragraph({ children: [new TextRun("")], spacing: { before: 0, after: n * 80 } });
}

function pageBreak() {
    return new Paragraph({ children: [new PageBreak()] });
}

// ─── Callout box (bordered paragraph) ────────────────────────────────────────
function callout(label, text, fillColor=LGRAY, labelColor=NAVY) {
    const border = bdr("AAAAAA", 6);
    const borders = { top: border, bottom: border, left: { style: BorderStyle.SINGLE, size: 24, color: labelColor }, right: border };
    return new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [9360],
        margins: { top: 0, bottom: 0, left: 0, right: 0 },
        rows: [
            new TableRow({ children: [
                new TableCell({
                    borders,
                    width: { size: 9360, type: WidthType.DXA },
                    shading: { fill: fillColor, type: ShadingType.CLEAR },
                    margins: { top: 100, bottom: 100, left: 200, right: 200 },
                    children: [
                        new Paragraph({ spacing: { before: 0, after: 40 }, children: [
                            new TextRun({ text: label, font: "Arial", size: 20, bold: true, color: labelColor })
                        ]}),
                        new Paragraph({ spacing: { before: 0, after: 0 }, children: [
                            new TextRun({ text, font: "Arial", size: 20 })
                        ]})
                    ]
                })
            ]})
        ]
    });
}

// ─── Table builder ────────────────────────────────────────────────────────────
function makeTable(headers, rows, colWidths) {
    const totalW = colWidths.reduce((a,b) => a+b, 0);
    const hdrBorder = { style: BorderStyle.SINGLE, size: 4, color: "AAAAAA" };
    const hdrBorders = { top: hdrBorder, bottom: hdrBorder, left: hdrBorder, right: hdrBorder };

    const headerRow = new TableRow({
        tableHeader: true,
        children: headers.map((h, i) => new TableCell({
            borders: hdrBorders,
            width: { size: colWidths[i], type: WidthType.DXA },
            shading: { fill: NAVY, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            children: [new Paragraph({ alignment: AlignmentType.LEFT, children: [
                new TextRun({ text: h, font: "Arial", size: 18, bold: true, color: "FFFFFF" })
            ]})]
        }))
    });

    const dataRows = rows.map((row, ri) => new TableRow({
        children: row.map((cell, i) => {
            const isArray = Array.isArray(cell);
            const cellText = isArray ? cell[0] : cell;
            const cellBold = isArray ? (cell[1] || false) : false;
            const cellColor = isArray ? (cell[2] || "000000") : "000000";
            return new TableCell({
                borders: { top: bdr(), bottom: bdr(), left: bdr(), right: bdr() },
                width: { size: colWidths[i], type: WidthType.DXA },
                shading: { fill: ri % 2 === 0 ? "FFFFFF" : LGRAY, type: ShadingType.CLEAR },
                margins: { top: 60, bottom: 60, left: 120, right: 120 },
                children: [new Paragraph({ children: [
                    new TextRun({ text: cellText, font: "Arial", size: 18, bold: cellBold, color: cellColor })
                ]})]
            });
        })
    }));

    return new Table({
        width: { size: totalW, type: WidthType.DXA },
        columnWidths: colWidths,
        rows: [headerRow, ...dataRows]
    });
}

// ─── Cover page ───────────────────────────────────────────────────────────────
function coverPage() {
    return [
        space(8),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 0, after: 160 },
            children: [new TextRun({ text: "WEINSTEIN COMMANDER", font: "Arial", size: 48, bold: true, color: NAVY })]
        }),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 0, after: 80 },
            children: [new TextRun({ text: "Commander Recovery Screener", font: "Arial", size: 36, bold: true, color: TEAL })]
        }),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 0, after: 240 },
            children: [new TextRun({ text: "User Guide", font: "Arial", size: 36, color: DKGRAY })]
        }),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: TEAL, space: 4 } },
            spacing: { before: 0, after: 240 },
            children: [new TextRun({ text: "", font: "Arial", size: 20 })]
        }),
        space(2),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 0, after: 80 },
            children: [new TextRun({ text: "Version 1.0  |  April 2026", font: "Arial", size: 22, color: DKGRAY })]
        }),
        new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 0, after: 80 },
            children: [new TextRun({ text: "For NSE / BSE Swing & Positional Traders", font: "Arial", size: 22, italic: true, color: DKGRAY })]
        }),
        space(2),
        new Table({
            width: { size: 9360, type: WidthType.DXA },
            columnWidths: [9360],
            rows: [new TableRow({ children: [new TableCell({
                borders: { top: bdr(AMBER, 10), bottom: bdr(AMBER, 10), left: bdr(AMBER, 10), right: bdr(AMBER, 10) },
                width: { size: 9360, type: WidthType.DXA },
                shading: { fill: "FEF3C7", type: ShadingType.CLEAR },
                margins: { top: 120, bottom: 120, left: 200, right: 200 },
                children: [
                    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 40 }, children: [
                        new TextRun({ text: "IMPORTANT", font: "Arial", size: 20, bold: true, color: AMBER })
                    ]}),
                    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 0 }, children: [
                        new TextRun({ text: "This tool is for educational and research purposes only. It does not constitute financial advice. Always conduct your own due diligence before trading.", font: "Arial", size: 18, color: AMBER })
                    ]})
                ]
            })]})],
        }),
        pageBreak()
    ];
}

// ─── Section 1: Overview ──────────────────────────────────────────────────────
function section1() {
    return [
        h1("1. System Overview"),
        body("The Commander Recovery Screener is a two-stage NSE stock screening system designed for swing and positional traders operating in post-correction or recovery market environments. It identifies high-conviction recovery setups through a combination of Chartink technical pre-screening and a Python-based fundamental and edge-detection engine."),
        space(),
        h2("1.1 What Is the Recovery Screener?"),
        body("Standard Weinstein Stage 2 scanners (Scanners 1-4) are designed for healthy bull markets where stocks are making new highs. They fail to generate results during sharp macro-driven corrections (e.g., geopolitical shocks, rate hikes) when the market is in Stage 4 decline or Stage 1 basing. The Recovery Screener fills this gap by identifying three distinct edges that outperform during recovery phases."),
        space(),
        h2("1.2 The Two-Stage Architecture"),
        makeTable(
            ["Stage", "Tool", "Purpose", "Output"],
            [
                ["Stage 1 — Pre-filter", "Chartink Scanners (5, 6, 7)", "Wide candidate net using technical conditions", "10-30 NSE stocks per scanner"],
                ["Stage 2 — Deep Filter", "Python Recovery Screener", "Full edge detection, signal hold window, RFF fundamentals, Mansfield RS, Weinstein Stage", "Recovery_Screener_Results.csv"]
            ],
            [1800, 2500, 2800, 2260]
        ),
        space(),
        h2("1.3 The Three Recovery Edges"),
        makeTable(
            ["Edge", "Signal Code", "What It Catches", "Market Context"],
            [
                [["REV-EARLY", true], "4 (highest)", "Stocks near golden cross with VCP base + pivot breakout", "Early recovery leaders"],
                [["REV-RS", true], "3", "RS Survivors with 20-day structural breakout + volume", "Relative strength leaders during selloff"],
                [["REV-CB", true], "2", "Four-pillar climax bottom bounce after capitulation", "Deep oversold reversal plays"],
                ["CB-Watch", "1", "Climax detected but no turn candle yet — monitor list", "Pre-signal watchlist"],
            ],
            [1800, 1800, 3200, 2560]
        ),
        space(),
        h2("1.4 Why Use a Signal Hold Window?"),
        body("A critical innovation in this system is the Signal Hold Window (default: 5 trading days). This solves a fundamental problem for post-market traders:"),
        bullet("Chartink scanners run intraday and use same-day conditions. By end of day, the exact candle conditions may no longer match."),
        bullet("The Python screener checks whether a valid signal fired in the last N trading days, not just today. Signals remain visible all weekend and into the following week."),
        bullet("This means you can run the pipeline on Friday evening and still see valid Monday setups on Saturday or Sunday."),
        space(),
        callout("KEY INSIGHT", "The Chartink scanners are wide candidate nets — they flag stocks for deeper analysis. The Python screener is the final judge that applies strict multi-pillar logic, fundamental filters, and the signal hold window.", "EFF6FF", NAVY),
        space()
    ];
}

// ─── Section 2: Three Chartink Scanners ───────────────────────────────────────
function section2() {
    return [
        pageBreak(),
        h1("2. The Three Chartink Recovery Scanners"),
        body("All three recovery scanners operate exclusively on the NSE CNX 500 universe ({57960}). They are deliberately designed as loose pre-filters — the strict conditions are enforced downstream by the Python screener."),
        space(),

        h2("2.1 Scanner 5 — REV-RS: RS Survivor Breakout"),
        makeTable(
            ["Condition", "Chartink Logic", "Purpose"],
            [
                ["RS Line > 30W SMA", "weekly close / rs:'nifty500' weekly close > weekly sma(..., 30)", "Mansfield RS positive — outperforming CNX500"],
                ["Price > SMA50", "daily close > daily sma(daily close, 50)", "Stock in short-term uptrend (recovering)"],
                ["Off 52W High >=8%", "daily close < daily max(250, daily high) * 0.92", "Still in correction zone — not extended"],
                ["Volume Activity", "daily volume > daily sma(daily volume, 50) * 1.2", "Institutional presence (relaxed 1.2x)"],
                ["Anti-Penny", "daily close > 20", "Minimum price floor: above Rs. 20"]
            ],
            [2000, 4500, 2860]
        ),
        space(),
        callout("DESIGN NOTE — Why No SMA50 < SMA200 Gate?", "RS Survivors often held up so well during the selloff that they never had a death cross — they may already be in Stage 2. Adding SMA50<SMA200 blocked all valid RS survivors during the April 2026 correction. The Python screener handles this nuance by checking Weinstein Stage independently.", "EFF6FF", NAVY),
        space(),
        body("Output file: Recovery_RS_Survivors.csv", { bold: true }),
        body("The Python screener then applies the strict 20-day breakout (close > highest high of prior 20 days) with 1.5x volume confirmation and the signal hold window."),
        space(),

        h2("2.2 Scanner 6 — REV-CB: Climax Bottom Bounce"),
        makeTable(
            ["Condition", "Chartink Logic", "Purpose"],
            [
                [">=10% Below SMA200", "daily close < daily sma(daily close, 200) * 0.90", "Stock in recovery zone (stretched down)"],
                ["RSI14 < 40", "daily rsi(14) < 40", "Oversold or recently recovered from oversold"],
                ["Anti-Penny", "daily close > 20", "Minimum price floor"]
            ],
            [2000, 4500, 2860]
        ),
        space(),
        callout("DESIGN NOTE — Why Such Wide Conditions?", "The original Scanner 6 required RSI3<15 + RSI14<30 + 2.5x volume all on the same bar — this caught stocks during the exact capitulation moment (e.g., April 4-7 shock) but returned zero results in the days/weeks after. The scanner was redesigned to catch the aftermath: stocks that already had their capitulation event and are now stabilising. The four-pillar logic (RSI3<15, RSI14<30, 2.5x volume climax, turn candle) is enforced by the Python screener with a 10-day lookback window.", "FEF3C7", AMBER),
        space(),
        body("Output file: Recovery_Climax_Bounce.csv", { bold: true }),
        space(),

        h2("2.3 Scanner 7 — REV-EARLY: Early Bird VCP"),
        makeTable(
            ["Condition", "Chartink Logic", "Purpose"],
            [
                ["Near Golden Cross", "daily sma(close, 50) >= daily sma(close, 200) * 0.92", "SMA50 within 8% of SMA200 (or already above)"],
                ["Price > SMA50", "daily close > daily sma(daily close, 50)", "Price above 50-day MA"],
                ["Price > SMA150", "daily close > daily sma(daily close, 150)", "Trend structure intact"],
                ["Mansfield RS Positive", "weekly close / rs:'nifty500' weekly close > sma(..., 30)", "Outperforming CNX500"],
                ["VCP Dry-up", "daily sma(volume, 5) < daily sma(volume, 50)", "Base compressing quietly — 5D avg < 50D avg"],
                ["Anti-Penny", "daily close > 20", "Minimum price floor"]
            ],
            [2000, 4500, 2860]
        ),
        space(),
        callout("DESIGN NOTE — Why No Volume Expansion in Chartink?", "The original scanner required VCP dry-up (5D vol < 50D vol) AND today's volume expansion (>1.5x) on the same bar — contradictory conditions that produced only 1 result. The scanner now captures stocks IN the base (dry-up confirmed). The pivot breakout with volume expansion is checked by the Python screener using a 15-day lookback with the signal hold window.", "EFF6FF", NAVY),
        space(),
        body("Output file: Recovery_Early_Birds.csv", { bold: true }),
        space()
    ];
}

// ─── Section 3: Python Recovery Screener ─────────────────────────────────────
function section3() {
    return [
        pageBreak(),
        h1("3. Python Recovery Screener — In Depth"),
        body("The Python screener (recovery_screener.py) is the intelligence layer. It reads the Chartink CSVs, downloads 400 days of EOD OHLCV from Yahoo Finance, and applies strict multi-pillar conditions with full indicator computation."),
        space(),

        h2("3.1 Data Sources"),
        makeTable(
            ["Source", "Files", "Role"],
            [
                ["Chartink Scanners", "Recovery_RS_Survivors.csv\nRecovery_Climax_Bounce.csv\nRecovery_Early_Birds.csv", "Primary candidate universe (10-30 stocks)"],
                ["Screener.in (optional)", "SCREENER_Recovery_RSLeaders.csv\nSCREENER_Recovery_ClimaxBounce.csv\nSCREENER_Recovery_EarlyBirds.csv", "RFF fundamental data lookup + [SI] intersection tag"],
                ["Yahoo Finance (live)", "Downloaded at runtime via yfinance", "EOD OHLCV for 400 days (daily) + weekly data for Mansfield RS"]
            ],
            [2000, 3500, 3860]
        ),
        space(),
        callout("IMPORTANT — Screener.in Files Are Optional", "If SCREENER_Recovery_*.csv files are missing, the screener runs without RFF fundamentals. Stocks will show 'Not in Screener.in recovery screens' and the [SI] intersection tag will not be applied. Run Screener.in fetches for full fundamental scoring.", "EFF6FF", NAVY),
        space(),

        h2("3.2 The Three-Way Regime Gate"),
        body("The regime gate protects you from chasing recovery setups when the market is still in a downtrend. A signal is only valid if at least one of three conditions is met:"),
        makeTable(
            ["Gate", "Condition", "Logic"],
            [
                ["A — Death Cross", "CNX500 SMA50 < SMA200", "Market in classic recovery phase (death cross present)"],
                ["B — Correction Depth", "CNX500 >= 7% off 52W high", "Post-shock correction — SMA may not have crossed yet"],
                ["C — Stock Correction", "Individual stock >= 10% off its 52W high", "Per-symbol bypass — stock corrected even if market hasn't"]
            ],
            [1800, 3500, 4060]
        ),
        space(),
        body("Gate C enables stocks that have already staged strong personal corrections to qualify even when the broad market is healthy. This allows the system to find sector-specific recovery plays during rolling corrections."),
        space(),

        h2("3.3 Edge Detection Logic"),

        h3("3.3.1 REV-CB: Four-Pillar Climax Bottom Bounce"),
        body("The tightest and most rule-based of the three edges. All four pillars must be present:"),
        makeTable(
            ["Pillar", "Condition", "Value"],
            [
                ["1 — Stretch", "Close <= SMA200 x (1 - stretch_pct)", "Stock >= 15% below 200-day SMA"],
                ["2 — Washout", "RSI14 < 30 AND RSI3 < 15", "Dual RSI confirms capitulation"],
                ["3 — Climax Volume", "Volume >= 2.5x 50-day avg AND (red candle OR wide range > 1.5x ATR)", "Institutional selling climax"],
                ["4 — Turn Candle", "Green bar, closes in top 40% of range, breaks prior day's high", "First sign of demand absorption"]
            ],
            [2000, 3600, 3760]
        ),
        space(),
        body("Signal logic: Signal=2 (REV-CB Buy) if climax fired within 10 days AND turn candle fired within 5 days. Signal=1 (CB-Watch) if climax is active but no turn yet."),
        space(),

        h3("3.3.2 REV-RS: RS Survivor Structural Breakout"),
        body("Targets stocks with positive Mansfield RS that have held up during the selloff and are now breaking out of a 20-day structure:"),
        bullet("Mansfield RS must be positive (RS Line > 26W SMA of RS Line)"),
        bullet("Stock must be above SMA50 today (position still valid)"),
        bullet("Within the last 5 trading days: close > highest high of prior 20 days AND volume >= 1.5x 50-day average"),
        bullet("Regime gate: market in recovery OR stock off 10%+ from 52W high"),
        space(),
        body("No SMA50 < SMA200 requirement. RS Survivors may already be in Stage 2 and should not be penalised for it."),
        space(),

        h3("3.3.3 REV-EARLY: Early Bird VCP Near Golden Cross"),
        body("Catches stocks that are compressing into a tight VCP base and breaking out just as the golden cross (SMA50 crossing SMA200) approaches or occurs:"),
        bullet("SMA50 >= SMA200 x 0.95 (within 5% of golden cross or already above)"),
        bullet("Price > SMA50 AND SMA150 (trend structure intact)"),
        bullet("ATR(10) < ATR_avg(50) x 1.5 (base is tightening — VCP compression)"),
        bullet("5-day volume average before the bar < 50-day volume average (dry-up confirmed)"),
        bullet("Close > highest high of prior 15 days (pivot breakout)"),
        bullet("Volume >= 1.5x 50-day average on breakout bar"),
        space(),

        h2("3.4 Mansfield RS Calculation"),
        body("The screener computes a proper Mansfield RS score using weekly OHLCV data:"),
        new Table({
            width: { size: 9360, type: WidthType.DXA },
            columnWidths: [9360],
            rows: [new TableRow({ children: [new TableCell({
                borders: { top: bdr(TEAL, 8), bottom: bdr(TEAL, 8), left: bdr(TEAL, 8), right: bdr(TEAL, 8) },
                width: { size: 9360, type: WidthType.DXA },
                shading: { fill: "F0FDF4", type: ShadingType.CLEAR },
                margins: { top: 100, bottom: 100, left: 200, right: 200 },
                children: [
                    new Paragraph({ spacing: { before: 0, after: 40 }, children: [new TextRun({ text: "Mansfield RS Formula", font: "Courier New", size: 19, bold: true, color: GREEN })]}),
                    new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text: "RS_Line  = Stock_Weekly_Close / CNX500_Weekly_Close", font: "Courier New", size: 19, color: "000000" })]}),
                    new Paragraph({ spacing: { before: 0, after: 0 }, children: [new TextRun({ text: "Mansfield_RS = (RS_Line / SMA26_of_RS_Line - 1) x 10", font: "Courier New", size: 19, color: "000000" })]}),
                    new Paragraph({ spacing: { before: 20, after: 0 }, children: [new TextRun({ text: "Positive = Outperforming CNX500 | Negative = Lagging CNX500", font: "Arial", size: 18, italic: true, color: DKGRAY })]})
                ]
            })]})],
        }),
        space(),

        h2("3.5 Recovery Fundamental Filter (RFF)"),
        body("The RFF applies 6 checks to weed out financially weak companies that are technically setting up for a recovery that never materialises. Data comes from Screener.in exports:"),
        makeTable(
            ["Check", "Metric", "Threshold", "Rationale"],
            [
                ["NI > 0", "Net Profit (TTM)", "Positive", "Company must be profitable — no terminal declines"],
                ["OCF > 0", "Operating Cash Flow", "Positive", "Real cash earnings, not accounting profits"],
                ["ICR > 2", "Interest Coverage Ratio", "Greater than 2x", "Can comfortably service debt"],
                ["D/E < 2", "Debt to Equity", "Less than 2.0", "Not over-leveraged"],
                ["CR > 1", "Current Ratio", "Greater than 1.0", "Short-term solvency adequate"],
                ["ROA > 5%", "Return on Assets", "Greater than 5%", "Efficient asset utilisation"]
            ],
            [1200, 2200, 1600, 4360]
        ),
        space(),
        body("RFF Score ranges from 0-6. The minimum passing score is set by rff_min_score (default: 1). A score of 6/6 indicates a financially sound company. If Screener.in data is unavailable, the RFF is marked as unverified and the stock still passes."),
        space(),

        h2("3.6 Composite Score (0-21 Points)"),
        makeTable(
            ["Component", "Points", "Condition"],
            [
                ["Signal Quality", "0-3", "REV-EARLY=3, REV-RS=2, REV-CB=1, CB-Watch=0"],
                ["RFF Fundamental Score", "0-6", "1 point per passing RFF check (NI, OCF, ICR, D/E, CR, ROA)"],
                ["Mansfield RS Tier", "0-3", ">5=3 pts, >2=2 pts, >0=1 pt, <=0=0 pts"],
                ["Weinstein Stage 2", "2", "Weekly price above rising 30W SMA"],
                ["Relative Volume", "2", "Today's volume >= 1.5x 50-day average"],
                ["RSI Momentum", "1", "RSI14 between 50 and 70 (momentum without overextension)"],
                ["Price vs SMA50", "1", "Close > SMA50"],
                ["Price vs SMA150", "1", "Close > SMA150"],
                ["Screener.in Intersection [SI]", "+1 bonus", "Stock appears in BOTH Chartink AND Screener.in screens"]
            ],
            [2800, 1200, 5360]
        ),
        space(),
        callout("SCORING TIP", "A stock scoring 14+ is considered high conviction. Scores of 18-21 are exceptional and warrant immediate attention. The [SI] bonus tag means the stock passed both a technical Chartink filter AND a fundamental Screener.in query — this double-confirmation is the strongest signal.", "F0FDF4", GREEN),
        space()
    ];
}

// ─── Section 4: Step-by-Step Running Guide ────────────────────────────────────
function section4() {
    return [
        pageBreak(),
        h1("4. Step-by-Step Running Guide"),

        h2("4.1 Method A — Complete Workflow (Recommended)"),
        body("The Complete Workflow runs all pipeline phases including the recovery screener automatically. This is the recommended approach for end-of-day or weekend use."),
        space(),
        numbered("Open the Streamlit Web Commander: streamlit run weinstein_commander_web_v3.0.py"),
        numbered("In your browser, navigate to the Dashboard tab."),
        numbered("Click Run Complete Workflow. The system will execute all phases in sequence."),
        numbered("Monitor the progress in the terminal window where Streamlit is running."),
        numbered("When complete, navigate to Hunter > Selection > Recovery Screener to see results."),
        space(),
        callout("IMPORTANT — Working Directory", "Always launch the Streamlit commander from the correct directory: E:\\gemini\\VS Code\\ (or wherever your CSVs and Python scripts reside). The screener uses os.path.dirname(os.path.abspath(__file__)) to locate files, so the working directory must match the script location.", "FEF3C7", AMBER),
        space(),

        h2("4.2 Method B — Manual Step-by-Step"),
        body("Use this method when you want to run only the recovery screening without the full pipeline, or when troubleshooting individual phases."),
        space(),

        h3("Step 1: Run Recovery Scanners on Chartink"),
        numbered("Open Web Commander and navigate to Hunter > Scanners."),
        numbered("Scroll to the Recovery Phase Scanners section."),
        numbered("Click Scan 5 — REV-RS: RS Survivor Breakout. Wait for confirmation."),
        numbered("Click Scan 6 — REV-CB: Climax Bottom Bounce. Wait for confirmation."),
        numbered("Click Scan 7 — REV-EARLY: Early Bird VCP. Wait for confirmation."),
        body("This creates three files in your working directory:", { bold: true }),
        bullet("Recovery_RS_Survivors.csv"),
        bullet("Recovery_Climax_Bounce.csv"),
        bullet("Recovery_Early_Birds.csv"),
        space(),

        h3("Step 2: (Optional) Fetch Screener.in Fundamentals"),
        body("For full RFF fundamental scoring and [SI] intersection detection:"),
        numbered("Navigate to the Dashboard or Screener tab."),
        numbered("Run the Screener.in fetch for recovery screens."),
        numbered("This creates SCREENER_Recovery_RSLeaders.csv, SCREENER_Recovery_ClimaxBounce.csv, and SCREENER_Recovery_EarlyBirds.csv."),
        space(),

        h3("Step 3: Run the Python Recovery Screener"),
        numbered("Navigate to Hunter > Selection > Recovery Screener."),
        numbered("Click Run Recovery Screener."),
        numbered("Wait for the screener to download OHLCV data from Yahoo Finance (approx. 30-120 seconds depending on candidate count)."),
        numbered("Results appear in the table below the button."),
        space(),

        h3("Step 4: Filter and Interpret Results"),
        numbered("Use the Signal dropdown to filter by edge type (REV-EARLY, REV-RS, REV-CB)."),
        numbered("Use the Min Mansfield RS slider to filter for outperforming stocks."),
        numbered("Use the Max Signal Age filter to limit to fresh signals (e.g., last 2 days)."),
        numbered("Sort by Score (descending) to see highest-conviction setups at the top."),
        space(),

        h2("4.3 Method C — Auto-Pilot (Full Automation)"),
        body("The AI Lab Auto-Pilot mode runs the entire 8-phase pipeline automatically:"),
        makeTable(
            ["Phase", "Description", "Recovery Screener Involvement"],
            [
                ["Phase 1", "Run all 7 Chartink scanners", "Scans 5, 6, 7 generate recovery CSVs"],
                ["Phase 2", "Fetch Screener.in fundamental data", "SCREENER_Recovery_*.csv created"],
                ["Phase 3", "Process HTML data", "Not applicable"],
                ["Phase 4", "Run Golden Matcher (Stage 2 setups)", "Not applicable"],
                ["Phase 4.5", "Run Recovery Screener", "Core recovery screening step"],
                ["Phase 5", "Generate local watchlists", "Recovery results included"],
                ["Phase 6", "Sync to Strike.Money", "Recovery watchlists pushed"],
                ["Phase 7", "Sync to TradingView", "Recovery watchlists pushed"],
                ["Phase 8", "Dispatch Gmail report", "Recovery summary included"]
            ],
            [1000, 3200, 5160]
        ),
        space()
    ];
}

// ─── Section 5: Reading the Results Table ────────────────────────────────────
function section5() {
    return [
        pageBreak(),
        h1("5. Reading the Results Table"),
        body("The Recovery Screener results table appears in Hunter > Selection > Recovery Screener after running the screener. Here is a complete guide to every column:"),
        space(),

        h2("5.1 Column Reference"),
        makeTable(
            ["Column", "Description", "How to Use"],
            [
                [["Symbol", true], "NSE ticker symbol. May include [SI] tag.", "[SI] = also in Screener.in recovery screens. Highest conviction."],
                [["Signal_Label", true], "Edge type: REV-EARLY, REV-RS, REV-CB, CB-Watch", "REV-EARLY (4) > REV-RS (3) > REV-CB (2) > CB-Watch (1)"],
                [["Signal_Date", true], "Date when the signal first fired", "Older signal = closer to expiry. Fresh = more runway."],
                [["Age_Days", true], "Trading days elapsed since signal fired", "0 = today. Max 5 before expiry (default hold window)."],
                [["Score", true], "Composite score 0-21", "Higher = more conviction. Prioritise 14+."],
                [["RFF_Score", true], "Recovery Fundamental Filter score 0-6", "6/6 = financially sound. Below 3 = increased risk."],
                [["Weinstein_Stage", true], "Stage 1-4 based on 30W SMA", "Stage 2 preferred. Stage 1 = basing (acceptable for recovery)."],
                [["Mansfield_RS", true], "Relative strength vs CNX500", "Positive = outperforming. Higher = stronger RS."],
                [["RSI14", true], "14-period RSI (daily)", "50-70 = momentum sweet spot for recovery plays."],
                [["Rel_Vol", true], "Today's volume / 50-day average volume", ">1.5 = strong volume. >2.5 = exceptional. <0.8 = weak."],
                [["Entry", true], "Suggested entry price (current close)", "Use as a reference. Actual entry depends on your setup."],
                [["SL", true], "Stop-loss level", "Based on climax low (REV-CB) or SMA50 / ATR (REV-RS, EARLY)."],
                [["T1", true], "First profit target", "Based on SMA200 (if below) or 10% gain above entry."],
                [["RR_T1", true], "Risk-reward ratio to T1", "Prefer >= 2.0. Below 1.5 = skip unless other factors compelling."],
                [["SL_pct", true], "Stop-loss distance as % of entry", "Keep below 10-12% for swing trades. Tighter is better."],
                [["T1_pct", true], "Target 1 gain as % of entry", "Paired with SL_pct to understand the trade math."],
                [["Details", true], "Python screener detail string", "Shows exactly how the signal was detected (e.g., 'RS breakout 2d ago, holding above SMA50')."]
            ],
            [2000, 2800, 4560]
        ),
        space(),

        h2("5.2 Understanding the [SI] Intersection Tag"),
        body("The [SI] tag next to a symbol's name is one of the most powerful signals in the system. It means the stock appeared in BOTH:"),
        bullet("A Chartink recovery scanner (technical pre-filter)"),
        bullet("A Screener.in recovery query (fundamental + technical combined)"),
        space(),
        body("Because both tools use different methodologies, a stock passing both is rare and highly significant. The [SI] intersection also grants +1 bonus point to the composite Score."),
        space(),
        callout("EXAMPLE", "BAJFINANCE [SI] with Score=17, REV-RS, Mansfield RS=+4.2, RFF=5/6 means: technically an RS Survivor with a fresh 20-day breakout, outperforming the market, financially sound (5 of 6 RFF checks passed), and confirmed by Screener.in. This is a high-conviction setup.", "F0FDF4", GREEN),
        space(),

        h2("5.3 Signal Freshness and Age Interpretation"),
        makeTable(
            ["Age_Days", "Interpretation", "Action"],
            [
                ["0", "Signal fired today", "Maximum urgency — review immediately"],
                ["1-2", "Very fresh — within 2 days", "High priority — entry still optimal"],
                ["3", "Moderately fresh", "Acceptable — check chart for follow-through"],
                ["4", "Approaching expiry", "Act today or let it expire. Re-evaluate entry."],
                ["5", "Last day of hold window", "Signal expires tonight. Only act if chart confirms continuation."],
                [">5", "Signal expired (shown as 0)", "Do not enter. Wait for new signal."]
            ],
            [1600, 3000, 4760]
        ),
        space()
    ];
}

// ─── Section 6: Entry/Exit Framework ─────────────────────────────────────────
function section6() {
    return [
        pageBreak(),
        h1("6. Entry, Stop-Loss & Target Framework"),
        body("The Python screener pre-calculates suggested entry, stop-loss, and target levels. These are starting points — always verify on the chart before executing."),
        space(),

        h2("6.1 Entry Rules by Edge"),
        makeTable(
            ["Edge", "Entry Trigger", "Confirmation Required"],
            [
                ["REV-EARLY", "Close above the 15-day pivot high with expanding volume (>1.5x)", "Volume expansion + candle closes in top 50% of range"],
                ["REV-RS", "Close above the 20-day structural high with 1.5x+ volume", "Volume confirmation. Do NOT enter on low-volume breakouts."],
                ["REV-CB", "Turn candle: green, closes in top 40%, breaks prior day high", "Turn candle fired within 10 days of the climax bottom"]
            ],
            [1800, 4000, 3560]
        ),
        space(),

        h2("6.2 Stop-Loss Calculation"),
        makeTable(
            ["Edge", "SL Method", "Typical Distance"],
            [
                ["REV-CB", "Lowest low of the 5 bars around the climax bar", "5-12% from entry (wide — capitulation bars have large ranges)"],
                ["REV-RS", "SMA50 level at time of breakout. Secondary: 2x ATR below entry", "3-8% from entry"],
                ["REV-EARLY", "Lowest low of the base / VCP structure. Secondary: SMA50", "3-7% from entry"]
            ],
            [1800, 4000, 3560]
        ),
        space(),
        callout("STOP-LOSS DISCIPLINE", "Never risk more than 1-2% of your portfolio on any single recovery trade. These are recovery setups — not all recoveries sustain. Use the SL_pct column to pre-calculate your position size before entering.", "FEF3C7", AMBER),
        space(),

        h2("6.3 Target Calculation"),
        makeTable(
            ["Target", "Method", "Action"],
            [
                ["T1 (First Target)", "SMA200 if price is below it; otherwise Entry + 10%", "Take 30-50% of position off at T1. Raise stop to breakeven."],
                ["T2 (Second Target)", "52-week high area or -5% of prior major resistance", "Take another 30% off. Trail stop on remainder."],
                ["T3 (Full Trail)", "Keep a runner with a trailing stop below 10W SMA", "Ride for larger gains if market confirms Stage 2 resumption"]
            ],
            [1600, 3600, 4160]
        ),
        space(),

        h2("6.4 Position Sizing"),
        body("Use the RR_T1 column to ensure minimum risk/reward discipline:"),
        bullet("RR_T1 >= 2.0: Full position allocation"),
        bullet("RR_T1 1.5-2.0: Reduce position size by 30%"),
        bullet("RR_T1 < 1.5: Skip the trade unless extraordinary conviction from Score and [SI] tag"),
        space(),

        h2("6.5 Signal Priority Matrix"),
        makeTable(
            ["Scenario", "Priority", "Trade Size"],
            [
                ["REV-EARLY, Score>=16, [SI] tag, RS>+3, RFF=5+", "Tier 1 — Maximum", "Full allocation"],
                ["REV-RS, Score>=14, Mansfield RS positive, RFF>=3", "Tier 2 — High", "75% allocation"],
                ["REV-CB, Score>=12, Turn candle confirmed, RFF>=2", "Tier 2 — High", "75% allocation"],
                ["CB-Watch, Score>=10, No turn yet", "Tier 3 — Monitor", "No position yet. Add to watchlist."],
                ["Any signal, Score<10 or RFF=0-1", "Low conviction", "Skip or very small exploratory position"]
            ],
            [3800, 2000, 3560]
        ),
        space()
    ];
}

// ─── Section 7: Configuration Reference ──────────────────────────────────────
function section7() {
    return [
        pageBreak(),
        h1("7. Configuration Reference"),
        body("All parameters are in the CONFIG dictionary at the top of recovery_screener.py. Modify with caution — changes affect all signal detection logic."),
        space(),

        makeTable(
            ["Parameter", "Default", "Effect of Changing"],
            [
                [["signal_hold_days", true], "5", "How many trading days a signal stays active. Increase for weekend coverage; decrease for stricter freshness."],
                [["cb_climax_window", true], "10", "How many days back to look for a REV-CB climax bar. Wider window catches older capitulation events."],
                [["min_daily_turnover_cr", true], "5.0 Cr", "Minimum liquidity filter in INR Crores. Raise to exclude illiquid stocks."],
                [["cb_stretch_pct", true], "15%", "REV-CB: stock must be at least this far below SMA200 at climax. Raise for deeper oversold only."],
                [["cb_vol_mult", true], "2.5x", "REV-CB: climax volume must be this multiple of 50-day average. Lower to 2.0 for more candidates."],
                [["rs_bo_len", true], "20", "REV-RS: breakout checks vs. highest high of this many prior days. Increase for structurally stronger breakouts."],
                [["vol_confirm_mult", true], "1.5x", "REV-RS / REV-EARLY: breakout volume must be this multiple. Raise for stricter confirmation."],
                [["early_pivot_len", true], "15", "REV-EARLY: pivot breakout vs. highest high of this many prior days."],
                [["near_gc_pct", true], "5%", "REV-EARLY: SMA50 must be within this % of SMA200 (or above). Widen to 8% for more candidates."],
                [["vcp_atr_mult", true], "1.5x", "REV-EARLY: ATR(10) must be below ATR_avg(50) x this multiple. VCP compression check."],
                [["mkt_correction_pct", true], "7%", "Regime gate B: CNX500 must be this far off its 52W high. Lower to 5% for more sensitive regime detection."],
                [["min_stock_correction_pct", true], "10%", "Regime gate C: individual stock must be this far off its 52W high for per-symbol bypass."],
                [["rff_min_score", true], "1", "Minimum RFF score to pass. Set to 0 to disable fundamental filter. Raise to 3+ for quality-only trades."],
                [["data_lookback_days", true], "400", "Days of EOD history downloaded from Yahoo Finance. Must be >= 200 for SMA200 warmup."]
            ],
            [2800, 1200, 5360]
        ),
        space()
    ];
}

// ─── Section 8: Workflow Schedule ────────────────────────────────────────────
function section8() {
    return [
        pageBreak(),
        h1("8. Recommended Weekly Workflow Schedule"),
        space(),
        makeTable(
            ["Day / Time", "Action", "Notes"],
            [
                [["Monday–Thursday, Post-Market (3:45–5:00 PM)", true], "Run Complete Workflow from Dashboard", "Fresh Chartink data + Python screener. New signals and expired signals refresh automatically."],
                [["Friday, Post-Market", true], "Run Complete Workflow + review all signals", "Signals fired Friday will remain valid through Monday (5 hold days covers weekend)."],
                [["Saturday or Sunday", true], "Review results table in Web Commander", "No new runs needed — Friday's signals are still active. Plan entry levels for Monday open."],
                [["Monday Morning (Pre-Open)", true], "Check signal Age_Days — any at 5 = expiring today", "If a Friday signal is at Age=3 and still valid on chart, consider entry at Monday open."],
                [["Anytime — Market Recovery Phase", true], "Switch from Stage 2 scanners to Recovery Scanners", "When CNX500 drops >=7% from 52W high or individual sector corrects sharply."],
                [["Anytime — Market Resuming Stage 2", true], "Switch back to Stage 2 scanners (1-4)", "When CNX500 SMA50 > SMA200 and recovery phase ends. Recovery signals will naturally expire."]
            ],
            [3000, 3000, 3360]
        ),
        space(),
        callout("WORKFLOW TIP", "Do not run the pipeline during market hours (9:15 AM to 3:30 PM IST). Chartink data updates intraday and may produce signals that do not hold at market close. Always run post-market for clean end-of-day data.", "FEF3C7", AMBER),
        space()
    ];
}

// ─── Section 9: Troubleshooting ──────────────────────────────────────────────
function section9() {
    return [
        pageBreak(),
        h1("9. Troubleshooting"),
        space(),

        h2("9.1 Common Issues and Solutions"),
        makeTable(
            ["Symptom", "Cause", "Solution"],
            [
                ["No Recovery Screener results after running", "Chartink CSVs are empty (0 stocks passed scanners) OR Python screener not yet run", "Check CSV files in your working directory. If empty, market may not be in recovery phase. Lower scanner thresholds or check Chartink connectivity."],
                ["Results show 0 stocks but CSVs have data", "Regime gate is blocking all candidates", "Check if CNX500 is >= 7% off its 52W high. Lower mkt_correction_pct if needed for current conditions."],
                ["[SI] tag not appearing", "SCREENER_Recovery_*.csv files missing", "Run the Screener.in fetch step before running the Python screener."],
                ["HTTP 404 errors for some symbols", "Invalid NSE codes or BSE-only listings in Chartink results", "These are filtered by the _valid_sym() function. If a stock regularly fails, it may be suspended or not available on Yahoo Finance as a .NS ticker."],
                ["'No Recovery Screener results yet' after Complete Workflow", "CWD mismatch — screener ran from wrong directory", "Ensure run_pipeline.py restores cwd after recovery_screener.main() call. Check that DATA_DIR resolves correctly."],
                ["Staleness warning (>28 hours)", "Recovery screener was not run in the last 28 hours", "Run the screener again. The warning appears in the Web Commander header."],
                ["259 candidates instead of 10-30", "Screener.in was set as primary source instead of Chartink", "Architecture: Chartink = primary (technical candidates), Screener.in = RFF lookup only. Do not swap these roles."],
                ["Signal Age shows 5 on weekend", "Signal fired on Friday — 5 days is the hold window default", "This is expected. The signal expires Monday. Plan your trade for Monday open."],
                ["Mansfield RS shows NaN", "Insufficient weekly history (< 27 weeks) or Yahoo Finance returned no weekly data", "Check the symbol. May be a recently listed stock or data gap."]
            ],
            [2800, 2800, 3760]
        ),
        space(),

        h2("9.2 Verifying the Pipeline Is Running Correctly"),
        body("Use this checklist to confirm each phase completed:"),
        bullet("After Scanners: Check that Recovery_RS_Survivors.csv, Recovery_Climax_Bounce.csv, and Recovery_Early_Birds.csv exist and have data."),
        bullet("After Recovery Screener: Check that Recovery_Screener_Results.csv exists. Open it — it should have columns Symbol, Signal, Score, etc."),
        bullet("In Web Commander: The Recovery Screener section should show a last-run timestamp. If it says 'No results yet', the CSV is missing or empty."),
        bullet("Terminal output: Look for lines starting [REV-RS], [REV-CB], [REV-EARLY] — these indicate stocks that were processed. Watch for 'No climax bar', 'Regime gate failed', and 'No RS breakout' messages — these explain why stocks did not qualify."),
        space()
    ];
}

// ─── Section 10: Quick Reference ─────────────────────────────────────────────
function section10() {
    return [
        pageBreak(),
        h1("10. Quick Reference"),
        space(),

        h2("10.1 Files at a Glance"),
        makeTable(
            ["File", "Created By", "Used By"],
            [
                ["Recovery_RS_Survivors.csv", "Chartink Scanner 5", "Python Recovery Screener (primary candidates)"],
                ["Recovery_Climax_Bounce.csv", "Chartink Scanner 6", "Python Recovery Screener (primary candidates)"],
                ["Recovery_Early_Birds.csv", "Chartink Scanner 7", "Python Recovery Screener (primary candidates)"],
                ["SCREENER_Recovery_RSLeaders.csv", "Screener.in fetch", "Python Recovery Screener (RFF + [SI] detection)"],
                ["SCREENER_Recovery_ClimaxBounce.csv", "Screener.in fetch", "Python Recovery Screener (RFF + [SI] detection)"],
                ["SCREENER_Recovery_EarlyBirds.csv", "Screener.in fetch", "Python Recovery Screener (RFF + [SI] detection)"],
                ["Recovery_Screener_Results.csv", "Python Recovery Screener", "Web Commander results table, watchlist exports"]
            ],
            [3500, 2800, 3060]
        ),
        space(),

        h2("10.2 Signal Priority At a Glance"),
        makeTable(
            ["Signal", "Code", "Min Score for Tier 1", "Key Condition"],
            [
                [["REV-EARLY", true, "1A5276"], "4", "16+", "VCP base + pivot breakout near golden cross"],
                [["REV-RS", true, "1A5276"], "3", "14+", "RS outperformer + 20D structural breakout"],
                [["REV-CB", true, "1A5276"], "2", "12+", "4-pillar climax bottom + turn candle"],
                [["CB-Watch", true, DKGRAY], "1", "N/A", "Climax active, waiting for turn — monitor only"]
            ],
            [2400, 1000, 2500, 3460]
        ),
        space(),

        h2("10.3 Regime Gate Summary"),
        makeTable(
            ["Gate", "Condition", "Status"],
            [
                ["A — Death Cross", "CNX500 SMA50 < SMA200", "Market in full recovery phase"],
                ["B — Correction Depth", "CNX500 >= 7% off 52-week high", "Post-shock, SMA may not have crossed yet"],
                ["C — Stock Bypass", "Individual stock >= 10% off 52-week high", "Per-symbol — works even in healthy markets"]
            ],
            [2000, 4000, 3360]
        ),
        space(),

        h2("10.4 RFF Quick Check"),
        makeTable(
            ["Metric", "Pass Condition", "Source Field (Screener.in)"],
            [
                ["NI > 0", "Net Profit TTM positive", "Net profit / Net Profit / PAT"],
                ["OCF > 0", "Operating Cash Flow positive", "Cash from operating activity / CFO"],
                ["ICR > 2", "Interest Coverage > 2.0x", "Interest Coverage Ratio / ICR"],
                ["D/E < 2", "Debt to Equity < 2.0", "Debt to equity / D/E"],
                ["CR > 1", "Current Ratio > 1.0", "Current ratio / Current Ratio"],
                ["ROA > 5%", "Return on Assets > 5%", "Return on assets / ROA (or ROCE x 0.6 if ROA missing)"]
            ],
            [2000, 3000, 4360]
        ),
        space(),

        h2("10.5 Web Commander Navigation"),
        makeTable(
            ["Task", "Location in Web Commander"],
            [
                ["Run Recovery Chartink Scanners (5, 6, 7)", "Hunter > Scanners > Recovery Phase Scanners"],
                ["Run Python Recovery Screener", "Hunter > Selection > Recovery Screener > Run Recovery Screener"],
                ["Filter results by edge type", "Hunter > Selection > Recovery Screener > Signal dropdown"],
                ["Filter by Mansfield RS strength", "Hunter > Selection > Recovery Screener > Min Mansfield RS"],
                ["Filter by signal freshness", "Hunter > Selection > Recovery Screener > Max Signal Age (days)"],
                ["Run Complete Workflow (all phases)", "Dashboard > Run Complete Workflow"],
                ["Run Full Auto-Pilot", "AI Lab > Run Full Auto-Pilot"],
                ["Check pipeline run status", "Dashboard > last-run timestamp or terminal output"]
            ],
            [3500, 5860]
        ),
        space()
    ];
}

// ─── Build and write the document ────────────────────────────────────────────
async function main() {
    const doc = new Document({
        numbering: {
            config: [
                {
                    reference: "bullets",
                    levels: [
                        { level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
                          style: { paragraph: { indent: { left: 600, hanging: 300 } } } },
                        { level: 1, format: LevelFormat.BULLET, text: "\u25E6", alignment: AlignmentType.LEFT,
                          style: { paragraph: { indent: { left: 1000, hanging: 300 } } } }
                    ]
                },
                {
                    reference: "numbers",
                    levels: [
                        { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
                          style: { paragraph: { indent: { left: 600, hanging: 300 } } } }
                    ]
                }
            ]
        },
        styles: {
            default: {
                document: { run: { font: "Arial", size: 20 } }
            },
            paragraphStyles: [
                {
                    id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
                    run: { size: 28, bold: true, font: "Arial", color: NAVY },
                    paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 0 }
                },
                {
                    id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
                    run: { size: 24, bold: true, font: "Arial", color: TEAL },
                    paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 }
                },
                {
                    id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
                    run: { size: 22, bold: true, font: "Arial", color: NAVY },
                    paragraph: { spacing: { before: 180, after: 60 }, outlineLevel: 2 }
                }
            ]
        },
        sections: [{
            properties: {
                page: {
                    size: { width: 12240, height: 15840 },
                    margin: { top: 1080, right: 1080, bottom: 1080, left: 1080 }
                }
            },
            headers: {
                default: new Header({
                    children: [
                        new Paragraph({
                            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: NAVY, space: 2 } },
                            spacing: { before: 0, after: 60 },
                            children: [
                                new TextRun({ text: "Commander Recovery Screener — User Guide", font: "Arial", size: 16, color: DKGRAY }),
                                new TextRun({ text: "\t", font: "Arial", size: 16 }),
                                new TextRun({ text: "v1.0  |  April 2026", font: "Arial", size: 16, color: DKGRAY })
                            ],
                            tabStops: [{ type: "right", position: 9000 }]
                        })
                    ]
                })
            },
            footers: {
                default: new Footer({
                    children: [
                        new Paragraph({
                            border: { top: { style: BorderStyle.SINGLE, size: 4, color: NAVY, space: 2 } },
                            spacing: { before: 60, after: 0 },
                            children: [
                                new TextRun({ text: "Weinstein Commander Suite | For educational purposes only", font: "Arial", size: 16, color: DKGRAY }),
                                new TextRun({ text: "\t", font: "Arial", size: 16 }),
                                new TextRun({ text: "Page ", font: "Arial", size: 16, color: DKGRAY }),
                                new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 16, color: DKGRAY })
                            ],
                            tabStops: [{ type: "right", position: 9000 }]
                        })
                    ]
                })
            },
            children: [
                ...coverPage(),
                ...section1(),
                ...section2(),
                ...section3(),
                ...section4(),
                ...section5(),
                ...section6(),
                ...section7(),
                ...section8(),
                ...section9(),
                ...section10()
            ]
        }]
    });

    const buffer = await Packer.toBuffer(doc);
    const outPath = "Commander_Recovery_Screener_User_Guide.docx";
    fs.writeFileSync(outPath, buffer);
    console.log("SUCCESS: Written to " + outPath + " (" + buffer.length + " bytes)");
}

main().catch(e => { console.error("ERROR:", e.message); process.exit(1); });
