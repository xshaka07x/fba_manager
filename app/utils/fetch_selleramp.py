# app/utils/fetch_selleramp.py
from scraping.scraper import get_selleramp_data

def fetch_selleramp_info(ean, prix_achat):
    """
    🔍 Récupère les données SellerAmp en fonction d'un EAN et du prix d'achat.
    Renvoie : (nom, prix_amazon, roi, profit, sales_estimation)
    """
    try:
        prix_amazon, roi, profit, sales_estimation, alerts = get_selleramp_data(ean, prix_achat)

        if not all([prix_amazon, roi, profit, sales_estimation]):
            print(f"⚠️ Aucune donnée valide récupérée pour EAN {ean}.")
            return None, None, None, None, None

        return prix_amazon, roi, profit, sales_estimation, alerts

    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données SellerAmp pour {ean}: {e}")
        return None, None, None, None, None
