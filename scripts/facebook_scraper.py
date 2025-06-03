import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
# IMPORTANT: Replace this with the actual path to your Chrome user profile.
# This profile should already be logged into Facebook.
CHROME_PROFILE_PATH = "PATH_TO_YOUR_CHROME_PROFILE" # e.g., "/Users/youruser/Library/Application Support/Google/Chrome/Profile 1" or "C:\Users\youruser\AppData\Local\Google\Chrome\User Data\Profile 1"
TARGET_FACEBOOK_URL = "https://www.facebook.com/facebook" # Example: Facebook's own page

def setup_driver(profile_path):
    """Sets up the Chrome WebDriver with a specific user profile."""
    chrome_options = Options()
    if not profile_path or profile_path == "PATH_TO_YOUR_CHROME_PROFILE":
        print("WARNING: CHROME_PROFILE_PATH is not set. Selenium will use a default or new profile.")
        print("Make sure to set CHROME_PROFILE_PATH in the script to your logged-in Chrome profile.")
    else:
        chrome_options.add_argument(f"user-data-dir={profile_path}")

    # Optional: Run headless (without opening a browser window)
    # chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--disable-gpu") # Recommended for headless
    # chrome_options.add_argument("--window-size=1920,1200") # Optional

    try:
        driver = webdriver.Chrome(options=chrome_options)
        return driver
    except Exception as e:
        print(f"Error setting up WebDriver: {e}")
        print("Please ensure you have ChromeDriver installed and it's in your PATH, or specify its location.")
        print("You can download ChromeDriver from: https://chromedriver.chromium.org/downloads")
        return None

def scrape_facebook_page_posts(driver, page_url, num_posts_to_scrape=5):
    """Scrapes posts from a Facebook page."""
    posts_data = []
    try:
        driver.get(page_url)
        print(f"Navigated to: {page_url}")

        # Wait for posts to load - this selector might need adjustment
        # This is a generic selector for a post container. Facebook's structure is complex and changes.
        # Consider looking for elements with role="article" or similar.
        # For this initial version, we'll use a simple time.sleep and a broad selector.
        time.sleep(5) # Allow time for dynamic content to load

        # Scroll down to load more posts if necessary
        for _ in range(3): # Scroll a few times
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)

        # This selector is highly likely to change and is just an example.
        # It tries to find elements that might contain post text.
        # Inspect Facebook's HTML structure carefully for robust selectors.
        # Common attributes for posts might include 'aria-posinset' or specific class names.
        # Let's try to find divs that might be post containers based on a common pattern (this is very fragile)
        # A more robust approach would involve finding elements with specific `role` attributes like `article`.

        # Attempting to find elements with role='article'
        # post_elements = driver.find_elements(By.XPATH, "//div[@role='article']")

        # Facebook's structure is complex. For a stub, let's try a more general approach
        # to find text blocks. This will likely grab more than just posts.
        # This is a placeholder selector and will need significant refinement.
        # For now, let's try finding divs with specific data attributes often used for content.
        # Example: data-ad-preview="message" or similar for post text.
        # Due to the difficulty of a stable selector without inspection, this will be very basic.

        # Let's assume posts are within divs and have some text.
        # This is a very naive approach for demonstration.
        # A better way is to use specific, stable attributes if available.
        # For example, elements with 'data-pagelet' attributes that correspond to posts.

        # Trying a more specific but still potentially fragile selector for post text content
        # This looks for elements that are known to often contain the main text of a post.
        # The class names on Facebook are often obfuscated and change frequently.
        # The selector 'div[data-ad-preview="message"]' is sometimes used for the main text body of a post.
        # Another common pattern is text directly within an element with role="article".

        # Let's try to find all divs that could be posts, then extract text.
        # This is a common challenge with scraping Facebook.
        # For this stub, we'll simulate finding a few pieces of text.
        # Replace this with actual, effective selectors after inspecting the target page.

        # A common pattern for post text is within a div with specific styling or attributes.
        # Let's try a very generic approach of finding divs with text.
        # This will require significant refinement.
        possible_post_elements = driver.find_elements(By.XPATH, "//div[string-length(normalize-space(.)) > 50]") # Example: find divs with more than 50 chars

        print(f"Found {len(possible_post_elements)} potential post elements. Scraping up to {num_posts_to_scrape}.")

        for i, el in enumerate(possible_post_elements):
            if i >= num_posts_to_scrape:
                break
            try:
                post_text = el.text.strip()
                if len(post_text) > 20: # Filter out very short texts
                    posts_data.append({"url": page_url, "post_text": post_text, "scraped_at": time.time()})
                    print(f"Scraped post {i+1}: {post_text[:100]}...") # Print first 100 chars
            except Exception as e:
                print(f"Error scraping individual post element: {e}")

        if not posts_data:
            print("No posts found or scraped. The selectors might need adjustment or the page structure is different than expected.")
            print("Common Facebook post text containers can be divs with classes like 'x1iorvi4 x1pi30zi x1l90r2v x1swvt13' or similar, but these change.")
            print("Consider inspecting the page and using more specific XPATH or CSS selectors.")

    except Exception as e:
        print(f"Error during scraping Facebook page {page_url}: {e}")

    return pd.DataFrame(posts_data)

