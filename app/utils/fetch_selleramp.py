# app/utils/fetch_selleramp.py

import time
import re
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Configuration Selenium
options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

def fetch_selleramp_info(ean, prix_magasin, max_retries=1):
    """🔍 Récupère les données SellerAmp (sans scraping)."""
    driver_selleramp = None

    for attempt in range(max_retries):
        try:
            print(f"⚡ Attempt {attempt + 1}/{max_retries} for EAN {ean}...")

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

            # Gestion des erreurs
            if driver_selleramp.find_elements(By.XPATH, "//*[contains(text(), 'Please choose the most suitable match:')]"):
                print(f"⚠️ Multiple choices detected for EAN {ean}. Ignoring product.")
                return None, None, None, None, None  # ✅ Retourne 5 valeurs

            if driver_selleramp.find_elements(By.XPATH, "//*[contains(text(), 'No results were found')]"):
                print(f"⚠️ No results found for EAN {ean}. Ignoring product.")
                return None, None, None, None, None  # ✅ Retourne 5 valeurs

            # Récupération des données
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
            sales_estimation = driver_selleramp.find_element(By.CSS_SELECTOR, '.estimated_sales_per_mo').text

            # 🔄 Ajout de la 5e valeur (alerts)
            alerts = None  # SellerAmp ne semble pas fournir cette info ici, donc on met `None`

            return prix_amazon, roi, profit, sales_estimation, alerts  # ✅ Retourne bien 5 valeurs
        except Exception as e:
            print(f"⚠️ Error in fetching data for EAN {ean}: {e}")
            time.sleep(2)
        finally:
            if driver_selleramp:
                driver_selleramp.quit()

    return None, None, None, None, None  # ✅ Toujours retourner 5 valeurs même en cas d'erreur
