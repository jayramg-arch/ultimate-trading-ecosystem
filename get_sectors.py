import yfinance as yf
import concurrent.futures

symbols = '''360ONE          CRISIL          JSWDULUX        PPLPHARMA
AADHARHFC       DEEPAKFERT      JYOTICNC        PTCIL
ABLBL           ECLERX          KAYNES          PWL
ABREL           ELECON          KFINTECH        RAILTEL
ABSLAMC         EMCURE          KIRLOSENG       RKFORGE
ACMESOLAR       ENRIN           KPRMILL         RPOWER
ACUTAAS         ETERNAL         LATENTVIEW      RRKABEL
AEGISLOG        FIRSTCRY        LEMONTREE       SAGILITY
AEGISVOPAK      FIVESTAR        LENSKART        SAMMAANCAP
AFCONS          FLUOROCHEM      LGEINDIA        SARDAEN
AIIL            FORCEMOT        LLOYDSME        SAREGAMA
ANANDRATHI      GALLANTT        LTF             SBFC
ARE&M           GMRAIRPORT      LTFOODS         SCI
ATGL            GODFRYPHLP      LTM             SPLPETRO
ATHERENERG      GODIGIT         MEESHO          SUNDARMFIN
AWL             GVT&D           MMTC            SWANCORP
BBTC            HBLENGINE       MSUMI           SYRMA
BDL             HEXT            NAVA            TARIL
BHARTIHEXA      HONASA          NETWEB          TATACAP
BIKAJI          HYUNDAI         NIACL           TBOTEK
BLUEDART        IDEA            NIVABUPA        TEJASNET
BLUEJET         IFCI            NTPCGREEN       TENNIND
CAMS            IGIL            OLAELEC         THELEELA
CCL             IKS             OLECTRA         TMCV
CEMPRO          INDGN           ONESOURCE       TMPV
CGCL            IREDA           PARADEEP        TRAVELFOOD
CHENNPETRO      ITCHOTELS       PCBL            URBANCO
CHOICEIN        J&KBANK         PFIZER          USHAMART
CHOLAHLDNG      JAINREC         PGEL            VMM
COHANCE         JBMA            PINELABS        WOCKPHARMA
CONCORDBIO      JPPOWER         PIRAMALFIN      ZENTEC
CPPLUS          JSWCEMENT       POWERINDIA      ZFCVINDIA'''.split()

# Some of these might not be listed exactly as given or are IPOs, e.g., HYUNDAI, SWIGGY, NTPCGREEN, OLAELEC.
# Some might have `.NS` appended.
# I'll create a mapping to check industry.

def get_industry(sym):
    try:
        t = yf.Ticker(f"{sym}.NS")
        info = t.info
        if 'industry' in info:
            return sym, info['sector'], info['industry']
        
        t = yf.Ticker(f"{sym}.BO")
        info = t.info
        if 'industry' in info:
            return sym, info['sector'], info['industry']
            
    except:
        pass
    return sym, "Unknown", "Unknown"

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(get_industry, symbols))

for sym, sector, ind in results:
    print(f"{sym:15} {sector[:20]:20} {ind}")
