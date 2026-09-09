import re

data = """360ONE          Financial Services   Asset Management
CRISIL          Financial Services   Financial Data & Stock Exchanges
JSWDULUX        Unknown              Unknown
PPLPHARMA       Healthcare           Drug Manufacturers - Specialty & Generic
AADHARHFC       Financial Services   Mortgage Finance
DEEPAKFERT      Basic Materials      Chemicals
JYOTICNC        Industrials          Specialty Industrial Machinery
PTCIL           Industrials          Metal Fabrication
ABLBL           Consumer Cyclical    Apparel Retail
ECLERX          Technology           Information Technology Services
KAYNES          Technology           Electronic Components
PWL             Consumer Defensive   Education & Training Services
ABREL           Real Estate          Real Estate Services
ELECON          Industrials          Specialty Industrial Machinery
KFINTECH        Technology           Software - Application
RAILTEL         Communication Servic Telecom Services
ABSLAMC         Financial Services   Asset Management
EMCURE          Healthcare           Drug Manufacturers - Specialty & Generic
KIRLOSENG       Industrials          Specialty Industrial Machinery
RKFORGE         Industrials          Metal Fabrication
ACMESOLAR       Utilities            Utilities - Renewable
ENRIN           Utilities            Utilities - Renewable
KPRMILL         Consumer Cyclical    Textile Manufacturing
RPOWER          Utilities            Utilities - Independent Power Producers
ACUTAAS         Basic Materials      Specialty Chemicals
ETERNAL         Consumer Cyclical    Internet Retail
LATENTVIEW      Industrials          Consulting Services
RRKABEL         Industrials          Electrical Equipment & Parts
AEGISLOG        Energy               Oil & Gas Refining & Marketing
FIRSTCRY        Consumer Cyclical    Internet Retail
LEMONTREE       Consumer Cyclical    Lodging
SAGILITY        Healthcare           Health Information Services
AEGISVOPAK      Energy               Oil & Gas Equipment & Services
FIVESTAR        Financial Services   Credit Services
LENSKART        Healthcare           Medical Instruments & Supplies
SAMMAANCAP      Financial Services   Mortgage Finance
AFCONS          Industrials          Engineering & Construction
FLUOROCHEM      Basic Materials      Specialty Chemicals
LGEINDIA        Technology           Consumer Electronics
SARDAEN         Basic Materials      Steel
AIIL            Financial Services   Capital Markets
FORCEMOT        Consumer Cyclical    Auto Manufacturers
LLOYDSME        Basic Materials      Steel
SAREGAMA        Communication Servic Entertainment
ANANDRATHI      Financial Services   Asset Management
GALLANTT        Basic Materials      Steel
LTF             Financial Services   Credit Services
SBFC            Financial Services   Credit Services
ARE&M           Industrials          Electrical Equipment & Parts
GMRAIRPORT      Industrials          Airports & Air Services
LTFOODS         Consumer Defensive   Packaged Foods
SCI             Industrials          Marine Shipping
ATGL            Utilities            Utilities - Regulated Gas
GODFRYPHLP      Consumer Defensive   Tobacco
LTM             Technology           Information Technology Services
SPLPETRO        Basic Materials      Specialty Chemicals
ATHERENERG      Consumer Cyclical    Auto Manufacturers
GODIGIT         Financial Services   Insurance - Property & Casualty
MEESHO          Consumer Cyclical    Internet Retail
SUNDARMFIN      Financial Services   Credit Services
AWL             Consumer Defensive   Packaged Foods
GVT&D           Industrials          Specialty Industrial Machinery
MMTC            Industrials          Conglomerates
SWANCORP        Industrials          Conglomerates
BBTC            Consumer Defensive   Packaged Foods
HBLENGINE       Industrials          Electrical Equipment & Parts
MSUMI           Consumer Cyclical    Auto Parts
SYRMA           Technology           Electronic Components
BDL             Industrials          Aerospace & Defense
HEXT            Technology           Information Technology Services
NAVA            Industrials          Conglomerates
TARIL           Industrials          Electrical Equipment & Parts
BHARTIHEXA      Communication Servic Telecom Services
HONASA          Consumer Defensive   Household & Personal Products
NETWEB          Technology           Computer Hardware
TATACAP         Financial Services   Asset Management
BIKAJI          Consumer Defensive   Packaged Foods
HYUNDAI         Consumer Cyclical    Auto Manufacturers
NIACL           Financial Services   Insurance - Diversified
TBOTEK          Consumer Cyclical    Travel Services
BLUEDART        Industrials          Integrated Freight & Logistics
IDEA            Communication Servic Telecom Services
NIVABUPA        Financial Services   Insurance - Life
TEJASNET        Technology           Communication Equipment
BLUEJET         Healthcare           Biotechnology
IFCI            Financial Services   Credit Services
NTPCGREEN       Utilities            Utilities - Renewable
TENNIND         Consumer Cyclical    Auto Parts
CAMS            Technology           Information Technology Services
IGIL            Basic Materials      Other Precious Metals & Mining
OLAELEC         Consumer Cyclical    Auto Manufacturers
THELEELA        Consumer Cyclical    Lodging
CCL             Consumer Defensive   Packaged Foods
IKS             Healthcare           Health Information Services
OLECTRA         Industrials          Farm & Heavy Construction Machinery
TMCV            Consumer Cyclical    Auto Manufacturers
CEMPRO          Industrials          Engineering & Construction
INDGN           Healthcare           Health Information Services
ONESOURCE       Healthcare           Biotechnology
TMPV            Consumer Cyclical    Auto Manufacturers
CGCL            Financial Services   Credit Services
IREDA           Financial Services   Credit Services
PARADEEP        Basic Materials      Agricultural Inputs
TRAVELFOOD      Consumer Cyclical    Restaurants
CHENNPETRO      Energy               Oil & Gas Refining & Marketing
ITCHOTELS       Consumer Cyclical    Resorts & Casinos
PCBL            Basic Materials      Specialty Chemicals
URBANCO         Technology           Software - Application
CHOICEIN        Financial Services   Capital Markets
J&KBANK         Financial Services   Banks - Regional
PFIZER          Healthcare           Drug Manufacturers - General
USHAMART        Basic Materials      Steel
CHOLAHLDNG      Financial Services   Credit Services
JAINREC         Basic Materials      Other Industrial Metals & Mining
PGEL            Technology           Electronic Components
VMM             Consumer Cyclical    Department Stores
COHANCE         Healthcare           Drug Manufacturers - Specialty & Generic
JBMA            Consumer Cyclical    Auto Parts
PINELABS        Technology           Software - Infrastructure
WOCKPHARMA      Healthcare           Drug Manufacturers - Specialty & Generic
CONCORDBIO      Healthcare           Biotechnology
JPPOWER         Utilities            Utilities - Independent Power Producers
PIRAMALFIN      Financial Services   Credit Services
ZENTEC          Industrials          Aerospace & Defense
CPPLUS          Industrials          Building Products & Equipment
JSWCEMENT       Basic Materials      Building Materials
POWERINDIA      Industrials          Electrical Equipment & Parts
ZFCVINDIA       Consumer Cyclical    Auto Parts"""

