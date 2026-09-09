import csv
import io
import sys
import pandas as pd
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# Verified Nifty categories and official NSE/NiftyIndices endpoints
indices_urls = {
    "Broad Market": {
        "Nifty 50": "ind_nifty50list.csv",
        "Nifty Next 50": "ind_niftynext50list.csv",
        "Nifty 100": "ind_nifty100list.csv",
        "Nifty 200": "ind_nifty200list.csv",
        "Nifty 500": "ind_nifty500list.csv",
        "Nifty Midcap 50": "ind_niftymidcap50list.csv",
        "Nifty Midcap 100": "ind_niftymidcap100list.csv",
        "Nifty Midcap 150": "ind_niftymidcap150list.csv",
        "Nifty Smallcap 50": "ind_niftysmallcap50list.csv",
        "Nifty Smallcap 100": "ind_niftysmallcap100list.csv",
        "Nifty Smallcap 250": "ind_niftysmallcap250list.csv",
        "Nifty Microcap 250": "ind_niftymicrocap250_list.csv",
        "Nifty Total Market": "ind_niftytotalmarket_list.csv",
    },
    "Sectoral": {
        "Nifty Auto": "ind_niftyautolist.csv",
        "Nifty Bank": "ind_niftybanklist.csv",
        "Nifty Financial Services": "ind_niftyfinancelist.csv",
        "Nifty FMCG": "ind_niftyfmcglist.csv",
        "Nifty Healthcare": "ind_niftyhealthcarelist.csv",
        "Nifty IT": "ind_niftyitlist.csv",
        "Nifty Media": "ind_niftymedialist.csv",
        "Nifty Metal": "ind_niftymetallist.csv",
        "Nifty Oil & Gas": "ind_niftyoilgaslist.csv",
        "Nifty Pharma": "ind_niftypharmalist.csv",
        "Nifty Private Bank": "ind_nifty_privatebanklist.csv",
        "Nifty PSU Bank": "ind_niftypsubanklist.csv",
        "Nifty Realty": "ind_niftyrealtylist.csv",
        "Nifty Consumer Durables": "ind_niftyconsumerdurableslist.csv",
    },
    "Thematic": {
        "Nifty Commodities": "ind_niftycommoditieslist.csv",
        "Nifty CPSE": "ind_niftycpselist.csv",
        "Nifty Energy": "ind_niftyenergylist.csv",
        "Nifty India Consumption": "ind_niftyconsumptionlist.csv",
        "Nifty Infrastructure": "ind_niftyinfralist.csv",
        "Nifty MNC": "ind_niftymnclist.csv",
        "Nifty PSE": "ind_niftypselist.csv",
        "Nifty Services Sector": "ind_niftyservicelist.csv",
        "Nifty Housing": "ind_niftyhousing_list.csv",
    },
    "Strategy": {
        "Nifty 200 Alpha 30": "ind_nifty200alpha30_list.csv",
        "Nifty 100 Alpha 30": "ind_nifty100alpha30list.csv",
        "Nifty 100 Low Volatility 30": "ind_nifty100lowvolatility30list.csv",
        "Nifty Quality 30": "ind_niftyquality30list.csv",
        "Nifty Midcap 150 Quality 50": "ind_niftymidcap150quality50list.csv",
        "Nifty Div Opp 50": "ind_niftydivopp50list.csv",
        "Nifty50 Value 20": "ind_nifty50_value20.csv",
    },
}

master_list = []
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

print("Downloading live constituent data from NSE (NiftyIndices)...")

