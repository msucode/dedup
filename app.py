import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import re

st.title("Patient Duplicate Finder v2")

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
    
    st.subheader("Select Columns")
    name_col = st.selectbox("Name", cols)
    mobile_col = st.selectbox("Mobile", cols)
    addr_col = st.selectbox("Address", cols)
    
    if st.button("🔍 Find Duplicates"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        st.info("Building index...")
        yearly_blocks = {}
        for idx, row in df_yearly.iterrows():
            key = get_block_key(row[mobile_col])
            if key not in yearly_blocks:
                yearly_blocks[key] = []
            yearly_blocks[key].append(row)
        
        st.info("Comparing records...")
        
        all_results = []
        
        for i, daily_row in df_daily.iterrows():
            block_key = get_block_key(daily_row[mobile_col])
            candidates = yearly_blocks.get(block_key, [])
            
            daily_name = normalize(daily_row[name_col])
            daily_mobile = normalize(daily_row[mobile_col])
            daily_addr = normalize(daily_row[addr_col])
            
            matches = []
            
            for yearly_row in candidates:
                yearly_name = normalize(yearly_row[name_col])
                yearly_mobile = normalize(yearly_row[mobile_col])
                yearly_addr = normalize(yearly_row[addr_col])
                
                # Name similarity
                n_pct = fuzz.token_sort_ratio(daily_name, yearly_name)
                
                # Mobile match
                mobile_match = (daily_mobile == yearly_mobile)
                
                # Address similarity
                a_pct = fuzz.token_set_ratio(daily_addr, yearly_addr)
                
                # NEW STRICTER LOGIC
                score = 0
                confidence = "❌ NOT DUPLICATE"
                
                # HIGH CONFIDENCE (≥90): Mobile + Name must BOTH be strong
                if mobile_match and n_pct >= 80:
                    score = 50 + (n_pct/100)*30 + (a_pct/100)*20
                    if score >= 90:
                        confidence = "🔴 HIGH - Same Person"
                    elif score >= 80:
                        confidence = "🟡 MEDIUM - Check Name"
                    else:
                        confidence = "⚪ LOW - Weak Match"
                
                # MEDIUM (70-89): Mobile match but name is weak = FAMILY or ERROR
                elif mobile_match and n_pct >= 50:
                    score = 50 + (n_pct/100)*30 + (a_pct/100)*20
                    confidence = "⚪ LOW - Same Mobile, Different Name (Family?)"
                
                # NO MOBILE MATCH: Need very high name+address
                elif n_pct >= 90 and a_pct >= 70:
                    score = (n_pct/100)*50 + (a_pct/100)*50
                    confidence = "🟡 MEDIUM - No Mobile Match"
                
                if score >= 70 or (mobile_match and n_pct >= 50):
                    matches.append({
                        'score': round(score),
                        'n_pct': n_pct,
                        'a_pct': a_pct,
                        'mobile_match': mobile_match,
                        'confidence': confidence,
                        'daily_row': daily_row,
                        'yearly_row': yearly_row
                    })
            
            # Sort and keep top 5
            matches.sort(key=lambda x: (x['score'], x['n_pct']), reverse=True)
            matches = matches[:5]
            
            for rank, match in enumerate(matches, 1):
                all_results.append({
                    'Daily_Rec': i+1,
                    'Rank': rank,
                    'Score': match['score'],
                    'Confidence': match['confidence'],
                    'Daily_Name': match['daily_row'][name_col],
                    'Yearly_Name': match['yearly_row'][name_col],
                    'Name%': f"{int(match['n_pct'])}%",
                    'Daily_Mobile': match['daily_row'][mobile_col],
                    'Yearly_Mobile': match['yearly_row'][mobile_col],
                    'Mobile': '✅' if match['mobile_match'] else '❌',
                    'Daily_Addr': str(match['daily_row'][addr_col])[:40],
                    'Yearly_Addr': str(match['yearly_row'][addr_col])[:40],
                    'Addr%': f"{int(match['a_pct'])}%"
                })
        
        if all_results:
            df_out = pd.DataFrame(all_results)
            
            # Separate into categories
            high = df_out[df_out['Confidence'].str.contains('HIGH')]
            medium = df_out[df_out['Confidence'].str.contains('MEDIUM')]
            low = df_out[df_out['Confidence'].str.contains('LOW')]
            
            st.success(f"✅ Results: {len(high)} High Confidence, {len(medium)} Medium, {len(low)} Low")
            
            if len(high) > 0:
                st.subheader("🔴 High Confidence Duplicates (Same Person)")
                st.dataframe(high, use_container_width=True)
            
            if len(medium) > 0:
                st.subheader("🟡 Medium - Needs Manual Check")
                st.dataframe(medium, use_container_width=True)
            
            if len(low) > 0:
                with st.expander("⚪ Low Confidence (Likely Different People)"):
                    st.dataframe(low, use_container_width=True)
            
            st.download_button("📥 Download All", df_out.to_csv(index=False), "results.csv")
        else:
            st.warning("No matches found")
