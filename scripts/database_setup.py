import psycopg2
from psycopg2 import sql # For dynamic SQL if needed, good practice
import configparser
import os
import sys

# --- Configuration ---
# Determine the path to config.ini relative to this script's location
# This assumes database_setup.py is in the 'scripts' directory.
# For more robustness, you might pass the config path as an argument or use environment variables.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, '..', 'config.ini') # Assumes config.ini is in parent directory

def read_db_config(config_filepath=DEFAULT_CONFIG_PATH):
    """Reads database configuration from the config.ini file."""
    if not os.path.exists(config_filepath):
        print(f"Error: Configuration file '{config_filepath}' not found.")
        print("Please copy 'config.ini.template' to 'config.ini' and fill in your details.")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_filepath)

    db_config = {}
    try:
        db_config['host'] = config.get('DatabasePostgreSQL', 'host')
        db_config['port'] = config.get('DatabasePostgreSQL', 'port')
        db_config['dbname'] = config.get('DatabasePostgreSQL', 'dbname')
        db_config['user'] = config.get('DatabasePostgreSQL', 'user')
        db_config['password'] = config.get('DatabasePostgreSQL', 'password')
        # Optional SSL mode
        if config.has_option('DatabasePostgreSQL', 'sslmode'):
            db_config['sslmode'] = config.get('DatabasePostgreSQL', 'sslmode')
    except configparser.NoSectionError:
        print(f"Error: [DatabasePostgreSQL] section not found in '{config_filepath}'.")
        sys.exit(1)
    except configparser.NoOptionError as e:
        print(f"Error: Missing option in [DatabasePostgreSQL] section: {e}")
        sys.exit(1)

    return db_config

def get_db_connection(db_config):
    """Establishes a connection to the PostgreSQL database."""
    conn = None
    try:
        print(f"Connecting to PostgreSQL database '{db_config['dbname']}' on {db_config['host']}:{db_config['port']}...")
        conn = psycopg2.connect(**db_config)
        print("Connection successful.")
    except psycopg2.OperationalError as e:
        print(f"Error connecting to PostgreSQL: {e}")
        print("Please ensure PostgreSQL server is running and accessible,")
        print(f"and that the database '{db_config['dbname']}' exists and user '{db_config['user']}' has connection permissions.")
        sys.exit(1) # Exit if connection fails as script cannot proceed
    except Exception as e:
        print(f"An unexpected error occurred during connection: {e}")
        sys.exit(1) # Exit for other unexpected connection errors
    return conn

def create_table(conn, create_table_sql, table_name):
    """Creates a table using the provided SQL statement."""
    try:
        with conn.cursor() as cur:
            cur.execute(create_table_sql)
        conn.commit()
        print(f"Table '{table_name}' checked/created successfully.")
    except psycopg2.Error as e:
        print(f"Error creating table '{table_name}': {e}")
        conn.rollback() # Rollback changes if an error occurs during table creation
        # Depending on desired behavior, you might want to re-raise the error or sys.exit
        # For this script, we'll print the error and let initialize_database decide to continue or not.
        raise  # Re-raise the exception to be caught by the caller if needed


