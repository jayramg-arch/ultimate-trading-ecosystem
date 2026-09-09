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

def run_gemini_briefing():
    """Call Gemini 2.5 Flash directly with the just-generated prompt and
    persist the markdown report. Replaces the manual paste-into-web-UI
    step that used to gate the workflow.
    """
    print("[*] Running Gemini 2.5 Flash strategic briefing...")
    try:
        from gemini_reporter import generate_strategic_briefing
        text = generate_strategic_briefing(
            prompt_path="Gemini_Analysis_Prompt.txt",
            out_path="Strategic_Briefing_AI.md",
        )
        if text.startswith("Warning:"):
            print(f"[!] AI step degraded: {text[:120]}…")
            return False
        print(f"[OK] AI briefing written to Strategic_Briefing_AI.md ({len(text)} chars).")
        return True
    except Exception as e:
        print(f"[X] AI briefing failed: {e}")
        return False


def main():
    print("[>] Starting Strategic Briefing Workflow...")
    print("-" * 40)

    # 1. Run Analysis & Prompt Generation
    if not run_step("quant_analyst.py"):
        print("[!] Aborting Workflow due to Analysis Failure.")
        input("Press Enter to Exit...")
        return

    # 2. Run Gemini 2.5 Flash on the generated prompt (replaces the
    #    manual "paste into web UI" loop). Non-fatal if it fails —
    #    PDF + email continue with the rule-based content.
    _ai_ok = run_gemini_briefing()

    # 3. Run PDF Generation (Rule-Based Report). The PDF builder will
    #    automatically append a "AI Strategic Briefing" section if
    #    Strategic_Briefing_AI.md exists on disk (see generate_report_pdf.py).
    run_step("generate_report_pdf.py")

    # 4. Open Generated Files
    print("-" * 40)
    print("[>] Opening Artifacts...")

    for f in ("Gemini_Analysis_Prompt.txt",
              "Strategic_Briefing_AI.md",
              "Strategic_Briefing_Automated.pdf"):
        if os.path.exists(f):
            print(f"[FILE] Opening {f}...")
            webbrowser.open(f)
        else:
            print(f"[X] {f} not found!")

    # 5. Email Dispatch
    print("-" * 40)
    print("[>] Dispatching Report via Gmail...")
    try:
        import gmail_dispatcher
        gmail_dispatcher.dispatch_strategic_briefing()
    except Exception as e:
        print(f"[X] Error dispatching email: {e}")

    if not _ai_ok:
        print("[!] Note: AI briefing did not complete cleanly. "
               "PDF and email contain rule-based analysis only.")

    print("\n[OK] Workflow Complete. You can close this window.")
    input("Press Enter to Close...")

if __name__ == "__main__":
    main()
