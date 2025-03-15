# scraping/scraper.py

import sys
import os

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
import re
from datetime import datetime
import pytz
from app import db, create_app
from app.models import ProductKeepa
from app.utils.fetch_keepa import get_keepa_data

# Configuration Selenium
options = Options()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--log-level=3')
options.add_experimental_option('excludeSwitches', ['enable-logging'])

def extraire_details_produit(driver, url):
    """Extrait le nom, prix et EAN d'un produit."""
    try:
        # Ouvre le produit dans un nouvel onglet
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[1])
        driver.get(url)

        # Attente que la page charge
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
        
        # Extraction du nom et prix
        nom_element = driver.find_element(By.CSS_SELECTOR, 'div.template-grid-whilist h1.green-text')
        nom_produit = nom_element.text.strip()
        
        prix_element = driver.find_element(By.CSS_SELECTOR, 'li.price.price-with-taxes.content-price-detail-zento span.price-value')
        prix_text = prix_element.text.strip().replace('€', '').replace(',', '.').strip()
        prix_retail = float(prix_text)
        
        # Extraction de l'EAN depuis le code source
        page_source = driver.page_source
        ean_match = re.search(r'"ean13"\s*:\s*"(\d{13})"', page_source)
        
        if not ean_match:
            return None
            
        ean = ean_match.group(1)
        print(f"Analyse du produit {ean} - {nom_produit}")

        return {
            'nom': nom_produit,
            'prix_retail': prix_retail,
            'ean': ean,
            'url': url
        }
        
    except Exception as e:
        print(f"Erreur extraction produit: {str(e)}")
        return None  
    finally:
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

def ean_existe_deja(ean):
    """Vérifie si l'EAN existe déjà en base."""
    return db.session.query(ProductKeepa).filter_by(ean=ean).count() > 0

def insert_or_update_product(data):
    """Insère ou met à jour un produit en base."""
    try:
        paris_timezone = pytz.timezone("Europe/Paris")
        updated_at = datetime.now(paris_timezone)
        
        # Création ou mise à jour du produit
        product = ProductKeepa(
            nom=data['nom'],
            ean=data['ean'],
            prix_retail=data['prix_retail'],
            prix_amazon=data['prix_amazon'],
            profit=data['profit'],
            roi=data['roi'],
            url=data['url'],
            sales_estimation=data['sales_estimation'],
            updated_at=updated_at
        )
        
        db.session.add(product)
        db.session.commit()
        print(f"✅ Produit ajouté: {data['nom']} (Ventes: {data['sales_estimation']}, ROI: {data['roi']}%)")
        return True
        
    except Exception as e:
        print(f"Erreur DB: {str(e)}")
        db.session.rollback()
        return False

def scrap_produits_sur_page(driver, nb_max_produits, urls_traitees):
    """Scrape les produits d'une page."""
    produits_ajoutes = 0
    produits_scannes = 0
    
    try:
        elements_produits = driver.find_elements(By.CSS_SELECTOR, 'div.col-sx-zento')
        total_produits_page = len(elements_produits)
        print(f"\nNombre de produits sur la page: {total_produits_page}")
        
        # Si moins de 52 produits, c'est la dernière page
        is_last_page = total_produits_page < 52
        
        for element in elements_produits:
            produits_scannes += 1
            if produits_scannes % 10 == 0:
                print(f"\n📊 Progression: {produits_scannes} produits scannés sur cette page\n")
            
            if produits_ajoutes >= nb_max_produits:
            break

        try:
                lien_produit = element.find_element(By.CSS_SELECTOR, 'a.format-img-zento').get_attribute('href')
                if lien_produit in urls_traitees:
                continue

                urls_traitees.add(lien_produit)
                produit = extraire_details_produit(driver, lien_produit)
                
                if not produit:
                continue

                if ean_existe_deja(produit['ean']):
                    print(f"Produit déjà en base: {produit['nom']}")
                continue

                keepa_data = get_keepa_data(produit['ean'], produit['prix_retail'])
                
                if keepa_data:
                    # Fusion des données produit et Keepa
                    produit.update(keepa_data)
                    if insert_or_update_product(produit):
                        produits_ajoutes += 1
                        
            except Exception as e:
                print(f"Erreur produit: {str(e)}")
                continue

        print(f"\nRésumé de la page:")
        print(f"- Produits scannés: {produits_scannes}")
        print(f"- Produits ajoutés: {produits_ajoutes}")
        return produits_ajoutes, urls_traitees, produits_scannes, is_last_page

        except Exception as e:
        print(f"Erreur page: {str(e)}")
        return 0, urls_traitees, produits_scannes, False

def lancer_scraping(url, nb_produits, page_depart=1):
    """Lance le scraping avec pagination."""
    driver = None
    urls_traitees = set()
    produits_ajoutes = 0
    total_produits_scannes = 0
    page = page_depart
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        url_base = re.sub(r'\?pageNumber-3=\d+', '', url)
        
        while produits_ajoutes < nb_produits:
            url_page = f"{url_base}?pageNumber-3={page}"
            print(f"\nAnalyse de la page {page}...")
            
            driver.get(url_page)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-sx-zento')))
            
            nouveaux_produits, urls_traitees, produits_scannes, is_last_page = scrap_produits_sur_page(
                driver,
                nb_produits - produits_ajoutes,
                urls_traitees
            )
            
            total_produits_scannes += produits_scannes
            produits_ajoutes += nouveaux_produits
            print(f"\nProgression globale:")
            print(f"- Total produits scannés: {total_produits_scannes}")
            print(f"- Produits ajoutés: {produits_ajoutes}/{nb_produits}")
            
            if nouveaux_produits == 0:
                print("Aucun nouveau produit trouvé sur cette page")
            
            # Si c'est la dernière page, on arrête
            if is_last_page:
                print("\nDernière page atteinte, arrêt du scraping")
                break
                
            page += 1
            
    except Exception as e:
        print(f"Erreur scraping: {str(e)}")
    finally:
        if driver:
        driver.quit()

if __name__ == "__main__":
    try:
        app = create_app()
        with app.app_context():
            if len(sys.argv) < 3 or len(sys.argv) > 4:
                print("Usage: python scraper.py <url> <nombre_produits> [page_depart]")
                sys.exit(1)
                
    url = sys.argv[1]
    nb_scrap = int(sys.argv[2])
            page_depart = int(sys.argv[3]) if len(sys.argv) == 4 else 1
            
            print(f"Démarrage du scraping à partir de la page {page_depart}")
            lancer_scraping(url, nb_scrap, page_depart)
            
    except Exception as e:
        print(f"Erreur: {str(e)}")
        raise