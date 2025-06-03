import configparser
import psycopg2
from psycopg2 import sql
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import os
import random
import re # For extracting usernames from URLs or text

# --- Configuration ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(SCRIPT_DIR, '..', '..', 'config.ini') # config.ini in project root

def load_config(config_filepath=DEFAULT_CONFIG_PATH):
    """Loads configuration from the config.ini file."""
    if not os.path.exists(config_filepath):
        print(f"Error: Configuration file '{config_filepath}' not found.")
        print("Please copy 'config.ini.template' to 'config.ini' and fill it out.")
        return None
    config = configparser.ConfigParser()
    config.read(config_filepath)
    return config

# --- Database Interaction (Stubs/Basic Implementation - can be refactored later) ---
def get_db_connection(db_config_dict):
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**db_config_dict)
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def get_platform_id(conn, platform_name="Twitter"): # Changed default
    """Gets the ID of the platform from the 'platforms' table."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM platforms WHERE name = %s;", (platform_name,))
        result = cur.fetchone()
        if result:
            return result[0]
        else:
            cur.execute("INSERT INTO platforms (name) VALUES (%s) RETURNING id;", (platform_name,))
            platform_id = cur.fetchone()[0]
            conn.commit()
            print(f"Inserted platform '{platform_name}' with ID {platform_id}.")
            return platform_id

def get_or_create_author_db(conn, platform_id, platform_specific_author_id, username=None, display_name=None, profile_url=None, bio=None):
    """Gets an existing author's ID or creates a new author record for Twitter/X."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM authors WHERE platform_id = %s AND platform_specific_author_id = %s;", (platform_id, platform_specific_author_id))
        result = cur.fetchone()
        if result:
            return result[0]
        else:
            # Ensure username is extracted if only display_name is available initially
            if not username and display_name: # Basic assumption
                 username = display_name.replace(" ", "").lower()
            if not username: # If still no username, use part of the author_id
                 username = platform_specific_author_id.replace("user_","")[:15]


            cur.execute("""
                INSERT INTO authors (platform_id, platform_specific_author_id, username, display_name, profile_url, bio)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
            """, (platform_id, platform_specific_author_id, username, display_name, profile_url, bio))
            author_id = cur.fetchone()[0]
            conn.commit()
            return author_id

