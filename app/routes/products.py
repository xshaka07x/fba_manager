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

@products_bp.route('/update_price/<int:product_id>', methods=['POST'])
def update_price(product_id):
    try:
        product = db.session.query(Product).get(product_id)
        if not product:
            return jsonify({"success": False, "message": "Produit introuvable."}), 404

        prix_retail = float(request.json.get("prix_retail", product.prix_retail))
        prix_amazon = float(request.json.get("prix_amazon", product.prix_amazon))

        # ✅ Enregistrement dans l'historique
        historique = HistoriquePrix(produit_id=product_id, prix_retail=prix_retail, prix_amazon=prix_amazon)
        db.session.add(historique)

        # ✅ Mise à jour des prix du produit
        product.prix_retail = prix_retail
        product.prix_amazon = prix_amazon
        db.session.commit()

        return jsonify({"success": True, "message": "Prix mis à jour et enregistré dans l'historique."}), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur : {str(e)}"}), 500

@products_bp.route('/add', methods=['POST'])
def add_product():
    try:
        data = request.json
        new_product = Product(
            nom=data.get("nom"),
            ean=data.get("ean"),
            prix_retail=float(data.get("prix_retail", 0)),
            prix_amazon=float(data.get("prix_amazon", 0))
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify({"success": True, "message": "Produit ajouté avec succès !"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": f"Erreur : {str(e)}"}), 500


@products_bp.route('/historique_prix/<int:product_id>', methods=['GET'])
def historique_prix(product_id):
    historique = db.session.query(HistoriquePrix).filter_by(produit_id=product_id).order_by(HistoriquePrix.date_enregistrement).all()

    data = [
        {
            "date": h.date_enregistrement.strftime("%d/%m/%Y"),
            "prix_retail": h.prix_retail,
            "prix_amazon": h.prix_amazon or 0
        } 
        for h in historique
    ]

    return jsonify(data)

@products_bp.route('/historique/<int:produit_id>')
def historique_prix_view(produit_id):  # <-- Nouveau nom ici
    historique = HistoriquePrix.query.filter_by(produit_id=produit_id).order_by(HistoriquePrix.date_enregistrement.desc()).all()

    data = [
        {
            "prix_retail": item.prix_retail,
            "prix_amazon": item.prix_amazon,
            "date": item.date_enregistrement.strftime("%d/%m/%Y %H:%M")
        }
        for item in historique
    ]

    return jsonify(data)


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
