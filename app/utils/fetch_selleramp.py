# app/utils/fetch_selleramp.py

import time
import re
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

# Configuring selenium for fetch_selleramp without scraping the product details
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

def fetch_selleramp_info(ean, prix_magasin, max_retries=1):
    """Fetch SellerAmp data based on the EAN provided (without scraping)."""
    driver_selleramp = None

    for attempt in range(max_retries):
        try:
            print(f"⚡ Attempt {attempt + 1}/{max_retries} for EAN {ean}...")

            # Initializing Selenium WebDriver for SellerAmp site
            driver_selleramp = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            driver_selleramp.get('https://sas.selleramp.com/')

            WebDriverWait(driver_selleramp, 15).until(
                EC.presence_of_element_located((By.ID, "loginform-email"))
            ).send_keys("thomasroger1189@gmail.com")
            driver_selleramp.find_element(By.ID, "loginform-password").send_keys("Gintoki62")
            driver_selleramp.find_element(By.NAME, "login-button").click()

            WebDriverWait(driver_selleramp, 45).until(
                EC.presence_of_element_located((By.ID, 'saslookup-search_term'))
            ).send_keys(ean + Keys.RETURN)
            time.sleep(3)

            # Handling multiple results or no result case
            if driver_selleramp.find_elements(By.XPATH, "//*[contains(text(), 'Please choose the most suitable match:')]"):
                print(f"⚠️ Multiple choices detected for EAN {ean}. Ignoring product.")
                return None, None, None, None

            if driver_selleramp.find_elements(By.XPATH, "//*[contains(text(), 'No results were found')]"):
                print(f"⚠️ No results found for EAN {ean}. Ignoring product.")
                return None, None, None, None

            # Fetching data
            WebDriverWait(driver_selleramp, 10).until(
                EC.presence_of_element_located((By.ID, 'qi_sale_price'))
            )
            prix_amazon = driver_selleramp.find_element(By.ID, 'qi_sale_price').get_attribute('value')

            cost_input = driver_selleramp.find_element(By.ID, 'qi_cost')
            cost_input.clear()
            cost_input.send_keys(str(prix_magasin))
            cost_input.send_keys(Keys.RETURN)

            WebDriverWait(driver_selleramp, 10).until(
                lambda d: d.find_element(By.ID, 'qi-roi').text != '- ∞%'
            )
            roi = driver_selleramp.find_element(By.ID, 'qi-roi').text
            profit = driver_selleramp.find_element(By.ID, 'qi-profit').text

            # Fetching sales estimation
            sales_estimation = driver_selleramp.find_element(By.CSS_SELECTOR, '.estimated_sales_per_mo').text

            return prix_amazon, roi, profit, sales_estimation
        except Exception as e:
            print(f"⚠️ Error in fetching data for EAN {ean}: {e}")
            time.sleep(2)
        finally:
            if driver_selleramp:
                driver_selleramp.quit()

    return None, None, None, None
