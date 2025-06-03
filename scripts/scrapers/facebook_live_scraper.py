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

# --- Database Interaction (Stubs/Basic Implementation) ---
def get_db_connection(db_config_dict):
    """Establishes a connection to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(**db_config_dict)
        # print("Database connection successful.")
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def get_platform_id(conn, platform_name="Facebook"):
    """Gets the ID of the platform from the 'platforms' table."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM platforms WHERE name = %s;", (platform_name,))
        result = cur.fetchone()
        if result:
            return result[0]
        else: # Insert if not exists
            cur.execute("INSERT INTO platforms (name) VALUES (%s) RETURNING id;", (platform_name,))
            platform_id = cur.fetchone()[0]
            conn.commit()
            print(f"Inserted platform '{platform_name}' with ID {platform_id}.")
            return platform_id

def get_or_create_author_db(conn, platform_id, platform_specific_author_id, username=None, display_name=None, profile_url=None, bio=None):
    """Gets an existing author's ID or creates a new author record."""
    # This is a simplified version. A real version would handle updates to existing authors.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id FROM authors
            WHERE platform_id = %s AND platform_specific_author_id = %s;
        """, (platform_id, platform_specific_author_id))
        result = cur.fetchone()
        if result:
            return result[0]
        else:
            cur.execute("""
                INSERT INTO authors (platform_id, platform_specific_author_id, username, display_name, profile_url, bio)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
            """, (platform_id, platform_specific_author_id, username, display_name, profile_url, bio))
            author_id = cur.fetchone()[0]
            conn.commit()
            # print(f"Inserted author '{display_name or username}' with ID {author_id}.")
            return author_id

def save_content_item_db(conn, platform_id, author_id, platform_specific_post_id, text_content, post_url=None, published_at=None, raw_data=None):
    """Saves a content item to the database."""
    # Simplified, real version would handle more fields and updates.
    with conn.cursor() as cur:
        try:
            cur.execute("""
                INSERT INTO content_items (platform_id, author_id, platform_specific_post_id, text_content, post_url, published_at, raw_data)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (platform_id, platform_specific_post_id) DO NOTHING;
                -- Or DO UPDATE SET ... if you want to update existing posts
            """, (platform_id, author_id, platform_specific_post_id, text_content, post_url, published_at, json.dumps(raw_data) if raw_data else None))
            conn.commit()
            # print(f"Saved/updated content item: {platform_specific_post_id}")
            return True
        except psycopg2.Error as e:
            print(f"DB Error saving content item {platform_specific_post_id}: {e}")
            conn.rollback()
            return False

# --- Selenium WebDriver Setup ---
def setup_driver(fb_scraper_config):
    """Sets up the Chrome WebDriver with a specific user profile."""
    profile_path = fb_scraper_config.get('chrome_profile_path_facebook')

    if not profile_path or profile_path == 'PATH_TO_YOUR_FACEBOOK_CHROME_PROFILE':
        print("WARNING: Facebook Chrome profile path not set in config.ini. Selenium will use a default or new profile.")
        print("Live scraping with your logged-in session will likely not work as intended.")
        # return None # Or proceed with default profile if testing without login is intended

    options = ChromeOptions()
    if profile_path and profile_path != 'PATH_TO_YOUR_FACEBOOK_CHROME_PROFILE':
         # Note: user-data-dir should be the PARENT of the "Profile X" directory or "Default" directory
         # e.g. /Users/user/Library/Application Support/Google/Chrome/
         # And then add argument profile-directory=Profile 1
        parts = os.path.split(profile_path)
        user_data_dir = parts[0]
        profile_directory = parts[1]
        options.add_argument(f"--user-data-dir={user_data_dir}")
        options.add_argument(f"--profile-directory={profile_directory}")
        print(f"Attempting to use Chrome profile: {profile_path}")

    # options.add_argument("--headless") # Run headless
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox") # Often needed for headless in Linux environments
    options.add_argument("--disable-dev-shm-usage") # Overcome limited resource problems
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36") # Example user agent
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) # Attempt to make it look less like a bot
    options.add_experimental_option('useAutomationExtension', False)
    # options.add_argument('--disable-blink-features=AutomationControlled') # Another attempt

    try:
        driver = webdriver.Chrome(options=options)
        # driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})") # Deprecated
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Ensure ChromeDriver is installed and compatible with your Chrome version, and in your PATH.")
        return None

# --- Core Scraping Logic ---
def scrape_facebook_page(driver, page_url, db_conn, platform_id, max_posts=10):
    """
    Scrapes posts from a Facebook page.
    This is a VERY basic stub and will need significant refinement.
    """
    print(f"Navigating to Facebook page: {page_url}")
    driver.get(page_url)
    time.sleep(random.uniform(5, 10)) # Wait for page to load

    # --- Cookie / Login Pop-up Handling (Very Basic Example) ---
    # Facebook often shows cookie consent or login prompts.
    # This needs to be adapted based on what actually appears.
    try:
        # Example: Look for a common cookie accept button text/aria-label
        # This selector is a GUESS. Update it by inspecting the page.
        cookie_accept_button_xpath = "//div[@aria-label='Allow all cookies']//div[@role='button']" # Example
        wait = WebDriverWait(driver, 10)
        accept_button = wait.until(EC.element_to_be_clickable((By.XPATH, cookie_accept_button_xpath)))
        accept_button.click()
        print("Attempted to accept cookie policy.")
        time.sleep(random.uniform(2, 4))
    except Exception as e:
        print(f"No cookie banner found or could not click it: {e}")
        # Might be an issue if it blocks content, or might be fine.

    # Scroll down to load more posts
    print("Scrolling to load posts...")
    for _ in range(5): # Scroll a few times
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(random.uniform(3, 7))

    print("Attempting to extract post data...")
    # IMPORTANT: Facebook's HTML is complex and uses obfuscated class names.
    # These selectors are placeholders and WILL need to be updated by inspecting the live page.
    # Look for `role="article"` or similar semantic HTML if possible.
    # This example tries to find divs that might be posts.

    # A more robust approach would be to use specific, less volatile attributes.
    # For instance, posts often have a top-level element with `role="article"`.
    # Inside that, you'd find elements for author, text, timestamp, etc.

    # Let's try to find elements with `role="article"`
    # The actual structure within these articles varies greatly.
    articles = driver.find_elements(By.XPATH, "//div[@role='article']")
    print(f"Found {len(articles)} potential 'article' elements.")

    posts_scraped_count = 0
    for i, article_el in enumerate(articles):
        if posts_scraped_count >= max_posts:
            break

        post_data = {"raw_element_text": article_el.text[:200]} # Basic raw data
        post_text = "N/A"
        author_name = "N/A"
        author_url = None
        post_url_extracted = None # Difficult to get reliably for each post from feed

        # Try to find post text (very fragile selector example)
        # Common text container classes often start with 'x', e.g., 'x1iorvi4 x1pi30zi'
        # This is a guess - inspect the page for actual selectors.
        try:
            # Look for text elements within the article.
            # This could be a span or div with specific data attributes or classes.
            # Example: find all spans, filter by length or content. This is inefficient.
            # A better way: find a specific element known to hold the main text.
            text_elements = article_el.find_elements(By.XPATH, ".//div[contains(@dir, 'auto') and string-length(normalize-space(.)) > 50]") # Example for text blocks
            if text_elements:
                post_text = text_elements[0].text.strip()
            else: # Fallback if specific text element not found
                # Try another common pattern for text (often in spans)
                span_texts = article_el.find_elements(By.XPATH, ".//span[string-length(normalize-space(.)) > 50]")
                if span_texts:
                    post_text = span_texts[0].text.strip()
                else: # If still no text, use a snippet of the article text if any
                    post_text = article_el.text.strip()[:500] if article_el.text else "N/A"


        except Exception as e:
            # print(f"Could not extract post text for article {i}: {e}")
            post_text = article_el.text.strip()[:500] if article_el.text else "N/A"


        # Try to find author name (also fragile)
        # Author links are often an 'a' tag with specific attributes or structure.
        try:
            # Look for 'a' tags with hrefs pointing to profiles, often with role="link"
            # This is a common pattern for author links.
            author_link_el = article_el.find_element(By.XPATH, ".//a[@role='link' and contains(@href, 'facebook.com/') and not(contains(@href,'/groups/')) and string-length(.//strong/text()) > 0]")
            author_name = author_link_el.text.strip()
            author_url = author_link_el.get_attribute('href')
            # Extract platform_specific_author_id from author_url if possible (complex)
        except Exception as e:
            # print(f"Could not extract author for article {i}: {e}")
            author_name = "Unknown Author" # Fallback

        platform_specific_post_id = f"fb_post_{page_url}_{i}_{time.time()}" # Placeholder ID
        platform_specific_author_id = author_url or f"fb_author_{author_name.replace(' ','_')}" # Placeholder

        print(f"--- Post {i+1} ---")
        print(f"Author: {author_name} ({author_url})")
        print(f"Text: {post_text[:150]}...")

        # --- Save to DB ---
        if db_conn:
            author_id_db = get_or_create_author_db(db_conn, platform_id, platform_specific_author_id, username=author_name, display_name=author_name, profile_url=author_url)
            save_content_item_db(db_conn, platform_id, author_id_db, platform_specific_post_id, post_text, post_url=page_url, raw_data=post_data) # Using page_url as post_url for now
            posts_scraped_count += 1
            print(f"Post {i+1} data (partially) sent to DB stubs.")

        time.sleep(random.uniform(1, 3)) # Small delay between processing posts

    print(f"Finished scraping attempt for {page_url}. Scraped {posts_scraped_count} posts.")


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Facebook Live Scraper...")
    config = load_config()

    if not config:
        print("Exiting due to configuration error.")
        exit()

    db_settings = dict(config['DatabasePostgreSQL'])
    fb_settings = config['FacebookScraper']

    # Example target: take the first one from default_scrape_targets
    targets = fb_settings.get('default_scrape_targets', '').split(',')
    if not targets or not targets[0].strip():
        print("No default_scrape_targets found for Facebook in config.ini. Please add a target URL.")
        exit()

    target_url = targets[0].strip()
    print(f"Target URL for scraping: {target_url}")

    driver = None
    db_connection = None
    try:
        db_connection = get_db_connection(db_settings)
        if not db_connection:
            print("Exiting due to database connection error.")
            exit()

        platform_main_id = get_platform_id(db_connection) # Get/create 'Facebook' platform ID

        driver = setup_driver(fb_settings)
        if driver:
            print("WebDriver setup successful.")
            scrape_facebook_page(driver, target_url, db_connection, platform_main_id, max_posts=5) # Scrape limited posts for test
        else:
            print("WebDriver setup failed. Cannot scrape.")

    except Exception as e:
        print(f"An error occurred in the main execution: {e}")
    finally:
        if driver:
            print("Closing WebDriver...")
            driver.quit()
        if db_connection:
            db_connection.close()
            # print("Database connection closed.")
    print("Facebook Live Scraper finished.")
