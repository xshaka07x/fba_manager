# scraping/scraper.py

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, StaleElementReferenceException
)
from webdriver_manager.chrome import ChromeDriverManager
import sys
import os

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import time
import re
import logging
from app import create_app, db
from app.models import Product
from mysql.connector import Error
from app.utils.db import get_db_connection
from datetime import datetime
import pytz
from datetime import timedelta  # 🔥 Ajout nécessaire en haut du fichier

# 🔗 Initialisation Flask
app = create_app()
with app.app_context():
    db.create_all()

# ⚙️ Configuration Selenium
options = Options()
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-features=VizDisplayCompositor")
options.add_argument("--window-size=1920,1080")
options.add_argument("--no-sandbox")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--headless=new")
options.page_load_strategy = 'eager'


try:
    from app import create_app, db
except ImportError as e:
    print(f"❌ Erreur d'import : {e}")
    print(f"🛠️ PYTHONPATH utilisé : {sys.path}")
    sys.exit(1)


project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_path not in sys.path:
    sys.path.insert(0, project_path)


def insert_or_update_product(nom, ean, prix_retail, url, prix_amazon, roi, profit, sales_estimation, alerts):
    """📝 Insère ou met à jour un produit avec TOUTES les données SellerAmp en DB Railway."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # ✅ Sécurisation et LOG du format ROI et PROFIT
        try:
            roi_clean = re.sub(r'[^\d\.-]', '', roi)  # Supprime tout sauf chiffres, points et tirets
            roi = float(roi_clean) if roi_clean else None
        except Exception as e:
            logging.error(f"⚠️ Erreur conversion ROI : {roi} -> {e}")
            roi = None

        try:
            profit_clean = re.sub(r'[^\d\.-]', '', profit)  # Supprime € et espaces
            profit = float(profit_clean) if profit_clean else None
        except Exception as e:
            logging.error(f"⚠️ Erreur conversion PROFIT : {profit} -> {e}")
            profit = None

        try:
            prix_amazon = float(prix_amazon) if prix_amazon.replace(".", "").isdigit() else None
        except Exception as e:
            logging.error(f"⚠️ Erreur conversion Prix Amazon : {prix_amazon} -> {e}")
            prix_amazon = None

        logging.info(f"🔄 Insertion : ROI={roi}, Profit={profit}, Prix_Amazon={prix_amazon}")

        cursor.execute("SELECT id FROM products WHERE ean = %s AND url = %s", (ean, url))
        result = cursor.fetchone()
        paris_timezone = pytz.timezone("Europe/Paris")
        updated_at = datetime.now(paris_timezone) + timedelta(hours=1)  # 🕒 ✅ On ajoute 1h ici

        if result:
            cursor.execute("""
                UPDATE products 
                SET nom = %s, prix_retail = %s, prix_amazon = %s, roi = %s, profit = %s, sales_estimation = %s, alerts = %s, updated_at = %s
                WHERE id = %s
            """, (nom, prix_retail, prix_amazon, roi, profit, sales_estimation, alerts, updated_at, result[0]))
            print(f"🔄 [SCRAPER] Produit mis à jour : {nom} | EAN: {ean}")
        else:
            cursor.execute("""
                INSERT INTO products (nom, ean, prix_retail, url, prix_amazon, roi, profit, sales_estimation, alerts)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (nom, ean, prix_retail, url, prix_amazon, roi, profit, sales_estimation, alerts))
            print(f"🆕 [SCRAPER] Produit inséré : {nom} | EAN: {ean}")

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        logging.error(f"❌ Erreur DB: {e}")


def set_items_per_page(driver):
    """📏 Sélectionne 96 produits par page avec gestion des erreurs."""
    try:
        print("⚡ Sélection de 96 produits par page...", flush=True)
        select_container = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".size-select .ng-select-container"))
        )
        select_container.click()
        options = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".size-select div.ng-option"))
        )
        for opt in options:
            if "96 par page" in opt.text:
                opt.click()
                print("✅ Option '96 par page' sélectionnée.")
                break
    except Exception as e:
        print(f"⚠️ Sélection 96 produits échouée : {e}", flush=True)


