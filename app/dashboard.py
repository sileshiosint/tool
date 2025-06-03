import streamlit as st
import pandas as pd
import time
import sqlite3
import json
import os

# --- Configuration ---
DATABASE_NAME = "data/social_media_analysis.db"

# Attempt to import project modules
try:
    from scripts.facebook_scraper import scrape_facebook_page_posts # (and others, kept short for example)
    from scripts.twitter_scraper import scrape_tweets_by_keyword # (and others)
    from scripts.nlp_analyzer import add_sentiment_to_dataframe, add_topic_classification_to_dataframe
    from scripts.report_generator import generate_pdf_report, generate_html_report
    from scripts.auth import get_user, verify_password # Added for authentication
    IMPORTS_SUCCESSFUL = True
    IMPORT_ERROR_MESSAGE = "" # Initialize IMPORT_ERROR_MESSAGE
except ImportError as e:
    # This error will be shown on the Streamlit page if imports fail
    IMPORTS_SUCCESSFUL = False
    IMPORT_ERROR_MESSAGE = str(e) # Store the import error message
    # Define dummy functions if imports fail, so the app can attempt to load parts of the UI
    # Scraper dummies
    def scrape_facebook_page_posts(*args, **kwargs): st.error(f"Module Error: {IMPORT_ERROR_MESSAGE}"); return pd.DataFrame()
    def scrape_tweets_by_keyword(*args, **kwargs): st.error(f"Module Error: {IMPORT_ERROR_MESSAGE}"); return pd.DataFrame()
    # NLP dummies
    def add_sentiment_to_dataframe(df, text_column_name): df['sentiment_label'] = 'N/A (Import Error)'; df['sentiment_score'] = 0.0; return df
    def add_topic_classification_to_dataframe(df, topics, text_column_name): df['topic_label'] = 'N/A (Import Error)'; df['topic_score'] = 0.0; return df
    # Report dummies
    def generate_pdf_report(*args, **kwargs): st.error(f"Module Error: {IMPORT_ERROR_MESSAGE}"); return None
    def generate_html_report(*args, **kwargs): st.error(f"Module Error: {IMPORT_ERROR_MESSAGE}"); return None
    # Auth dummies
    def get_user(username): st.error(f"Critical Auth Module Error: {IMPORT_ERROR_MESSAGE}"); return None
    def verify_password(s, h, p): st.error(f"Critical Auth Module Error: {IMPORT_ERROR_MESSAGE}"); return False


DEFAULT_CANDIDATE_TOPICS = [
    "armed conflict", "ceasefire violation", "peace talks", "humanitarian crisis",
    "displacement", "election security", "extremist propaganda", "hate speech",
    "human rights abuse", "political instability", "social unrest", "protest", "terrorism"
]

