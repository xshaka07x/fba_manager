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
from app.utils.fetch_keepa import get_asin_from_ean, get_keepa_data
import requests
import json

# Import du nouveau module Keepa

KEEPA_API_KEY = os.getenv("KEEPA_API_KEY", "ftclrhsi754hf3tblbljldbonk7n4cuthggk8gnt88c4k2sjkmre8th8cjf65jnc")
KEEPA_URL = "https://api.keepa.com/product"

if not KEEPA_API_KEY:
    raise ValueError("❌ ERREUR: La clé Keepa API n'est pas définie. Configure 'KEEPA_API_KEY' dans vos variables d'environnement.")


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


def insert_or_update_product(nom, ean, prix_retail, url, prix_amazon, difference, profit):
    """📝 Insère ou met à jour un produit avec les données Keepa en DB."""
    try:
        # Vérification des critères de filtrage
        if not ean or ean == "Non disponible":
            print(f"❌ [SCRAPER] Produit ignoré - Pas d'EAN : {nom}")
            return False

        # Vérifier si le profit est positif (critère de filtrage)
        if profit is not None and profit <= 0:
            print(f"❌ [SCRAPER] Produit ignoré - Profit négatif ou nul ({profit}€) : {nom}")
            return False

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM products_keepa WHERE ean = %s AND url = %s", (ean, url))
        result = cursor.fetchone()
        paris_timezone = pytz.timezone("Europe/Paris")
        updated_at = datetime.now(paris_timezone)

        if result:
            cursor.execute("""
                UPDATE products_keepa 
                SET nom = %s, prix_retail = %s, prix_amazon = %s, difference = %s, profit = %s, updated_at = %s
                WHERE id = %s
            """, (nom, prix_retail, prix_amazon, difference, profit, updated_at, result[0]))
            print(f"🔄 [SCRAPER] Produit mis à jour : {nom} | EAN: {ean}")
        else:
            cursor.execute("""
                INSERT INTO products_keepa (nom, ean, prix_retail, prix_amazon, difference, profit, url, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (nom, ean, prix_retail, prix_amazon, difference, profit, url, updated_at))
            print(f"🆕 [SCRAPER] Produit inséré : {nom} | EAN: {ean}")

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ Erreur DB: {e}")
        import traceback
        traceback.print_exc()
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
            profit=0  # Valeur par défaut
        )
        print(f"💾 [SCRAPER] Produit traité pour la DB : {produit['Nom']} | EAN: {produit['EAN']}")
    else:
        print(f"🔄 Produit {produit.get('Nom', 'Inconnu')} existant ou EAN manquant.")






def scrap_toutes_pages(driver, nb_max_total, url_base):
    """📄 Scrape toutes les pages nécessaires pour obtenir le nombre de produits demandé."""
    produits_scrapes = []
    produits_valides = 0  # Compteur de produits valides
    page_actuelle = 1
    urls_deja_traitees = set()

    print(f"📊 Objectif : {nb_max_total} produits valides à scraper (avec EAN et ROI > 10%)")

    while produits_valides < nb_max_total:
        try:
            # ✅ Construire proprement l'URL de la page actuelle
            if "pageNumber-3=" in url_base:
                url_pagination = re.sub(r'pageNumber-3=\d+', f'pageNumber-3={page_actuelle}', url_base)
            else:
                url_pagination = url_base + f"&pageNumber-3={page_actuelle}" if "?" in url_base else url_base + f"?pageNumber-3={page_actuelle}"

            print(f"\n📄 Scraping - Page {page_actuelle} ({produits_valides}/{nb_max_total} produits valides) - {url_pagination}")

            print("🌐 Chargement de la page...")
            driver.get(url_pagination)
            print("⏳ Attente du chargement complet...")
            time.sleep(3)  # Attente pour chargement complet

            # ✅ Vérifier si la page a bien chargé en détectant les produits
            try:
                print("🔍 Vérification de la présence des produits...")
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-sx-zento a.format-img-zento'))
                )
                print("✅ Produits détectés sur la page")
            except TimeoutException:
                print(f"⛔ Aucune donnée détectée sur la page {page_actuelle}. Arrêt du scraping.")
                break

            # ✅ Scraper les produits de la page
            print("🔍 Début du scraping des produits...")
            produits_page, eans_page_courante, urls_deja_traitees = scrap_produits_sur_page(
                driver, float('inf'), urls_deja_traitees  # Utiliser inf pour traiter tous les produits
            )

            # Compter les produits valides ajoutés
            for produit in produits_page:
                try:
                    # Vérifier si le produit a été inséré avec succès
                    if insert_or_update_product(
                        nom=produit['nom'],
                        ean=produit['ean'],
                        prix_retail=produit['prix_retail'],
                        url=produit['url'],
                        prix_amazon=produit['prix_amazon'],
                        difference=produit['difference'],
                        profit=produit['profit']
                    ):
                        produits_valides += 1
                        produits_scrapes.append(produit)
                        print(f"✅ Produit valide ajouté ({produits_valides}/{nb_max_total})")
                except Exception as e:
                    print(f"❌ Erreur lors de l'insertion du produit : {str(e)}")
                    continue

            print(f"✅ {len(produits_page)} produits traités sur cette page")
            print(f"📊 Total des produits valides : {produits_valides}/{nb_max_total}")

            # ✅ Vérification avant de passer à la page suivante
            if not produits_page:
                print("⚠️ Aucun produit enregistré sur cette page, tentative de la suivante...")
            
            page_actuelle += 1  # 📌 Passage automatique à la page suivante

        except Exception as e:
            print(f"❌ Erreur lors du scraping de la page {page_actuelle}: {str(e)}")
            break

    print(f"🎉 Fin du scraping. {produits_valides} produits valides ajoutés sur {nb_max_total} demandés.")
    return produits_scrapes






def ean_existe_deja(ean):
    """🔍 Vérifie si un produit avec cet EAN existe déjà dans la base de données."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products_keepa WHERE ean = %s", (ean,))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] > 0  # Renvoie True si l'EAN existe déjà
    except Exception as e:
        print(f"⚠️ Erreur lors de la vérification de l'EAN {ean} : {e}")
        return False



