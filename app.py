import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import re

st.title("Patient Duplicate Finder - Exact First, Then Fuzzy")

yearly_url = st.text_input("Yearly Database Sheet URL")
daily_url = st.text_input("Today's Linelist URL")

def convert_to_csv_url(url):
    sheet_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if sheet_id:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id.group(1)}/export?format=csv"
    return url

def normalize(text):
    if pd.isna(text): return ""
    return str(text).lower().strip()

def is_blank(text):
    normalized = normalize(text)
    return normalized == "" or normalized == "nan" or len(normalized) < 2

def get_block_key(mobile):
    m = str(mobile).strip()[-4:] if mobile else "XXXX"
    return m

if st.button("Load Sheets"):
    if yearly_url and daily_url:
        try:
            df_yearly = pd.read_csv(convert_to_csv_url(yearly_url))
            df_daily = pd.read_csv(convert_to_csv_url(daily_url))
            
            st.session_state['df_yearly'] = df_yearly
            st.session_state['df_daily'] = df_daily
            
            st.success(f"✅ {len(df_yearly)} yearly, {len(df_daily)} daily")
            st.write("**Columns:**", list(df_daily.columns[:15]))
        except Exception as e:
            st.error(f"❌ {e}")

if 'df_yearly' in st.session_state:
    cols = list(st.session_state['df_daily'].columns)
    
    st.subheader("Select Columns")
    name_col = st.selectbox("Name", cols)
    mobile_col = st.selectbox("Mobile", cols)
    addr_col = st.selectbox("Address", cols)
    
    if st.button("🔍 Find Duplicates"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        all_results = []
        exact_count = 0
        fuzzy_count = 0
        blank_count = 0
        
        # Build index - include ALL yearly records
        st.info("Building index...")
        yearly_blocks = {}
        for idx, row in df_yearly.iterrows():
            key = get_block_key(row[mobile_col])
            if key not in yearly_blocks:
                yearly_blocks[key] = []
            yearly_blocks[key].append(row)
        
        st.info("Stage 1: Checking for EXACT matches...")
        
        # Process each daily record
        for i, daily_row in df_daily.iterrows():
            # CHECK if daily has blank name or mobile
            daily_has_blank = is_blank(daily_row[name_col]) or is_blank(daily_row[mobile_col])
            
            # If blank, flag as PINK and continue to next
            if daily_has_blank:
                blank_count += 1
                all_results.append({
                    'Daily_Rec': i+1,
                    'Match_Type': '🟣 PINK - Blank Name/Mobile',
                    'Score': 0,
                    'Daily_Name': daily_row[name_col],
                    'Yearly_Name': 'N/A',
                    'Name%': 'N/A',
                    'Daily_Mobile': daily_row[mobile_col],
                    'Yearly_Mobile': 'N/A',
                    'Mobile': 'N/A',
                    'Daily_Addr': str(daily_row[addr_col])[:40],
                    'Yearly_Addr': 'N/A'
                })
                continue
            
            daily_name = normalize(daily_row[name_col])
            daily_mobile = normalize(daily_row[mobile_col])
            daily_addr = normalize(daily_row[addr_col])
            
            block_key = get_block_key(daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            exact_matches = []
            fuzzy_matches = []
            
            # STAGE 1: Check EXACT name match
            for yearly_row in candidates:
                yearly_name = normalize(yearly_row[name_col])
                yearly_mobile = normalize(yearly_row[mobile_col])
                yearly_addr = normalize(yearly_row[addr_col])
                
                # Skip yearly if it has blanks
                if is_blank(yearly_row[name_col]) or is_blank(yearly_row[mobile_col]):
                    continue
                
                if daily_name == yearly_name:
                    exact_matches.append({
                        'daily_row': daily_row,
                        'yearly_row': yearly_row,
                        'mobile_match': daily_mobile == yearly_mobile
                    })
            
            # If EXACT match found
            if exact_matches:
                exact_count += 1
                for match in exact_matches[:3]:
                    all_results.append({
                        'Daily_Rec': i+1,
                        'Match_Type': '🟢 EXACT NAME MATCH',
                        'Score': 100,
                        'Daily_Name': match['daily_row'][name_col],
                        'Yearly_Name': match['yearly_row'][name_col],
                        'Name%': '100%',
                        'Daily_Mobile': match['daily_row'][mobile_col],
                        'Yearly_Mobile': match['yearly_row'][mobile_col],
                        'Mobile': '✅' if match['mobile_match'] else '❌',
                        'Daily_Addr': str(match['daily_row'][addr_col])[:40],
                        'Yearly_Addr': str(match['yearly_row'][addr_col])[:40]
                    })
            
            # STAGE 2: FUZZY search
            else:
                for yearly_row in candidates:
                    yearly_name = normalize(yearly_row[name_col])
                    yearly_mobile = normalize(yearly_row[mobile_col])
                    yearly_addr = normalize(yearly_row[addr_col])
                    
                    # Skip yearly if blank
                    if is_blank(yearly_row[name_col]) or is_blank(yearly_row[mobile_col]):
                        continue
                    
                    n_pct = fuzz.token_sort_ratio(daily_name, yearly_name)
                    a_pct = fuzz.token_set_ratio(daily_addr, yearly_addr)
                    mobile_match = (daily_mobile == yearly_mobile)
                    
                    score = 0
                    
                    if mobile_match:
                        score = 50 + (n_pct/100)*30 + (a_pct/100)*20
                    else:
                        score = (n_pct/100)*50 + (a_pct/100)*50
                    
                    if score >= 85:
                        match_type = '🔴 HIGH - Fuzzy Match'
                    elif score >= 70:
                        match_type = '🟡 MEDIUM - Fuzzy Match'
                    elif score >= 60:
                        match_type = '⚪ LOW - Fuzzy Match'
                    else:
                        continue
                    
                    fuzzy_matches.append({
                        'score': round(score),
                        'n_pct': n_pct,
                        'a_pct': a_pct,
                        'mobile_match': mobile_match,
                        'match_type': match_type,
                        'daily_row': daily_row,
                        'yearly_row': yearly_row
                    })
                
                if fuzzy_matches:
                    fuzzy_count += 1
                    fuzzy_matches.sort(key=lambda x: x['score'], reverse=True)
                    for match in fuzzy
