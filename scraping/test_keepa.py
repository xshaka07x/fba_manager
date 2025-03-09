import requests
import sys
import json

# 🔑 API Keepa
KEEPA_API_KEY = "ftclrhsi754hf3tblbljldbonk7n4cuthggk8gnt88c4k2sjkmre8th8cjf65jnc"
KEEPA_URL = "https://api.keepa.com/product"

def test_keepa_data(ean):
    """🔍 Test de récupération des données Keepa pour un EAN spécifique."""
    print(f"\n🔍 Test Keepa pour EAN : {ean}")
    
    try:
        # Construire l'URL de l'API Keepa avec les bons paramètres
        params = {
            'key': KEEPA_API_KEY,
            'domain': '4',  # Amazon.fr (4 au lieu de 1)
            'code': ean,
            'stats': '1',
            'buybox': '1',
            'history': '1'
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
        print("\n📦 Données brutes reçues :")
        print(json.dumps(data, indent=2))
        
        # Vérifier que les données sont présentes
        if not data or 'products' not in data or not data['products']:
            print("\n❌ Pas de données dans la réponse")
            print("ℹ️ Vérifiez que l'EAN est correct et qu'il existe sur Amazon.fr")
            return None
            
        # Extraire les données du premier produit
        product = data['products'][0]
        
        # Extraire le prix depuis les statistiques
        if 'stats' in product and 'current' in product['stats']:
            current_stats = product['stats']['current']
            if len(current_stats) > 1 and current_stats[1] > 0:
                prix_amazon = float(current_stats[1]) / 100.0  # Conversion des centimes en euros
                print(f"\n💰 Prix Amazon actuel : {prix_amazon}€")
                
                # Afficher les statistiques si disponibles
                stats = product['stats']
                print("\n📊 Statistiques :")
                if 'avg' in stats and len(stats['avg']) > 1 and stats['avg'][1] > 0:
                    print(f"   - Prix moyen : {float(stats['avg'][1]) / 100.0}€")
                if 'min' in stats and stats['min'][1] and isinstance(stats['min'][1], list) and len(stats['min'][1]) > 1:
                    print(f"   - Prix minimum : {float(stats['min'][1][1]) / 100.0}€")
                if 'max' in stats and stats['max'][1] and isinstance(stats['max'][1], list) and len(stats['max'][1]) > 1:
                    print(f"   - Prix maximum : {float(stats['max'][1][1]) / 100.0}€")
                
                return prix_amazon
            else:
                print("\n❌ Prix Amazon non disponible dans les statistiques")
        else:
            print("\n❌ Pas de statistiques disponibles")
        
        return None
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la récupération des données Keepa : {str(e)}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("❌ Usage: python test_keepa.py <EAN>")
        sys.exit(1)
        
    ean = sys.argv[1]
    test_keepa_data(ean) 