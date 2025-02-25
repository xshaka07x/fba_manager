# main.py
import subprocess
import os
from urllib.parse import urlparse
from datetime import datetime
import json


SCRAPER_PATH = r"scraping/scraper.py"
COMPARE_PATH = r"scraping/compare.py"
SCRAPS_DIR = r"_scraps"


def creer_dossier():
    """📂 Crée un dossier d'export avec timestamp."""
    now = datetime.now().strftime("%d-%m-%Y_%H%M%S")
    dossier = os.path.join(SCRAPS_DIR, f"{now}_scrap")
    os.makedirs(dossier, exist_ok=True)
    return dossier


def lancer_scrap(urls, nb_produits, dossier):
    """🚀 Lance le scraping pour chaque URL et fusionne en un JSON final."""
    fichier_final = os.path.join(dossier, "listing.json")
    all_produits, produits_requis = [], nb_produits

    for url in urls:
        if produits_requis <= 0:
            break
        fichier_temp = os.path.join(dossier, f"temp_{urlparse(url).netloc}.json")
        try:
            subprocess.run(
                ["python", SCRAPER_PATH, url, str(produits_requis), fichier_temp],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"🚨 Échec subprocess pour {url} : {e}")
            continue

        if os.path.exists(fichier_temp):
            with open(fichier_temp, 'r', encoding='utf-8') as f:
                produits = json.load(f)
                all_produits.extend(produits)
            produits_requis = nb_produits - len(all_produits)
            print(f"✅ Fusion : {len(all_produits)} produits.")
        else:
            print(f"🚨 Fichier non trouvé : {fichier_temp}")

    with open(fichier_final, 'w', encoding='utf-8') as f:
        json.dump(all_produits, f, ensure_ascii=False, indent=4)
    return fichier_final



def lancer_compare(fichier_json, dossier):
    """🚀 Lance compare.py avec le JSON généré."""
    if os.path.exists(fichier_json):
        subprocess.run(["python", COMPARE_PATH, fichier_json, dossier], check=True)
        print(f"🎉 Analyse SellerAmp terminée dans : {dossier}")
    else:
        print(f"🚨 JSON non trouvé : {fichier_json}")



if __name__ == "__main__":
    urls = [input("🌐 Entrez l'URL à scraper : ")]
    nb_produits = int(input("🔢 Nombre total de produits à scraper : "))

    dossier_export = creer_dossier()
    fichier_json = lancer_scrap(urls, nb_produits, dossier_export)
    lancer_compare(fichier_json, dossier_export)
