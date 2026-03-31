from fpdf import FPDF
import json
from datetime import datetime
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load Deep Intel Data
INPUT_FILE = "market_intel.json"
try:
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        full_data = json.load(f)
        # Handle new vs old format
        if isinstance(full_data, list):
            data = full_data
            macro = {}
            account = {}
        else:
            data = full_data.get('Portfolio', [])
            macro = full_data.get('Macro', {})
            account = full_data.get('Account', {})
except FileNotFoundError:
    print(f"Error: {INPUT_FILE} not found. Run quant_analyst.py first.")
    exit(1)

# Group by Sector
sectors = {}
total_aum = 0
for item in data:
    sec = item['Fundamental'].get('Sector', 'Unknown')
    if sec not in sectors: sectors[sec] = []
    sectors[sec].append(item)
    # Calc AUM
    if 'Position' in item:
        total_aum += item['Position'].get('CurrentValue', 0)

# Sort Sectors by number of bullish stocks? Or just alpha
for sec in sectors:
    sectors[sec].sort(key=lambda x: (x['Technical']['Stage'] == 'STAGE 2 (UP)', x['Technical']['RS_Rating']), reverse=True)

sorted_sector_keys = sorted(sectors.keys())

class ProReportPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Antigravity Professional Analysis', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, f'Strategic Daily Briefing | {datetime.now().strftime("%Y-%m-%d")}', 0, 1, 'C')
        self.ln(5)
        self.line(10, 25, 200, 25)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Automated Expert System', 0, 0, 'C')

    def format_indian_number(self, n):
        try:
            if n is None or n == "N/A": return "N/A"
            f_n = float(n)
            is_neg = f_n < 0
            f_n = abs(f_n)
            
            s = f"{f_n:.2f}"
            parts = s.split('.')
            main = parts[0]
            
            if len(main) <= 3:
                res = main
            else:
                last_three = main[-3:]
                remaining = main[:-3]
                rev_rem = remaining[::-1]
                groups = [rev_rem[i:i+2] for i in range(0, len(rev_rem), 2)]
                res = ",".join(groups)[::-1] + "," + last_three
            
            final = f"{res}.{parts[1]}"
            return f"-{final}" if is_neg else final
        except:
            return str(n)

    def safe_text(self, text):
        return str(text).encode('latin-1', 'replace').decode('latin-1')
        
    def draw_sentiment_badge(self, rating):
        self.set_font('Arial', 'B', 8)
        # Colors for Sentiment
        if rating == "Strong Buy": self.set_fill_color(0, 100, 0); self.set_text_color(255, 255, 255)
        elif rating == "Buy": self.set_fill_color(0, 180, 0); self.set_text_color(255, 255, 255)
        elif rating == "Strong Sell": self.set_fill_color(150, 0, 0); self.set_text_color(255, 255, 255)
        elif rating == "Sell": self.set_fill_color(220, 50, 50); self.set_text_color(255, 255, 255)
        else: self.set_fill_color(230, 230, 230); self.set_text_color(0, 0, 0)
        
        self.cell(30, 6, self.safe_text(rating.upper()), 0, 0, 'C', 1)
        self.set_text_color(0, 0, 0)

    def draw_verdict_badge(self, verdict):
        self.set_font('Arial', 'B', 9)
        if "BUY" in verdict or "GROWTH" in verdict:
            self.set_fill_color(0, 150, 0)
            self.set_text_color(255, 255, 255)
        elif "SELL" in verdict or "AVOID" in verdict:
            self.set_fill_color(200, 50, 50)
            self.set_text_color(255, 255, 255)
        elif "SPECULATIVE" in verdict:
            self.set_fill_color(255, 140, 0)
            self.set_text_color(255, 255, 255)
        else:
            self.set_fill_color(200, 200, 200)
            self.set_text_color(0, 0, 0)
            
        self.cell(40, 6, self.safe_text(verdict), 0, 0, 'C', 1)
        self.set_text_color(0, 0, 0)

    def draw_macro_section(self, macro_data):
        if not macro_data: return
        
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Global & Macro-Economic Context', 0, 1)
        self.ln(2)
        
        narratives = macro_data.get("Analysis", {})
        
        # 1. Geo-Politics with Analysis
        risk = macro_data.get('GeoPolitical_Risk', 'UNKNOWN')
        color = (0, 150, 0) if risk == 'LOW' else (255, 140, 0) if risk == 'MODERATE' else (200, 0, 0)
        
        self.set_font('Arial', 'B', 10)
        self.cell(50, 6, "Geo-Political Risk Level:", 0, 0)
        self.set_text_color(*color)
        self.cell(0, 6, risk, 0, 1)
        self.set_text_color(0, 0, 0)
        
        if "Geopolitics" in narratives:
             self.set_font('Arial', 'I', 9)
             self.multi_cell(0, 5, self.safe_text(narratives["Geopolitics"]))
        self.ln(4)

        # 2. Macro Table
        self.set_font('Arial', 'B', 9)
        self.cell(40, 8, "Benchmark", 1, 0, 'C')
        self.cell(40, 8, "Value", 1, 0, 'C')
        self.cell(40, 8, "Change %", 1, 0, 'C')
        self.cell(40, 8, "Trend", 1, 1, 'C')
        
        self.set_font('Arial', '', 9)
        for k, v in macro_data.items():
            if k in ['GeoPolitical_Risk', 'Top_News', 'Analysis']: continue
            self.cell(40, 7, k, 1)
            self.cell(40, 7, self.format_indian_number(v.get('Current',0)), 1, 0, 'R')
            
            # Color for change
            chg = v.get('Change', 0)
            if chg > 0: self.set_text_color(0, 150, 0)
            elif chg < 0: self.set_text_color(200, 0, 0)
            self.cell(40, 7, f"{chg}%", 1, 0, 'R')
            self.set_text_color(0, 0, 0)
            
            self.cell(40, 7, v.get('Trend','FLAT'), 1, 1, 'C')
            
        self.ln(4)
        
        # 3. Macro Narrative
        if "Macro" in narratives and narratives["Macro"]:
            self.set_font('Arial', 'B', 10)
            self.cell(0, 6, "Macro-Economic Outlook:", 0, 1)
            self.set_font('Arial', '', 9)
            self.multi_cell(0, 5, self.safe_text(narratives["Macro"]))
            self.ln(4)
        
        # 4. News Section
        news = macro_data.get('Top_News', [])
        if news:
            self.set_font('Arial', 'B', 12)
            self.cell(0, 8, "Key Market Headlines", 0, 1)
            self.set_font('Arial', '', 9)
            
            for n in news:
                src = n.get('Source', 'Global')
                title = self.safe_text(n.get('Title', ''))
                # Bullet point format
                self.cell(5, 5, ">", 0, 0)
                self.set_font('Arial', 'B', 9)
                self.cell(20, 5, f"[{src}]", 0, 0)
                self.set_font('Arial', '', 9)
                self.multi_cell(0, 5, title)
                self.ln(1)
            
        self.ln(5)

    def draw_portfolio_analytics(self, total_aum, assets, account):
        
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'Portfolio Composition & Exposure', 0, 1)
        self.ln(2)
        
        # Account Summary
        cash = account.get('AvailableCash', 0)
        total_nw = total_aum + cash
        
        self.set_font('Arial', '', 10)
        self.cell(50, 6, "Invested Value:", 0, 0)
        self.set_font('Arial', 'B', 10)
        self.cell(40, 6, self.format_indian_number(total_aum), 0, 1)
        
        self.set_font('Arial', '', 10)
        self.cell(50, 6, "Available Cash:", 0, 0)
        self.set_font('Arial', 'B', 10)
        self.cell(40, 6, self.format_indian_number(cash), 0, 1)
        
        self.set_fill_color(220, 220, 220)
        self.cell(90, 8, f" Total Account Value:  {self.format_indian_number(total_nw)}", 1, 1, 'L', 1)
        self.ln(6)
        
        if total_aum == 0: return # Stop if no assets
        
        # Calculate Sector Weights
        sec_ws = {}
        for a in assets:
            s = a['Fundamental'].get('Sector', 'Unknown')
            val = a.get('Position', {}).get('CurrentValue', 0)
            sec_ws[s] = sec_ws.get(s, 0) + val
            
        # Sort by Weight
        sorted_ws = sorted(sec_ws.items(), key=lambda x: x[1], reverse=True)
        
        self.set_font('Arial', 'B', 9)
        self.cell(60, 6, "Sector Allocation", 1, 0, 'C')
        self.cell(40, 6, "Exposure (Amt)", 1, 0, 'C')
        self.cell(40, 6, "Weight %", 1, 1, 'C')
        
        self.set_font('Arial', '', 9)
        for sec, val in sorted_ws:
            if val == 0: continue
            pct = round((val / total_aum) * 100, 1)
            self.cell(60, 6, self.safe_text(sec), 1)
            self.cell(40, 6, self.format_indian_number(val), 1, 0, 'R')
            self.cell(40, 6, f"{pct}%", 1, 1, 'R')
            
        self.ln(10)

    def draw_asset_block(self, item):
        sym = item['Symbol']
        tech = item['Technical']
        analysis = item['Analysis']
        pos = item.get('Position', {})
        
        # New Page Logic is handled by Loop outer context usually, but here we check per block
        if self.get_y() > 240: self.add_page()
            
        self.set_font('Arial', 'B', 12)
        # 1. Title Row: SYMBOL ... VERDICT
        self.cell(30, 8, self.safe_text(sym), 0, 0)
        
        # Verdict Badge
        self.draw_verdict_badge(analysis['Verdict'])
        self.set_x(85)
        self.draw_sentiment_badge(item.get('Sentiment', {}).get('Rating', 'Hold'))
        
        # Price info
        self.set_font('Arial', '', 10)
        price_str = f"  |  Price: {item['CMP']}"
        if pos.get('Qty', 0) > 0:
            pnl_pct = round(((item['CMP'] - pos['AvgPrice']) / pos['AvgPrice']) * 100, 1)
            price_str += f"  |  Avg: {pos['AvgPrice']}  |  PnL: {pnl_pct}%"
            
        self.cell(0, 8, price_str, 0, 1, 'R')
        
        # 2. Analysis Text
        self.ln(2)
        
        # Thesis
        self.set_font('Arial', 'B', 9)
        self.cell(35, 5, "Technical Thesis:", 0, 0)
        self.set_font('Arial', '', 9)
        self.multi_cell(0, 5, self.safe_text(analysis['Thesis']))
        self.ln(1)
        
        # Context
        self.set_font('Arial', 'B', 9)
        self.cell(35, 5, "Fund. Context:", 0, 0)
        self.set_font('Arial', '', 9)
        self.multi_cell(0, 5, self.safe_text(analysis['Context']))
        self.ln(1)
        
        # Strategy Desc
        self.set_font('Arial', 'B', 9)
        self.cell(35, 5, "Strategic View:", 0, 0)
        self.set_font('Arial', 'I', 9)
        self.multi_cell(0, 5, self.safe_text(analysis['Verdict_Desc']))
        
        # Divider
        self.ln(3)
        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_draw_color(0, 0, 0)
        self.ln(5)

