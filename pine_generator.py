def generate_pine_code(symbols):
    clean_syms = []
    if symbols:
        for s in symbols:
            s = s.strip()
            if not s or s.lower() == 'symbol' or s.lower() == 'ticker': continue
            # TradingView exports often have exchange prefixes like NSE:RELIANCE
            if ':' not in s:
                s = f"NSE:{s}"
            clean_syms.append(s)
            
    final_syms = clean_syms[:30]
    while len(final_syms) < 30:
        final_syms.append("") # Pad unused slots with empty strings

    pine_inputs = ""
    for i in range(1, 31):
        pine_inputs += f's{i}  = input.symbol("{final_syms[i-1]}", group=grpSym)\n'
        
    return f"""//@version=6
indicator("Commander Screener Dashboard [ULTIMATE] v3.0", overlay=true)

// ==========================================
// 1. INPUTS
// ==========================================
grpSym = "Watchlist Symbols (Max 30)"
{pine_inputs}
grpConfig = "Ranking & Table Config"
benchSym = input.symbol("NSE:NIFTY", title="Benchmark (For RS)", group=grpConfig)
sortBy = input.string("Score/Grade", title="Rank/Sort By", options=["Score/Grade", "Volume Thrust", "Proximity to 52-Wk High", "Proximity to 50-SMA", "Relative Strength (Qtr)"], group=grpConfig)
sortDir = input.string("Descending (Best to Worst)", title="Sort Direction", options=["Descending (Best to Worst)", "Ascending (Worst to Best)"], group=grpConfig)
tbPos = input.string(position.bottom_center, title="Table Position", options=[position.top_center, position.bottom_center, position.middle_center, position.top_right], group=grpConfig)


// ==========================================
// 2. TYPES & DATA FETCHING ENGINE (Pine v6 UDT)
// ==========================================
type RawMetrics
    float c
    float o
    float e20
    float s50
    float s150
    float s200
    float s200_10
    float h250
    float v
    float vSma
    float rsi
    float atr10
    float atr40
    float roc65
    float slope50

type ProcessedStock
    string ticker
    float price
    string stageStr
    string gradeStr
    int score
    float distFromHigh
    float distFrom50
    float volThrust
    string vcpStr
    string rsStr
    string slopeStr
    string rsiStr
    color bgCol
    string recStr

b_qtr_roc = request.security(benchSym, timeframe.period, ta.roc(close, 65))

f_get_metrics() =>
    s50 = ta.sma(close, 50)
    slp = ta.linreg(s50, 5, 0) - ta.linreg(s50, 5, 1) // 5-day slope of 50SMA
    RawMetrics.new(
      close, open, ta.ema(close, 20), s50, ta.sma(close, 150), ta.sma(close, 200),
      ta.sma(close, 200)[10], ta.highest(high, 250), volume, ta.sma(volume, 50),
      ta.rsi(close, 14), ta.atr(10), ta.atr(40), ta.roc(close, 65), slp)

f_process_stock(string sym, RawMetrics rm, float benchRoc) =>
    if na(rm.c) or rm.c == 0
        ProcessedStock.new(sym, 0, "N/A", "N/A", 0, 0, 0, 0, "N/A", "N/A", "N/A", "0.0", color.gray, "WAIT")
    else
        score = 0
        grade = "F"
        stage = "STAGE 4 (DN)"
        bg = color.new(#ff5252, 70) 
        
        // 1. Stage & Grade Logic
        if (rm.c > rm.s150) and (rm.s150 > rm.s200) and (rm.s200 > rm.s200_10) // 200 Rising
            stage := "STAGE 2 (UP)"
            if (rm.c > rm.s50) and (rm.s50 > rm.s150)
                grade := "A"
                score += 25
                bg := color.new(#00e676, 50)
            else
                grade := "B"
                score += 15
                bg := color.new(#00e676, 70)
        else if (rm.c > rm.s200)
            stage := "STAGE 1 (BASE)"
            grade := "C"
            score += 10
            bg := color.new(#ffeb3b, 50)
        else if (rm.s50 < rm.s200)
            stage := "STAGE 4 (DN)"
            grade := "D"
            score += 0
            bg := color.new(#ff9800, 50)

        // 2. Relative Strength
        alpha = rm.roc65 - benchRoc
        rs_str = "Lagging"
        if alpha > 15
            score += 15
            rs_str := "🔥 LEADING"
        else if alpha > 5
            score += 5
            rs_str := "Improving"
            
        // 3. 50 DMA Slope
        slope_str = "Flat"
        if rm.slope50 > (rm.s50 * 0.001) // threshold
            slope_str := "Rising ↗"
            score += 10
        else if rm.slope50 < -(rm.s50 * 0.001)
            slope_str := "Falling ↘"
            
        // 4. Volatility / VCP
        vcp_str = "Normal"
        if rm.atr10 < (rm.atr40 * 0.70)
            vcp_str := "⚡ SQUEEZE"
            score += 10
        else if rm.atr10 > (rm.atr40 * 1.5)
            vcp_str := "Expanded"

        // 5. Volume Thrust
        vThrust = 0.0
        if rm.vSma > 0 and (rm.c > rm.o)
            vThrust := (rm.v / rm.vSma) * 100
            if vThrust > 150
                score += 10

        // 6. Extent & Distances
        d52High = rm.h250 > 0 ? ((rm.c - rm.h250) / rm.h250) * 100 : 0
        d50SMA = rm.s50 > 0 ? ((rm.c - rm.s50) / rm.s50) * 100 : 0
        
        // 7. RSI
        if rm.rsi > 50 and rm.rsi < 70
            score += 5
        rsi_str = str.tostring(rm.rsi, "#.1")
        if rm.rsi > 70
            rsi_str += " (OB)"
            
        // 8. Dynamic Recommendation
        rec = "WAIT"
        if stage == "STAGE 2 (UP)" and rm.c > rm.e20
            if vcp_str == "⚡ SQUEEZE" and rm.v < rm.vSma // Volume Dry Up
                rec := "🎯 SWING SETUP"
            else if vThrust > 120
                rec := "BUY (Momentum)"
            else
                rec := "HOLD (Trend)"
        else if stage == "STAGE 1 (BASE)" 
            rec := "WATCH (Basing)"
        else if stage == "STAGE 4 (DN)" or grade == "D"
            rec := "AVOID / SELL"

        ProcessedStock.new(sym, rm.c, stage, grade, score, d52High, d50SMA, vThrust, vcp_str, rs_str, slope_str, rsi_str, bg, rec)

// ==========================================
// 3. REQUEST THE UDT METRICS
// ==========================================
m1 = request.security(s1, timeframe.period, f_get_metrics())
m2 = request.security(s2, timeframe.period, f_get_metrics())
m3 = request.security(s3, timeframe.period, f_get_metrics())
m4 = request.security(s4, timeframe.period, f_get_metrics())
m5 = request.security(s5, timeframe.period, f_get_metrics())
m6 = request.security(s6, timeframe.period, f_get_metrics())
m7 = request.security(s7, timeframe.period, f_get_metrics())
m8 = request.security(s8, timeframe.period, f_get_metrics())
m9 = request.security(s9, timeframe.period, f_get_metrics())
m10 = request.security(s10, timeframe.period, f_get_metrics())
m11 = request.security(s11, timeframe.period, f_get_metrics())
m12 = request.security(s12, timeframe.period, f_get_metrics())
m13 = request.security(s13, timeframe.period, f_get_metrics())
m14 = request.security(s14, timeframe.period, f_get_metrics())
m15 = request.security(s15, timeframe.period, f_get_metrics())
m16 = request.security(s16, timeframe.period, f_get_metrics())
m17 = request.security(s17, timeframe.period, f_get_metrics())
m18 = request.security(s18, timeframe.period, f_get_metrics())
m19 = request.security(s19, timeframe.period, f_get_metrics())
m20 = request.security(s20, timeframe.period, f_get_metrics())
m21 = request.security(s21, timeframe.period, f_get_metrics())
m22 = request.security(s22, timeframe.period, f_get_metrics())
m23 = request.security(s23, timeframe.period, f_get_metrics())
m24 = request.security(s24, timeframe.period, f_get_metrics())
m25 = request.security(s25, timeframe.period, f_get_metrics())
m26 = request.security(s26, timeframe.period, f_get_metrics())
m27 = request.security(s27, timeframe.period, f_get_metrics())
m28 = request.security(s28, timeframe.period, f_get_metrics())
m29 = request.security(s29, timeframe.period, f_get_metrics())
m30 = request.security(s30, timeframe.period, f_get_metrics())

// ==========================================
// 4. DRAW 13-COLUMN TABLE
// ==========================================
var table ui = table.new(tbPos, 14, 32, bgcolor=#1a1a24, border_color=#363c4e, border_width=1)

if barstate.islast
    a_stocks = array.new<ProcessedStock>()
    if s1 != ""
        array.push(a_stocks, f_process_stock(s1, m1, b_qtr_roc))
    if s2 != ""
        array.push(a_stocks, f_process_stock(s2, m2, b_qtr_roc))
    if s3 != ""
        array.push(a_stocks, f_process_stock(s3, m3, b_qtr_roc))
    if s4 != ""
        array.push(a_stocks, f_process_stock(s4, m4, b_qtr_roc))
    if s5 != ""
        array.push(a_stocks, f_process_stock(s5, m5, b_qtr_roc))
    if s6 != ""
        array.push(a_stocks, f_process_stock(s6, m6, b_qtr_roc))
    if s7 != ""
        array.push(a_stocks, f_process_stock(s7, m7, b_qtr_roc))
    if s8 != ""
        array.push(a_stocks, f_process_stock(s8, m8, b_qtr_roc))
    if s9 != ""
        array.push(a_stocks, f_process_stock(s9, m9, b_qtr_roc))
    if s10 != ""
        array.push(a_stocks, f_process_stock(s10, m10, b_qtr_roc))
    if s11 != ""
        array.push(a_stocks, f_process_stock(s11, m11, b_qtr_roc))
    if s12 != ""
        array.push(a_stocks, f_process_stock(s12, m12, b_qtr_roc))
    if s13 != ""
        array.push(a_stocks, f_process_stock(s13, m13, b_qtr_roc))
    if s14 != ""
        array.push(a_stocks, f_process_stock(s14, m14, b_qtr_roc))
    if s15 != ""
        array.push(a_stocks, f_process_stock(s15, m15, b_qtr_roc))
    if s16 != ""
        array.push(a_stocks, f_process_stock(s16, m16, b_qtr_roc))
    if s17 != ""
        array.push(a_stocks, f_process_stock(s17, m17, b_qtr_roc))
    if s18 != ""
        array.push(a_stocks, f_process_stock(s18, m18, b_qtr_roc))
    if s19 != ""
        array.push(a_stocks, f_process_stock(s19, m19, b_qtr_roc))
    if s20 != ""
        array.push(a_stocks, f_process_stock(s20, m20, b_qtr_roc))
    if s21 != ""
        array.push(a_stocks, f_process_stock(s21, m21, b_qtr_roc))
    if s22 != ""
        array.push(a_stocks, f_process_stock(s22, m22, b_qtr_roc))
    if s23 != ""
        array.push(a_stocks, f_process_stock(s23, m23, b_qtr_roc))
    if s24 != ""
        array.push(a_stocks, f_process_stock(s24, m24, b_qtr_roc))
    if s25 != ""
        array.push(a_stocks, f_process_stock(s25, m25, b_qtr_roc))
    if s26 != ""
        array.push(a_stocks, f_process_stock(s26, m26, b_qtr_roc))
    if s27 != ""
        array.push(a_stocks, f_process_stock(s27, m27, b_qtr_roc))
    if s28 != ""
        array.push(a_stocks, f_process_stock(s28, m28, b_qtr_roc))
    if s29 != ""
        array.push(a_stocks, f_process_stock(s29, m29, b_qtr_roc))
    if s30 != ""
        array.push(a_stocks, f_process_stock(s30, m30, b_qtr_roc))
    
    // Sort Engine
    a_sortVals = array.new_float()
    for s in a_stocks
        float v = 0.0
        if sortBy == "Score/Grade"
            v := s.score + (s.volThrust / 1000) 
        else if sortBy == "Volume Thrust"
            v := s.volThrust
        else if sortBy == "Proximity to 52-Wk High"
            v := s.distFromHigh * -1 
        else if sortBy == "Relative Strength (Qtr)"
            v := s.rsStr == "🔥 LEADING" ? 2 : (s.rsStr == "Improving" ? 1 : 0)
        else
            v := math.abs(s.distFrom50) * -1
        array.push(a_sortVals, v)
        
    int[] indices = array.sort_indices(a_sortVals)
    
    // Headers (13 Columns)
    table.cell(ui, 0, 0, "RANK", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 1, 0, "TICKER", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 2, 0, "SCORE", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 3, 0, "STAGE", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 4, 0, "R. STRENGTH", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 5, 0, "50-DMA SLOPE", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 6, 0, "VOLATILITY", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 7, 0, "VOL THRUST%", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 8, 0, "% FROM ATH", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 9, 0, "50-SMA DIST%", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 10, 0, "RSI (14)", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    table.cell(ui, 11, 0, "RECOMMENDATION", bgcolor=#1A237E, text_color=color.white, text_size=size.small)
    
    bool isDesc = sortDir == "Descending (Best to Worst)"
    
    if array.size(indices) > 0
        for i = 0 to array.size(indices) - 1
            idx = isDesc ? array.get(indices, (array.size(indices) - 1) - i) : array.get(indices, i)
            s = array.get(a_stocks, idx)
            
            cleanTick = str.replace_all(s.ticker, "NSE:", "")
            
            table.cell(ui, 0, i+1, str.tostring(i+1), bgcolor=s.bgCol, text_color=color.white, text_size=size.small)
            table.cell(ui, 1, i+1, cleanTick, bgcolor=s.bgCol, text_color=color.white, text_size=size.small)
            table.cell(ui, 2, i+1, str.tostring(s.score) + "/100 (" + s.gradeStr + ")", bgcolor=s.bgCol, text_color=color.white, text_size=size.small)
            table.cell(ui, 3, i+1, s.stageStr, bgcolor=s.bgCol, text_color=color.white, text_size=size.small)
            
            // RS
            color rsCol = str.contains(s.rsStr, "LEADING") ? color.lime : color.white
            table.cell(ui, 4, i+1, s.rsStr, bgcolor=s.bgCol, text_color=rsCol, text_size=size.small)
            
            // Slope
            color slpCol = str.contains(s.slopeStr, "Rising") ? color.lime : (str.contains(s.slopeStr, "Falling") ? color.red : color.white)
            table.cell(ui, 5, i+1, s.slopeStr, bgcolor=s.bgCol, text_color=slpCol, text_size=size.small)
            
            // VCP
            color vcpCol = str.contains(s.vcpStr, "SQUEEZE") ? color.yellow : color.white
            table.cell(ui, 6, i+1, s.vcpStr, bgcolor=s.bgCol, text_color=vcpCol, text_size=size.small)
            
            // Vol Thrust
            color vCol = color.white
            if s.volThrust > 150
                vCol := color.yellow // Accumulation!
            valStr = s.volThrust > 0 ? str.tostring(s.volThrust, "#.#") + "%" : "0%"
            table.cell(ui, 7, i+1, valStr, bgcolor=s.bgCol, text_color=vCol, text_size=size.small)
            
            // ATH Dist
            table.cell(ui, 8, i+1, str.tostring(s.distFromHigh, "#.#") + "%", bgcolor=s.bgCol, text_color=color.white, text_size=size.small)
            
            // SMA Dist
            color dCol = color.white
            if math.abs(s.distFrom50) < 5.0
                dCol := color.lime // Nice tight EMA compression
            table.cell(ui, 9, i+1, str.tostring(s.distFrom50, "#.#") + "%", bgcolor=s.bgCol, text_color=dCol, text_size=size.small)

            // RSI
            color cRsi = str.contains(s.rsiStr, "OB") ? color.red : color.white
            table.cell(ui, 10, i+1, s.rsiStr, bgcolor=s.bgCol, text_color=cRsi, text_size=size.small)

            // Rec
            color rCol = str.contains(s.recStr, "BUY") or str.contains(s.recStr, "SETUP") ? color.lime : color.white
            table.cell(ui, 11, i+1, s.recStr, bgcolor=s.bgCol, text_color=rCol, text_size=size.small)
"""
