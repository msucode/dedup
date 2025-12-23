import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import re

st.title("Patient Duplicate Finder")

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
    """Use ONLY last 4 digits of mobile for blocking"""
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
    
    top_n = st.slider("Show top matches per record", 1, 5, 3)
    min_score = st.slider("Minimum score", 60, 95, 70)
    
    if st.button("🔍 Find Duplicates"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        # Build block index
        st.info("Building index...")
        yearly_blocks = {}
        for idx, row in df_yearly.iterrows():
            key = get_block_key(row[mobile_col])
            if key not in yearly_blocks:
                yearly_blocks[key] = []
            yearly_blocks[key].append(row)
        
        st.info(f"Index built. Starting comparison...")
        
        all_results = []
        
        for i, daily_row in df_daily.iterrows():
            block_key = get_block_key(daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            daily_name = normalize(daily_row[name_col])
            daily_mobile = normalize(daily_row[mobile_col])
            daily_addr = normalize(daily_row[addr_col])
            
            matches_for_this_record = []
            
            for yearly_row in candidates:
                yearly_name = normalize(yearly_row[name_col])
                yearly_mobile = normalize(yearly_row[mobile_col])
                yearly_addr = normalize(yearly_row[addr_col])
                
                score = 0
                
                # Mobile exact = 50
                if daily_mobile == yearly_mobile:
                    score += 50
                    m_pct = 100
                else:
                    m_pct = 0
                
                # Name fuzzy = 30
                n_pct = fuzz.token_sort_ratio(daily_name, yearly_name)
                score += (n_pct / 100) * 30
                
                # Address fuzzy = 20
                a_pct = fuzz.token_set_ratio(daily_addr, yearly_addr)
                score += (a_pct / 100) * 20
                
                if score >= min_score:
                    matches_for_this_record.append({
                        'score': round(score),
                        'n_pct': n_pct,
                        'm_pct': m_pct,
                        'a_pct': a_pct,
                        'daily_row': daily_row,
                        'yearly_row': yearly_row
                    })
            
            # Keep only TOP N matches for this daily record
            matches_for_this_record.sort(key=lambda x: x['score'], reverse=True)
            matches_for_this_record = matches_for_this_record[:top_n]
            
            for match in matches_for_this_record:
                all_results.append({
                    'Daily_Record': i+1,
                    'Score': match['score'],
                    'Status': '🔴 DUPLICATE' if match['score'] >= 85 else '🟡 REVIEW',
                    'Daily_Name': match['daily_row'][name_col],
                    'Yearly_Name': match['yearly_row'][name_col],
                    'Name_Match': f"{match['n_pct']}%",
                    'Daily_Mobile': match['daily_row'][mobile_col],
                    'Yearly_Mobile': match['yearly_row'][mobile_col],
                    'Mobile_Match': f"{match['m_pct']}%",
                    'Daily_Address': str(match['daily_row'][addr_col])[:60],
                    'Yearly_Address': str(match['yearly_row'][addr_col])[:60],
                    'Address_Match': f"{match['a_pct']}%"
                })
        
        if all_results:
            df_out = pd.DataFrame(all_results)
            st.success(f"✅ Found {len(df_out)} matches from {len(df_daily)} daily records")
            st.caption(f"Showing top {top_n} matches per record, minimum score {min_score}")
            
            st.dataframe(df_out, use_container_width=True, height=600)
            st.download_button("📥 Download", df_out.to_csv(index=False), "duplicates.csv")
        else:
            st.warning(f"No matches found above {min_score} score")
