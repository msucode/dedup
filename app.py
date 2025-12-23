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

def get_block_key(name, mobile):
    """First 2 chars of name + last 4 of mobile"""
    n = normalize(name)[:2] if name else "XX"
    m = str(mobile)[-4:] if mobile else "0000"
    return f"{n}_{m}"

if st.button("Load Sheets"):
    if yearly_url and daily_url:
        try:
            df_yearly = pd.read_csv(convert_to_csv_url(yearly_url))
            df_daily = pd.read_csv(convert_to_csv_url(daily_url))
            
            st.session_state['df_yearly'] = df_yearly
            st.session_state['df_daily'] = df_daily
            
            st.success(f"✅ {len(df_yearly)} yearly, {len(df_daily)} daily")
            st.write("**Columns:**", list(df_daily.columns[:10]))
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
        
        # Build block index for yearly data
        progress = st.progress(0, "Building index...")
        yearly_blocks = {}
        for idx, row in df_yearly.iterrows():
            key = get_block_key(row[name_col], row[mobile_col])
            if key not in yearly_blocks:
                yearly_blocks[key] = []
            yearly_blocks[key].append(row)
        
        progress.progress(30, "Comparing records...")
        
        results = []
        total = len(df_daily)
        
        for i, daily_row in df_daily.iterrows():
            # Only compare with same block
            block_key = get_block_key(daily_row[name_col], daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            daily_name = normalize(daily_row[name_col])
            daily_mobile = normalize(daily_row[mobile_col])
            daily_addr = normalize(daily_row[addr_col])
            
            for yearly_row in candidates:
                yearly_name = normalize(yearly_row[name_col])
                yearly_mobile = normalize(yearly_row[mobile_col])
                yearly_addr = normalize(yearly_row[addr_col])
                
                score = 0
                
                # Mobile
                if daily_mobile == yearly_mobile:
                    score += 50
                    m_pct = 100
                else:
                    m_pct = 0
                
                # Name
                n_pct = fuzz.token_sort_ratio(daily_name, yearly_name)
                score += (n_pct / 100) * 30
                
                # Address
                a_pct = fuzz.token_set_ratio(daily_addr, yearly_addr)
                score += (a_pct / 100) * 20
                
                if score >= 60:
                    results.append({
                        'Score': round(score),
                        'Status': '🔴' if score >= 80 else '🟡',
                        'Daily_Name': daily_row[name_col],
                        'Yearly_Name': yearly_row[name_col],
                        'N%': n_pct,
                        'Daily_Mobile': daily_row[mobile_col],
                        'Yearly_Mobile': yearly_row[mobile_col],
                        'M%': m_pct,
                        'Daily_Addr': str(daily_row[addr_col])[:50],
                        'Yearly_Addr': str(yearly_row[addr_col])[:50],
                        'A%': a_pct
                    })
            
            if i % 10 == 0:
                progress.progress(30 + int((i/total) * 70))
        
        progress.progress(100, "Done!")
        
        if results:
            df_out = pd.DataFrame(results).sort_values('Score', ascending=False)
            st.success(f"✅ Found {len(df_out)} matches")
            st.dataframe(df_out, use_container_width=True, height=600)
            
            st.download_button("📥 Download", df_out.to_csv(index=False), "duplicates.csv")
        else:
            st.warning("No duplicates found")