def scroll_page(driver, max_scrolls=15, wait_time=1):
    """📜 Scroll dynamique avec chargement incrémental."""
    print("🔄 Scroll pour chargement des produits...", flush=True)
    last_height = 0
    for i in range(max_scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        new_height = driver.execute_script("return document.body.scrollHeight")
        produits_visibles = driver.find_elements(By.CSS_SELECTOR, 'a.product-card-link')
        print(f"📈 Scroll {i + 1} - Produits visibles : {len(produits_visibles)}", flush=True)
        if new_height == last_height:
            break
        last_height = new_height


def extraire_details_produit(driver, url, timeout_sec=3):
    """🔍 Extraction des données produit avec vérification préalable dans la DB."""
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(url)

        WebDriverWait(driver, timeout_sec).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        prix_entier = WebDriverWait(driver, timeout_sec).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.price-unit'))
        ).text.strip()

        centimes = driver.find_element(By.CSS_SELECTOR, 'span.price-cents').text.strip().replace(",", ".")
        prix = f"{prix_entier}{centimes} €"
        print(f"💶 Prix trouvé : {prix} pour {url}")

        ean = re.search(r'\b\d{13}\b', driver.page_source)
        ean_code = ean.group(0) if ean else "Non disponible"

        # 🔍 Vérifier si l'EAN est déjà en DB AVANT de continuer
        if ean_existe_deja(ean_code):
            print(f"⏭ Produit {ean_code} déjà en base, on passe au suivant.")
            return None  # On ignore ce produit

        # 🌐 Enrichissement SellerAmp
        start_time = time.time()
        prix_amazon, roi, profit, sales_estimation, alerts = get_selleramp_data(
            ean_code, float(prix.replace("€", "").strip())
        )

        # ⏱️ Timeout
        if (time.time() - start_time) > 5 and not (prix_amazon and roi and profit):
            print(f"⚡ Timeout > 5s. Produit {ean_code} ignoré.")
            return None

        if prix_amazon and roi and profit:
            insert_or_update_product(
                driver.title, ean_code, float(prix.replace("€", "").strip()), url, prix_amazon, roi, profit, sales_estimation, alerts
            )
            print(f"💾 Produit enrichi : {driver.title} | EAN: {ean_code}")
            return {
                'Nom': driver.title,
                'Prix': prix,
                'EAN': ean_code,
                'URL': url,
                'Prix_Amazon': prix_amazon,
                'ROI': roi,
                'Profit': profit,
                'Sales_Estimation': sales_estimation,
                'Alerts': alerts
            }

        return None

    finally:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])





def enregistrer_produit(produit):
    """💾 Enregistre le produit si non existant en DB."""
    if produit and produit['EAN']:
        insert_or_update_product(
            produit['Nom'],
            produit['EAN'],
            float(produit['Prix'].replace("€", "").strip()),
            produit['URL']
        )
        print(f"💾 [SCRAPER] Produit traité pour la DB : {produit['Nom']} | EAN: {produit['EAN']}")
    else:
        print(f"🔄 Produit {produit.get('Nom', 'Inconnu')} existant ou EAN manquant.")




def get_selleramp_data(ean, prix_magasin, max_retries=2):
    """🔍 Récupère les données SellerAmp enrichies : ROI, profit, sales_estimation, alerts."""
    from selenium.webdriver.common.keys import Keys
    driver_selleramp = None
    for attempt in range(max_retries):
        try:
            print(f"⚡ Tentative {attempt + 1}/{max_retries} pour EAN {ean}...")
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

            # ✅ Détection choix multiples ou EAN introuvable
            if driver_selleramp.find_elements(By.XPATH, "//*[contains(text(), 'Please choose the most suitable match:')]"):
                print(f"⚠️ Choix multiple détecté pour EAN {ean}. Produit ignoré.")
                return None, None, None, None, None

            if driver_selleramp.find_elements(By.XPATH, "//*[contains(text(), 'No results were found')]"):
                print(f"⚠️ Aucun résultat SellerAmp pour EAN {ean}. Produit ignoré.")
                return None, None, None, None, None

            # ✅ Récupération des données
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

            # ✅ Récupération sales_estimation et alerts
            sales_estimation = driver_selleramp.find_element(By.CSS_SELECTOR, '.estimated_sales_per_mo').text
            alerts = driver_selleramp.find_element(By.CSS_SELECTOR, '#qi-alerts .qi-alert-not').text

            print(f"🔄 Données SellerAmp récupérées : {prix_amazon}€, ROI: {roi}, Profit: {profit}€, Sales: {sales_estimation}, Alerts: {alerts}")
            return prix_amazon, roi, profit, sales_estimation, alerts

        except Exception as e:
            print(f"⚠️ Erreur SellerAmp EAN {ean}: {e}")
            time.sleep(2)
        finally:
            if driver_selleramp:
                driver_selleramp.quit()

    return None, None, None, None, None


