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
import signal
import time
import re
import logging
import pytz
import requests
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

sys.stderr = open(os.devnull, "w")  # Cache les erreurs dans un "trou noir"
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

from app import db
from app.models import ProductKeepa
from app.utils.fetch_keepa import get_asin_from_ean, get_keepa_data

# Import du nouveau module Keepa
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY", "ftclrhsi754hf3tblbljldbonk7n4cuthggk8gnt88c4k2sjkmre8th8cjf65jnc")
KEEPA_URL = "https://api.keepa.com/product"

if not KEEPA_API_KEY:
    raise ValueError("❌ ERREUR: La clé Keepa API n'est pas définie. Configure 'KEEPA_API_KEY' dans vos variables d'environnement.")

# En haut du fichier, après les imports
logging.getLogger('selenium').setLevel(logging.CRITICAL)
os.environ['WDM_LOG_LEVEL'] = '0'

# ⚙️ Configuration Selenium
options = Options()

# Suppression des logs
options.add_argument('--log-level=3')
options.add_experimental_option('excludeSwitches', ['enable-logging'])

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
options.add_argument("--window-size=1920,1080")  # Taille de fenêtre fixe
options.add_argument("--start-maximized")  # Maximiser la fenêtre
options.add_argument("--disable-blink-features=AutomationControlled")  # Désactiver la détection d'automatisation

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


def get_db_connection():
    """📝 Retourne une connexion à la base de données."""
    return db.session

def insert_or_update_product(nom, ean, prix_retail, url, prix_amazon, difference, profit, sales_estimation):
    """📝 Insère ou met à jour un produit avec les données Keepa en DB."""
    try:
        if not ean or ean == "Non disponible":
            return False

        if profit is not None and profit <= 0:
            return False

        # Calcul du ROI
        roi = (profit * 100 / prix_retail) if prix_retail > 0 else 0

        # Vérification du ROI maximal
        if roi > 800:
            print(f"⚠️ Produit ignoré (ROI anormalement élevé : {roi}%) | {nom}")
            return False

        paris_timezone = pytz.timezone("Europe/Paris")
        updated_at = datetime.now(paris_timezone)

        # Utilisation de SQLAlchemy au lieu de SQL brut
        existing_product = ProductKeepa.query.filter_by(ean=ean, url=url).first()

        if existing_product:
            existing_product.nom = nom
            existing_product.prix_retail = prix_retail
            existing_product.prix_amazon = prix_amazon
            existing_product.difference = difference
            existing_product.profit = profit
            existing_product.roi = roi
            existing_product.sales_estimation = sales_estimation
            existing_product.updated_at = updated_at
        else:
            new_product = ProductKeepa(
                nom=nom,
                ean=ean,
                prix_retail=prix_retail,
                prix_amazon=prix_amazon,
                difference=difference,
                profit=profit,
                roi=roi,
                url=url,
                sales_estimation=sales_estimation,
                updated_at=updated_at
            )
            db.session.add(new_product)

        db.session.commit()
        return True

    except Exception as e:
        print(f"Erreur lors de l'insertion/mise à jour du produit : {str(e)}")
        db.session.rollback()
        return False


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
    """📜 Scroll dynamique avec chargement incrémental et vérification des produits."""
    print("🔄 Scroll pour chargement des produits...", flush=True)
    last_height = 0
    no_change_count = 0
    max_no_change = 3  # Nombre maximum de scrolls sans changement avant d'arrêter

    for i in range(max_scrolls):
        # Scroll vers le bas
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)

        # Vérification de la hauteur
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            no_change_count += 1
            print(f"⚠️ Scroll {i + 1} - Aucun changement de hauteur ({no_change_count}/{max_no_change})", flush=True)
        else:
            no_change_count = 0
            print(f"✅ Scroll {i + 1} - Nouvelle hauteur: {new_height}", flush=True)

        # Vérification des produits
        produits_visibles = driver.find_elements(By.CSS_SELECTOR, 'div.col-sx-zento a.format-img-zento')
        print(f"📈 Scroll {i + 1} - Produits visibles : {len(produits_visibles)}", flush=True)

        # Si on a des produits et qu'on n'a pas eu de changement depuis un moment, on arrête
        if len(produits_visibles) > 0 and no_change_count >= max_no_change:
            print("✅ Chargement des produits terminé", flush=True)
            break

        last_height = new_height

    # Vérification finale
    produits_finaux = driver.find_elements(By.CSS_SELECTOR, 'div.col-sx-zento a.format-img-zento')
    print(f"🎯 Total des produits chargés : {len(produits_finaux)}", flush=True)

# La fonction get_keepa_data est importée depuis app.utils.fetch_keepa
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
            nom=produit['Nom'],
            ean=produit['EAN'],
            prix_retail=float(produit['Prix'].replace("€", "").strip()),
            url=produit['URL'],
            prix_amazon=0,  # Valeur par défaut
            difference=0,  # Valeur par défaut
            profit=0,  # Valeur par défaut
            sales_estimation=0  # Valeur par défaut
        )
        print(f"💾 [SCRAPER] Produit traité pour la DB : {produit['Nom']} | EAN: {produit['EAN']}")
    else:
        print(f"🔄 Produit {produit.get('Nom', 'Inconnu')} existant ou EAN manquant.")