# --- Session State Initialization ---
# Ensure all necessary session state keys are initialized once
def init_session_state():
    defaults = {
        'authenticated_user': None,
        'login_message': None,
        'scan_results': pd.DataFrame(),
        'last_scan_params': {},
        'last_report_query': ""
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- Database Helper Functions (condensed) ---
def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def save_data_to_db(df_analyzed, platform, query, text_col_name):
    if df_analyzed.empty: return 0
    conn = get_db_connection(); cursor = conn.cursor(); rows_added = 0
    for _, row in df_analyzed.iterrows():
        post_text = row.get(text_col_name, ""); post_id_on_platform = row.get('post_id_on_platform', f"{platform.lower()}_{pd.Timestamp.now().timestamp()}_{hash(post_text)}_{rows_added}") # Added rows_added for more uniqueness
        user_name = row.get('user_name_on_platform', 'N/A'); post_url = query if query and (query.startswith('http://') or query.startswith('https://')) else None # Corrected get post_url
        raw_j = json.dumps(row.to_dict())
        try:
            cursor.execute("INSERT OR IGNORE INTO scraped_content (platform, source_query, post_id_on_platform, user_name_on_platform, post_url, post_text, raw_data_json) VALUES (?, ?, ?, ?, ?, ?, ?)", (platform, query, post_id_on_platform, user_name, post_url, post_text, raw_j))
            content_id = None
            if cursor.lastrowid: content_id = cursor.lastrowid; rows_added +=1
            else:
                cursor.execute("SELECT id FROM scraped_content WHERE post_id_on_platform = ?", (post_id_on_platform,)); existing_row = cursor.fetchone()
                if existing_row: content_id = existing_row['id']
            if content_id:
                cursor.execute("INSERT INTO analysis_results (content_id, sentiment_label, sentiment_score, topic_label, topic_score) VALUES (?, ?, ?, ?, ?)", (content_id, row.get('sentiment_label'), row.get('sentiment_score'), row.get('topic_label'), row.get('topic_score'))) # topic_label from NLP
        except sqlite3.Error as e: st.warning(f"DB Error saving {post_id_on_platform}: {e}")
    conn.commit(); conn.close(); return rows_added

def load_results_from_db(query_filter=None, limit=100):
    conn = get_db_connection()
    sql_q = """SELECT sc.*, ar.sentiment_label, ar.sentiment_score, ar.topic_label, ar.topic_score, ar.analysis_timestamp
               FROM scraped_content sc
               LEFT JOIN (
                   SELECT *, ROW_NUMBER() OVER(PARTITION BY content_id ORDER BY analysis_timestamp DESC) as rn
                   FROM analysis_results
               ) ar ON sc.id = ar.content_id AND ar.rn = 1"""
    params = []
    if query_filter: sql_q += " WHERE sc.source_query LIKE ?"; params.append(f"%{query_filter}%")
    sql_q += " ORDER BY sc.scraped_timestamp DESC LIMIT ?"; params.append(limit)
    df = pd.read_sql_query(sql_q, conn, params=params); conn.close(); return df

# --- Scan Logic (condensed) ---
def run_scan(platform, query, twitter_scrape_type, num_items):
    st.session_state.scan_results = pd.DataFrame(); raw_data = pd.DataFrame(); text_col_name = "text"; data_found_simulated = False
    with st.spinner(f"Simulating scan for {platform} '{query}'..."):
        if platform == "Facebook": sim_posts = [{'post_id_on_platform': f"fb_post_{query.replace(' ','_')}_{i}_{int(time.time())}_{hash(str(i))}", 'url': query, 'post_text': f"FB sample {i} for {query}", 'user_name_on_platform': f"FBUser{i}", 'scraped_at': time.time()} for i in range(num_items)]; raw_data = pd.DataFrame(sim_posts); text_col_name = "post_text"; data_found_simulated = True # Added scraped_at
        elif platform == "Twitter": sim_tweets = [{'post_id_on_platform': f"tw_tweet_{query.replace(' ','_')}_{i}_{int(time.time())}_{hash(str(i))}", 'source_info': query, 'tweet_text': f"Twitter sample {i} for {query} ({twitter_scrape_type})", 'user_name_on_platform': f"TwitterUser{i}", 'scraped_at': time.time()} for i in range(num_items)]; raw_data = pd.DataFrame(sim_tweets); text_col_name = "tweet_text"; data_found_simulated = True # Added scraped_at
        else: st.warning(f"Platform '{platform}' not fully implemented.")
        if data_found_simulated and not raw_data.empty:
            analyzed_data = add_sentiment_to_dataframe(raw_data.copy(), text_column_name=text_col_name)
            analyzed_data = add_topic_classification_to_dataframe(analyzed_data, DEFAULT_CANDIDATE_TOPICS, text_column_name=text_col_name)
            if 'topic' in analyzed_data.columns and 'topic_label' not in analyzed_data.columns: analyzed_data.rename(columns={'topic': 'topic_label', 'topic_score': 'topic_score'}, inplace=True) # Ensure correct column name
            rows_saved = save_data_to_db(analyzed_data, platform, query, text_col_name); st.success(f"{rows_saved} new items processed and saved.")
    st.session_state.scan_results = load_results_from_db(query_filter=query); st.session_state.last_report_query = query
    if st.session_state.scan_results.empty: st.caption(f"No results in DB for '{query}'.")


# --- Login Form ---
def display_login_form():
    st.subheader("Analyst Login")
    if st.session_state.login_message:
        st.error(st.session_state.login_message)

    with st.form("login_form"):
        username = st.text_input("Username", key="login_username_input")
        password = st.text_input("Password", type="password", key="login_password_input")
        submitted = st.form_submit_button("Login")

        if submitted:
            if not username or not password:
                st.session_state.login_message = "Username and password are required."
            else:
                user_data = get_user(username) # From scripts.auth
                if user_data and verify_password(user_data['salt'], user_data['hashed_password'], password): # From scripts.auth
                    st.session_state.authenticated_user = user_data['username']
                    st.session_state.login_message = None
                else:
                    st.session_state.login_message = "Invalid username or password."
            st.experimental_rerun()
    st.caption("If this is the first run, or you need to add users, use the `scripts/manage_users.py` command-line tool.")


# --- Main Application ---
def main_app_content():
    st.sidebar.success(f"Logged in as: {st.session_state.authenticated_user}")
    if st.sidebar.button("Logout", key="logout_button"):
        # Clear relevant session state keys upon logout
        keys_to_clear = ['authenticated_user', 'scan_results', 'last_scan_params', 'last_report_query']
        for key in keys_to_clear:
            if key in st.session_state:
                if isinstance(st.session_state[key], pd.DataFrame):
                    st.session_state[key] = pd.DataFrame() # Clear DataFrame
                elif isinstance(st.session_state[key], dict):
                     st.session_state[key] = {} # Clear dict
                else:
                    st.session_state[key] = None # Set others to None
        st.session_state.login_message = "You have been logged out."
        st.experimental_rerun()

    st.sidebar.header("Scan Parameters")
    platform = st.sidebar.selectbox("Select Platform", ["Facebook", "Twitter"], key="app_platform_select")
    twitter_scrape_type = st.sidebar.selectbox("Twitter Scan Type", ["Keyword", "User Profile"], key="app_twitter_type_select") if platform == "Twitter" else ""
    query = st.sidebar.text_input("Enter Username/Keyword/URL", key="app_query_input")
    num_items_to_scrape = st.sidebar.slider("Number of items to SIMULATE", 1, 30, 5, key="app_num_items_slider")

    current_scan_params = {"platform": platform, "query": query, "twitter_scrape_type": twitter_scrape_type, "num_items": num_items_to_scrape}

    if st.sidebar.button("Start Scan & Save", key="app_start_scan_button"):
        if query:
            st.session_state.last_scan_params = current_scan_params.copy()
            run_scan(platform, query, twitter_scrape_type, num_items_to_scrape)
        else: st.sidebar.warning("Please enter a search query.")

    if not query and st.session_state.last_scan_params.get("query") and st.session_state.scan_results.empty:
        last_query_val = st.session_state.last_scan_params.get("query")
        st.info(f"No current query. Loading previous results for: '{last_query_val}'")
        st.session_state.scan_results = load_results_from_db(query_filter=last_query_val)
        st.session_state.last_report_query = last_query_val

    st.header("Scan Results (from Database)")
    if not st.session_state.scan_results.empty:
        display_cols = [col for col in ["platform", "source_query", "post_text", "user_name_on_platform", "sentiment_label", "sentiment_score", "topic_label", "topic_score", "scraped_timestamp", "post_id_on_platform"] if col in st.session_state.scan_results.columns]
        st.dataframe(st.session_state.scan_results[display_cols])
        col_charts1, col_charts2 = st.columns(2)
        with col_charts1:
            if 'sentiment_label' in st.session_state.scan_results.columns: st.bar_chart(st.session_state.scan_results['sentiment_label'].value_counts())
        with col_charts2:
            if 'topic_label' in st.session_state.scan_results.columns: st.bar_chart(st.session_state.scan_results['topic_label'].value_counts())
    else: st.caption("No data to display. Run a scan or check database for current query.")

    st.header("Reporting")
    active_query_for_report = query if query else st.session_state.last_report_query
    if not st.session_state.scan_results.empty:
        report_query_display = active_query_for_report or "current_selection"; report_timestamp = time.strftime("%Y%m%d_%H%M%S")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Generate HTML Report", key="app_html_report_button"):
                fn_html = f"report_html_{report_query_display.replace(' ','_').replace('/','_').replace(':','_')}_{report_timestamp}.html"
                html_path = generate_html_report(st.session_state.scan_results, f"HTML Report: {report_query_display}", output_filename=fn_html)
                if html_path and os.path.exists(html_path):
                    with open(html_path, "r", encoding="utf-8") as f: html_bytes = f.read()
                    st.download_button("Download HTML", html_bytes, fn_html, "text/html", key="app_download_html_button"); st.success(f"HTML: {fn_html}")
                else: st.error("Failed to generate HTML report.")
        with col2:
            if st.button("Generate PDF Report", key="app_pdf_report_button"):
                fn_pdf = f"report_pdf_{report_query_display.replace(' ','_').replace('/','_').replace(':','_')}_{report_timestamp}.pdf"
                pdf_path = generate_pdf_report(st.session_state.scan_results, f"PDF Report: {report_query_display}", output_filename=fn_pdf)
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f: pdf_bytes = f.read()
                    st.download_button("Download PDF", pdf_bytes, fn_pdf, "application/pdf", key="app_download_pdf_button"); st.success(f"PDF: {fn_pdf}")
                else: st.error("PDF failed. wkhtmltopdf installed and in PATH?")
    else: st.caption("No data for report. Run a scan first.")

    st.header("Archive (Placeholder)");
    if st.button("View Full Archive", key="app_view_archive_button"):
        st.info("Loading all results from database (up to a limit)...")
        full_archive_df = load_results_from_db(limit=200)
        if not full_archive_df.empty:
            st.session_state.scan_results = full_archive_df; st.session_state.last_report_query = "full_archive"; st.session_state.last_scan_params = {}
            st.success(f"Loaded {len(full_archive_df)} items into results table from archive.")
        else: st.warning("Archive is currently empty.")


def main():
    st.set_page_config(page_title="Social Media Analysis Dashboard", layout="wide")
    init_session_state() # Ensure session state is initialized

    if not IMPORTS_SUCCESSFUL:
        st.error(f"Critical Error: Failed to import core modules: {IMPORT_ERROR_MESSAGE}")
        st.error("The application cannot run. Please check the console logs and project setup. Make sure all dependencies in 'requirements.txt' are installed and scripts are in the correct 'scripts/' directory.")
        return

    # Check if user is authenticated
    if not st.session_state.get('authenticated_user'):
        st.title("Social Media Analysis Dashboard") # Show title on login page too
        display_login_form()
    else:
        # Avoid re-showing title if already shown or if coming from login
        if 'main_app_displayed_once' not in st.session_state:
             st.title("Social Media Analysis Dashboard")
             st.session_state.main_app_displayed_once = True
        main_app_content()

if __name__ == "__main__":
    main()
