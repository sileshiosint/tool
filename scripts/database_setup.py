import sqlite3
import json # For storing raw data if needed

DATABASE_NAME = "data/social_media_analysis.db"

def create_connection(db_file):
    """ Create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print(f"Connected to SQLite database: {db_file} (SQLite version: {sqlite3.sqlite_version})")
    except sqlite3.Error as e:
        print(e)
    return conn

def create_table(conn, create_table_sql):
    """ Create a table from the create_table_sql statement """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        print(f"Table created successfully: {create_table_sql.split('(')[0].split('EXISTS')[-1].strip()}")
    except sqlite3.Error as e:
        print(f"Error creating table: {e}")

def initialize_database():
    """ Initialize the database by creating necessary tables if they don't exist. """
    conn = create_connection(DATABASE_NAME)

    if conn is not None:
        # --- Scraped Content Table ---
        # Stores the core information directly scraped from platforms.
        # source_identifier: User ID, page ID, hashtag, keyword, etc.
        # user_id_on_platform: Unique ID of the user who made the post (if available)
        # user_name_on_platform: Display name of the user (if available)
        # raw_data_json: To store the full, unprocessed JSON/dict from the scraper for future use or debugging
        sql_create_scraped_content_table = """
        CREATE TABLE IF NOT EXISTS scraped_content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,                         -- e.g., 'Facebook', 'Twitter'
            source_query TEXT,                            -- The keyword, URL, or user ID used for the search
            user_id_on_platform TEXT,                   -- Platform-specific user ID of the post author
            user_name_on_platform TEXT,                 -- Display name of the post author
            post_id_on_platform TEXT UNIQUE,            -- Platform-specific ID of the post/tweet itself (if available and unique)
            post_url TEXT,                              -- Direct URL to the post/tweet (if available)
            post_text TEXT NOT NULL,                    -- The main text content of the post/tweet
            published_timestamp TEXT,                   -- When the post was originally published (if available)
            scraped_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, -- When we scraped it
            raw_data_json TEXT                          -- Store the original scraped item as JSON
        );
        """
        create_table(conn, sql_create_scraped_content_table)

        # --- Analysis Results Table ---
        # Stores results from NLP and other analyses, linked to scraped_content.
        sql_create_analysis_results_table = """
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id INTEGER NOT NULL,                -- Foreign Key to scraped_content.id
            sentiment_label TEXT,
            sentiment_score REAL,
            topic_label TEXT,
            topic_score REAL,
            language_detected TEXT,
            keywords_extracted TEXT,                    -- Could be JSON list
            named_entities_extracted TEXT,              -- Could be JSON list of dicts
            analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (content_id) REFERENCES scraped_content (id) ON DELETE CASCADE
        );
        """
        create_table(conn, sql_create_analysis_results_table)

        # --- Analyst Accounts Table (Basic for now) ---
        # For secure analyst access later
        sql_create_analyst_accounts_table = """
        CREATE TABLE IF NOT EXISTS analyst_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role TEXT DEFAULT 'analyst', -- e.g., 'analyst', 'admin'
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        create_table(conn, sql_create_analyst_accounts_table)

        # --- Search Archive Table ---
        # To log searches made by analysts
        sql_create_search_archive_table = """
        CREATE TABLE IF NOT EXISTS search_archive (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analyst_id INTEGER,                         -- Optional: Link to analyst_accounts
            platform TEXT,
            query TEXT,
            search_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            num_results INTEGER DEFAULT 0,
            FOREIGN KEY (analyst_id) REFERENCES analyst_accounts (id) ON DELETE SET NULL
        );
        """
        create_table(conn, sql_create_search_archive_table)

        conn.close()
        print("Database initialization complete. Tables checked/created.")
    else:
        print("Error! Cannot create the database connection.")

if __name__ == '__main__':
    print("Initializing database schema...")
    initialize_database()