def initialize_database():
    """Initializes the database by creating necessary tables if they don't exist."""
    db_params = read_db_config()
    conn = get_db_connection(db_params)

    if conn:
        try:
            # --- Platforms Table ---
            sql_create_platforms_table = """
            CREATE TABLE IF NOT EXISTS platforms (
                id SERIAL PRIMARY KEY,
                name TEXT UNIQUE NOT NULL  -- e.g., 'Facebook', 'Twitter'
            );"""
            create_table(conn, sql_create_platforms_table, "platforms")

            # --- Scrape Targets Table ---
            sql_create_scrape_targets_table = """
            CREATE TABLE IF NOT EXISTS scrape_targets (
                id SERIAL PRIMARY KEY,
                platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
                target_value TEXT NOT NULL,         -- e.g., user ID, page name, keyword, URL
                target_type TEXT,                   -- e.g., 'user_profile', 'page', 'keyword_search'
                is_active BOOLEAN DEFAULT TRUE,
                last_scraped_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (platform_id, target_value, target_type)
            );"""
            create_table(conn, sql_create_scrape_targets_table, "scrape_targets")

            # --- Authors Table ---
            sql_create_authors_table = """
            CREATE TABLE IF NOT EXISTS authors (
                id SERIAL PRIMARY KEY,
                platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
                platform_specific_author_id TEXT NOT NULL, -- e.g., Facebook user ID, Twitter user ID
                username TEXT,                      -- Twitter handle, Facebook vanity URL part
                display_name TEXT,
                bio TEXT,
                profile_url TEXT,
                followers_count INTEGER,
                following_count INTEGER,
                profile_image_url TEXT,
                first_seen_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (platform_id, platform_specific_author_id)
            );"""
            create_table(conn, sql_create_authors_table, "authors")

            # --- Content Items Table ---
            sql_create_content_items_table = """
            CREATE TABLE IF NOT EXISTS content_items (
                id SERIAL PRIMARY KEY,
                platform_id INTEGER NOT NULL REFERENCES platforms(id) ON DELETE CASCADE,
                author_id INTEGER REFERENCES authors(id) ON DELETE SET NULL, -- Link to our authors table
                scrape_target_id INTEGER REFERENCES scrape_targets(id) ON DELETE SET NULL,
                platform_specific_post_id TEXT, -- Tweet ID, Facebook post ID. Should be unique per platform.
                parent_platform_specific_post_id TEXT, -- For replies/comments
                post_url TEXT,
                text_content TEXT, -- Can be NULL if it's e.g. just an image
                published_at TIMESTAMPTZ,        -- Original publication time
                scraped_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                media_urls TEXT[],              -- Array of URLs for images, videos
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,   -- For platforms like Twitter/X
                raw_data JSONB,                 -- Store the full original JSON/object from scraper
                UNIQUE (platform_id, platform_specific_post_id)
            );"""
            create_table(conn, sql_create_content_items_table, "content_items")

            # Index for faster lookup of replies/comments
            with conn.cursor() as cur: # Create index separately, allowing create_table to be more generic
                 cur.execute("CREATE INDEX IF NOT EXISTS idx_content_items_parent_post_id ON content_items (platform_id, parent_platform_specific_post_id);")
            conn.commit()
            print("Index 'idx_content_items_parent_post_id' checked/created.")


            # --- Analysis NLP Table ---
            sql_create_analysis_nlp_table = """
            CREATE TABLE IF NOT EXISTS analysis_nlp (
                id SERIAL PRIMARY KEY,
                content_item_id INTEGER NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
                detected_language TEXT,
                sentiment_label TEXT,
                sentiment_score REAL,
                topic_label TEXT,
                topic_score REAL,
                keywords TEXT[],                -- Array of keywords
                named_entities JSONB,           -- Store as JSON, e.g., [{"text": "...", "label_": "..."}, ...]
                analyzed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                model_version TEXT,             -- Version of the NLP model used
                UNIQUE (content_item_id)        -- Assuming one primary analysis per content item for now
            );"""
            create_table(conn, sql_create_analysis_nlp_table, "analysis_nlp")

            # --- Analyst Users Table ---
            # This schema is compatible with scripts/auth.py
            sql_create_analyst_users_table = """
            CREATE TABLE IF NOT EXISTS analyst_users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                salt TEXT NOT NULL,
                hashed_password TEXT NOT NULL,
                role TEXT DEFAULT 'analyst',    -- e.g., 'analyst', 'admin'
                email TEXT UNIQUE,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMPTZ
            );"""
            create_table(conn, sql_create_analyst_users_table, "analyst_users")

            # --- Audit Logs Table ---
            sql_create_audit_logs_table = """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES analyst_users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,           -- e.g., 'login', 'run_scan', 'export_report'
                details TEXT,                   -- e.g., target of scan, report parameters
                ip_address TEXT,
                timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
            );"""
            create_table(conn, sql_create_audit_logs_table, "audit_logs")

            print("\nDatabase initialization complete. All tables checked/created.")

        except psycopg2.Error as e:
            # This will catch errors from create_table if they were re-raised
            print(f"A database error occurred during initialization: {e}")
            print("Initialization may be incomplete.")
            # Depending on policy, might want to sys.exit(1) here too
        finally:
            if conn:
                conn.close()
                print("Database connection closed.")

if __name__ == '__main__':
    print("Initializing PostgreSQL database schema...")
    print("IMPORTANT: This script creates tables in an EXISTING PostgreSQL database.")
    print("Ensure the database specified in 'config.ini' exists and the user has permissions.")
    initialize_database()