def scrap_toutes_pages(url_base, nb_produits):
    """🔄 Scrape toutes les pages jusqu'à obtenir le nombre de produits souhaité."""
    produits = []
    eans = []
    urls_traitees = set()
    page = 1
    produits_valides = 0

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        while produits_valides < nb_produits:
            driver.get(f"{url_base}?pageNumber-3={page}")
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-sx-zento'))
                )
            except TimeoutException:
                break

            nouveaux_produits, nouveaux_eans, urls_traitees = scrap_produits_sur_page(driver, nb_produits - produits_valides, urls_traitees)
            
            produits.extend(nouveaux_produits)
            eans.extend(nouveaux_eans)
            produits_valides = sum(1 for p in produits if p.get('profit', 0) > 0)
            
            if produits_valides >= nb_produits:
                break
            
            print(f"Page {page} terminée, analyse de la page {page + 1}")
            page += 1

        return produits

    except Exception:
        return []
    finally:
        try:
            driver.quit()
        except:
            pass



def ean_existe_deja(ean):
    """🔍 Vérifie si un produit avec cet EAN existe déjà dans la base de données."""
    try:
        count = db.session.query(ProductKeepa).filter_by(ean=ean).count()
        return count > 0
    except Exception as e:
        print(f"⚠️ Erreur lors de la vérification de l'EAN {ean} : {e}")
        return False



def scrap_produits_sur_page(driver, nb_max_produits, urls_deja_traitees):
    """🔍 Scrape les produits sur la page courante."""
    produits = []
    eans_page_courante = []
    produits_valides = 0

    try:
        elements_produits = driver.find_elements(By.CSS_SELECTOR, 'div.col-sx-zento')
        
        for element in elements_produits:
            if produits_valides >= nb_max_produits:
                return produits, eans_page_courante, urls_deja_traitees

            try:
                lien_produit = element.find_element(By.CSS_SELECTOR, 'a.format-img-zento').get_attribute('href')
                if lien_produit in urls_deja_traitees:
                    continue

                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(lien_produit)
                
                try:
                    nom_element = driver.find_element(By.CSS_SELECTOR, 'div.template-grid-whilist h1.green-text')
                    nom_produit = nom_element.text.strip()
                    
                    prix_element = driver.find_element(By.CSS_SELECTOR, 'li.price.price-with-taxes.content-price-detail-zento span.price-value')
                    prix_text = prix_element.text.strip().replace('€', '').replace(',', '.').strip()
                    prix_retail = float(prix_text)
                    
                    product_element = driver.find_element(By.CSS_SELECTOR, '[data-product]')
                    product_data = product_element.get_attribute('data-product')
                    product_json = json.loads(product_data)
                    ean = product_json.get('stock', {}).get('ean13')
                    
                    print(f"Analyse du produit {ean} - {nom_produit}")

                    if not ean:
                        print("❌ Non conforme. Produit suivant. (EAN manquant)")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        continue
                        
                    if ean_existe_deja(ean):
                        print("🔄 Produit déjà scanné précédemment.")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        continue

                    keepa_data = get_keepa_data(ean, prix_retail)
                    
                    if keepa_data and keepa_data.get('status') == 'OK':
                        prix_amazon = keepa_data.get('prix_amazon')
                        difference = keepa_data.get('difference')
                        profit = keepa_data.get('profit')
                        sales_estimation = keepa_data.get('sales_estimation', 0)
                        is_pl = keepa_data.get('is_pl', False)
                        
                        # Ignorer les Private Labels
                        if is_pl:
                            print(f"❌ Produit ignoré car Private Label: {nom_produit}")
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            continue

                        # Ignorer les produits avec peu de ventes
                        if sales_estimation <= 1:
                            print(f"❌ Produit ignoré car peu de ventes ({sales_estimation}): {nom_produit}")
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            continue
                        
                        if all([prix_amazon, difference, profit]):
                            produit = {
                                'nom': nom_produit,
                                'ean': ean,
                                'prix_retail': prix_retail,
                                'prix_amazon': prix_amazon,
                                'difference': difference,
                                'profit': profit,
                                'url': lien_produit,
                                'sales_estimation': sales_estimation
                            }
                            
                            if insert_or_update_product(
                                nom=nom_produit,
                                ean=ean,
                                prix_retail=prix_retail,
                                url=lien_produit,
                                prix_amazon=prix_amazon,
                                difference=difference,
                                profit=profit,
                                sales_estimation=sales_estimation
                            ):
                                print(f"✅ Produit ajouté - Ventes estimées: {sales_estimation}")
                                produits.append(produit)
                                eans_page_courante.append(ean)
                                urls_deja_traitees.add(lien_produit)
                                produits_valides += 1
                        else:
                            print("❌ Non conforme. Produit suivant. (Données Amazon incomplètes)")
                    else:
                        print("❌ Non conforme. Produit suivant. (ASIN non trouvé)")
                        
                except Exception:
                    print("❌ Non conforme. Produit suivant. (Erreur extraction données)")
                
                driver.close()
                driver.switch_to.window(driver.window_handles[0])

            except Exception:
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                continue
        
        return produits, eans_page_courante, urls_deja_traitees
        
    except Exception:
        return [], [], urls_deja_traitees



def lancer_scraping(url, nb_scrap_total):
    """🚀 Lancement principal du scraping avec pagination par URL."""
    driver = None
    try:
        print(f"Demarrage du scrap sur {url} pour {nb_scrap_total} produits.")
        url_base = re.sub(r'\?page=\d+', '', url)
        
        try:
            response = requests.get(url_base, timeout=10)
            if response.status_code != 200:
                return []
        except Exception:
            return []

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url_base)
        time.sleep(5)

        produits_scrapes = scrap_toutes_pages(url_base, nb_scrap_total)
        print(f"{len(produits_scrapes)} produits analysés. Analyse terminée.")
        return produits_scrapes

    except Exception:
        return []
    finally:
        if driver:
            driver.quit()



if __name__ == "__main__":
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            url = sys.argv[1]
            nb_scrap = int(sys.argv[2])
            lancer_scraping(url, nb_scrap)
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du script : {str(e)}")