def scrap_produits_sur_page(driver, nb_max_produits, urls_deja_traitees):
    """🔍 Scrape les produits sur la page courante."""
    produits = []
    eans_page_courante = []
    
    print("🔍 Recherche des produits sur la page...")
    try:
        # Vérifier si la page est chargée
        print("⏳ Attente du chargement de la page...")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        print("✅ Page chargée")
        
        # Trouver tous les produits sur la page
        elements_produits = driver.find_elements(By.CSS_SELECTOR, 'div.col-sx-zento')
        print(f"✅ {len(elements_produits)} produits trouvés sur la page")
        
        if not elements_produits:
            print("⚠️ Aucun produit trouvé sur la page")
            return [], [], urls_deja_traitees

        # Traiter tous les produits de la page jusqu'à atteindre le nombre total souhaité
        for element in elements_produits:
            try:
                # Récupérer le lien du produit
                lien_produit = element.find_element(By.CSS_SELECTOR, 'a.format-img-zento').get_attribute('href')
                if lien_produit in urls_deja_traitees:
                    print(f"⏭️ Produit déjà traité : {lien_produit}")
                    continue

                print(f"\n🔍 Traitement du produit : {lien_produit}")
                
                # Ouvrir le produit dans un nouvel onglet
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(lien_produit)
                
                # Attendre le chargement de la page
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Récupérer le nom du produit
                try:
                    nom_element = driver.find_element(By.CSS_SELECTOR, 'div.template-grid-whilist h1.green-text')
                    nom_produit = nom_element.text.strip()
                    print(f"📝 Nom du produit : {nom_produit}")
                except NoSuchElementException:
                    print("⚠️ Nom du produit non trouvé")
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
                
                # Récupérer le prix
                try:
                    prix_element = driver.find_element(By.CSS_SELECTOR, 'li.price.price-with-taxes.content-price-detail-zento span.price-value')
                    prix_text = prix_element.text.strip().replace('€', '').replace(',', '.').strip()
                    prix_retail = float(prix_text)
                    print(f"💰 Prix retail : {prix_retail}€")
                except (NoSuchElementException, ValueError):
                    print("⚠️ Prix non trouvé ou invalide")
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
                
                # Récupérer l'EAN depuis le script
                try:
                    # Chercher l'élément avec l'attribut data-product
                    product_element = driver.find_element(By.CSS_SELECTOR, '[data-product]')
                    product_data = product_element.get_attribute('data-product')
                    
                    # Parser le JSON
                    product_json = json.loads(product_data)
                    
                    # Extraire l'EAN depuis le chemin stock.ean13
                    ean = product_json.get('stock', {}).get('ean13')
                    
                    if ean:
                        print(f"🔢 EAN : {ean}")
                    else:
                        print("⚠️ EAN non trouvé dans les données du produit")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        continue
                except Exception as e:
                    print(f"⚠️ Erreur lors de la récupération de l'EAN : {str(e)}")
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
                
                # Vérifier si l'EAN existe déjà
                if ean_existe_deja(ean):
                    print(f"⏭️ EAN {ean} déjà présent dans la base de données")
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
                
                # Récupérer les données Keepa
                print("🔍 Récupération des données Keepa...")
                keepa_data = get_keepa_data(ean, prix_retail)
                
                if keepa_data and keepa_data.get('status') == 'OK':
                    prix_amazon = keepa_data.get('prix_amazon')
                    difference = keepa_data.get('difference')
                    profit = keepa_data.get('profit')
                    
                    # Vérifier que toutes les valeurs nécessaires sont présentes
                    if all([prix_amazon, difference, profit]):
                        print(f"✅ Données Keepa récupérées :")
                        print(f"   - Prix Amazon : {prix_amazon}€")
                        print(f"   - Difference : {difference}")
                        print(f"   - Profit : {profit}")
                    else:
                        print("❌ Données Keepa incomplètes")
                        print(f"   - Prix Amazon : {prix_amazon}")
                        print(f"   - Difference : {difference}")
                        print(f"   - Profit : {profit}")
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        continue
                else:
                    print("❌ Pas de données Keepa disponibles")
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                    continue
                
                # Créer le produit
                produit = {
                    'nom': nom_produit,
                    'ean': ean,
                    'prix_retail': prix_retail,
                    'prix_amazon': prix_amazon,
                    'difference': difference,
                    'profit': profit,
                    'url': lien_produit
                }
                
                # Ajouter à la liste des produits
                produits.append(produit)
                eans_page_courante.append(ean)
                urls_deja_traitees.add(lien_produit)
                print(f"✅ Produit ajouté avec succès")
                
                # Insérer le produit en base de données
                print("💾 Sauvegarde en base de données...")
                try:
                    insert_or_update_product(
                        nom=nom_produit,
                        ean=ean,
                        prix_retail=prix_retail,
                        url=lien_produit,
                        prix_amazon=prix_amazon,
                        difference=difference,
                        profit=profit
                    )
                    print("✅ Produit sauvegardé en base de données")
                except Exception as e:
                    print(f"❌ Erreur lors de la sauvegarde en base de données : {str(e)}")
                
                # Fermer l'onglet et revenir à la liste
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                
                # Si on a atteint le nombre total d'entrées souhaité, on arrête
                if len(produits) >= nb_max_produits:
                    print(f"🎯 Nombre total d'entrées atteint ({nb_max_produits})")
                    break
                
            except Exception as e:
                print(f"❌ Erreur lors du traitement du produit : {str(e)}")
                if len(driver.window_handles) > 1:
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])
                continue
        
        print(f"\n📊 Résumé de la page : {len(produits)} produits traités avec succès")
        return produits, eans_page_courante, urls_deja_traitees
        
    except Exception as e:
        print(f"❌ Erreur lors du scraping de la page : {str(e)}")
        print("Stack trace complet :")
        import traceback
        traceback.print_exc()
        return [], [], urls_deja_traitees



