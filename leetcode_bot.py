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
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    TimeoutException, WebDriverException,
    NoSuchElementException, ElementClickInterceptedException
)
import google.generativeai as genai

# ------------------ Logging Configuration ------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('leetcode_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ------------------ Environment Variables ------------------
load_dotenv()
LEETCODE_SESSION = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJfYXV0aF91c2VyX2lkIjoiMTUxNTg2ODYiLCJfYXV0aF91c2VyX2JhY2tlbmQiOiJhbGxhdXRoLmFjY291bnQuYXV0aF9iYWNrZW5kcy5BdXRoZW50aWNhdGlvbkJhY2tlbmQiLCJfYXV0aF91c2VyX2hhc2giOiJiYzE2Y2Y0OGFjMWVhNGE3MDYwZmM0MjQ0Y2FmMmQ0MGI0ZDE1MjkxMjRjYjkxZDMwNWI3OGI2MGYzMTlkMzBlIiwic2Vzc2lvbl91dWlkIjoiNGMxZWJkNzQiLCJpZCI6MTUxNTg2ODYsImVtYWlsIjoiYXN3aW5jc2Vza2N0QGdtYWlsLmNvbSIsInVzZXJuYW1lIjoiUTJrRUtoMDBzWSIsInVzZXJfc2x1ZyI6IlEya0VLaDAwc1kiLCJhdmF0YXIiOiJodHRwczovL2Fzc2V0cy5sZWV0Y29kZS5jb20vdXNlcnMvUTJrRUtoMDBzWS9hdmF0YXJfMTcyOTM0MjE0Ny5wbmciLCJyZWZyZXNoZWRfYXQiOjE3NDQyMTMxNDksImlwIjoiMTAzLjEzMC4yMDQuNjciLCJpZGVudGl0eSI6IjgzMTNkNTlhYjQ1ODJiMjk1MThiMmJjMTc3YjIzNTkxIiwiZGV2aWNlX3dpdGhfaXAiOlsiNjFiODI5YmZjMjNkYmRmNjQ3NGUwN2JhZDJmOWEwYmMiLCIxMDMuMTMwLjIwNC42NyJdLCJfc2Vzc2lvbl9leHBpcnkiOjEyMDk2MDB9.TOpe-8yuQPtXh_hLBvaZva1lGfqVW-23SXhDV_OUBT0'
CSRF_TOKEN = 'wOlG8ENh18aCakGi82ayGoSdwp4UbMWh6tbsvHrxaKzRXJxdEmSZblLThwaiqz6G'
GEMINI_API_KEY = 'AIzaSyC_VZfdiNXsNXr8kVxz8U4mtTTRG11K9Fs'
# ------------------ Gemini AI Configuration ------------------
# ------------------ Gemini AI Configuration ------------------
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(model_name="gemini-1.5-pro")
else:
    logger.warning("GEMINI_API_KEY not found. AI features will be disabled.")
    model = None

# ------------------ Config ------------------
CONFIG = {
    'headless': False,
    'timeout': 30,
    'min_delay': 1,
    'max_delay': 3,
    'problem_url': None,
    'max_retries': 3,
    'screenshots_dir': "screenshots"
}

# ------------------ Utility Functions ------------------
def ensure_directory(directory: str) -> None:
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def get_modifier_key() -> Keys:
    return Keys.COMMAND if platform.system() == 'Darwin' else Keys.CONTROL

def human_delay(min_sec: float = CONFIG['min_delay'], max_sec: float = CONFIG['max_delay']) -> None:
    time.sleep(random.uniform(min_sec, max_sec))

def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    if CONFIG['headless']:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
    driver = uc.Chrome(version_main=134, options=options)
    driver.set_page_load_timeout(CONFIG['timeout'])
    return driver

def clear_editor(driver: uc.Chrome, modifier_key: Keys) -> None:
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
                logger.error("Failed to clear editor after retries")
                raise
            logger.warning(f"Retrying clear editor ({attempt + 1}) due to: {str(e)}")
            human_delay(1, 2)

def type_solution(driver: uc.Chrome, solution_code: str) -> None:
    try:
        clear_editor(driver, get_modifier_key())
        editor = WebDriverWait(driver, CONFIG['timeout']).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".monaco-editor textarea"))
        )
        editor.click()
        human_delay(0.5, 1)
        try:
            pyperclip.copy(solution_code.strip())
        except pyperclip.PyperclipException:
            logger.warning("⚠️ Clipboard failed. Try `sudo apt install xclip` on Ubuntu.")
            editor.send_keys(solution_code)
            return
        action = ActionChains(driver)
        action.key_down(get_modifier_key()).send_keys("v").key_up(get_modifier_key()).perform()
        human_delay(1, 2)
        if not editor.get_attribute('value'):
            logger.warning("Fallback to keystroke typing")
            editor.send_keys(solution_code)
    except Exception as e:
        logger.error(f"Failed to type solution: {str(e)}")
        raise

def submit_solution(driver: uc.Chrome) -> Optional[str]:
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
        logger.info(f"📸 Screenshot saved: {screenshot_path}")
        return result
    except TimeoutException:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"{CONFIG['screenshots_dir']}/error_{timestamp}.png"
        driver.save_screenshot(screenshot_path)
        logger.error(f"⚠️ Timeout - screenshot saved to {screenshot_path}")
        raise

def handle_verification(driver: uc.Chrome) -> None:
    try:
        if "human" in driver.title.lower() or "security" in driver.title.lower():
            logger.warning("⚠️ Captcha or human verification required. Waiting...")
            WebDriverWait(driver, 120).until_not(
                lambda d: "human" in d.title.lower() or "security" in d.title.lower()
            )
            human_delay(2, 3)
    except Exception as e:
        logger.warning(f"Verification handling issue: {str(e)}")

def inject_cookies(driver: uc.Chrome) -> None:
    if not LEETCODE_SESSION or not CSRF_TOKEN:
        raise ValueError("Missing cookies (LEETCODE_SESSION or CSRF_TOKEN)")
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
    logger.info("🔑 Cookies injected. Refreshing...")
    driver.refresh()
    human_delay(2, 3)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"{CONFIG['screenshots_dir']}/after_login_{timestamp}.png"
    driver.save_screenshot(screenshot_path)
    logger.info(f"📸 Saved post-login screenshot: {screenshot_path}")

def get_solution_from_gemini(problem_url: str) -> str:
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
            solution_code = response.text.strip().replace("```cpp", "").replace("```", "").strip()
            logger.info(f"✅ Received solution ({len(solution_code)} chars)")
            return solution_code
        raise ValueError("Empty response from Gemini AI")
    except Exception as e:
        logger.error(f"❌ Failed to get solution: {str(e)}")
        raise

def get_todays_problem_url(driver: uc.Chrome) -> str:
    for attempt in range(CONFIG['max_retries']):
        try:
            driver.get("https://leetcode.com/problemset/")
            human_delay(2, 4)
            today = 9
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
    ensure_directory(CONFIG['screenshots_dir'])
    driver = None
    try:
        driver = setup_driver()
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
            logger.warning("Fallback to default solution")
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
            logger.info("🛑 Browser closed.")

# ------------------ Run Script ------------------
if __name__ == "__main__":
    try:
        solve_problem()
    except Exception as e:
        logger.error(f"Script failed: {str(e)}", exc_info=True)
        exit(1)