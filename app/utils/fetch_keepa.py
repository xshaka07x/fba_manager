import requests
import os
from selenium import webdriver
import logging
import sys

# Suppression des logs Selenium/DevTools
logging.getLogger('selenium').setLevel(logging.CRITICAL)
os.environ['WDM_LOG_LEVEL'] = '0'
sys.stderr = open(os.devnull, 'w')

# 🔑 API Keepa
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY", "ftclrhsi754hf3tblbljldbonk7n4cuthggk8gnt88c4k2sjkmre8th8cjf65jnc")
KEEPA_URL = "https://api.keepa.com/product"

def get_asin_from_ean(ean):
    """🔍 Recherche un ASIN via un EAN en utilisant Keepa API."""
    try:
        params = {
            "key": KEEPA_API_KEY,
            "domain": 4,  # Amazon France
            "code": ean  # Keepa utilise "code" pour les recherches EAN/UPC
        }

        response = requests.get(KEEPA_URL, params=params, timeout=10)
        data = response.json()

        if not data or "error" in data:
            return None

        if "products" in data and len(data["products"]) > 0:
            asin = data["products"][0].get("asin")
            if asin:
                return asin

    except (requests.exceptions.Timeout, requests.exceptions.RequestException):
        pass

    return None


def get_keepa_data(ean, prix_retail):
    """🔍 Récupère les données Keepa pour un produit via EAN."""
    if not isinstance(ean, str) or len(ean) < 8:
        return None
        
    try:
        # Configuration optimisée pour recherche EAN
        params = {
            'key': KEEPA_API_KEY,
            'domain': '4',      # Amazon.fr
            'code': ean,
            'code_type': 'ean', # Spécifie explicitement la recherche par EAN
            'stats': '180',     # Statistiques sur 180 jours
            'buybox': '1',      # Info buybox
            'update': '1',      # Force la mise à jour
            'rating': '1',      # Inclut les évaluations
            'out_of_stock': '1' # Inclut les produits en rupture
        }
        
        response = requests.get(KEEPA_URL, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"Erreur API Keepa ({response.status_code}) pour EAN {ean}")
            return None
            
        data = response.json()
        
        # Log pour debug
        if 'error' in data:
            print(f"Erreur Keepa pour EAN {ean}: {data.get('error', {}).get('message', 'Erreur inconnue')}")
            return None
            
        if not data.get('products'):
            print(f"Aucun produit trouvé sur Keepa pour EAN {ean}")
            return None
            
        product = data['products'][0]
        
        # Récupération du prix (d'abord Amazon, puis vendeurs tiers)
        current_amazon_price = None
        
        if 'stats' in product:
            stats = product['stats']
            current = stats.get('current', [])
            
            # Prix Amazon (index 1)
            if len(current) > 1 and current[1] is not None and current[1] > 0:
                current_amazon_price = float(current[1]) / 100.0
            
            # Prix vendeur tiers (index 2) si pas de prix Amazon
            elif len(current) > 2 and current[2] is not None and current[2] > 0:
                current_amazon_price = float(current[2]) / 100.0
                
            # Prix nouveau vendeur tiers (index 3) en dernier recours
            elif len(current) > 3 and current[3] is not None and current[3] > 0:
                current_amazon_price = float(current[3]) / 100.0
        
        if current_amazon_price:
            difference = current_amazon_price - prix_retail
            profit = difference * 0.7
            
            return {
                'status': 'OK',
                'prix_amazon': current_amazon_price,
                'difference': difference,
                'profit': profit,
                'asin': product.get('asin'),
                'nom': product.get('title', 'Nom non trouvé'),
                'url': f"https://www.amazon.fr/dp/{product.get('asin')}"
            }
        else:
            print(f"Aucun prix valide trouvé sur Keepa pour EAN {ean}")
        
        return None
        
    except Exception as e:
        print(f"Erreur technique Keepa pour EAN {ean}: {str(e)}")
        return None

# Configuration Selenium pour supprimer les messages
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--log-level=3')  # Supprime la plupart des logs
options.add_experimental_option('excludeSwitches', ['enable-logging'])  # Supprime les messages DevTools
