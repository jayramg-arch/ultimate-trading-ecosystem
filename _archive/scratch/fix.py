import io

with io.open('Weinstein and Swing Pro Dashboard v64.0.pine', 'r', encoding='utf-8') as f:
    content = f.read()

# Only replace specific instances
content = content.replace('Weinstein & Swing Pro Dashboard [v64.0]', 'Weinstein & Swing Pro Dashboard [v65.0]')
content = content.replace('Weinstein and Swing Pro Dashboard v64.0', 'Weinstein and Swing Pro Dashboard v65.0')
content = content.replace('v64.0: bumped', 'v65.0: bumped')

changelog_addition = """// ==========================================
// CHANGELOG v65.0
// ==========================================
// - REORGANIZATION: Restructured the dashboard table logic to follow a true top-down approach.
// - Left Column flows from Macro & Sector -> Asset Quality -> Action/Setup -> Portfolio Management.
// - Right Column flows from Positional (Weekly) -> Swing (Daily) -> Recovery -> Alpha Screener.
"""
content = content.replace('// ==========================================\n// CHANGELOG v64.0', changelog_addition + '// ==========================================\n// CHANGELOG v64.0')

old_drawing_block = """    // --- LEFT COLUMN ---
    // GROUP 1: MACRO & COMMON CONTEXT
    drawRowL(panel, rowL, "RECOMMENDATION", displayRec, recColor, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "CATALYST (Edge)", chartCat, chartCatCol, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "ASSET QUALITY", assetQuality, gradeCol, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "ACTION SIGNAL", actionSignal, conf_col, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "TRADE STYLE", style_txt, style_col, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "PERSONA", persona_txt, persona_col, c_bg, c_text, color.black)
    rowL += 1
    
    // Trade & Portfolio Status
    drawRowL(panel, rowL, "PORTFOLIO HEALTH", pfStr, pfCol, c_bg, c_text, c_val_text)
    rowL += 1
    if tradeActive
        drawRowL(panel, rowL, "MY TRADE", tradeStatus, tradeColor, c_bg, c_text, c_val_text)
        rowL += 1
        drawRowL(panel, rowL, "ENTRY DATE", entryDateStr, color.gray, c_bg, c_text, c_val_text)
        rowL += 1
        drawRowL(panel, rowL, "DAYS HELD", str.tostring(daysHeld) + " Day(s)", daysHeld > 30 ? color.blue : color.gray, c_bg, c_text, c_val_text)
        rowL += 1
        drawRowL(panel, rowL, "Time Stop (P/S)", timeWarnStr, timeWarnCol, c_bg, c_text, c_val_text)
        rowL += 1
        if finalSL > 0
            drawRowL(panel, rowL, "Dynamic Profile", mktProfile, isBullMarket ? color.green : color.red, c_bg, c_text, c_val_text)
            rowL += 1
            drawRowL(panel, rowL, "Current R:R", rrText, currentR >= 1.0 ? color.green : color.orange, c_bg, c_text, c_val_text)
            rowL += 1

    // INST. ACTIVITY & FILTERS
    table.cell(panel, 0, rowL, "--- INST. ACTIVITY & FILTERS ---", bgcolor=color.new(color.yellow, 70), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 1, rowL, "", bgcolor=color.new(color.yellow, 70))
    rowL += 1

    drawRowL(panel, rowL, "Daily Close > CPR", cpr_ok ? "YES" : "NO", cpr_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Price > M-VWAP", mvwap_ok ? "YES" : "NO", mvwap_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Vol Shelf (VWMA)", vol_shelf_ok ? "YES" : "NO", vol_shelf_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Vol Accum (Setup)", vol_acc_ok ? "PASS" : "WAIT", vol_acc_ok ? color.green : color.gray, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "VCP Tightness", vcp_ok ? "PASS" : "WAIT", vcp_ok ? color.green : color.orange, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Anti-Algo BO Gate", anti_algo_ok ? "PASS" : "FAIL", anti_algo_ok ? color.green : color.red, c_bg, c_text, c_val_text)  // v63.0
    rowL += 1

    // Breadth & Sector
    table.cell(panel, 0, rowL, "--- BREADTH & SECTOR ---", bgcolor=color.new(color.gray, 70), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 1, rowL, "", bgcolor=color.new(color.gray, 70))
    rowL += 1

    drawRowL(panel, rowL, "Mkt Health (N500)", mktState, mktColor, c_bg, c_text, c_val_text)
    rowL += 1
    string secStr = syminfo.sector + " / " + syminfo.industry
    drawRowL(panel, rowL, "Sector Info", secStr, color.gray, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Sector Velocity (ROC)", secVelStr, secVelCol, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "RS (vs Nifty 50)", f_rrg_icon(rs50State) + " " + rs50State, f_rrg_color(rs50State), c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "RS (vs N500)", f_rrg_icon(rs500State) + " " + rs500State, f_rrg_color(rs500State), c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "RS (" + autoSectorName + ")", f_rrg_icon(rsSecState) + " " + rsSecState, f_rrg_color(rsSecState), c_bg, c_text, color.black)
    rowL += 1
    color _secStageDispCol = str.contains(secStageStr, "STAGE 2") ? color.lime : str.contains(secStageStr, "STAGE 1") ? color.yellow : color.red
    drawRowL(panel, rowL, "Sector Stage (W)", secStageStr, _secStageDispCol, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "Next Earnings", earnStr, earnColor, c_bg, c_text, c_val_text)
    rowL += 1

    // --- RIGHT COLUMN ---
    // GROUP 2: POSITIONAL
    table.cell(panel, 2, rowR, "--- 🦁 POSITIONAL: THE HUNTER ---", bgcolor=color.new(color.blue, 30), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 3, rowR, "(Weinstein/Weekly)", bgcolor=color.new(color.blue, 30), text_color=color.white, text_size=size.small, text_halign=text.align_center)
    rowR += 1

    drawRowR(panel, rowR, "Market Structure", stageDisplay, stageCol, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Master Trend (W)", f_trendText(wTrendDir), f_trendColor(wTrendDir), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "30-Week MA Slope", wMASlopeState, wMASlopeState == "RISING" ? color.green : (wMASlopeState == "FALLING" ? color.red : color.blue), c_bg, c_text, c_val_text)
    rowR += 1
    bool pAbove30 = wClose > wMA30
    drawRowR(panel, rowR, "Price > 30W MA", pAbove30 ? "YES" : "NO", pAbove30 ? color.green : color.red, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Overhead Resist", str.tostring(resistCount) + " Level(s)", resistCount == 0 ? color.green : color.orange, c_bg, c_text, c_val_text)
    rowR += 1
    
    // --- Room for Trade Metric ---
    string roomStr = "CLEAR"
    color roomCol = color.green
    if resistCount == 0 or na(ovhPrice)
        roomStr := "BLUE SKY 🚀"
        roomCol := color.lime
    else if ovhPrice <= close
        roomStr := "CLEAR (BO)"
        roomCol := color.lime
    else
        float distToOvh = ((ovhPrice - close) / close) * 100
        if finalEntry > 0 and finalSL > 0
            float computedRisk = math.abs(finalEntry - finalSL)
            float t1_val_check = finalEntry + (computedRisk * dyn_T1_R)
            if t1_val_check > ovhPrice and close < ovhPrice
                roomStr := "⚠️ NO ROOM (vs " + str.tostring(math.round_to_mintick(ovhPrice)) + ")"
                roomCol := color.orange
            else
                roomStr := "CLEAR (" + str.tostring(distToOvh, "#.1") + "%)"
        else
            roomStr := str.tostring(distToOvh, "#.1") + "% (vs " + str.tostring(math.round_to_mintick(ovhPrice)) + ")"
            roomCol := distToOvh < 5.0 ? color.orange : color.green

    drawRowR(panel, rowR, "Room for Trade", roomStr, roomCol, c_bg, c_text, c_val_text)
    rowR += 1

    drawRowR(panel, rowR, "52W High Space", s_dev52, dev52 > -15 ? color.green : color.gray, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "ATH Space", s_devATH, (not na(devATH) and devATH > -15) ? color.green : color.gray, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Weekly PB Health", wkHealthStr, wkHealthCol, c_bg, c_text, c_val_text)
    rowR += 1

    table.cell(panel, 2, rowR, "--- 🎯 SWING: THE SNIPER ---", bgcolor=color.new(color.purple, 30), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 3, rowR, "(Minervini/Daily)", bgcolor=color.new(color.purple, 30), text_color=color.white, text_size=size.small, text_halign=text.align_center)
    rowR += 1

    drawRowR(panel, rowR, "Daily Trend (D)", f_trendText(dTrendDir), f_trendColor(dTrendDir), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Trend Template (>200d)", dSmaAligned ? "ALIGNED" : "MISALIGNED", dSmaAligned ? color.green : color.red, c_bg, c_text, c_val_text)
    rowR += 1
    bool pAbove50 = dClose > dMA50
    drawRowR(panel, rowR, "Price > 50 DMA", pAbove50 ? "YES" : "NO", pAbove50 ? color.green : color.red, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "50 DMA Slope", d50SlopeState, d50SlopeState == "RISING" ? color.green : (d50SlopeState == "FALLING" ? color.red : color.gray), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Price Action Structure", paState, paColor, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Volume Trend", volState, volColor, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Volatility State (ADR)", patStr, color.gray, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, ema_lbl + " Proximity", emaState, emaColor, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Key-Level/Zone Proximity", keyLvlState, keyLvlColor, c_bg, c_text, c_val_text)
    rowR += 1
    string rsiStr = str.tostring(currRsi, "#.##") + " / " + currRsiDiv
    drawRowR(panel, rowR, "RSI & Divergence", rsiStr, currRsiDiv == "BULLISH DIV" ? color.green : (currRsiDiv == "BEARISH DIV" ? color.red : color.gray), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Daily Pullback Health", dayHealthStr, dayHealthCol, c_bg, c_text, c_val_text)
    rowR += 1"""

