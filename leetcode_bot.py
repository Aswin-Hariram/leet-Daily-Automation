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
    'headless': True,
    'timeout': 30,
    'min_delay': 1,
    'max_delay': 3,
    'problem_url': "https://leetcode.com/problems/two-sum/",
    'max_retries': 3,
    'screenshots_dir': "screenshots",
    'xvfb': platform.system() == 'Linux'
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
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
    options.add_argument("--window-size=1920,1080")

    try:
        driver = uc.Chrome(
            options=options,
            headless=CONFIG['headless'],
            use_subprocess=True,
            auto_install=True
        )
        driver.set_page_load_timeout(CONFIG['timeout'])
        return driver
    except Exception as e:
        logger.error(f"Failed to setup driver: {str(e)}")
        raise

def clear_editor(driver: uc.Chrome, modifier_key: Keys) -> None:
    """Clear the code editor content."""
    for attempt in range(CONFIG['max_retries']):
        try:
            editor = WebDriverWait(driver, CONFIG['timeout']).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".monaco-editor textarea"))
            )
            editor.click()
            human_delay(0.5, 1)

            action = ActionChains(driver)
            action.key_down(modifier_key).send_keys("a").key_up(modifier_key).perform()
            human_delay(0.2, 0.5)
            action.send_keys(Keys.BACKSPACE).perform()
            human_delay(0.5, 1)
            return
        except (TimeoutException, ElementClickInterceptedException) as e:
            if attempt == CONFIG['max_retries'] - 1:
                logger.error(f"Failed to clear editor after {CONFIG['max_retries']} attempts")
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
            human_delay(1, 2)

def type_solution(driver: uc.Chrome, solution_code: str) -> None:
    """Type the solution code into the editor."""
    try:
        clear_editor(driver, get_modifier_key())
        
        editor = WebDriverWait(driver, CONFIG['timeout']).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".monaco-editor textarea"))
        )
        editor.click()
        human_delay(0.5, 1)

        pyperclip.copy(solution_code.strip())
        
        action = ActionChains(driver)
        action.key_down(get_modifier_key()).send_keys("v").key_up(get_modifier_key()).perform()
        human_delay(1, 2)
        
        if not editor.get_attribute('value'):
            logger.warning("Code may not have pasted correctly. Trying alternative method...")
            editor.send_keys(solution_code)
    except Exception as e:
        logger.error(f"Failed to type solution: {str(e)}")
        raise
    
def submit_solution(driver: uc.Chrome) -> Optional[str]:
    """Submit the solution and return the result."""
    try:
        submit_btn = WebDriverWait(driver, CONFIG['timeout']).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-e2e-locator='console-submit-button']"))
        )
        
        driver.execute_script("arguments[0].scrollIntoView();", submit_btn)
        submit_btn.click()
        logger.info("📤 Submitted. Waiting for result...")

        result_element = WebDriverWait(driver, CONFIG['timeout']).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-e2e-locator='submission-result']"))
        )
        result = result_element.text
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        status = "success" if "Accepted" in result else "failure"
        screenshot_path = f"{CONFIG['screenshots_dir']}/{status}_{timestamp}.png"
        driver.save_screenshot(screenshot_path)
        logger.info(f"📸 {status.capitalize()} screenshot saved to {screenshot_path}")
            
        logger.info(f"📊 Result: {result}")
        return result
    except TimeoutException:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"{CONFIG['screenshots_dir']}/error_{timestamp}.png"
        driver.save_screenshot(screenshot_path)
        logger.error(f"⚠️ Error screenshot saved to {screenshot_path}")
        logger.error("Failed to submit solution: Submit button or result not found")
        raise

def handle_verification(driver: uc.Chrome) -> None:
    """Handle any verification challenges that might appear."""
    try:
        if "human" in driver.title.lower() or "security" in driver.title.lower():
            logger.warning("⚠️ Verification required. Please complete manually...")
            WebDriverWait(driver, 120).until_not(
                lambda d: "human" in d.title.lower() or "security" in d.title.lower()
            )
            human_delay(2, 3)
    except Exception as e:
        logger.warning(f"Verification check failed: {str(e)}")

