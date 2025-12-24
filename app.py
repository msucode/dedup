import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import re

st.title("MSU MUMBAI, Patient Duplicate Finder - Exact First, Then Fuzzy")

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
    
    st.subheader("Select Columns to Compare")
    col1, col2 = st.columns(2)
    
    with col1:
        name_col = st.selectbox("Column 1 (Primary - usually Name)", cols, key='col1')
        mobile_col = st.selectbox("Column 2 (Primary - usually Mobile)", cols, key='col2')
    
    with col2:
        addr_col = st.selectbox("Column 3 (Secondary)", cols, key='col3')
        extra_col = st.selectbox("Column 4 (Secondary)", cols, key='col4')
    
    st.caption("Scoring: Col1=30pts, Col2=40pts, Col3=15pts, Col4=15pts | Total=100pts")
    
    if st.button("🔍 Find Duplicates"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        all_results = []
        exact_count = 0
        fuzzy_count = 0
        
        st.info("Building index...")
        yearly_blocks = {}
        for idx, row in df_yearly.iterrows():
            key = get_block_key(row[mobile_col])
            if key not in yearly_blocks:
                yearly_blocks[key] = []
            yearly_blocks[key].append(row)
        
        st.info("Stage 1: Searching EXACT matches...")
        
        for i, daily_row in df_daily.iterrows():
            daily_name = normalize(daily_row[name_col])
            daily_mobile = normalize(daily_row[mobile_col])
            daily_addr = normalize(daily_row[addr_col])
            daily_extra = normalize(daily_row[extra_col])
            
            block_key = get_block_key(daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            exact_matches = []
            fuzzy_matches = []
            
            # STAGE 1: EXACT name match
            for yearly_row in candidates:
                yearly_name = normalize(yearly_row[name_col])
                yearly_mobile = normalize(yearly_row[mobile_col])
                yearly_addr = normalize(yearly_row[addr_col])
                yearly_extra = normalize(yearly_row[extra_col])
                
                if daily_name == yearly_name and daily_name != "":
                    exact_matches.append({
                        'daily_row': daily_row,
                        'yearly_row': yearly_row,
                        'mobile_match': daily_mobile == yearly_mobile,
                        'addr_match': daily_addr == yearly_addr,
                        'extra_match': daily_extra == yearly_extra
                    })
            
            if exact_matches:
                exact_count += 1
                for match in exact_matches[:3]:
                    all_results.append({
                        'Daily_Rec': i+1,
                        'Match_Type': '🟢 EXACT',
                        'Score': 100,
                        'Daily_Col1': match['daily_row'][name_col],
                        'Yearly_Col1': match['yearly_row'][name_col],
                        'Col1%': '100%',
                        'Daily_Col2': match['daily_row'][mobile_col],
                        'Yearly_Col2': match['yearly_row'][mobile_col],
                        'Col2': '✅' if match['mobile_match'] else '❌',
                        'Daily_Col3': str(match['daily_row'][addr_col])[:30],
                        'Yearly_Col3': str(match['yearly_row'][addr_col])[:30],
                        'Col3': '✅' if match['addr_match'] else '❌',
                        'Daily_Col4': str(match['daily_row'][extra_col])[:30],
                        'Yearly_Col4': str(match['yearly_row'][extra_col])[:30],
                        'Col4': '✅' if match['extra_match'] else '❌'
                    })
            
            # STAGE 2: FUZZY
            else:
                for yearly_row in candidates:
                    yearly_name = normalize(yearly_row[name_col])
                    yearly_mobile = normalize(yearly_row[mobile_col])
                    yearly_addr = normalize(yearly_row[addr_col])
                    yearly_extra = normalize(yearly_row[extra_col])
                    
                    # Calculate fuzzy scores for all 4 columns
                    col1_pct = fuzz.token_sort_ratio(daily_name, yearly_name)
                    col2_match = (daily_mobile == yearly_mobile)
                    col3_pct = fuzz.token_set_ratio(daily_addr, yearly_addr)
                    col3_match = (daily_addr == yearly_addr)
                    col4_pct = fuzz.token_set_ratio(daily_extra, yearly_extra)
                    col4_match = (daily_extra == yearly_extra)
                    
                    # NEW SCORING: 40+30+15+15 = 100
                    score = 0
                    if col2_match:
                        score += 40  # Column 2 (mobile) exact match
                    
                    score += (col1_pct / 100) * 30  # Column 1 (name) fuzzy
                    score += (col3_pct / 100) * 15  # Column 3 fuzzy
                    score += (col4_pct / 100) * 15  # Column 4 fuzzy
                    
                    if score >= 85:
                        match_type = '🔴 HIGH'
                    elif score >= 70:
                        match_type = '🟡 MEDIUM'
                    elif score >= 60:
                        match_type = '⚪ LOW'
                    else:
                        continue
                    
                    fuzzy_matches.append({
                        'score': round(score),
                        'col1_pct': col1_pct,
                        'col2_match': col2_match,
                        'col3_pct': col3_pct,
                        'col3_match': col3_match,
                        'col4_pct': col4_pct,
                        'col4_match': col4_match,
                        'match_type': match_type,
                        'daily_row': daily_row,
                        'yearly_row': yearly_row
                    })
                
                if fuzzy_matches:
                    fuzzy_count += 1
                    fuzzy_matches.sort(key=lambda x: x['score'], reverse=True)
                    for match in fuzzy_matches[:3]:
                        all_results.append({
                            'Daily_Rec': i+1,
                            'Match_Type': match['match_type'],
                            'Score': match['score'],
                            'Daily_Col1': match['daily_row'][name_col],
                            'Yearly_Col1': match['yearly_row'][name_col],
                            'Col1%': f"{int(match['col1_pct'])}%",
                            'Daily_Col2': match['daily_row'][mobile_col],
                            'Yearly_Col2': match['yearly_row'][mobile_col],
                            'Col2': '✅' if match['col2_match'] else '❌',
                            'Daily_Col3': str(match['daily_row'][addr_col])[:30],
                            'Yearly_Col3': str(match['yearly_row'][addr_col])[:30],
                            'Col3': '✅' if match['col3_match'] else '❌',
                            'Col3%': f"{int(match['col3_pct'])}%",
                            'Daily_Col4': str(match['daily_row'][extra_col])[:30],
                            'Yearly_Col4': str(match['yearly_row'][extra_col])[:30],
                            'Col4': '✅' if match['col4_match'] else '❌',
                            'Col4%': f"{int(match['col4_pct'])}%"
                        })
        
        st.success(f"✅ {exact_count} EXACT | {fuzzy_count} FUZZY")
        
        if all_results:
            df_out = pd.DataFrame(all_results)
            
            exact = df_out[df_out['Match_Type'].str.contains('EXACT')]
            high = df_out[df_out['Match_Type'].str.contains('HIGH')]
            medium = df_out[df_out['Match_Type'].str.contains('MEDIUM')]
            low = df_out[df_out['Match_Type'].str.contains('LOW')]
            
            if len(exact) > 0:
                st.subheader(f"🟢 Exact ({len(exact)})")
                st.dataframe(exact, use_container_width=True)
            
            if len(high) > 0:
                st.subheader(f"🔴 High ({len(high)})")
                st.dataframe(high, use_container_width=True)
            
            if len(medium) > 0:
                st.subheader(f"🟡 Medium ({len(medium)})")
                st.dataframe(medium, use_container_width=True)
            
            if len(low) > 0:
                with st.expander(f"⚪ Low ({len(low)})"):
                    st.dataframe(low, use_container_width=True)
            
            st.download_button("📥 Download", df_out.to_csv(index=False), "duplicates.csv")
        else:
            st.warning("No matches")
