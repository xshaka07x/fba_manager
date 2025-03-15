import requests
import os
from selenium import webdriver
import logging
import sys
import time

# Suppression des logs Selenium/DevTools
logging.getLogger('selenium').setLevel(logging.CRITICAL)
os.environ['WDM_LOG_LEVEL'] = '0'
sys.stderr = open(os.devnull, 'w')

# 🔑 API Keepa
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY", "ftclrhsi754hf3tblbljldbonk7n4cuthggk8gnt88c4k2sjkmre8th8cjf65jnc")
KEEPA_URL = "https://api.keepa.com/product"

def get_keepa_data(ean, prix_retail):
    """🔍 Récupère les données Keepa pour un produit via EAN."""
    try:
        params = {
            'key': KEEPA_API_KEY,
            'domain': 4,        # Amazon.fr
            'code': ean,        # EAN du produit
            'offers': 20,       # Nombre minimum d'offres requis
            'history': 1,       # Historique des prix
            'stats': 1          # Statistiques de vente
        }
        
        response = requests.get(KEEPA_URL, params=params, timeout=15)
        data = response.json()
        
        if not data.get('products'):
            print(f"❌ {ean}: Aucune donnée Keepa")
            return None
            
        product = data['products'][0]
        stats = product.get('stats', {})
        
        # Prix Buy Box courante (index 18 dans le tableau current)
        current = stats.get('current', [])
        if len(current) > 18 and current[18] is not None and current[18] > 0:
            prix_amazon = float(current[18]) / 100.0
        else:
            print(f"❌ {ean}: Pas de Buy Box")
            return None
            
        # Estimation des ventes (30 derniers jours)
        sales_estimation = stats.get('salesRankDrops30', 0)
        
        # Détection PL (basée sur le nombre de vendeurs)
        offers = product.get('offers', [])
        is_pl = len(offers) <= 2  # Si 2 vendeurs ou moins, considéré comme PL
        
        # Calcul des frais Amazon (selon calculateur Amazon)
        frais_vente = prix_amazon * 0.13  # 13% du prix de vente
        frais_digital = 0.25  # Frais des services numériques
        frais_gestion = frais_vente + frais_digital  # Total frais de gestion
        frais_expedition = 5.87  # Tarif d'expédition de base
        frais_stockage = 0.10  # Coût de stockage mensuel par unité
        
        # Total des frais et TVA
        frais_totaux = frais_gestion + frais_expedition + frais_stockage
        tva_frais = frais_totaux * 0.20
        
        # Calcul du profit et ROI
        profit = prix_amazon - prix_retail - frais_totaux - tva_frais
        roi = (profit * 100 / prix_retail) if prix_retail > 0 else 0
        marge_nette = (profit * 100 / prix_amazon) if prix_amazon > 0 else 0
        
        # Vérification des critères avec logs détaillés
        if is_pl:
            print(f"❌ {ean}: Rejeté - Produit PL ({len(offers)} vendeurs)")
            return None
            
        if sales_estimation <= 1:
            print(f"❌ {ean}: Rejeté - Pas assez de ventes ({sales_estimation} ventes/30j)")
            return None
            
        if roi <= 20:
            print(f"❌ {ean}: Rejeté - ROI insuffisant ({roi:.2f}% <= 20%)")
            return None
            
        print(f"✅ Produit trouvé - EAN: {ean}")
        print(f"   Prix Amazon: {prix_amazon:.2f}€ | Prix achat: {prix_retail:.2f}€ | ROI: {roi:.2f}% | Ventes: {sales_estimation}")
        
        return {
            'status': 'OK',
            'prix_amazon': prix_amazon,
            'prix_retail': prix_retail,
            'profit': profit,
            'roi': roi,
            'marge_nette': marge_nette,
            'sales_estimation': sales_estimation,
            'is_pl': is_pl,
            'frais_totaux': frais_totaux,
            'tva_frais': tva_frais,
            'frais_gestion': frais_gestion,
            'frais_expedition': frais_expedition,
            'frais_stockage': frais_stockage,
            'frais_vente': frais_vente,
            'frais_digital': frais_digital
        }
            
    except Exception as e:
        print(f"❌ {ean}: Erreur - {str(e)}")
        return None

# Configuration Selenium pour supprimer les messages
options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--log-level=3')  # Supprime la plupart des logs
options.add_experimental_option('excludeSwitches', ['enable-logging'])  # Supprime les messages DevTools
