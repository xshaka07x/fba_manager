import pandas as pd
import time
from datetime import datetime
import os
import sys
from dotenv import load_dotenv

# Ajouter le répertoire parent au PYTHONPATH pour permettre l'import depuis app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.utils.fetch_keepa import get_keepa_data

# Charger les variables d'environnement
load_dotenv()

# Définir les chemins pour les dossiers de travail
ANALYSIS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'analysis')
INPUT_DIR = os.path.join(ANALYSIS_DIR, 'input')
OUTPUT_DIR = os.path.join(ANALYSIS_DIR, 'output')
LOGS_DIR = os.path.join(ANALYSIS_DIR, 'logs')

# Créer les dossiers s'ils n'existent pas
for directory in [ANALYSIS_DIR, INPUT_DIR, OUTPUT_DIR, LOGS_DIR]:
    if not os.path.exists(directory):
        os.makedirs(directory)

# Liste des marques autorisées (non PL)
MARQUES_AUTORISEES = {
    'Bioderma', 'Puressentiel', "L'Oréal", 'Kérastase', 'Neutrogena', 
    'Johnson & Johnson', 'IT Cosmetics', 'adidas', 'Rimmel', 
    'Maybelline New York', 'Estée Lauder', 'Rasasi', 'NYX', 
    "L'Oréal Paris", 'Redken', 'Mustela', 'Nivea', 'Revlon'
}