def inject_cookies(driver: uc.Chrome) -> None:
    """Inject authentication cookies into the browser."""
    if not LEETCODE_SESSION or not CSRF_TOKEN:
        raise ValueError("Missing required environment variables: LEETCODE_SESSION or CSRF_TOKEN")
    
    driver.get("https://leetcode.com")
    human_delay(1, 2)
    
    driver.add_cookie({
        'name': 'LEETCODE_SESSION', 
        'value': LEETCODE_SESSION, 
        'domain': '.leetcode.com',
        'secure': True,
        'path': '/'
    })
    driver.add_cookie({
        'name': 'csrftoken', 
        'value': CSRF_TOKEN, 
        'domain': '.leetcode.com',
        'secure': True,
        'path': '/'
    })
    logger.info("🔑 Cookies injected. Refreshing page...")
    driver.refresh()
    human_delay(2, 3)

def get_solution_from_gemini(problem_url: str) -> str:
    """Get solution code from Gemini AI for the given problem."""
    try:
        problem_name = problem_url.split('/')[-2]
        
        prompt = f"""Please provide a C++ solution for the LeetCode problem '{problem_name}'.
        Requirements:
        1. Complete implementation with all necessary includes
        2. Optimal time and space complexity
        3. Clean, well-commented code
        4. Ready to submit on LeetCode
        
        Return only the code without any additional explanation or markdown formatting."""
        
        logger.info(f"🤖 Requesting solution for: {problem_name}")
        response = model.generate_content(prompt)
        
        if response and response.text:
            solution_code = response.text.strip()
            solution_code = solution_code.replace("```cpp", "").replace("```", "").strip()
            
            logger.info(f"✅ Received solution ({len(solution_code)} chars)")
            return solution_code
        raise ValueError("Empty response from Gemini AI")
            
    except Exception as e:
        logger.error(f"❌ Failed to get solution: {str(e)}")
        raise

def get_todays_problem_url(driver: uc.Chrome) -> str:
    """Get today's problem URL from the problemset page."""
    for attempt in range(CONFIG['max_retries']):
        try:
            driver.get("https://leetcode.com/problemset/")
            human_delay(2, 4)
            today = datetime.now().day
            logger.info(f"🔍 Looking for today's problem (Day {today})...")
            
            WebDriverWait(driver, CONFIG['timeout']).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/problems/']"))
            )
            
            problem_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/problems/']")
            for link in problem_links:
                try:
                    day_element = link.find_element(By.CSS_SELECTOR, "span:not(.hidden)")
                    if day_element.text.strip() == str(today):
                        problem_url = link.get_attribute('href')
                        if problem_url:
                            logger.info(f"📅 Found today's problem: {problem_url}")
                            return problem_url
                except NoSuchElementException:
                    continue
                    
            raise ValueError(f"Could not find problem for day {today}")
            
        except Exception as e:
            if attempt == CONFIG['max_retries'] - 1:
                logger.error(f"Failed after {CONFIG['max_retries']} attempts: {str(e)}")
                raise
            logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying...")
            human_delay(3, 5)

def solve_problem(problem_url: str = None) -> None:
    """Main function to solve a LeetCode problem."""
    ensure_directory(CONFIG['screenshots_dir'])
    driver = None
    vdisplay = None
    
    try:
        if CONFIG['xvfb']:
            from xvfbwrapper import Xvfb
            vdisplay = Xvfb(width=1920, height=1080, colordepth=24)
            vdisplay.start()
            logger.info("Started Xvfb virtual display")
        
        driver = setup_driver()
        modifier_key = get_modifier_key()

        logger.info("🚀 Starting LeetCode session...")
        driver.get("https://leetcode.com")
        human_delay(2, 4)

        handle_verification(driver)
        inject_cookies(driver)

        if not problem_url:
            logger.info("🔍 Finding today's problem...")
            problem_url = get_todays_problem_url(driver)
            
        logger.info(f"📝 Navigating to problem: {problem_url}")
        driver.get(problem_url)
        human_delay(2, 4)

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
        if vdisplay:
            vdisplay.stop()
            logger.info("Stopped Xvfb virtual display")

if __name__ == "__main__":
    try:
        solve_problem()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}", exc_info=True)
        exit(1)