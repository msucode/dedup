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

def normalize_text(text):
    if pd.isna(text): return ""
    return str(text).lower().strip()

if st.button("Load & Map Columns"):
    if yearly_url and daily_url:
        try:
            yearly_csv = convert_to_csv_url(yearly_url)
            daily_csv = convert_to_csv_url(daily_url)
            
            df_yearly = pd.read_csv(yearly_csv)
            df_daily = pd.read_csv(daily_csv)
            
            st.session_state['df_yearly'] = df_yearly
            st.session_state['df_daily'] = df_daily
            
            st.success(f"Loaded: {len(df_yearly)} yearly, {len(df_daily)} daily")
            st.write("**Yearly Columns:**", list(df_yearly.columns))
            st.write("**Daily Columns:**", list(df_daily.columns))
            
        except Exception as e:
            st.error(f"Error: {e}")

if 'df_yearly' in st.session_state:
    st.subheader("Map Your Columns")
    
    yearly_cols = list(st.session_state['df_yearly'].columns)
    daily_cols = list(st.session_state['df_daily'].columns)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Yearly Sheet Mapping:**")
        yearly_name = st.selectbox("Name Column (Yearly)", yearly_cols, key='yn')
        yearly_mobile = st.selectbox("Mobile Column (Yearly)", yearly_cols, key='ym')
        yearly_address = st.selectbox("Address Column (Yearly)", yearly_cols, key='ya')
        yearly_facility = st.selectbox("Facility Column (Yearly)", yearly_cols, key='yf')
        yearly_disease = st.selectbox("Disease Column (Yearly)", yearly_cols, key='yd')
    
    with col2:
        st.write("**Daily Sheet Mapping:**")
        daily_name = st.selectbox("Name Column (Daily)", daily_cols, key='dn')
        daily_mobile = st.selectbox("Mobile Column (Daily)", daily_cols, key='dm')
        daily_address = st.selectbox("Address Column (Daily)", daily_cols, key='da')
        daily_facility = st.selectbox("Facility Column (Daily)", daily_cols, key='df')
        daily_disease = st.selectbox("Disease Column (Daily)", daily_cols, key='dd')
    
    if st.button("Find Duplicates Now"):
        df_yearly = st.session_state['df_yearly']
        df_daily = st.session_state['df_daily']
        
        results = []
        
        with st.spinner("Comparing records..."):
            for idx, daily_row in df_daily.iterrows():
                daily_name_val = normalize_text(daily_row[daily_name])
                daily_mobile_val = normalize_text(daily_row[daily_mobile])
                daily_addr_val = normalize_text(daily_row[daily_address])
                
                for yidx, yearly_row in df_yearly.iterrows():
                    yearly_name_val = normalize_text(yearly_row[yearly_name])
                    yearly_mobile_val = normalize_text(yearly_row[yearly_mobile])
                    yearly_addr_val = normalize_text(yearly_row[yearly_address])
                    
                    score = 0
                    name_sim = 0
                    mobile_sim = 0
                    addr_sim = 0
                    
                    # Mobile exact match = 50 points
                    if daily_mobile_val and yearly_mobile_val:
                        if daily_mobile_val == yearly_mobile_val:
                            score += 50
                            mobile_sim = 100
                        else:
                            mobile_sim = fuzz.ratio(daily_mobile_val, yearly_mobile_val)
                            if mobile_sim > 80:
                                score += (mobile_sim / 100) * 50
                    
                    # Name fuzzy match = 30 points
                    if daily_name_val and yearly_name_val:
                        name_sim = fuzz.token_sort_ratio(daily_name_val, yearly_name_val)
                        score += (name_sim / 100) * 30
                    
                    # Address fuzzy match = 20 points
                    if daily_addr_val and yearly_addr_val:
                        addr_sim = fuzz.token_set_ratio(daily_addr_val, yearly_addr_val)
                        score += (addr_sim / 100) * 20
                    
                    if score >= 60:
                        status = "🔴 HIGH" if score >= 80 else "🟡 REVIEW"
                        results.append({
                            'Status': status,
                            'Score': round(score, 1),
                            'Daily_Name': daily_row[daily_name],
                            'Yearly_Name': yearly_row[yearly_name],
                            'Name%': f"{int(name_sim)}%",
                            'Daily_Mobile': daily_row[daily_mobile],
                            'Yearly_Mobile': yearly_row[yearly_mobile],
                            'Mobile%': f"{int(mobile_sim)}%",
                            'Daily_Address': daily_row[daily_address],
                            'Yearly_Address': yearly_row[yearly_address],
                            'Address%': f"{int(addr_sim)}%",
                            'Daily_Facility': daily_row[daily_facility],
                            'Yearly_Facility': yearly_row[yearly_facility],
                            'Daily_Disease': daily_row[daily_disease],
                            'Yearly_Disease': yearly_row[yearly_disease]
                        })
        
        if results:
            df_results = pd.DataFrame(results)
            df_results = df_results.sort_values('Score', ascending=False)
            
            st.success(f"Found {len(df_results)} matches")
            
            high = df_results[df_results['Score'] >= 80]
            medium = df_results[(df_results['Score'] >= 60) & (df_results['Score'] < 80)]
            
            if len(high) > 0:
                st.subheader(f"🔴 High Confidence ({len(high)})")
                st.dataframe(high, use_container_width=True)
            
            if len(medium) > 0:
                st.subheader(f"🟡 Review Needed ({len(medium)})")
                st.dataframe(medium, use_container_width=True)
            
            csv = df_results.to_csv(index=False)
            st.download_button("Download CSV", csv, "duplicates.csv", "text/csv")
        else:
            st.info("No duplicates found")