def save_content_item_db(conn, platform_id, author_id, platform_specific_post_id, text_content, post_url=None, published_at=None, raw_data=None, like_count=0, comment_count=0, share_count=0, view_count=0):
    """Saves a tweet/content item to the database."""
    with conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO content_items (platform_id, author_id, platform_specific_post_id, text_content, post_url, published_at, raw_data, like_count, comment_count, share_count, view_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (platform_id, platform_specific_post_id) DO NOTHING;
            """, (platform_id, author_id, platform_specific_post_id, text_content, post_url, published_at, json.dumps(raw_data) if raw_data else None, like_count, comment_count, share_count, view_count))
            conn.commit()
            return True
        except psycopg2.Error as e:
            print(f"DB Error saving content item {platform_specific_post_id}: {e}")
            conn.rollback()
            return False

# --- Selenium WebDriver Setup ---
def setup_driver(scraper_config): # Renamed for clarity
    """Sets up the Chrome WebDriver with a specific user profile for Twitter/X."""
    profile_path = scraper_config.get('chrome_profile_path_twitter') # Changed key

    if not profile_path or profile_path == 'PATH_TO_YOUR_TWITTER_CHROME_PROFILE': # Changed placeholder
        print("WARNING: Twitter Chrome profile path not set in config.ini. Live scraping may fail or use default profile.")

    options = ChromeOptions()
    if profile_path and profile_path != 'PATH_TO_YOUR_TWITTER_CHROME_PROFILE':
        parts = os.path.split(profile_path)
        user_data_dir = parts[0]
        profile_directory = parts[1]
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_directory}")
        print(f"Attempting to use Chrome profile for Twitter/X: {profile_path}")

    options.add_argument("--disable-gpu"); options.add_argument("--no-sandbox"); options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36") # Updated UA
    options.add_experimental_option("excludeSwitches", ["enable-automation"]); options.add_experimental_option('useAutomationExtension', False)

    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver for Twitter/X: {e}"); return None

# --- Core Scraping Logic ---
def scrape_twitter_keyword_search(driver, keyword, db_conn, platform_id, max_tweets=10):
    """
    Scrapes tweets from a Twitter/X keyword search.
    This is a VERY basic stub and will need significant refinement.
    Selectors are based on common 'data-testid' attributes but can change.
    """
    search_url = f"https://twitter.com/search?q={keyword.replace(' ', '%20')}&src=typed_query"
    print(f"Navigating to Twitter/X search: {search_url}")
    driver.get(search_url)
    time.sleep(random.uniform(5, 10)) # Wait for page and initial results

    # Scroll down to load more tweets
    print("Scrolling to load tweets...")
    for _ in range(3): # Scroll a few times
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(4, 8))

    print("Attempting to extract tweet data...")
    # Twitter/X uses 'data-testid' attributes which are generally more stable.
    # Common structure: article data-testid="tweet" -> div data-testid="tweetText"
    tweet_articles = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']")
    print(f"Found {len(tweet_articles)} potential 'tweet' articles.")

    tweets_scraped_count = 0
    for i, article_el in enumerate(tweet_articles):
        if tweets_scraped_count >= max_tweets: break

        tweet_text = "N/A"; author_username = "N/A"; author_display_name = "N/A"; tweet_id = None; post_url = None

        try:
            # Extract tweet text
            text_el = article_el.find_element(By.XPATH, ".//div[@data-testid='tweetText']")
            tweet_text = text_el.text.strip()

            # Extract author info (often within a structure leading to user profile link)
            # Example: find 'a' tags with href like '/username' that also contain time element
            # This is complex due to varying structures for usernames and display names.
            # A common pattern for user info: div data-testid="User-Name"
            user_name_container = article_el.find_element(By.XPATH, ".//div[@data-testid='User-Name']")
            links_in_user_container = user_name_container.find_elements(By.XPATH, ".//a[@role='link']")

            author_profile_url_part = None
            for link_el in links_in_user_container:
                href = link_el.get_attribute('href')
                if href and ("/" in href and not "status" in href and not "search" in href and not "photo" in href): # Basic filter for profile links
                    author_profile_url_part = href.split('/')[-1] # Get username from URL
                    # post_url = href # This is user profile URL, not tweet URL yet.
                    # Try to get display name from text within this link structure
                    spans_in_link = link_el.find_elements(By.XPATH, ".//span")
                    if spans_in_link: # Often multiple spans, one is display name, one might be @handle
                        author_display_name = spans_in_link[0].text.strip() # Guessing first span
                        if len(spans_in_link) > 1 and spans_in_link[1].text.startswith("@"):
                             author_username = spans_in_link[1].text.strip()[1:] # Remove @
                    if not author_username and author_profile_url_part: # if @handle not found, use the URL part
                        author_username = author_profile_url_part
                    break # Found a likely user link

            if not author_username or author_username == "N/A": # Fallback if parsing failed
                author_username = f"unknown_user_{i}"
                author_display_name = "Unknown User"


            # Extract Tweet ID (often part of the permalink for the tweet)
            # Permalink is typically an 'a' tag with href containing '/status/'
            time_el = article_el.find_element(By.XPATH, ".//time/parent::a")
            tweet_permalink = time_el.get_attribute('href')
            if tweet_permalink and "/status/" in tweet_permalink:
                tweet_id = tweet_permalink.split("/status/")[-1].split('?')[0]
                post_url = tweet_permalink # This is the actual tweet URL
            else: # Fallback ID if permalink structure is not as expected
                 tweet_id = f"twitter_tweet_{keyword.replace(' ','_')}_{i}_{int(time.time())}"


            print(f"--- Tweet {i+1} (ID: {tweet_id}) ---")
            print(f"Author: {author_display_name} (@{author_username})")
            print(f"Text: {tweet_text[:100]}...")
            print(f"URL: {post_url}")

            # --- Save to DB ---
            if db_conn:
                # platform_specific_author_id can be the username for Twitter if numeric ID not easily available
                author_id_db = get_or_create_author_db(db_conn, platform_id, platform_specific_author_id=author_username, username=author_username, display_name=author_display_name, profile_url=f"https://twitter.com/{author_username}")
                save_content_item_db(db_conn, platform_id, author_id_db, tweet_id, tweet_text, post_url=post_url, raw_data={"text": tweet_text, "author": author_username, "source_keyword": keyword})
                tweets_scraped_count += 1

        except Exception as e:
            print(f"Error processing tweet article {i}: {e}")
            # import traceback; traceback.print_exc() # For debugging
            continue # Skip this tweet if there's an error

        time.sleep(random.uniform(1, 2))

    print(f"Finished Twitter/X search scraping for '{keyword}'. Scraped {tweets_scraped_count} tweets.")


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Twitter/X Live Scraper...")
    config = load_config()

    if not config: print("Exiting: config error."); exit()

    db_settings = dict(config['DatabasePostgreSQL'])
    twitter_settings = config['TwitterScraper']

    targets = twitter_settings.get('default_scrape_targets', '').split(',')
    if not targets or not targets[0].strip(): print("No default_scrape_targets for Twitter in config.ini."); exit()

    target_keyword = targets[0].strip() # Assuming first target is a keyword for this example
    print(f"Target keyword for scraping: {target_keyword}")

    driver = None; db_connection = None
    try:
        db_connection = get_db_connection(db_settings)
        if not db_connection: print("Exiting: DB connection error."); exit()

        platform_main_id = get_platform_id(db_connection, platform_name="Twitter")

        driver = setup_driver(twitter_settings)
        if driver:
            print("WebDriver setup successful for Twitter/X.")
            scrape_twitter_keyword_search(driver, target_keyword, db_connection, platform_main_id, max_tweets=5)
        else:
            print("WebDriver setup failed for Twitter/X. Cannot scrape.")

    except Exception as e:
        print(f"An error occurred in the main execution (Twitter/X): {e}")
        # import traceback; traceback.print_exc() # For debugging
    finally:
        if driver: print("Closing WebDriver..."); driver.quit()
        if db_connection: db_connection.close()
    print("Twitter/X Live Scraper finished.")

EOF

echo "scripts/scrapers/twitter_live_scraper.py created."
echo "This is a foundational stub. Selectors for tweets, authors, etc., are basic and WILL REQUIRE REFINEMENT."
echo "Ensure 'config.ini' is populated with your Chrome profile path for Twitter/X and PostgreSQL details."
echo "Run 'python scripts/database_setup.py' first for PostgreSQL tables."
echo "Test with: python scripts/scrapers/twitter_live_scraper.py"