def map_sector(sector, ind):
    if sector == 'Financial Services':
        if 'Bank' in ind:
            return 'NSE:BANKNIFTY'
        return 'NSE:CNXFIN'
    if sector == 'Healthcare':
        return 'NSE:CNXPHARMA'
    if sector == 'Technology':
        return 'NSE:CNXIT'
    if sector == 'Real Estate':
        return 'NSE:CNXREALTY'
    if sector == 'Energy' or sector == 'Utilities':
        return 'NSE:CNXENERGY'
    if sector == 'Consumer Defensive':
        return 'NSE:CNXFMCG'
    if sector == 'Consumer Cyclical':
        if 'Auto' in ind:
            return 'NSE:CNXAUTO'
        return 'NSE:CNXCONSUM'
    if sector == 'Industrials':
        if 'Consulting' in ind:
            return 'NSE:CNXIT'
        return 'NSE:CNXINFRA'
    if sector == 'Communication Servic' or sector == 'Communication Services':
        if 'Entertainment' in ind:
            return 'NSE:CNXMEDIA'
        return 'NSE:CNXINFRA'
    if sector == 'Basic Materials':
        if 'Steel' in ind or 'Metals' in ind:
            return 'NSE:CNXMETAL'
        if 'Chemicals' in ind:
            return 'NSE:CNXCOMMODITIES'
        if 'Building Materials' in ind:
            return 'NSE:CNXINFRA'
        return 'NSE:CNXCOMMODITIES'
    if sector == 'Unknown':
        # JSWDULUX is paint
        return 'NSE:CNXFMCG'
    return 'NSE:CNX500'

results = []
for line in data.strip().split('\n'):
    parts = line.split(maxsplit=2)
    if len(parts) >= 3:
        sym = parts[0]
        sector = parts[1].strip()
        if sector == "Communication" and parts[2].startswith("Servic"):
            sector = "Communication Services"
            ind = parts[2][len("Servic"):].strip()
        else:
            ind = parts[2].strip()
        
        tv_sector = map_sector(sector, ind)
        results.append(f'"{sym}" => "{tv_sector}"')

print("\n".join(results))
