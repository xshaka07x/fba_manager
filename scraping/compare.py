# compare.py

import psutil
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from concurrent.futures import ThreadPoolExecutor

import logging
import pandas as pd
import json
import os
import re
import sys
import time
import subprocess
import logging
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from webdriver_manager.chrome import ChromeDriverManager
from random import randint


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.utils.db import get_db_connection  # 📡 Connexion DB Railway

# 📝 CONFIGURATION LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("compare.log"), logging.StreamHandler()]
)


# 🔀 Ports dynamiques
def get_dynamic_port():
    """🔀 Retourne un port aléatoire pour éviter les conflits."""
    return str(randint(9000, 9999))


def kill_browser_processes():
    for proc in psutil.process_iter():
        if proc.name().lower() in ['chromedriver.exe']:
            try:
                proc.kill()
                logging.info(f"✅ Processus {proc.name()} arrêté.")
            except psutil.NoSuchProcess:
                pass



def create_driver():
    chrome_options = Options()

    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--remote-debugging-port=" + get_dynamic_port())
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
    chrome_options.add_argument("--disable-features=TensorFlowLite")
    chrome_options.add_argument("--disable-blink-features=TensorFlowLite")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")




    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )




def generate_html_report(data, output_path):
    """📄 Génère un rapport HTML à partir de données JSON."""
    html_content = f"""
    <html>
    <head><title>Rapport SellerAmp</title></head>
    <body>
    <h1>Rapport des Produits</h1>
    <table border="1">
        <tr>
            <th>Nom</th><th>EAN</th><th>Prix Magasin</th><th>Prix Amazon</th><th>ROI</th><th>Profit</th>
        </tr>
    """
    for produit in data:
        html_content += f"""
        <tr>
            <td>{produit.get('Nom')}</td>
            <td>{produit.get('EAN')}</td>
            <td>{produit.get('Prix')}</td>
            <td>{produit.get('Prix_Amazon', 'N/A')}</td>
            <td>{produit.get('ROI', 'N/A')}</td>
            <td>{produit.get('Profit', 'N/A')}</td>
        </tr>
        """
    html_content += "</table></body></html>"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    logging.info(f"📁 Rapport HTML généré avec succès : {output_path}")


def detecter_choix_multiples(driver):
    """🛑 Détecte plusieurs choix SellerAmp pour un EAN donné."""
    return bool(driver.find_elements(By.XPATH, "//*[contains(text(), 'choose the most suitable match')]"))


def detecter_aucun_resultat(driver, ean):
    """❌ Détecte l'absence de résultats pour un EAN donné."""
    return bool(driver.find_elements(By.XPATH, f"//*[contains(text(), 'No results were found for the term \"{ean}\"')]"))


def update_selleramp_data(ean, prix_amazon, roi, profit):
    """🔧 Met à jour prix_amazon, ROI et profit pour tous les produits avec le même EAN."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE products
            SET prix_amazon = %s, roi = %s, profit = %s
            WHERE ean = %s
        """, (prix_amazon, roi, profit, ean))

        logging.info(f"✅ Données SellerAmp mises à jour pour EAN {ean}.")
        print(f"🔄 [COMPARE] SellerAmp mis à jour : EAN: {ean} | Prix Amazon: {prix_amazon}€ | ROI: {roi} | Profit: {profit}€")


        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"❌ Erreur update SellerAmp pour EAN {ean}: {e}")


