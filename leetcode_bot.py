import os
import time
import random
import platform
import logging
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
import pyperclip
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (TimeoutException, WebDriverException, 
                                      NoSuchElementException, ElementClickInterceptedException)
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('leetcode_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
LEETCODE_SESSION = os.getenv("LEETCODE_SESSION")
CSRF_TOKEN = os.getenv("CSRF_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Configure Gemini AI
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-pro")
else:
    logger.warning("GEMINI_API_KEY not found. AI features will be disabled.")
    model = None

# Configuration
CONFIG = {
    'headless': True,  # Changed to True for Ubuntu
    'timeout': 30,
    'min_delay': 1,
    'max_delay': 3,
    'problem_url': "https://leetcode.com/problems/two-sum/",
    'max_retries': 3,
    'screenshots_dir': "screenshots",
    'xvfb': platform.system() == 'Linux'  # Enable Xvfb for Linux
}

def ensure_directory(directory: str) -> None:
    """Ensure a directory exists, create if it doesn't."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def get_modifier_key() -> Keys:
    """Return the appropriate modifier key based on the operating system."""
    return Keys.COMMAND if platform.system() == 'Darwin' else Keys.CONTROL

def human_delay(min_sec: float = CONFIG['min_delay'], max_sec: float = CONFIG['max_delay']) -> None:
    """Add a random delay to simulate human behavior."""
    time.sleep(random.uniform(min_sec, max_sec))

def setup_driver() -> uc.Chrome:
    """Initialize and configure the Chrome WebDriver."""
    options = uc.ChromeOptions()
    
    if CONFIG['headless']:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--remote-debugging-port=9222")
    
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    
    try:
        driver = uc.Chrome(
            options=options,
            headless=CONFIG['headless'],
            version_main=120  # Specify Chrome version
        )
        driver.set_page_load_timeout(CONFIG['timeout'])
        return driver
    except Exception as e:
        logger.error(f"Failed to setup driver: {str(e)}")
        raise

# [Rest of the functions remain the same as in your original script...]

def solve_problem(problem_url: str = None) -> None:
    """Main function to solve a LeetCode problem."""
    ensure_directory(CONFIG['screenshots_dir'])
    driver = None
    
    try:
        # Start Xvfb if on Linux
        if CONFIG['xvfb']:
            from xvfbwrapper import Xvfb
            vdisplay = Xvfb()
            vdisplay.start()
            logger.info("Started Xvfb virtual display")
        
        driver = setup_driver()
        modifier_key = get_modifier_key()

        logger.info("🚀 Starting LeetCode session...")
        driver.get("https://leetcode.com")
        human_delay(2, 4)

        handle_verification(driver)
        inject_cookies(driver)

        # Get problem URL if not provided
        if not problem_url:
            logger.info("🔍 Finding today's problem...")
            problem_url = get_todays_problem_url(driver)
            
        logger.info(f"📝 Navigating to problem: {problem_url}")
        driver.get(problem_url)
        human_delay(2, 4)

        # Get solution from Gemini
        if model:
            solution_code = get_solution_from_gemini(problem_url)
        else:
            logger.warning("Using default solution since Gemini API key not available")
            solution_code = """class Solution {
public:
    vector<int> twoSum(vector<int>& nums, int target) {
        unordered_map<int, int> num_map;
        for (int i = 0; i < nums.size(); i++) {
            int complement = target - nums[i];
            if (num_map.find(complement) != num_map.end()) {
                return {num_map[complement], i};
            }
            num_map[nums[i]] = i;
        }
        return {};
    }
};"""

        # Wait for editor and submit solution
        WebDriverWait(driver, CONFIG['timeout']).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".monaco-editor"))
        )
        
        logger.info("✍️ Preparing to submit solution...")
        clear_editor(driver, modifier_key)
        type_solution(driver, solution_code)
        
        result = submit_solution(driver)
        logger.info(f"🎉 Final result: {result}")

    except Exception as e:
        logger.error(f"❌ Critical error: {str(e)}", exc_info=True)
        if driver:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            driver.save_screenshot(f"{CONFIG['screenshots_dir']}/critical_error_{timestamp}.png")
        raise
    finally:
        if driver:
            driver.quit()
            logger.info("🛑 Driver closed")
        if CONFIG['xvfb'] and 'vdisplay' in locals():
            vdisplay.stop()
            logger.info("Stopped Xvfb virtual display")

if __name__ == "__main__":
    try:
        solve_problem()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}", exc_info=True)
        exit(1)