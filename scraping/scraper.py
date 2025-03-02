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
sys.stderr = open(os.devnull, "w")  # Cache les erreurs dans un "trou noir"
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

import signal
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
import tkinter as tk
from tkinter import messagebox
import threading


# 🔗 Initialisation Flask
app = create_app()
with app.app_context():
    db.create_all()

# ⚙️ Configuration Selenium
options = Options()

# 🛑 Désactiver WebRTC et WebSockets
options.add_argument("--disable-webrtc")
options.add_argument("--disable-features=WebRtcHideLocalIpsWithMdns")
options.add_argument("--force-webrtc-ip-handling-policy=default_public_interface_only")
options.add_argument("--disable-ipv6")
options.add_argument("--disable-web-security")
options.add_argument("--disable-background-networking")

# 🚀 Désactiver le GPU et WebGL
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-features=VizDisplayCompositor")
options.add_argument("--disable-accelerated-2d-canvas")
options.add_argument("--disable-accelerated-video-decode")
options.add_argument("--disable-accelerated-mjpeg-decode")
options.add_argument("--disable-accelerated-video")
options.add_argument("--disable-gl-drawing-for-tests")
options.add_argument("--disable-webgl")  # Désactive WebGL

# 🔇 Suppression des logs inutiles
options.add_experimental_option("excludeSwitches", ["enable-logging", "enable-automation", "ignore-certificate-errors"])
options.add_experimental_option("useAutomationExtension", False)

# 🕶️ Mode headless pour éviter les erreurs graphiques
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

# 🎯 Suppression des logs système
os.environ["WTF_CSRF_ENABLED"] = "False"
os.environ["PYTHONWARNINGS"] = "ignore"
sys.stderr = open(os.devnull, "w")  # Supprime les erreurs
#sys.stdout = open(os.devnull, "w")  # Supprime les logs visibles


def signal_handler(sig, frame):
    print("\n🛑 Arrêt du script demandé. Fermeture propre de Selenium...")
    try:
        driver.quit()  # Fermer Selenium proprement
    except NameError:
        pass  # Si driver n'existe pas encore, on ignore
    sys.exit(0)  # Quitte proprement le programme

# Capture du signal Ctrl+C
signal.signal(signal.SIGINT, signal_handler)


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


def extraire_details_produit(driver, url, timeout_sec=5):
    """🔍 Extraction des données produit (nom, prix, EAN, URL)."""
    try:
        # 🌍 Ouvre le produit dans un nouvel onglet
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(url)

        # ⏳ Attente que la page charge
        WebDriverWait(driver, timeout_sec).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

        # 💶 Extraction du prix (CSS puis fallback JS)
        try:
            prix_element = WebDriverWait(driver, timeout_sec).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "div.content-price-zento span.price-value"))
            )
            prix = prix_element.text.strip().replace("\xa0€", "€")
        except TimeoutException:
            prix = driver.execute_script(
                "return document.querySelector('span.price-value') ? document.querySelector('span.price-value').textContent.trim() : 'Non disponible';"
            )

        # 🔍 Extraction de l'EAN depuis le HTML
        try:
            ean_match = re.search(r'"ean13"\s*:\s*"(\d{13})"', driver.page_source)
            ean_code = ean_match.group(1) if ean_match else "Non disponible"
        except Exception:
            ean_code = "Non disponible"

        print(f"✅ Produit récupéré : {driver.title} | Prix : {prix} | EAN : {ean_code}")

        return {
            'Nom': driver.title,
            'Prix': prix,
            'EAN': ean_code,
            'URL': url
        }

    except Exception:
        print(f"❌ Erreur sur {url}, produit ignoré.")
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




def get_selleramp_data(ean, prix_magasin, max_retries=1):
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

            # 🚨 FILTRES 🚨
            if alerts == "PL":
                print(f"⚠️ Produit ignoré (Private Label - PL) | EAN: {ean}")
                return None, None, None, None, None

            if sales_estimation.lower() == "unknown":
                print(f"⚠️ Produit ignoré (Sales Estimation inconnu) | EAN: {ean}")
                return None, None, None, None, None

            # 💰 Convertir ROI en float pour appliquer le filtre
            try:
                roi_clean = re.sub(r'[^\d\.-]', '', roi)  # Supprime tout sauf chiffres, points et tirets
                roi_value = float(roi_clean) if roi_clean else None
            except Exception as e:
                print(f"⚠️ Erreur conversion ROI : {roi} -> {e}")
                roi_value = None

            if roi_value is None or roi_value <= 10:
                print(f"⚠️ Produit ignoré (ROI trop bas : {roi_value}%) | EAN: {ean}")
                return None, None, None, None, None

            print(f"🔄 Données SellerAmp récupérées : {prix_amazon}€, ROI: {roi_value}%, Profit: {profit}€, Sales: {sales_estimation}, Alerts: {alerts}")
            return prix_amazon, roi, profit, sales_estimation, alerts

        except Exception as e:
            print(f"⚠️ Erreur SellerAmp EAN {ean}: {e}")
            time.sleep(2)
        finally:
            if driver_selleramp:
                driver_selleramp.quit()

    return None, None, None, None, None