def lancer_scraping(url, nb_scrap_total):
    """🚀 Lancement principal du scraping avec pagination par URL."""
    driver = None
    try:
        print(f"🚀 [SCRAPER] Démarrage du scraping pour : {url}")
        print(f"📊 Nombre de produits à scraper : {nb_scrap_total}")

        # Extraire l'URL de base sans ?page=
        url_base = re.sub(r'\?page=\d+', '', url)
        print(f"🔗 URL de base : {url_base}")

        # Vérifier si le site est accessible
        print("🌐 Vérification de l'accessibilité du site...")
        try:
            response = requests.get(url_base, timeout=10)
            if response.status_code != 200:
                print(f"❌ Site non accessible (status code: {response.status_code})")
                return []
            print("✅ Site accessible")
        except Exception as e:
            print(f"❌ Erreur lors de la vérification du site : {str(e)}")
            return []

        print("⚙️ Initialisation du driver Chrome...")
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            print("✅ Driver Chrome initialisé")
        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation du driver Chrome : {str(e)}")
            print("Stack trace complet :")
            import traceback
            traceback.print_exc()
            return []

        print("🌐 Chargement de la page...")
        try:
            driver.get(url_base)
            print("✅ Page chargée")
        except Exception as e:
            print(f"❌ Erreur lors du chargement de la page : {str(e)}")
            return []

        print("⏳ Attente du chargement complet...")
        time.sleep(5)  # Attente plus longue pour le chargement initial

        print("🔄 Démarrage du scraping des pages...")
        try:
            produits_scrapes = scrap_toutes_pages(driver, nb_scrap_total, url_base)
            print(f"🎉 FIN : {len(produits_scrapes)} produits enrichis et insérés en DB.")
            return produits_scrapes
        except Exception as e:
            print(f"❌ Erreur lors du scraping des pages : {str(e)}")
            print("Stack trace complet :")
            import traceback
            traceback.print_exc()
            return []

    except Exception as e:
        print(f"❌ Erreur générale lors du scraping : {str(e)}")
        print("Stack trace complet :")
        import traceback
        traceback.print_exc()
        return []

    finally:
        if driver:
            try:
                print("🛑 Fermeture du driver Chrome...")
                driver.quit()
                print("✅ Driver Chrome fermé")
            except Exception as e:
                print(f"⚠️ Erreur lors de la fermeture du driver : {str(e)}")



if __name__ == "__main__":
    print("🚀 Démarrage du script de scraping")
    try:
        url = sys.argv[1]
        nb_scrap = int(sys.argv[2])
        print(f"📝 Arguments reçus : URL={url}, NB_PRODUITS={nb_scrap}")
        produits_scrapes = lancer_scraping(url, nb_scrap)
        print(f"🎉 Scraping terminé. Total : {len(produits_scrapes)} produit(s) enrichi(s).")
    except Exception as e:
        print(f"❌ Erreur lors de l'exécution du script : {str(e)}")