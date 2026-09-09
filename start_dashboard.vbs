Set WshShell = CreateObject("WScript.Shell")
WScript.Sleep 45000
WshShell.Run "cmd.exe /c cd ""C:\Users\jayra\Documents\GeminiVSCode"" && ""C:\Users\jayra\Documents\GeminiVSCode\.venv\Scripts\python.exe"" -m streamlit run weinstein_commander_web_v4.0.py --server.headless true > NUL 2>&1", 0, False
