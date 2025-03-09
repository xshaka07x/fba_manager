import requests
import os
from selenium import webdriver

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
            print(f"❌ [Keepa] Erreur API : {data.get('error', 'Réponse vide')}")
            return None

        if "products" in data and len(data["products"]) > 0:
            asin = data["products"][0].get("asin")
            if asin:
                print(f"✅ [Keepa] ASIN trouvé : {asin} pour EAN {ean}")
                return asin
            else:
                print(f"⚠️ [Keepa] Aucun ASIN trouvé pour EAN {ean}")
        else:
            print(f"⚠️ [Keepa] Aucun produit trouvé pour EAN {ean}")

    except requests.exceptions.Timeout:
        print(f"❌ [Keepa] Timeout API pour EAN {ean}")
    except requests.exceptions.RequestException as e:
        print(f"❌ [Keepa] Erreur API : {e}")

    return None


def get_keepa_data(ean, prix_retail):
    """🔍 Récupère les données Keepa pour un produit."""
    print(f"\n🔍 Récupération des données Keepa pour EAN {ean}")
    
    # Vérifier que l'EAN est valide
    if not isinstance(ean, str) or len(ean) < 8:
        print("❌ EAN invalide")
        return None
        
    try:
        # Construire l'URL de l'API Keepa
        params = {
            'key': KEEPA_API_KEY,
            'domain': '4',  # Amazon.fr
            'code': ean,
            'stats': '1',
            'buybox': '1'
        }
        
        url = f"{KEEPA_URL}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
        print(f"🌐 Appel API Keepa : {url}")
        
        # Faire la requête HTTP
        response = requests.get(url)
        print(f"📡 Status code : {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Erreur HTTP : {response.status_code}")
            return None
            
        # Parser la réponse JSON
        data = response.json()
        print(f"✅ Réponse Keepa reçue")
        
        # Vérifier que les données sont présentes
        if not data or 'products' not in data or not data['products']:
            print("❌ Pas de données dans la réponse")
            return None
            
        # Extraire les données du premier produit
        product = data['products'][0]
        
        # Extraire le prix depuis les statistiques
        if 'stats' in product and 'current' in product['stats']:
            current_stats = product['stats']['current']
            if len(current_stats) > 1 and current_stats[1] > 0:
                prix_amazon = float(current_stats[1]) / 100.0  # Conversion des centimes en euros
                print(f"💰 Prix Amazon trouvé : {prix_amazon}€")
                
                # Calcul de la différence brute
                difference = prix_amazon - prix_retail
                
                # Calcul du profit (différence - 30% de frais)
                profit = difference * 0.7  # On garde 70% après les frais
                
                print(f"📊 Détail des calculs :")
                print(f"   - Prix retail : {prix_retail}€")
                print(f"   - Prix Amazon : {prix_amazon}€")
                print(f"   - Différence brute : {difference}€")
                print(f"   - Profit estimé (après 30% frais) : {profit}€")
                
                # Formatage des valeurs pour la base de données
                try:
                    result = {
                        'status': 'OK',
                        'prix_amazon': prix_amazon,
                        'difference': difference,
                        'profit': profit
                    }
                    print(f"✅ Données Keepa calculées : {result}")
                    return result
                except Exception as e:
                    print(f"❌ Erreur lors du formatage des données : {str(e)}")
                    print("Stack trace :")
                    import traceback
                    traceback.print_exc()
                    return None
            else:
                print("❌ Prix Amazon non disponible dans les statistiques")
        else:
            print("❌ Pas de statistiques disponibles")
        
        return None
        
    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données Keepa : {str(e)}")
        print("Stack trace :")
        import traceback
        traceback.print_exc()
        return None

options = webdriver.ChromeOptions()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
