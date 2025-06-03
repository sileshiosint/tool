import streamlit as st
import pandas as pd
import configparser
import psycopg2
import os
import time

# --- Configuration & Imports ---
NLP_PROCESSING_AVAILABLE = False
NLP_NER_AVAILABLE = False # Flag for NER specific function
NLP_IMPORT_ERROR_MESSAGE = ""
SPACY_MODEL_LOADED_SUCCESSFULLY = False # Flag for spaCy model status

try:
    from scripts.scrapers.facebook_live_scraper import (
        load_config as fb_load_config,
        setup_driver as fb_setup_driver,
        scrape_facebook_page,
        get_platform_id as fb_get_platform_id
    )
    from scripts.scrapers.twitter_live_scraper import (
        load_config as tw_load_config,
        setup_driver as tw_setup_driver,
        scrape_twitter_keyword_search,
        get_platform_id as tw_get_platform_id
    )
    IMPORTS_SUCCESSFUL = True # Scraper imports assumed successful if this point is reached

    try:
        from scripts.nlp_processing import process_content_for_language_detection, process_content_for_ner, NLP_SPACY_EN
        NLP_PROCESSING_AVAILABLE = True # For language detection
        NLP_NER_AVAILABLE = True      # For NER
        if NLP_SPACY_EN is not None:  # Check if the spaCy model itself loaded in nlp_processing
            SPACY_MODEL_LOADED_SUCCESSFULLY = True
        else:
            NLP_IMPORT_ERROR_MESSAGE = "spaCy model (en_core_web_sm) not loaded. NER will be disabled. Run 'python -m spacy download en_core_web_sm'."
            # NER_AVAILABLE will remain False if NLP_SPACY_EN is None
            NLP_NER_AVAILABLE = False


    except ImportError as e_nlp:
        NLP_PROCESSING_AVAILABLE = False
        NLP_NER_AVAILABLE = False
        NLP_IMPORT_ERROR_MESSAGE = f"NLP script import error: {str(e_nlp)}"

except ImportError as e_scraper:
    IMPORTS_SUCCESSFUL = False
    IMPORT_ERROR_MESSAGE = f"Scraper script import error: {str(e_scraper)}"
    NLP_PROCESSING_AVAILABLE = False
    NLP_NER_AVAILABLE = False
    if not NLP_IMPORT_ERROR_MESSAGE:
        NLP_IMPORT_ERROR_MESSAGE = "NLP processing unavailable due to core import failures."


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, '..', 'config.ini')

@st.cache_resource
def load_app_config(config_filepath=DEFAULT_CONFIG_PATH):
    if not os.path.exists(config_filepath):
        st.error(f"FATAL: Configuration file '{config_filepath}' not found. Please create it from config.ini.template.")
        return None
    config = configparser.ConfigParser()
    config.read(config_filepath)
    return config

@st.cache_resource
def get_db_connection(_db_config_dict):
    try:
        conn = psycopg2.connect(**_db_config_dict)
        return conn
    except psycopg2.OperationalError as e:
        st.error(f"DB Connection Error: {e}. Check config.ini and PostgreSQL server.")
        return None
    except Exception as e:
        st.error(f"DB Connection Setup Error: {e}. Ensure db_settings are loaded.")
        return None

def load_data_from_postgres(conn, platform_filter=None, target_filter=None, limit=100):
    if conn is None: return pd.DataFrame()
    query = """
    SELECT
        ci.id, p.name as platform, a.display_name as author_display_name, a.username as author_username,
        ci.text_content, ci.post_url, ci.published_at, ci.scraped_at,
        ci.like_count, ci.comment_count, ci.share_count, ci.view_count,
        an.detected_language, an.sentiment_label, an.sentiment_score, an.topic_label, an.topic_score,
        an.named_entities -- Added for NER results
    FROM content_items ci
    JOIN platforms p ON ci.platform_id = p.id
    LEFT JOIN authors a ON ci.author_id = a.id
    LEFT JOIN (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY content_item_id ORDER BY analyzed_at DESC) as rn
        FROM analysis_nlp
    ) an ON ci.id = an.content_item_id AND an.rn = 1
    WHERE 1=1
    """
    params = []
    if platform_filter: query += " AND p.name = %s"; params.append(platform_filter)
    query += " ORDER BY ci.scraped_at DESC LIMIT %s;"; params.append(limit)
    try:
        df = pd.read_sql_query(query, conn, params=tuple(params))
        if 'named_entities' in df.columns: # Convert JSON string back to list/dict for display if needed
            df['named_entities'] = df['named_entities'].apply(lambda x: json.loads(x) if isinstance(x, str) else x)
        return df
    except Exception as e: st.error(f"Error loading data from DB: {e}"); return pd.DataFrame()