def setup_logging():
    """Configure le système de logging"""
    log_file = os.path.join(LOGS_DIR, f'analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    return log_file

def calculate_fba_fees(price):
    """Calcule les frais FBA en fonction du prix"""
    if price <= 10:
        return 3.27
    elif price <= 30:
        return 4.75
    else:
        return 5.4 + (price * 0.04)

def calculate_roi(buy_price, sell_price):
    """Calcule le ROI en pourcentage"""
    if buy_price <= 0 or sell_price <= 0:
        return 0
    
    fba_fees = calculate_fba_fees(sell_price)
    # Commission Amazon (15%)
    amazon_commission = sell_price * 0.15
    # Frais totaux
    total_fees = fba_fees + amazon_commission
    # Profit net
    net_profit = sell_price - total_fees - buy_price
    # ROI
    roi = (net_profit / buy_price) * 100
    return roi

def get_asin_from_ean(keepa_api, ean):
    """Convertit un EAN en ASIN via l'API Keepa"""
    try:
        print(f"Recherche de l'ASIN pour l'EAN: {ean}")
        # Utiliser la méthode de recherche par code-barres de Keepa
        result = keepa_api.search_for_ean(ean)
        if result and len(result) > 0:
            asin = result[0]
            print(f"ASIN trouvé: {asin}")
            return asin
        print(f"Aucun ASIN trouvé pour l'EAN: {ean}")
        return None
    except Exception as e:
        print(f"Erreur lors de la conversion EAN->ASIN: {str(e)}")
        return None

def get_keepa_price(keepa_api, ean):
    """Récupère le prix actuel sur Amazon via Keepa"""
    try:
        # D'abord convertir l'EAN en ASIN
        asin = get_asin_from_ean(keepa_api, ean)
        if not asin:
            print(f"Impossible de trouver l'ASIN pour l'EAN: {ean}")
            return None, None

        print(f"Requête Keepa pour ASIN: {asin} (EAN: {ean})")
        products = keepa_api.query(asin)
        
        if not products:
            print(f"Aucun produit trouvé pour ASIN: {asin}")
            return None, None

        product = products[0]
        if not product or 'data' not in product:
            print(f"Données invalides pour ASIN: {asin}")
            return None, None
            
        # Récupérer l'historique des prix Amazon
        if 'csv' not in product['data'] or not product['data']['csv']:
            print(f"Pas d'historique de prix pour ASIN: {asin}")
            return None, None
            
        amazon_price_history = product['data']['csv'][0]
        if not amazon_price_history or len(amazon_price_history) == 0:
            print(f"Historique de prix vide pour ASIN: {asin}")
            return None, None

        # Obtenir le dernier prix valide
        last_valid_price = None
        for price in reversed(amazon_price_history):
            if price > 0:  # Prix valide
                last_valid_price = price / 100  # Keepa stocke les prix * 100
                break

        if last_valid_price is None:
            print(f"Aucun prix valide trouvé pour ASIN: {asin}")
            return None, None

        title = product.get('title', 'Titre non disponible')
        print(f"Prix trouvé pour {asin}: {last_valid_price}€ - {title}")
        return last_valid_price, title

    except Exception as e:
        print(f"Erreur lors de la récupération du prix Keepa pour EAN {ean}: {str(e)}")
        return None, None

def analyze_excel(file_name):
    """Analyse le fichier Excel et compare avec les données Keepa"""
    try:
        # Configurer le logging
        log_file = setup_logging()
        
        # Construire les chemins complets
        input_file = os.path.join(INPUT_DIR, file_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(OUTPUT_DIR, f'resultats_{timestamp}.xlsx')
        
        # Vérifier si le fichier existe
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"Le fichier {file_name} n'existe pas dans le dossier input")

        print(f"Lecture du fichier {file_name}...")
        with open(log_file, 'a') as f:
            f.write(f"[{datetime.now()}] Début de l'analyse du fichier {file_name}\n")
        
        # Lire d'abord toutes les lignes pour trouver où commencent les vraies données
        df_preview = pd.read_excel(
            input_file,
            nrows=20,
            dtype={'A': str}  # Force la colonne A (GTIN) à être lue comme du texte
        )
        
        # Trouver la première ligne contenant un EAN valide (13 chiffres)
        start_row = 0
        for idx, row in df_preview.iterrows():
            value = str(row.iloc[0]).strip()  # Première colonne (A)
            if value.isdigit() and len(value) == 13:  # EAN valide
                start_row = idx
                break
        
        print(f"Début des données trouvé à la ligne {start_row + 1}")
        
        # Initialiser les variables pour la lecture par lots
        chunk_size = 500  # Lire 500 lignes à la fois
        current_row = start_row
        refs_processed = 0  # Compteur de références traitées
        results = []
        errors = []
        
        while refs_processed < 1200:
            # Lire un nouveau lot de données
            df_chunk = pd.read_excel(
                input_file,
                skiprows=current_row,
                nrows=chunk_size,
                usecols=[0, 3, 4],  # Colonnes A (GTIN), D (Marque) et E (Prix)
                names=['GTIN', 'Marque', 'Prix'],
                dtype={'GTIN': str}
            )
            
            # Si plus de données à lire, sortir de la boucle
            if df_chunk.empty:
                print("Plus de données à lire dans le fichier")
                break
                
            # Filtrer les marques autorisées
            df_chunk = df_chunk[df_chunk['Marque'].isin(MARQUES_AUTORISEES)]
            
            # Mettre à jour le point de départ pour la prochaine lecture
            current_row += chunk_size
            
            # Pour chaque ligne du chunk
            for index, row in df_chunk.iterrows():
                # Vérifier si on a atteint la limite
                if refs_processed >= 1200:
                    break
                    
                try:
                    gtin = str(row['GTIN']).strip()
                    marque = row['Marque']
                    
                    # Incrémenter le compteur de références traitées
                    refs_processed += 1
                    
                    try:
                        catalogue_price = float(str(row['Prix']).replace('€', '').replace(',', '.').strip())
                    except:
                        print(f"Prix catalogue invalide pour {gtin}: {row['Prix']}")
                        continue
                    
                    if not gtin or pd.isna(gtin) or not gtin.isdigit() or len(gtin) != 13:
                        print(f"GTIN invalide: {gtin}")
                        continue
                        
                    if pd.isna(catalogue_price) or catalogue_price <= 0:
                        print(f"Prix catalogue invalide pour {gtin}: {catalogue_price}")
                        continue
                    
                    status_msg = f"Traitement de {gtin} (Marque: {marque}) - {refs_processed}/1200..."
                    print(status_msg)
                    with open(log_file, 'a') as f:
                        f.write(f"[{datetime.now()}] {status_msg}\n")
                    
                    # Utiliser get_keepa_data de fetch_keepa.py
                    keepa_result = get_keepa_data(gtin, catalogue_price)
                    
                    if keepa_result and keepa_result.get('status') == 'OK':
                        results.append({
                            'GTIN': gtin,
                            'Marque': marque,
                            'Prix Catalogue': catalogue_price,
                            'Prix Amazon': keepa_result['prix_amazon'],
                            'Profit Estimé': keepa_result['profit'],
                            'ROI': keepa_result['roi'],
                            'Marge Nette': keepa_result['marge_nette'],
                            'Ventes Estimées': keepa_result['sales_estimation'],
                            'Frais Totaux': keepa_result['frais_totaux'],
                            'TVA sur Frais': keepa_result['tva_frais']
                        })
                    else:
                        errors.append(f"Impossible de récupérer les données pour {gtin} ({marque})")
                    
                    # Pause pour respecter les limites de l'API
                    time.sleep(2)
                    
                except Exception as e:
                    error_msg = f"Erreur lors du traitement de {gtin} (Marque: {marque}): {str(e)}"
                    print(error_msg)
                    errors.append(error_msg)
                    continue
            
            print(f"Progression: {refs_processed}/1200 références traitées")
        
        # Créer un DataFrame avec les résultats
        if not results:
            raise Exception("Aucun résultat n'a été obtenu après analyse")
            
        results_df = pd.DataFrame(results)
        
        # Trier par ROI décroissant
        results_df = results_df.sort_values('ROI', ascending=False)
        
        # Sauvegarder les résultats
        results_df.to_excel(output_file, index=False)
        
        # Sauvegarder les erreurs dans un fichier séparé si nécessaire
        if errors:
            error_file = os.path.join(OUTPUT_DIR, f'erreurs_{timestamp}.txt')
            with open(error_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(errors))
        
        completion_msg = f"Analyse terminée. {refs_processed} références traitées. Résultats sauvegardés dans {output_file}"
        if errors:
            completion_msg += f"\nDes erreurs ont été rencontrées, voir {error_file}"
        
        print(completion_msg)
        with open(log_file, 'a') as f:
            f.write(f"[{datetime.now()}] {completion_msg}\n")
            
        return results_df, output_file
        
    except Exception as e:
        error_msg = f"Erreur lors de l'analyse: {str(e)}"
        print(error_msg)
        if 'log_file' in locals():
            with open(log_file, 'a') as f:
                f.write(f"[{datetime.now()}] ERROR: {error_msg}\n")
        return None, None

if __name__ == "__main__":
    file_name = "qojita.xlsx"  # Nom du fichier à analyser (doit être dans le dossier input)
    analyze_excel(file_name) 