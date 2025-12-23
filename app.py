import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
import re

st.title("Patient Duplicate Finder")
st.write("Paste Google Sheet URLs (set to 'Anyone with link can view')")

# Input URLs
yearly_url = st.text_input("Yearly Database Sheet URL")
daily_url = st.text_input("Today's Linelist URL")

def convert_to_csv_url(url):
    """Convert Google Sheet URL to CSV export URL"""
    sheet_id = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if sheet_id:
        return f"https://docs.google.com/spreadsheets/d/{sheet_id.group(1)}/export?format=csv"
    return url

def normalize_text(text):
    """Clean text for matching"""
    if pd.isna(text): return ""
    return str(text).lower().strip()

def get_blocking_key(name, mobile):
    """Create blocking key for fast comparison"""
    name_key = normalize_text(name)[:2] if name else ""
    mobile_key = str(mobile)[-4:] if mobile else ""
    return f"{name_key}_{mobile_key}"

def calculate_match_score(row1, row2):
    """Calculate similarity score between two records"""
    score = 0
    details = {}
    
    # Mobile match (50 points)
    mobile1 = normalize_text(row1.get('Mobile', ''))
    mobile2 = normalize_text(row2.get('Mobile', ''))
    if mobile1 and mobile2 and mobile1 == mobile2:
        score += 50
        details['Mobile'] = "100%"
    else:
        details['Mobile'] = "0%"
    
    # Name match (30 points)
    name1 = normalize_text(row1.get('Name', ''))
    name2 = normalize_text(row2.get('Name', ''))
    if name1 and name2:
        name_sim = fuzz.token_sort_ratio(name1, name2)
        score += (name_sim / 100) * 30
        details['Name'] = f"{name_sim}%"
    else:
        details['Name'] = "0%"
    
    # Address match (20 points)
    addr1 = normalize_text(row1.get('Address', ''))
    addr2 = normalize_text(row2.get('Address', ''))
    if addr1 and addr2:
        addr_sim = fuzz.token_set_ratio(addr1, addr2)
        score += (addr_sim / 100) * 20
        details['Address'] = f"{addr_sim}%"
    else:
        details['Address'] = "0%"
    
    return round(score, 1), details

if st.button("Find Duplicates"):
    if yearly_url and daily_url:
        try:
            # Load data
            with st.spinner("Loading sheets..."):
                yearly_csv = convert_to_csv_url(yearly_url)
                daily_csv = convert_to_csv_url(daily_url)
                
                df_yearly = pd.read_csv(yearly_csv)
                df_daily = pd.read_csv(daily_csv)
            
            st.success(f"Loaded: {len(df_yearly)} yearly records, {len(df_daily)} daily records")
            
            # Create blocking index
            with st.spinner("Building search index..."):
                df_yearly['block_key'] = df_yearly.apply(
                    lambda x: get_blocking_key(x.get('Name'), x.get('Mobile')), axis=1
                )
                yearly_blocks = df_yearly.groupby('block_key').apply(lambda x: x.to_dict('records')).to_dict()
            
            # Find matches
            results = []
            with st.spinner("Finding duplicates..."):
                for idx, daily_row in df_daily.iterrows():
                    block_key = get_blocking_key(daily_row.get('Name'), daily_row.get('Mobile'))
                    
                    # Get candidate matches from same block
                    candidates = yearly_blocks.get(block_key, [])
                    
                    # Score all candidates
                    matches = []
                    for yearly_row in candidates:
                        score, details = calculate_match_score(daily_row.to_dict(), yearly_row)
                        if score >= 60:  # Only keep meaningful matches
                            matches.append({
                                'score': score,
                                'yearly_row': yearly_row,
                                'details': details
                            })
                    
                    # Keep top 3 matches
                    matches = sorted(matches, key=lambda x: x['score'], reverse=True)[:3]
                    
                    for match in matches:
                        status = "🔴 HIGH - Duplicate" if match['score'] >= 80 else "🟡 MEDIUM - Review"
                        results.append({
                            'Daily_Name': daily_row.get('Name'),
                            'Daily_Mobile': daily_row.get('Mobile'),
                            'Daily_Address': daily_row.get('Address'),
                            'Daily_Facility': daily_row.get('Facility', ''),
                            'Daily_Disease': daily_row.get('Disease', ''),
                            'Yearly_Name': match['yearly_row'].get('Name'),
                            'Yearly_Mobile': match['yearly_row'].get('Mobile'),
                            'Yearly_Address': match['yearly_row'].get('Address'),
                            'Yearly_Facility': match['yearly_row'].get('Facility', ''),
                            'Yearly_Disease': match['yearly_row'].get('Disease', ''),
                            'Score': match['score'],
                            'Name_Match': match['details']['Name'],
                            'Mobile_Match': match['details']['Mobile'],
                            'Address_Match': match['details']['Address'],
                            'Status': status
                        })
            
            # Display results
            if results:
                df_results = pd.DataFrame(results)
                st.success(f"Found {len(df_results)} potential duplicates")
                
                # Show high confidence first
                df_high = df_results[df_results['Score'] >= 80]
                df_medium = df_results[(df_results['Score'] >= 60) & (df_results['Score'] < 80)]
                
                if len(df_high) > 0:
                    st.subheader(f"🔴 High Confidence Duplicates ({len(df_high)})")
                    st.dataframe(df_high, use_container_width=True)
                
                if len(df_medium) > 0:
                    st.subheader(f"🟡 Need Review ({len(df_medium)})")
                    st.dataframe(df_medium, use_container_width=True)
                
                # Download button
                csv = df_results.to_csv(index=False)
                st.download_button(
                    label="Download Full Report (CSV)",
                    data=csv,
                    file_name="duplicate_report.csv",
                    mime="text/csv"
                )
            else:
                st.info("No duplicates found above 60% threshold")
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.write("Make sure sheets are set to 'Anyone with link can view'")
    else:
        st.warning("Please enter both sheet URLs")