def scrap_toutes_pages(driver, nb_max_total, url_base):
    produits_scrapes = []
    page_actuelle = 1
    urls_deja_traitees = set()

    while len(produits_scrapes) < nb_max_total:
        # ✅ Construire proprement l'URL de la page actuelle
        if "pageNumber-3=" in url_base:
            url_pagination = re.sub(r'pageNumber-3=\d+', f'pageNumber-3={page_actuelle}', url_base)
        else:
            url_pagination = url_base + f"&pageNumber-3={page_actuelle}" if "?" in url_base else url_base + f"?pageNumber-3={page_actuelle}"

        print(f"\n📄 Scraping - Page {page_actuelle} ({len(produits_scrapes)}/{nb_max_total}) - {url_pagination}")

        driver.get(url_pagination)
        time.sleep(3)  # Attente pour chargement complet

        # ✅ Vérifier si la page a bien chargé en détectant les produits
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-sx-zento a.format-img-zento'))
            )
        except TimeoutException:
            print(f"⛔ Aucune donnée détectée sur la page {page_actuelle}. Arrêt du scraping.")
            break

        # ✅ Scraper les produits de la page
        produits_page, eans_page_courante, urls_deja_traitees = scrap_produits_sur_page(
            driver, nb_max_total - len(produits_scrapes), urls_deja_traitees
        )

        produits_scrapes.extend(produits_page)

        print(f"✅ {len(produits_scrapes)} produit(s) récupéré(s) sur {nb_max_total}.")

        # ✅ Vérification avant de passer à la page suivante
        if not produits_page:
            print("⚠️ Aucun produit enregistré sur cette page, tentative de la suivante...")
        
        page_actuelle += 1  # 📌 Passage automatique à la page suivante

    print("🎉 Fin du scraping.")
    return produits_scrapes






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


def scrap_produits_sur_page(driver, nb_max, urls_deja_traitees):
    """🔎 Scrape les produits de la page en cours, enrichit avec SellerAmp et insère en DB si valide."""
    produits = []
    scroll_page(driver, max_scrolls=15, wait_time=1)
    produits_urls = [
        a.get_attribute('href') for a in driver.find_elements(By.CSS_SELECTOR, 'div.col-sx-zento a.format-img-zento')
    ]

    print(f"🔍 {len(produits_urls)} produits trouvés sur cette page.")

    total_produits = len(produits_urls)
    produits_traite = 0

    for url in produits_urls:
        if len(produits) >= nb_max:
            break
        try:
            # 🔍 Étape 1 : Extraction produit
            produit = extraire_details_produit(driver, url, timeout_sec=3)
            produits_traite += 1  
            
            if not produit or produit['EAN'] == "Non disponible":
                print(f"⚠️ Produit ignoré (EAN manquant) : {url}")
                continue

            nom, prix_retail, ean, url_produit = produit['Nom'], produit['Prix'], produit['EAN'], produit['URL']
            
            try:
                # Nettoyage : Suppression des espaces insécables, "€", "HT" et remplacement de la virgule
                prix_retail = re.sub(r'[^\d,]', '', prix_retail)  # Supprime tout sauf chiffres et virgule
                prix_retail = prix_retail.replace(",", ".")  # Convertit en notation décimale anglaise
                prix_retail = float(prix_retail)  # Conversion en float
            except ValueError:
                print(f"⚠️ Produit ignoré (Prix non valide) : {url}")
                continue


            print(f"🔍 Produit trouvé : {nom} | Prix magasin : {prix_retail}€ | EAN : {ean}")

            # 🔎 Étape 2 : Récupération SellerAmp
            prix_amazon, roi, profit, sales_estimation, alerts = get_selleramp_data(ean, prix_retail)

            if not prix_amazon or not roi or not profit or not sales_estimation:
                print(f"⚠️ Produit ignoré (Données SellerAmp incomplètes) : {url}")
                continue

            # 🚨 Étape 3 : Vérification des critères (ROI min 10%)
            try:
                roi_value = float(re.sub(r'[^\d\.-]', '', roi))
            except ValueError:
                roi_value = 0

            if roi_value < 10:
                print(f"⚠️ Produit ignoré (ROI trop bas : {roi_value}%) | {nom}")
                continue

            # ✅ Étape 4 : Insertion en base de données
            insert_or_update_product(nom, ean, prix_retail, url_produit, prix_amazon, roi, profit, sales_estimation, alerts)
            print(f"✅ Produit ajouté en DB : {nom} | Prix : {prix_retail}€ | ROI : {roi_value}%")

            produits.append(produit)
            urls_deja_traitees.add(url)

            print(f"📊 Progression : {len(produits)} enregistré(s) / {nb_max} demandé(s) "
                  f"({produits_traite}/{total_produits} traités sur cette page)")

        except Exception as e:
            print(f"⚠️ Produit ignoré suite à une erreur : {e}", flush=True)

    eans_page_courante = {p['EAN'] for p in produits if 'EAN' in p}
    return produits, eans_page_courante, urls_deja_traitees



def lancer_scraping(url, nb_scrap_total):
    """🚀 Lancement principal du scraping avec pagination par URL."""
    try:
        print(f"🚀 [SCRAPER] Scraping pour : {url}")

        # Extraire l'URL de base sans ?page=
        url_base = re.sub(r'\?page=\d+', '', url)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url_base)

        produits_scrapes = scrap_toutes_pages(driver, nb_scrap_total, url_base)
        print(f"🎉 FIN : {len(produits_scrapes)} produits enrichis et insérés en DB.")
        return produits_scrapes

    finally:
        driver.quit()



if __name__ == "__main__":
    url = sys.argv[1]
    nb_scrap = int(sys.argv[2])
    produits_scrapes = lancer_scraping(url, nb_scrap)
    print(f"🎉 Scraping terminé. Total : {len(produits_scrapes)} produit(s) enrichi(s).")