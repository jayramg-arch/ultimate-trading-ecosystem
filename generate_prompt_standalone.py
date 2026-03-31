import json
import os
import time
import webbrowser
import sys
import subprocess

# reuse logic from quant_analyst if available, otherwise implement here
# For robustness, we will import the necessary functions from quant_analyst
# This ensures a single source of truth for the prompt structure.

def ensure_fresh_data():
    """
    Checks if market_intel.json exists and is recent (less than 1 hour old).
    If not, runs quant_analyst.py to refresh data.
    """
    input_file = "market_intel.json"
    
    # FORCE REFRESH: User wants to ensure latest data and correct cash
    if os.path.exists(input_file):
        try:
            os.remove(input_file)
            print("[-] Old Market Intelligence deleted. Forcing fresh analysis...")
        except:
            pass

    is_fresh = False # Always false to force run

    if not is_fresh:
        try:
            # Run quant_analyst.py
            print("[-] Launching Quantitative Analysis...")
            subprocess.run([sys.executable, "quant_analyst.py"], check=True)
            print("[OK] Analysis Complete.")
        except subprocess.CalledProcessError as e:
            print(f"[X] Error running analysis: {e}")
            return False
            
    return True

def main():
    print("==========================================")
    print("   GEMINI PROMPT GENERATOR v1.0")
    print("==========================================")
    
    # 1. Ensure Data
    if not ensure_fresh_data():
        input("Press Enter to Exit...")
        return

    # 2. Key Step: Trigger Prompt Generation Logic
    # We can either import the function or trust that quant_analyst 
    # already generated "Gemini_Analysis_Prompt.txt" as part of its run.
    # Looking at quant_analyst.py, it DOES generate the file at the end.
    
    # However, if data was fresh, we might want to regenerate the prompt 
    # just in case the code changed but data didn't. 
    # But for now, let's rely on the file existence.
    
    prompt_file = "Gemini_Analysis_Prompt.txt"
    pdf_file = "Strategic_Briefing_Automated.pdf"
    
    # 3. Generate PDF Report as well
    print("[-] Generating PDF Briefing...")
    try:
        subprocess.run([sys.executable, "generate_report_pdf.py"], check=True)
        print("[OK] PDF Generated.")
    except subprocess.CalledProcessError as e:
        print(f"[X] Error generating PDF: {e}")

    # 4. Open Files
    if os.path.exists(prompt_file):
        print(f"\n[SUCCESS] Opening Prompt File: {prompt_file}")
        print(">> Copy the content and paste it into Gemini Advanced / Ultra.")
        webbrowser.open(prompt_file)
    else:
        print(f"\n[X] Error: {prompt_file} was not found despite analysis success.")
        
    if os.path.exists(pdf_file):
        print(f"[SUCCESS] Opening PDF Report: {pdf_file}")
        webbrowser.open(pdf_file)
    else:
        print(f"[X] Error: {pdf_file} not found.")
        
    print("\n------------------------------------------")
    # input("Press Enter to close...") # Optional, maybe keep open for a bit
    time.sleep(2)

if __name__ == "__main__":
    main()
