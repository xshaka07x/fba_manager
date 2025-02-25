from sp_api.api import Catalog
from sp_api.base import Marketplaces, SellingApiException
from dotenv import load_dotenv
import os

# Charger les variables d'environnement
load_dotenv()

def get_asin_from_ean(ean_code):
    try:
        # Recherche de produits par EAN
        result = Catalog(marketplace=Marketplaces.FR).list_items(
            keyword=ean_code
        )
        # Extraire l'ASIN du premier résultat
        asin = result.payload['items'][0]['asin']
        print(f"ASIN pour EAN {ean_code} : {asin}")
        return asin
    except SellingApiException as e:
        print(f"Erreur API : {e}")
    except Exception as e:
        print(f"Erreur inattendue : {e}")

# Exemple d’utilisation
ean_example = '06957599324991'  # Remplace par un EAN valide
asin = get_asin_from_ean(ean_example)
