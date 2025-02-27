# app/routes/products.py
from flask import Blueprint, render_template, jsonify, request
from app.models import Product
from app import db
import json
import os
from datetime import datetime
import pytz  # 🕒 Pour la gestion du fuseau horaire

from datetime import timedelta  # ✅ Pour ajouter une heure

products_bp = Blueprint('products', __name__)
paris_tz = pytz.timezone('Europe/Paris')  # ✅ Fuseau horaire Paris

@products_bp.route('/')
def show_products():
    products = Product.query.order_by(Product.updated_at.desc()).all()

    # ✅ Ajout d'une heure lors de l'affichage
    for product in products:
        product.updated_at = (product.updated_at + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M")

    return render_template('products.html', produits=products)

@products_bp.route('/import_json', methods=['POST'])
def import_json():
    if 'file' not in request.files:
        return jsonify({'error': '❌ Aucun fichier trouvé'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '❌ Aucun fichier sélectionné'}), 400

    if file and file.filename.endswith('.json'):
        filepath = os.path.join(os.getcwd(), file.filename)
        file.save(filepath)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            inserted_count = 0
            for item in data:
                if not Product.query.filter_by(ean=item.get("EAN")).first():
                    product = Product(
                        nom=item.get("Nom"),
                        ean=item.get("EAN"),
                        prix_retail=float(item.get("Prix", 0)).__round__(2),
                        url=item.get("URL"),
                        prix_amazon=float(item.get("Prix_Amazon", 0)).__round__(2),
                        roi=float(item.get("ROI", 0)).__round__(2),
                        profit=float(item.get("Profit", 0)).__round__(2),
                        sales_estimation=item.get("Sales_Estimation", 0),
                        alerts=item.get("Alerts", "Aucune alerte")
                    )
                    # ✅ Correction de l'heure après création du produit
                    product.updated_at = datetime.now(paris_tz)  # Heure correcte de Paris
                    db.session.add(product)
                    inserted_count += 1

            db.session.commit()
            return jsonify({'message': f'✅ {inserted_count} produit(s) importé(s) avec succès !'}), 200

        except Exception as e:
            return jsonify({'error': f'🚨 Erreur lors de l’importation : {str(e)}'}), 500
    else:
        return jsonify({'error': '❌ Format de fichier non pris en charge'}), 400
