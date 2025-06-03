import psycopg2
from psycopg2 import sql
import configparser
import os
import sys
from langdetect import detect, lang_detect_exception # Import langdetect
import spacy # Added for NER
import json # Ensure json is imported for storing entities

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, '..', 'config.ini') # config.ini in project root

# --- spaCy Model Loading ---
NLP_SPACY_EN = None
SPACY_MODEL_NAME = "en_core_web_sm"
try:
    NLP_SPACY_EN = spacy.load(SPACY_MODEL_NAME)
    print(f"spaCy model '{SPACY_MODEL_NAME}' loaded successfully.")
except OSError:
    print(f"spaCy model '{SPACY_MODEL_NAME}' not found. Please download it by running:")
    print(f"python -m spacy download {SPACY_MODEL_NAME}")
    print("NER functionality will be disabled for this run.")
except Exception as e_spacy_load:
    print(f"An unexpected error occurred loading spaCy model '{SPACY_MODEL_NAME}': {e_spacy_load}")
    print("NER functionality will be disabled for this run.")


def read_db_config(config_filepath=DEFAULT_CONFIG_PATH):
    """Reads database configuration from the config.ini file."""
    if not os.path.exists(config_filepath):
        print(f"Error: NLP Processing - Configuration file '{config_filepath}' not found.")
        return None

    config = configparser.ConfigParser()
    config.read(config_filepath)

    db_config = {}
    try:
        db_config['host'] = config.get('DatabasePostgreSQL', 'host')
        db_config['port'] = config.get('DatabasePostgreSQL', 'port')
        db_config['dbname'] = config.get('DatabasePostgreSQL', 'dbname')
        db_config['user'] = config.get('DatabasePostgreSQL', 'user')
        db_config['password'] = config.get('DatabasePostgreSQL', 'password')
        if config.has_option('DatabasePostgreSQL', 'sslmode'):
            db_config['sslmode'] = config.get('DatabasePostgreSQL', 'sslmode')
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        print(f"Error: NLP Processing - DB config error in '{config_filepath}': {e}")
        return None
    return db_config

def get_db_connection(db_config_dict):
    """Establishes a connection to the PostgreSQL database."""
    if not db_config_dict:
        print("Error: NLP Processing - Database configuration is empty.")
        return None
    try:
        conn = psycopg2.connect(**db_config_dict)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: NLP Processing - connecting to PostgreSQL: {e}")
        return None
    except Exception as e:
        print(f"Error: NLP Processing - Unexpected error during DB connection: {e}")
        return None

def detect_language_text(text_content):
    """Detects language of a given text. Returns language code (e.g., 'en', 'es')."""
    if not text_content or not isinstance(text_content, str) or len(text_content.strip()) < 10:
        return "und"
    try:
        lang = detect(text_content)
        return lang
    except lang_detect_exception.LangDetectException:
        return "err_ambiguous"
    except Exception as e:
        print(f"Unexpected error in language detection for text '{text_content[:50]}...': {e}")
        return "err_unknown"

# --- Named Entity Recognition (NER) ---
def extract_entities_spacy(text_content, nlp_model=NLP_SPACY_EN):
    """Extracts named entities from text using spaCy. Returns list of dicts."""
    if not text_content or not isinstance(text_content, str) or nlp_model is None:
        return []
    doc = nlp_model(text_content)
    entities = [{'text': ent.text, 'label': ent.label_} for ent in doc.ents]
    return entities