# --- Main App UI ---
st.set_page_config(page_title="Live Scraper Dashboard", layout="wide")
st.title("Live Social Media Scraper Dashboard")

if not IMPORTS_SUCCESSFUL:
    st.error(f"Failed to import scraper modules: {IMPORT_ERROR_MESSAGE}")
    st.caption("Ensure project root is in PYTHONPATH or run Streamlit from there.")
    if not NLP_PROCESSING_AVAILABLE: st.error(f"NLP Language Detection module failed: {NLP_IMPORT_ERROR_MESSAGE}")
    if not NLP_NER_AVAILABLE: st.error(f"NLP NER module or spaCy model failed: {NLP_IMPORT_ERROR_MESSAGE}")
    st.stop()

app_config = load_app_config()
if not app_config: st.warning("`config.ini` not found or empty."); st.stop()

try: db_settings = dict(app_config['DatabasePostgreSQL'])
except KeyError: st.error("DatabasePostgreSQL section missing/incomplete in config.ini."); st.stop()

db_conn_test = get_db_connection(db_settings)
if db_conn_test: st.sidebar.success(f"Connected to DB: {db_settings.get('dbname')}"); db_conn_test.close()
else: st.sidebar.error("DB connection failed. Check config/server.")

# --- Sidebar for Controls ---
st.sidebar.header("Scraping Controls")
platform_to_scrape = st.sidebar.selectbox("Platform", ["Facebook", "Twitter/X"], key="platform_select")
target_input = st.sidebar.text_input("Target (URL/Keyword)", key="target_input")
num_items_to_scrape = st.sidebar.slider("Max items", 5, 30, 5, key="num_items_slider")

if 'scraping_in_progress' not in st.session_state: st.session_state.scraping_in_progress = False

if st.sidebar.button("Start Live Scan", key="start_scan_button", disabled=st.session_state.scraping_in_progress):
    if not target_input: st.sidebar.warning("Enter target.")
    else:
        st.session_state.scraping_in_progress = True
        st.sidebar.info(f"Scraping '{target_input}' from {platform_to_scrape}...")
        # (Scraping logic - condensed for brevity, assumed to be the same as previous correct version)
        scraper_config_section=None; scraper_module_setup_driver=None; scraper_module_scrape_function=None; scraper_module_get_platform_id=None
        platform_name_for_db = platform_to_scrape.split('/')[0]
        if platform_to_scrape == "Facebook":
            scraper_config_section = app_config['FacebookScraper']; scraper_module_setup_driver = fb_setup_driver
            scraper_module_scrape_function = scrape_facebook_page; scraper_module_get_platform_id = fb_get_platform_id
        elif platform_to_scrape == "Twitter/X":
            scraper_config_section = app_config['TwitterScraper']; scraper_module_setup_driver = tw_setup_driver
            scraper_module_scrape_function = scrape_twitter_keyword_search; scraper_module_get_platform_id = tw_get_platform_id

        driver = None; db_conn_scrape = None
        try:
            with st.spinner(f"Initializing {platform_to_scrape} scraper..."):
                db_conn_scrape = get_db_connection(db_settings)
                if not db_conn_scrape: st.error("DB connection failed."); st.session_state.scraping_in_progress = False; st.experimental_rerun()
                platform_id_db = scraper_module_get_platform_id(db_conn_scrape, platform_name=platform_name_for_db)
                driver = scraper_module_setup_driver(scraper_config_section)
            if driver and db_conn_scrape:
                st.success(f"WebDriver initialized. Starting scrape...");
                if platform_to_scrape == "Facebook": scraper_module_scrape_function(driver, target_input, db_conn_scrape, platform_id_db, max_posts=num_items_to_scrape)
                elif platform_to_scrape == "Twitter/X": scraper_module_scrape_function(driver, target_input, db_conn_scrape, platform_id_db, max_tweets=num_items_to_scrape)
                st.success(f"Finished scraping.")
            else: st.error(f"WebDriver init failed.")
        except Exception as e: st.error(f"Scraping error: {e}")
        finally:
            if driver: driver.quit(); st.info("WebDriver closed.")
            if db_conn_scrape: db_conn_scrape.close()
            st.session_state.scraping_in_progress = False; st.experimental_rerun()

