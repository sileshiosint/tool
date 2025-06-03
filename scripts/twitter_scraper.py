import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --- CONFIGURATION ---
# IMPORTANT: Replace this with the actual path to your Chrome user profile.
# This profile should already be logged into Twitter/X.
CHROME_PROFILE_PATH = "PATH_TO_YOUR_CHROME_PROFILE_TWITTER" # e.g., "/Users/youruser/Library/Application Support/Google/Chrome/Profile 1"
# It's good practice to use a separate profile for Twitter if you manage multiple, or the same one if it's logged into both.

TARGET_TWITTER_KEYWORD = "humanitarian aid" # Example keyword
TARGET_TWITTER_USER_PROFILE = "https://twitter.com/UN" # Example user profile

def setup_driver(profile_path):
    """Sets up the Chrome WebDriver with a specific user profile."""
    chrome_options = Options()
    if not profile_path or profile_path == "PATH_TO_YOUR_CHROME_PROFILE_TWITTER":
        print("WARNING: CHROME_PROFILE_PATH_TWITTER is not set. Selenium will use a default or new profile.")
        print("Make sure to set CHROME_PROFILE_PATH_TWITTER in the script to your logged-in Chrome profile for Twitter/X.")
    else:
        chrome_options.add_argument(f"user-data-dir={profile_path}")

    # Optional: Run headless
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--disable-gpu")
    # chrome_options.add_argument("--window-size=1920,1200")

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure you have ChromeDriver installed and it's in your PATH.")
        return None

def scrape_tweets_by_keyword(driver, keyword, num_tweets_to_scrape=10):
    """Scrapes tweets based on a keyword search on Twitter/X."""
    tweets_data = []
    search_url = f"https://twitter.com/search?q={keyword.replace(' ', '%20')}&src=typed_query"

    try:
        driver.get(search_url)
        print(f"Navigated to search results for keyword: {keyword}")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
        )
        print("Tweet articles found on search page.")

        # Scroll down to load more tweets
        for _ in range(3): # Scroll a few times
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3) # Wait for new tweets to load

        # Selector for tweet text. Twitter/X's structure uses 'data-testid' attributes which are usually more stable.
        # The main text of a tweet is often in a div with data-testid="tweetText".
        tweet_elements = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']//div[@data-testid='tweetText']")

        print(f"Found {len(tweet_elements)} potential tweet text elements. Scraping up to {num_tweets_to_scrape}.")

        for i, el in enumerate(tweet_elements):
            if i >= num_tweets_to_scrape:
                break
            try:
                tweet_text = el.text.strip()
                if tweet_text:
                    tweets_data.append({"source_keyword": keyword, "tweet_text": tweet_text, "scraped_at": time.time()})
                    print(f"Scraped tweet {i+1}: {tweet_text[:100]}...")
            except Exception as e:
                print(f"Error scraping individual tweet: {e}")

        if not tweets_data:
            print("No tweets found or scraped from keyword search. Selectors might need an update or no results for keyword.")

    except Exception as e:
        print(f"Error scraping tweets for keyword {keyword}: {e}")

    return pd.DataFrame(tweets_data)

def scrape_tweets_from_user_profile(driver, user_profile_url, num_tweets_to_scrape=10):
    """Scrapes tweets from a user's profile page on Twitter/X."""
    tweets_data = []
    try:
        driver.get(user_profile_url)
        print(f"Navigated to user profile: {user_profile_url}")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//article[@data-testid='tweet']"))
        )
        print("Tweet articles found on user profile page.")

        # Scroll down to load more tweets
        for _ in range(3): # Scroll a few times
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

        tweet_elements = driver.find_elements(By.XPATH, "//article[@data-testid='tweet']//div[@data-testid='tweetText']")

        print(f"Found {len(tweet_elements)} potential tweet text elements. Scraping up to {num_tweets_to_scrape}.")

        for i, el in enumerate(tweet_elements):
            if i >= num_tweets_to_scrape:
                break
            try:
                tweet_text = el.text.strip()
                if tweet_text:
                    # Could also try to get tweet permalink, user, timestamp etc.
                    tweets_data.append({"source_user_profile": user_profile_url, "tweet_text": tweet_text, "scraped_at": time.time()})
                    print(f"Scraped tweet {i+1}: {tweet_text[:100]}...")
            except Exception as e:
                print(f"Error scraping individual tweet from profile: {e}")

        if not tweets_data:
            print("No tweets found or scraped from user profile. Selectors might need an update or profile has no tweets.")

    except Exception as e:
        print(f"Error scraping tweets from user profile {user_profile_url}: {e}")

    return pd.DataFrame(tweets_data)


if __name__ == "__main__":
    print("Starting Twitter/X Scraper...")

    effective_chrome_profile_path = CHROME_PROFILE_PATH_TWITTER

    if effective_chrome_profile_path == "PATH_TO_YOUR_CHROME_PROFILE_TWITTER":
        print("="*50)
        print("IMPORTANT: To use your logged-in Twitter/X session,")
        print("you MUST set 'CHROME_PROFILE_PATH_TWITTER' in this script.")
        print("Skipping actual browser launch for this automated run as path is generic.")
        print("="*50)
        df_tweets_keyword = pd.DataFrame(columns=["source_keyword", "tweet_text", "scraped_at"])
        df_tweets_profile = pd.DataFrame(columns=["source_user_profile", "tweet_text", "scraped_at"])
    else:
        driver = setup_driver(effective_chrome_profile_path)
        if driver:
            print(f"--- Scraping by Keyword: {TARGET_TWITTER_KEYWORD} ---")
            df_tweets_keyword = scrape_tweets_by_keyword(driver, TARGET_TWITTER_KEYWORD, num_tweets_to_scrape=5)
            if not df_tweets_keyword.empty:
                print("\n--- Scraped Tweets (Keyword) ---")
                print(df_tweets_keyword)
            else:
                print("\nNo tweets were scraped for the keyword.")

            print(f"--- Scraping User Profile: {TARGET_TWITTER_USER_PROFILE} ---")
            df_tweets_profile = scrape_tweets_from_user_profile(driver, TARGET_TWITTER_USER_PROFILE, num_tweets_to_scrape=5)
            if not df_tweets_profile.empty:
                print("\n--- Scraped Tweets (Profile) ---")
                print(df_tweets_profile)
            else:
                print("\nNo tweets were scraped from the user profile.")

            driver.quit()
        else:
            print("WebDriver setup failed. Scraping aborted.")
            df_tweets_keyword = pd.DataFrame(columns=["source_keyword", "tweet_text", "scraped_at"])
            df_tweets_profile = pd.DataFrame(columns=["source_user_profile", "tweet_text", "scraped_at"])

    if not df_tweets_keyword.empty:
        print("\nKeyword tweets DataFrame created.")
    if not df_tweets_profile.empty:
        print("\nProfile tweets DataFrame created.")

    if df_tweets_keyword.empty and df_tweets_profile.empty:
        print("\nCreated empty DataFrames as scraping was skipped or failed.")


    print("Twitter/X Scraper script finished.")