pdf = ProReportPDF()
pdf.add_page()

# Executive Summary (Fake "Market Breadth" based on data)
bulls = sum(1 for x in data if "STAGE 2" in x['Technical']['Stage'])
bears = len(data) - bulls
pdf.set_font('Arial', 'B', 12)
pdf.cell(0, 8, f"Executive Summary: Market Breadth", 0, 1)
pdf.set_font('Arial', '', 10)
pdf.multi_cell(0, 5, f"Automated Scan Results: Of {len(data)} tracked assets, {bulls} are in constructive trends (Stage 2) and {bears} are in corrective phases. The report below splits these assets by SECTOR to highlight industry rotation.")
pdf.ln(5)

# 1. Macro Section
if macro:
    pdf.draw_macro_section(macro)

# 2. Portfolio Analytics
if total_aum > 0:
    pdf.draw_portfolio_analytics(total_aum, data, account)

# 3. Sector Loop
for sec in sorted_sector_keys:
    # Sector Header
    pdf.set_fill_color(240, 240, 250)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, pdf.safe_text(f"SECTOR: {sec.upper()}"), 1, 1, 'L', 1)
    pdf.ln(5)
    
    for item in sectors[sec]:
        pdf.draw_asset_block(item)
        
    pdf.ln(5)

pdf.output("Strategic_Briefing_Automated.pdf")
print("✅ Professional Briefing Generated.")