def cliquer_suivant(driver, page_actuelle, eans_page_precedente):
    try:
        bouton_suivant = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[aria-label=" page"]'))
        )
        bouton_suivant.click()
        print(f"➡️ Passage à la page {page_actuelle + 1}...")

        # Attente jusqu'à ce que les EANs changent, preuve que la page a bien été chargée
        WebDriverWait(driver, 10).until(
            lambda d: set(recuperer_eans(d)) != eans_page_precedente
        )
        return True
    except Exception as e:
        print(f"⚠️ Erreur lors du changement de page : {e}")
        return False



def ean_existe_deja(ean):
    """🔍 Vérifie si un produit avec cet EAN existe déjà dans la base de données."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products WHERE ean = %s", (ean,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] > 0  # Renvoie True si l'EAN existe déjà
    except Exception as e:
        print(f"⚠️ Erreur lors de la vérification de l'EAN {ean} : {e}")
        return False


def scrap_toutes_pages(driver, nb_max_total):
    produits_scrapes = []
    page_actuelle = 1
    eans_page_precedente = set()  # Pour vérifier si la page a bien changé

    while len(produits_scrapes) < nb_max_total:
        print(f"\n📄 Scraping - Page {page_actuelle} ({len(produits_scrapes)}/{nb_max_total})")

        # Scraper les produits sur la page actuelle
        produits_page, eans_page_courante = scrap_produits_sur_page(driver, nb_max_total - len(produits_scrapes))
        produits_scrapes.extend(produits_page)

        print(f"✅ {len(produits_scrapes)} produit(s) récupéré(s) sur {nb_max_total}.")

        # Si l'objectif est atteint, on arrête
        if len(produits_scrapes) >= nb_max_total:
            print("🎯 Objectif de scraping atteint.")
            break

        # Essayer de passer à la page suivante
        if cliquer_suivant(driver, page_actuelle, eans_page_precedente):
            page_actuelle += 1
            eans_page_precedente = eans_page_courante.copy()  # MAJ des EANs pour la vérification sur la prochaine page
        else:
            print("⚠️ Plus de pages disponibles ou navigation échouée.")
            break

    return produits_scrapes



def scrap_produits_sur_page(driver, nb_max, urls_deja_traitees):
    """🔎 Scrape les produits de la page en cours sans doublons jusqu'au quota demandé."""
    produits = []
    scroll_page(driver, max_scrolls=15, wait_time=1)
    produits_urls = [
        a.get_attribute('href') for a in driver.find_elements(By.CSS_SELECTOR, 'a.product-card-link')
        if a.get_attribute('href') not in urls_deja_traitees
    ]

    print(f"🔍 {len(produits_urls)} produits trouvés sur cette page.")

    for url in produits_urls:
        if len(produits) >= nb_max:
            break
        try:
            produit = extraire_details_produit(driver, url, timeout_sec=3)
            if produit:
                produits.append(produit)
                urls_deja_traitees.add(url)
                print(f"✅ [SCRAPER] Produit {produit['Nom']} enrichi et sauvegardé.")
        except Exception as e:
            print(f"⚠️ Produit ignoré suite à une erreur : {e}", flush=True)

    return produits





def lancer_scraping(url, nb_scrap_total):
    """🚀 Lancement principal du scraping sans JSON."""
    try:
        print(f"🚀 [SCRAPER] Scraping pour : {url}")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        produits_scrapes = []
        produits_scrapes = scrap_toutes_pages(driver, nb_scrap_total)
        print(f"🎉 FIN : {len(produits_scrapes)} produits enrichis et insérés en DB.")
        return produits_scrapes
    finally:
        driver.quit()


if __name__ == "__main__":
    url = sys.argv[1]
    nb_scrap = int(sys.argv[2])
    produits_scrapes = lancer_scraping(url, nb_scrap)
    print(f"🎉 Scraping terminé. Total : {len(produits_scrapes)} produit(s) enrichi(s).")