# --- NLP Processing Section in Sidebar ---
st.sidebar.header("NLP Processing")
if NLP_PROCESSING_AVAILABLE:
    if st.sidebar.button("Detect Language", key="detect_lang_button"):
        with st.spinner("Running language detection..."):
            nlp_db_conn = get_db_connection(db_settings)
            if nlp_db_conn:
                try:
                    num_lang_processed = process_content_for_language_detection(nlp_db_conn, limit=50)
                    if num_lang_processed > 0: st.sidebar.success(f"Language: {num_lang_processed} items processed."); st.experimental_rerun()
                    elif num_lang_processed == 0: st.sidebar.info("Language: No new items.")
                    else: st.sidebar.error("Language: Error during processing.")
                except Exception as e_nlp_run: st.sidebar.error(f"NLP run error: {e_nlp_run}")
                finally: nlp_db_conn.close()
            else: st.sidebar.error("DB connection failed for NLP.")

    if NLP_NER_AVAILABLE and SPACY_MODEL_LOADED_SUCCESSFULLY: # Check if spaCy model loaded
        if st.sidebar.button("Run NER (English Content)", key="run_ner_button"):
            with st.spinner("Running NER on English content..."):
                ner_db_conn = get_db_connection(db_settings)
                if ner_db_conn:
                    try:
                        num_ner_processed = process_content_for_ner(ner_db_conn, limit=25, language_filter='en')
                        if num_ner_processed > 0: st.sidebar.success(f"NER: {num_ner_processed} items processed."); st.experimental_rerun()
                        elif num_ner_processed == 0: st.sidebar.info("NER: No new 'en' items.")
                        else: st.sidebar.error("NER: Error during processing.")
                    except Exception as e_ner_run: st.sidebar.error(f"NER run error: {e_ner_run}")
                    finally: ner_db_conn.close()
                else: st.sidebar.error("DB connection failed for NER.")
    elif not SPACY_MODEL_LOADED_SUCCESSFULLY and NLP_NER_AVAILABLE : # If script is there but model failed
         st.sidebar.warning(f"NER disabled: spaCy model ({SPACY_MODEL_NAME}) not loaded. Check logs or download it.")
    elif not NLP_NER_AVAILABLE : # If script import failed
         st.sidebar.warning(f"NER Processing function not available: {NLP_IMPORT_ERROR_MESSAGE}")

else: st.sidebar.warning(f"NLP Processing script not available: {NLP_IMPORT_ERROR_MESSAGE}")

# --- Data Display Area ---
st.header("Scraped Data from PostgreSQL")
if st.button("Refresh Data", key="refresh_data"): st.experimental_rerun()

display_db_conn = get_db_connection(db_settings)
if display_db_conn:
    platform_filter = st.selectbox("Filter by Platform", ["All", "Facebook", "Twitter"], key="platform_display_filter")
    df_results = load_data_from_postgres(display_db_conn, platform_filter=None if platform_filter == "All" else platform_filter, limit=200)
    if not df_results.empty: st.dataframe(df_results); st.caption(f"Displaying {len(df_results)} items.")
    else: st.caption("No data for current filters.")
    display_db_conn.close()
else: st.warning("DB connection failed for display.")

st.caption("Note: Live scraping runs in foreground. Ensure `config.ini` is correct.")

if __name__ == '__main__': pass
