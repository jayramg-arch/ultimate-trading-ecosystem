
import os, glob

MANUAL_TITLE = '''# Weinstein-Minervini Commander Trading Bible
## The Complete Swing & Positional Trading System
### Version 1.0 — April 2026 | NSE India

---

> This is your single go-to reference for every decision in the trading ecosystem — from weekly scanning to real-time execution. Built on Stan Weinstein's Stage Analysis and Mark Minervini's SEPA methodology, automated by the Python Commander v4.0.

---

# TABLE OF CONTENTS

- PART I: Philosophy & Ecosystem Architecture
- PART II: The Master Workflow (Weekly + Daily)
- PART III: Core Strategy Logic
- PART IV: Recovery Market Playbook
- PART V: Risk & Position Sizing
- PART VI: The Python Commander
- APPENDICES: User Guides for Every Module

---
'''

SOURCE_FILES = [
    ('Weinstein_Commander_Suite_Trading_Manual.md', '# MASTER MANUAL'),
    ('COMMANDER_WEB_V4_QUICKSTART.md', '# APPENDIX A: Commander Web v4.0 Quickstart'),
    ('Weinstein_Swing_Pro_Dashboard_User_Guide.md', '# APPENDIX B: Swing Pro Dashboard v63.3 — User Guide'),
    ('Weinstein_Swing_Pro_Dashboard_Trading_Guide.md', '# APPENDIX C: Swing Pro Dashboard — Trading Guide'),
    ('Weinstein_Minervini_Strategy_User_Guide.md', '# APPENDIX D: Minervini Strategy v4.51 — User Guide'),
    ('Weinstein_Minervini_Strategy_Trading_Guide.md', '# APPENDIX E: Minervini Strategy — Trading Guide'),
    ('Commander_Screener_Beta_Edition_v2_3_User_Guide.md', '# APPENDIX F: Commander Beta Screener v2.3 — User Guide'),
    ('Commander_Screener_Beta_Edition_v2_3_Trading_Guide.md', '# APPENDIX G: Commander Beta Screener — Trading Guide'),
    ('Commander_Screener_User_Guide.md', '# APPENDIX H: Ultimate Screener v3.6 — User Guide'),
    ('Commander_Screener_Trading_Guide.md', '# APPENDIX I: Ultimate Screener — Trading Guide'),
    ('Weinstein_Fundamental_XRay_User_Guide.md', '# APPENDIX J: Fundamental X-Ray v2.2 — User Guide'),
    ('Weinstein_Fundamental_XRay_Trading_Guide.md', '# APPENDIX K: Fundamental X-Ray — Trading Guide'),
    ('Weinstein_Swing_Zigzag_Strict_v6_User_Guide.md', '# APPENDIX L: Swing Zigzag Strict v6.0 — User Guide'),
    ('Weinstein_Swing_Zigzag_Strict_v6_Trading_Guide.md', '# APPENDIX M: Swing Zigzag Strict — Trading Guide'),
    ('Weinstein_Recovery_Strategy v1.0 \u2014 User Guide.md', '# APPENDIX N: Recovery Strategy v1.0 — User Guide'),
    ('Weinstein_Recovery_Strategy v1.0 \u2014 Trading Manual.md', '# APPENDIX O: Recovery Strategy — Trading Manual'),
]

out = [MANUAL_TITLE]

for fname, section_header in SOURCE_FILES:
    if os.path.exists(fname):
        content = open(fname, encoding='utf-8', errors='replace').read()
        out.append('\n\n---\n\n')
        out.append(section_header + '\n\n')
        out.append(content)
        print(f'  Added: {fname}')
    else:
        print(f'  MISSING: {fname}')

final = ''.join(out)
outfile = 'Weinstein_Minervini_Trading_Bible.md'
with open(outfile, 'w', encoding='utf-8') as f:
    f.write(final)

kb = len(final) // 1024
print(f'Done. {outfile} = {kb} KB')

