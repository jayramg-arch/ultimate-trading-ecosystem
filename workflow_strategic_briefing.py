import subprocess
import os
import sys
import time
import webbrowser

def run_step(script_name):
    print(f"[*] Running {script_name}...")
    try:
        # Run script and wait for it to finish
        result = subprocess.run([sys.executable, script_name], check=True)
        print(f"[OK] {script_name} Completed.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[X] Error running {script_name}: {e}")
        return False

def main():
    print("[>] Starting Strategic Briefing Workflow...")
    print("-" * 40)

    # 1. Run Analysis & Prompt Generation
    if not run_step("quant_analyst.py"):
        print("[!] Aborting Workflow due to Analysis Failure.")
        input("Press Enter to Exit...")
        return

    # 2. Run PDF Generation (Rule-Based Report)
    run_step("generate_report_pdf.py")

    # 3. Open Generated Files
    print("-" * 40)
    print("[>] Opening Artifacts...")

    # Open Prompt File
    prompt_file = "Gemini_Analysis_Prompt.txt"
    if os.path.exists(prompt_file):
        print(f"[FILE] Opening {prompt_file}...")
        webbrowser.open(prompt_file)
    else:
        print(f"[X] {prompt_file} not found!")

    # Open PDF Report
    pdf_file = "Strategic_Briefing_Automated.pdf"
    if os.path.exists(pdf_file):
        print(f"[FILE] Opening {pdf_file}...")
        webbrowser.open(pdf_file)
    else:
        print(f"[X] {pdf_file} not found!")
        
    # 4. Email Dispatch
    print("-" * 40)
    print("[>] Dispatching Report via Gmail...")
    try:
        import gmail_dispatcher
        gmail_dispatcher.dispatch_strategic_briefing()
    except Exception as e:
        print(f"[X] Error dispatching email: {e}")
    
    print("\n[OK] Workflow Complete. You can close this window.")
    input("Press Enter to Close...")

if __name__ == "__main__":
    main()