def process_content_for_language_detection(db_conn, limit=100):
    """
    Fetches content items that haven't had language detected yet,
    detects language, and updates the analysis_nlp table.
    """
    if not db_conn:
        print("Error: NLP Processing - No database connection.")
        return 0

    processed_count = 0
    try:
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT ci.id, ci.text_content
                FROM content_items ci
                LEFT JOIN analysis_nlp an ON ci.id = an.content_item_id
                WHERE ci.text_content IS NOT NULL AND TRIM(ci.text_content) != ''
                  AND (an.id IS NULL OR an.detected_language IS NULL)
                ORDER BY ci.scraped_at DESC
                LIMIT %s;
            """, (limit,))
            content_to_process = cur.fetchall()

            if not content_to_process:
                print("NLP Language Detection: No new content items found needing language analysis.")
                return 0
            print(f"NLP Language Detection: Found {len(content_to_process)} items for language analysis.")

            for item_id, text_content in content_to_process:
                detected_lang = detect_language_text(text_content)
                cur.execute("SELECT id FROM analysis_nlp WHERE content_item_id = %s;", (item_id,))
                analysis_row = cur.fetchone()
                if analysis_row:
                    cur.execute("""
                        UPDATE analysis_nlp SET detected_language = %s, analyzed_at = CURRENT_TIMESTAMP
                        WHERE content_item_id = %s;
                    """, (detected_lang, item_id))
                else:
                    cur.execute("""
                        INSERT INTO analysis_nlp (content_item_id, detected_language, analyzed_at)
                        VALUES (%s, %s, CURRENT_TIMESTAMP);
                    """, (item_id, detected_lang))
                processed_count += 1
            db_conn.commit()
            print(f"NLP Language Detection: Successfully processed and updated {processed_count} items.")
    except psycopg2.Error as e:
        print(f"Error during NLP language processing (database operation): {e}")
        if db_conn: db_conn.rollback()
        return -1
    except Exception as e:
        print(f"An unexpected error occurred during language processing: {e}")
        if db_conn: db_conn.rollback()
        return -1
    return processed_count

def process_content_for_ner(db_conn, limit=50, language_filter='en'):
    """
    Fetches content items (optionally filtered by language) that haven't had NER
    applied yet, extracts entities, and updates analysis_nlp table.
    """
    if not db_conn:
        print("Error: NER Processing - No database connection.")
        return 0
    if NLP_SPACY_EN is None:
        print("Error: NER Processing - spaCy English model not loaded. Skipping NER.")
        return 0

    processed_count_ner = 0
    try:
        with db_conn.cursor() as cur:
            sql_select_ner = """
                SELECT ci.id, ci.text_content
                FROM content_items ci
                JOIN analysis_nlp an ON ci.id = an.content_item_id
                WHERE an.detected_language = %s AND an.named_entities IS NULL
                  AND ci.text_content IS NOT NULL AND TRIM(ci.text_content) != ''
                ORDER BY ci.scraped_at DESC
                LIMIT %s;
            """
            cur.execute(sql_select_ner, (language_filter, limit))
            content_to_process_ner = cur.fetchall()

            if not content_to_process_ner:
                print(f"NER Processing: No new content items found (lang={language_filter}) needing NER analysis.")
                return 0
            print(f"NER Processing: Found {len(content_to_process_ner)} items (lang={language_filter}) for NER analysis.")

            for item_id, text_content in content_to_process_ner:
                if not text_content: continue
                entities = extract_entities_spacy(text_content, NLP_SPACY_EN)
                entities_json = json.dumps(entities) if entities else None

                cur.execute("""
                    UPDATE analysis_nlp
                    SET named_entities = %s, analyzed_at = CURRENT_TIMESTAMP
                    WHERE content_item_id = %s;
                """, (entities_json, item_id))
                processed_count_ner += 1
            db_conn.commit()
            print(f"NER Processing: Successfully processed and updated {processed_count_ner} items for NER.")
    except psycopg2.Error as e:
        print(f"Error during NER processing (database operation): {e}")
        if db_conn: db_conn.rollback()
        return -1
    except Exception as e_ner_main:
        print(f"An unexpected error occurred during NER processing: {e_ner_main}")
        if db_conn: db_conn.rollback()
        return -1
    return processed_count_ner

if __name__ == '__main__':
    print("Starting NLP Processing (manual run)...")
    db_cfg = read_db_config()
    if not db_cfg:
        print("Exiting due to configuration loading failure."); sys.exit(1)
    connection = get_db_connection(db_cfg)
    if not connection:
        print("Exiting due to database connection failure."); sys.exit(1)

    try:
        print("\n--- Testing Language Detection ---")
        num_lang_processed = process_content_for_language_detection(connection, limit=10)
        if num_lang_processed > 0: print(f"Language detection run complete. {num_lang_processed} items processed.")
        elif num_lang_processed == 0: print("Language detection: No new items or none found.")
        else: print("Language detection run encountered an error.")

        # --- Test NER Processing ---
        if NLP_SPACY_EN:
            print("\n--- Testing NER Processing ---")
            num_ner_processed = process_content_for_ner(connection, limit=5, language_filter='en')
            if num_ner_processed > 0: print(f"NER processing run complete. {num_ner_processed} items processed.")
            elif num_ner_processed == 0: print("NER processing: No new 'en' items or none found.")
            else: print("NER processing run encountered an error.")
        else:
            print("\nSkipping NER Processing test as spaCy model was not loaded.")

    finally:
        if connection:
            connection.close()
            print("\nDatabase connection closed.")