new_drawing_block = """    // --- LEFT COLUMN ---
    // 1. BREADTH & SECTOR
    table.cell(panel, 0, rowL, "--- BREADTH & SECTOR ---", bgcolor=color.new(color.gray, 70), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 1, rowL, "", bgcolor=color.new(color.gray, 70))
    rowL += 1

    drawRowL(panel, rowL, "Mkt Health (N500)", mktState, mktColor, c_bg, c_text, c_val_text)
    rowL += 1
    string secStr = syminfo.sector + " / " + syminfo.industry
    drawRowL(panel, rowL, "Sector Info", secStr, color.gray, c_bg, c_text, c_val_text)
    rowL += 1
    color _secStageDispCol = str.contains(secStageStr, "STAGE 2") ? color.lime : str.contains(secStageStr, "STAGE 1") ? color.yellow : color.red
    drawRowL(panel, rowL, "Sector Stage (W)", secStageStr, _secStageDispCol, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "Sector Velocity (ROC)", secVelStr, secVelCol, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "RS (vs Nifty 50)", f_rrg_icon(rs50State) + " " + rs50State, f_rrg_color(rs50State), c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "RS (vs N500)", f_rrg_icon(rs500State) + " " + rs500State, f_rrg_color(rs500State), c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "RS (" + autoSectorName + ")", f_rrg_icon(rsSecState) + " " + rsSecState, f_rrg_color(rsSecState), c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "Next Earnings", earnStr, earnColor, c_bg, c_text, c_val_text)
    rowL += 1

    // 2. ASSET QUALITY & CONFIRMATION
    table.cell(panel, 0, rowL, "--- ASSET QUALITY & CONFIRM ---", bgcolor=color.new(color.yellow, 70), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 1, rowL, "", bgcolor=color.new(color.yellow, 70))
    rowL += 1

    drawRowL(panel, rowL, "ASSET QUALITY", assetQuality, gradeCol, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Vol Accum (Setup)", vol_acc_ok ? "PASS" : "WAIT", vol_acc_ok ? color.green : color.gray, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "VCP Tightness", vcp_ok ? "PASS" : "WAIT", vcp_ok ? color.green : color.orange, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Vol Shelf (VWMA)", vol_shelf_ok ? "YES" : "NO", vol_shelf_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Price > M-VWAP", mvwap_ok ? "YES" : "NO", mvwap_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Daily Close > CPR", cpr_ok ? "YES" : "NO", cpr_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "Anti-Algo BO Gate", anti_algo_ok ? "PASS" : "FAIL", anti_algo_ok ? color.green : color.red, c_bg, c_text, c_val_text)
    rowL += 1

    // 3. THE VERDICT & SETUP
    table.cell(panel, 0, rowL, "--- THE VERDICT & SETUP ---", bgcolor=color.new(color.teal, 70), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 1, rowL, "", bgcolor=color.new(color.teal, 70))
    rowL += 1

    drawRowL(panel, rowL, "RECOMMENDATION", displayRec, recColor, c_bg, c_text, c_val_text)
    rowL += 1
    drawRowL(panel, rowL, "CATALYST (Edge)", chartCat, chartCatCol, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "ACTION SIGNAL", actionSignal, conf_col, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "TRADE STYLE", style_txt, style_col, c_bg, c_text, color.black)
    rowL += 1
    drawRowL(panel, rowL, "PERSONA", persona_txt, persona_col, c_bg, c_text, color.black)
    rowL += 1

    // 4. TRADE & PORTFOLIO STATUS
    table.cell(panel, 0, rowL, "--- TRADE & PORTFOLIO ---", bgcolor=color.new(color.navy, 70), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 1, rowL, "", bgcolor=color.new(color.navy, 70))
    rowL += 1

    drawRowL(panel, rowL, "PORTFOLIO HEALTH", pfStr, pfCol, c_bg, c_text, c_val_text)
    rowL += 1
    if tradeActive
        drawRowL(panel, rowL, "MY TRADE", tradeStatus, tradeColor, c_bg, c_text, c_val_text)
        rowL += 1
        drawRowL(panel, rowL, "ENTRY DATE", entryDateStr, color.gray, c_bg, c_text, c_val_text)
        rowL += 1
        drawRowL(panel, rowL, "DAYS HELD", str.tostring(daysHeld) + " Day(s)", daysHeld > 30 ? color.blue : color.gray, c_bg, c_text, c_val_text)
        rowL += 1
        drawRowL(panel, rowL, "Time Stop (P/S)", timeWarnStr, timeWarnCol, c_bg, c_text, c_val_text)
        rowL += 1
        if finalSL > 0
            drawRowL(panel, rowL, "Dynamic Profile", mktProfile, isBullMarket ? color.green : color.red, c_bg, c_text, c_val_text)
            rowL += 1
            drawRowL(panel, rowL, "Current R:R", rrText, currentR >= 1.0 ? color.green : color.orange, c_bg, c_text, c_val_text)
            rowL += 1

    // --- RIGHT COLUMN ---
    // 1. POSITIONAL: THE HUNTER
    table.cell(panel, 2, rowR, "--- 🦁 POSITIONAL: THE HUNTER ---", bgcolor=color.new(color.blue, 30), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 3, rowR, "(Weinstein/Weekly)", bgcolor=color.new(color.blue, 30), text_color=color.white, text_size=size.small, text_halign=text.align_center)
    rowR += 1

    drawRowR(panel, rowR, "Market Structure", stageDisplay, stageCol, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Master Trend (W)", f_trendText(wTrendDir), f_trendColor(wTrendDir), c_bg, c_text, c_val_text)
    rowR += 1
    bool pAbove30 = wClose > wMA30
    drawRowR(panel, rowR, "Price > 30W MA", pAbove30 ? "YES" : "NO", pAbove30 ? color.green : color.red, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "30-Week MA Slope", wMASlopeState, wMASlopeState == "RISING" ? color.green : (wMASlopeState == "FALLING" ? color.red : color.blue), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Weekly PB Health", wkHealthStr, wkHealthCol, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Overhead Resist", str.tostring(resistCount) + " Level(s)", resistCount == 0 ? color.green : color.orange, c_bg, c_text, c_val_text)
    rowR += 1
    
    // --- Room for Trade Metric ---
    string roomStr = "CLEAR"
    color roomCol = color.green
    if resistCount == 0 or na(ovhPrice)
        roomStr := "BLUE SKY 🚀"
        roomCol := color.lime
    else if ovhPrice <= close
        roomStr := "CLEAR (BO)"
        roomCol := color.lime
    else
        float distToOvh = ((ovhPrice - close) / close) * 100
        if finalEntry > 0 and finalSL > 0
            float computedRisk = math.abs(finalEntry - finalSL)
            float t1_val_check = finalEntry + (computedRisk * dyn_T1_R)
            if t1_val_check > ovhPrice and close < ovhPrice
                roomStr := "⚠️ NO ROOM (vs " + str.tostring(math.round_to_mintick(ovhPrice)) + ")"
                roomCol := color.orange
            else
                roomStr := "CLEAR (" + str.tostring(distToOvh, "#.1") + "%)"
        else
            roomStr := str.tostring(distToOvh, "#.1") + "% (vs " + str.tostring(math.round_to_mintick(ovhPrice)) + ")"
            roomCol := distToOvh < 5.0 ? color.orange : color.green

    drawRowR(panel, rowR, "Room for Trade", roomStr, roomCol, c_bg, c_text, c_val_text)
    rowR += 1

    drawRowR(panel, rowR, "52W High Space", s_dev52, dev52 > -15 ? color.green : color.gray, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "ATH Space", s_devATH, (not na(devATH) and devATH > -15) ? color.green : color.gray, c_bg, c_text, c_val_text)
    rowR += 1

    // 2. SWING: THE SNIPER
    table.cell(panel, 2, rowR, "--- 🎯 SWING: THE SNIPER ---", bgcolor=color.new(color.purple, 30), text_color=color.white, text_size=size.normal, text_halign=text.align_left)
    table.cell(panel, 3, rowR, "(Minervini/Daily)", bgcolor=color.new(color.purple, 30), text_color=color.white, text_size=size.small, text_halign=text.align_center)
    rowR += 1

    drawRowR(panel, rowR, "Daily Trend (D)", f_trendText(dTrendDir), f_trendColor(dTrendDir), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Trend Template (>200d)", dSmaAligned ? "ALIGNED" : "MISALIGNED", dSmaAligned ? color.green : color.red, c_bg, c_text, c_val_text)
    rowR += 1
    bool pAbove50 = dClose > dMA50
    drawRowR(panel, rowR, "Price > 50 DMA", pAbove50 ? "YES" : "NO", pAbove50 ? color.green : color.red, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "50 DMA Slope", d50SlopeState, d50SlopeState == "RISING" ? color.green : (d50SlopeState == "FALLING" ? color.red : color.gray), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Price Action Structure", paState, paColor, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Volume Trend", volState, volColor, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Volatility State (ADR)", patStr, color.gray, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, ema_lbl + " Proximity", emaState, emaColor, c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Key-Level/Zone Proximity", keyLvlState, keyLvlColor, c_bg, c_text, c_val_text)
    rowR += 1
    string rsiStr = str.tostring(currRsi, "#.##") + " / " + currRsiDiv
    drawRowR(panel, rowR, "RSI & Divergence", rsiStr, currRsiDiv == "BULLISH DIV" ? color.green : (currRsiDiv == "BEARISH DIV" ? color.red : color.gray), c_bg, c_text, c_val_text)
    rowR += 1
    drawRowR(panel, rowR, "Daily Pullback Health", dayHealthStr, dayHealthCol, c_bg, c_text, c_val_text)
    rowR += 1"""

content = content.replace(old_drawing_block, new_drawing_block)

with io.open('Weinstein and Swing Pro Dashboard v65.0.pine', 'w', encoding='utf-8') as f:
    f.write(content)