if __name__ == "__main__":
    print("Starting Facebook Scraper...")

    # --- Check and Set Profile Path ---
    # For local testing, replace "PATH_TO_YOUR_CHROME_PROFILE" directly here or ensure the constant is set above.
    # Example for macOS: profile_path = "/Users/yourusername/Library/Application Support/Google/Chrome/Default"
    # Example for Windows: profile_path = "C:\Users\yourusername\AppData\Local\Google\Chrome\User Data\Default"
    # Note: "Default" is often the main profile. If you use multiple Chrome profiles, it might be "Profile 1", "Profile 2", etc.

    effective_chrome_profile_path = CHROME_PROFILE_PATH
    # To actually run this, you MUST change CHROME_PROFILE_PATH above or effective_chrome_profile_path here.
    # For this subtask, it will likely run with the warning as the path isn't set.

    if effective_chrome_profile_path == "PATH_TO_YOUR_CHROME_PROFILE":
        print("="*50)
        print("IMPORTANT: To use your logged-in Facebook session,")
        print("you MUST set the 'CHROME_PROFILE_PATH' variable in this script")
        print("to the path of your Chrome user profile directory.")
        print("Skipping actual browser launch for this automated run as path is generic.")
        print("="*50)
        # Create an empty DataFrame as a fallback for the subtask environment
        df_posts = pd.DataFrame(columns=["url", "post_text", "scraped_at"])
    else:
        driver = setup_driver(effective_chrome_profile_path)
        if driver:
            print(f"Attempting to scrape: {TARGET_FACEBOOK_URL}")
            df_posts = scrape_facebook_page_posts(driver, TARGET_FACEBOOK_URL, num_posts_to_scrape=5)
            if not df_posts.empty:
                print("\n--- Scraped Posts ---")
                print(df_posts)
            else:
                print("\nNo posts were scraped. This could be due to selectors needing an update,")
                print("the CHROME_PROFILE_PATH not being correctly configured for a logged-in session,")
                print("or Facebook's structure preventing access.")
            driver.quit()
        else:
            print("WebDriver setup failed. Scraping aborted.")
            df_posts = pd.DataFrame(columns=["url", "post_text", "scraped_at"])

    # For demonstration, save to a CSV if run directly (optional)
    if not df_posts.empty:
        # df_posts.to_csv("facebook_posts.csv", index=False)
        print("\nSuccessfully created DataFrame (data might be empty if scraping was skipped or failed).")
    else:
        print("\nCreated an empty DataFrame as scraping was skipped or failed.")

    print("Facebook Scraper script finished.")