def get_selleramp_data(ean, prix_magasin, max_retries=2):
    """🔍 Récupération avancée des données SellerAmp et mise à jour DB Railway."""
    driver = None  # ✅ Initialisation pour éviter UnboundLocalError
    for attempt in range(max_retries):
        try:
            logging.info(f"⚡ Tentative {attempt + 1}/{max_retries} pour EAN {ean}...")
            driver = create_driver()  # 🚀 Création driver Selenium
            driver.get('https://sas.selleramp.com/')

            # 💡 Connexion SellerAmp
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "loginform-email")))
            driver.find_element(By.ID, "loginform-email").send_keys("thomasroger1189@gmail.com")
            driver.find_element(By.ID, "loginform-password").send_keys("Gintoki62")  # 🔐 À sécuriser
            driver.find_element(By.NAME, "login-button").click()

            # 🔍 Recherche EAN
            WebDriverWait(driver, 45).until(EC.presence_of_element_located((By.ID, 'saslookup-search_term')))
            driver.find_element(By.ID, 'saslookup-search_term').send_keys(ean + Keys.RETURN)
            time.sleep(5)

            # 🛑 Gestion des cas particuliers
            if detecter_choix_multiples(driver):
                logging.warning(f"⚠️ Choix multiples pour EAN {ean}, sélection du premier résultat.")
                choix = driver.find_elements(By.CSS_SELECTOR, "div.match-item")
                if choix:
                    try:
                        choix[0].click()
                        WebDriverWait(driver, 10).until(lambda d: d.execute_script("return document.readyState") == "complete")
                        time.sleep(2)
                    except Exception as e:
                        logging.error(f"❌ Sélection du premier résultat échouée : {e}")
                        return "Choix multiples", "Choix multiples", "Choix multiples"
                else:
                    logging.warning(f"⚠️ Aucun élément cliquable pour EAN {ean}.")
                    return "Choix multiples", "Choix multiples", "Choix multiples"




            if detecter_aucun_resultat(driver, ean):
                logging.warning(f"⚠️ Aucun résultat pour EAN {ean}.")
                return "Aucun résultat", "Aucun résultat", "Aucun résultat"

            # 📊 Récupération des données SellerAmp
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, 'qi_sale_price')))
            prix_amazon = driver.find_element(By.ID, 'qi_sale_price').get_attribute('value')

            cost_input = driver.find_element(By.ID, 'qi_cost')
            cost_input.clear()
            cost_input.send_keys(str(prix_magasin))
            cost_input.send_keys(Keys.RETURN)

            WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, 'qi-roi').text != '- ∞%')
            roi = driver.find_element(By.ID, 'qi-roi').text
            profit = driver.find_element(By.ID, 'qi-profit').text

            # 🔗 Mise à jour immédiate dans la DB Railway
            update_selleramp_data(ean, prix_amazon, roi, profit)
            return prix_amazon, roi, profit

        except Exception as e:
            logging.warning(f"⚠️ Erreur pour EAN {ean}: {e}")
            time.sleep(3)
        finally:
            if driver:
                driver.quit()
                kill_browser_processes()



    # 🔙 Valeurs par défaut si tout échoue
    return "Non disponible", "Non disponible", "Non disponible"


def process_produit(produit):
    """🔄 Traite un produit unique avec détection avancée des erreurs."""
    ean = produit.get('EAN')
    prix_str = re.sub(r'[^\d.,]', '', produit.get('Prix', "0")).replace(",", ".")
    prix_magasin = float(prix_str) if prix_str else 0.0
    if ean and prix_magasin > 0:
        prix_amazon, roi, profit = get_selleramp_data(ean, prix_magasin)
        if roi not in ["Non disponible", "Choix multiples", "Aucun résultat"]:
            produit.update({'Prix_Amazon': prix_amazon, 'ROI': roi, 'Profit': profit})
            return produit
    return None


def enrichir_avec_selleramp(fichier_produits, dossier_export):
    """💡 Enrichit les données avec SellerAmp et génère un rapport HTML."""
    with open(fichier_produits, 'r', encoding='utf-8') as f:
        produits = json.load(f)

    produits_valides, produits_ignores = [], []

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(lambda p: produits_valides.append(p) if process_produit(p) else produits_ignores.append(p), produits))

    with open(fichier_produits, 'w', encoding='utf-8') as f:
        json.dump(produits_valides, f, ensure_ascii=False, indent=4)

    fichier_ignores = os.path.join(dossier_export, 'produits_ignores.json')
    with open(fichier_ignores, 'w', encoding='utf-8') as f:
        json.dump(produits_ignores, f, ensure_ascii=False, indent=4)

    rapport_html = os.path.join(dossier_export, 'rapport_selleramp.html')
    generate_html_report(produits_valides, rapport_html)
    logging.info(f"🎯 Analyse : {len(produits_valides)} valides | {len(produits_ignores)} ignorés.")



if __name__ == "__main__":
    fichier_json = sys.argv[1]
    dossier_export = sys.argv[2]
    enrichir_avec_selleramp(fichier_json, dossier_export)
