import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import re

st.title("Patient Duplicate Finder")

yearly_url = st.text_input("Yearly Sheet URL")
daily_url = st.text_input("Daily Sheet URL")

def convert_url(url):
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if match:
        return f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv"
    return url

def clean(text):
    if pd.isna(text):
        return ""
    return str(text).strip().lower()

def is_empty(text):
    cleaned = clean(text)
    return len(cleaned) < 2

if st.button("Load"):
    if yearly_url and daily_url:
        try:
            df_yearly = pd.read_csv(convert_url(yearly_url))
            df_daily = pd.read_csv(convert_url(daily_url))
            st.session_state['yearly'] = df_yearly
            st.session_state['daily'] = df_daily
            st.success(f"Loaded: {len(df_yearly)} yearly, {len(df_daily)} daily")
            st.write("Columns:", list(df_daily.columns))
        except Exception as e:
            st.error(str(e))

if 'yearly' in st.session_state:
    cols = list(st.session_state['daily'].columns)
    
    name_col = st.selectbox("Name Column", cols)
    mobile_col = st.selectbox("Mobile Column", cols)
    addr_col = st.selectbox("Address Column", cols)
    
    if st.button("Find Duplicates"):
        yearly = st.session_state['yearly']
        daily = st.session_state['daily']
        
        results = []
        
        for i, d_row in daily.iterrows():
            d_name = clean(d_row[name_col])
            d_mobile = clean(d_row[mobile_col])
            d_addr = clean(d_row[addr_col])
            
            # Check if blank
            if is_empty(d_row[name_col]) or is_empty(d_row[mobile_col]):
                results.append({
                    'Daily_Rec': i+1,
                    'Type': '🟣 BLANK',
                    'Score': 0,
                    'Daily_Name': d_row[name_col],
                    'Yearly_Name': '-',
                    'Daily_Mobile': d_row[mobile_col],
                    'Yearly_Mobile': '-'
                })
                continue
            
            matches = []
            
            # Compare with all yearly
            for j, y_row in yearly.iterrows():
                y_name = clean(y_row[name_col])
                y_mobile = clean(y_row[mobile_col])
                y_addr = clean(y_row[addr_col])
                
                # Skip blank yearly
                if is_empty(y_row[name_col]) or is_empty(y_row[mobile_col]):
                    continue
                
                # Check exact name match
                if d_name == y_name and d_name != "":
                    matches.append({
                        'type': '🟢 EXACT',
                        'score': 100,
                        'name_pct': 100,
                        'y_row': y_row
                    })
                else:
                    # Fuzzy match
                    name_sim = fuzz.token_sort_ratio(d_name, y_name)
                    addr_sim = fuzz.token_set_ratio(d_addr, y_addr)
                    mobile_same = (d_mobile == y_mobile)
                    
                    if mobile_same:
                        score = 50 + (name_sim/100)*30 + (addr_sim/100)*20
                    else:
                        score = (name_sim/100)*50 + (addr_sim/100)*50
                    
                    if score >= 60:
                        if score >= 85:
                            match_type = '🔴 HIGH'
                        elif score >= 70:
                            match_type = '🟡 MEDIUM'
                        else:
                            match_type = '⚪ LOW'
                        
                        matches.append({
                            'type': match_type,
                            'score': round(score),
                            'name_pct': name_sim,
                            'y_row': y_row
                        })
            
            # Get top 3 matches
            matches.sort(key=lambda x: x['score'], reverse=True)
            for match in matches[:3]:
                results.append({
                    'Daily_Rec': i+1,
                    'Type': match['type'],
                    'Score': match['score'],
                    'Daily_Name': d_row[name_col],
                    'Yearly_Name': match['y_row'][name_col],
                    'Name%': f"{int(match['name_pct'])}%",
                    'Daily_Mobile': d_row[mobile_col],
                    'Yearly_Mobile': match['y_row'][mobile_col]
                })
        
        if results:
            df_results = pd.DataFrame(results)
            st.success(f"Found {len(df_results)} matches")
            st.dataframe(df_results, use_container_width=True)
            st.download_button("Download", df_results.to_csv(index=False), "duplicates.csv")
        else:
            st.warning("No matches")