for category, indices in indices_urls.items():
    for index_name, filename in indices.items():
        url = f"https://niftyindices.com/IndexConstituent/{filename}"
        try:
            response = requests.get(url, headers=headers, timeout=12)

            if response.status_code != 200:
                print(f"❌ Failed to fetch: {index_name} (HTTP {response.status_code})")
                continue

            raw_text = response.text.strip()

            # Guard against HTML error pages returned with 200 status code
            if (
                "text/html" in response.headers.get("Content-Type", "").lower()
                or raw_text.lower().startswith("<!doctype")
                or "<html" in raw_text[:300].lower()
            ):
                print(f"⚠️ Skipping {index_name}: Received HTML response instead of CSV.")
                continue

            # Parse CSV rows cleanly
            csv_reader = csv.reader(io.StringIO(raw_text))
            raw_data = [row for row in csv_reader if row and any(cell.strip() for cell in row)]

            if not raw_data:
                print(f"⚠️ Skipping {index_name}: Empty content.")
                continue

            # Locate header row with Symbol / Company Name
            header_idx = None
            for i, row in enumerate(raw_data):
                row_str = " ".join(str(c).lower() for c in row)
                if "symbol" in row_str or "company name" in row_str or "isin code" in row_str:
                    header_idx = i
                    break

            if header_idx is None:
                print(f"⚠️ Skipping {index_name}: Could not detect valid CSV headers.")
                continue

            raw_header = raw_data[header_idx]
            col_names = [h.strip() for h in raw_header if h.strip()]
            num_cols = len(col_names)

            valid_rows = []
            for row in raw_data[header_idx + 1:]:
                if not row or not any(str(c).strip() for c in row):
                    continue

                clean_row = [str(cell).strip() for cell in row[:num_cols]]
                if len(clean_row) < num_cols:
                    clean_row.extend([""] * (num_cols - len(clean_row)))

                # Check if row looks like an HTML fragment or garbage
                first_few = " ".join(clean_row[:3]).lower()
                if "<html" in first_few or "<!doctype" in first_few or "<div" in first_few or "<head" in first_few:
                    continue

                valid_rows.append(clean_row)

            if not valid_rows:
                print(f"⚠️ Skipping {index_name}: No valid rows found.")
                continue

            # Build DataFrame
            df = pd.DataFrame(valid_rows, columns=col_names)

            # Standardize and keep only relevant columns
            normalized_cols = {}
            for col in df.columns:
                c_low = col.lower().strip()
                if "company" in c_low or "security" in c_low:
                    normalized_cols[col] = "Company Name"
                elif "industry" in c_low or "sector" in c_low:
                    normalized_cols[col] = "Industry"
                elif "symbol" in c_low or "ticker" in c_low:
                    normalized_cols[col] = "Symbol"
                elif "isin" in c_low:
                    normalized_cols[col] = "ISIN Code"
                elif "series" in c_low:
                    normalized_cols[col] = "Series"

            df = df.rename(columns=normalized_cols)

            desired_order = ["Company Name", "Industry", "Symbol", "Series", "ISIN Code"]
            existing_cols = [c for c in desired_order if c in df.columns]
            df = df[existing_cols]

            # Filter out any lingering HTML/bad symbols
            if "Symbol" in df.columns:
                df = df[~df["Symbol"].astype(str).str.contains("<|>", na=False)]
                df = df[df["Symbol"].astype(str).str.strip() != ""]

            # Insert metadata columns
            df.insert(0, "Index Name", index_name)
            df.insert(0, "Category", category)

            master_list.append(df)
            print(f"✅ Downloaded: {index_name} ({len(df)} constituents)")

        except Exception as e:
            print(f"⚠️ Error on {index_name}: {e}")

if master_list:
    # Concatenate all parsed dataframes together
    final_df = pd.concat(master_list, ignore_index=True)

    # Save properly to Excel with formatted column widths
    excel_filename = "Nifty_Indices_Master_List.xlsx"
    with pd.ExcelWriter(excel_filename, engine="openpyxl") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Master Constituents")

        ws = writer.sheets["Master Constituents"]
        # Freeze header row
        ws.freeze_panes = "A2"

        # Auto-adjust column widths for a clean look
        for col in ws.columns:
            max_len = 0
            col_letter = col[0].column_letter
            for cell in col:
                val = str(cell.value or "")
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    print(f"\n🎉 Success! Extracted {len(final_df)} total constituent mappings across {len(master_list)} indices.")
    print(f"📁 Saved cleanly to '{excel_filename}'.")
else:
    print("\nNo data fetched. Check your internet connection or proxy settings.")