# app/routes/products.py
from flask import Blueprint, render_template, jsonify, request
from app.models import Product, ProductKeepa, Scan
from app import db
import json
import os
from datetime import datetime
import pytz  # 🕒 Pour la gestion du fuseau horaire
from app.utils.fetch_keepa import get_keepa_data  # Import de la fonction get_keepa_data

from datetime import timedelta  # ✅ Pour ajouter une heure

products_bp = Blueprint('products', __name__)
paris_tz = pytz.timezone('Europe/Paris')  # ✅ Fuseau horaire Paris


@products_bp.route('/')
def show_products():
    produits_keepa = ProductKeepa.query.order_by(ProductKeepa.updated_at.desc()).all()
    produits_scan = Scan.query.order_by(Scan.updated_at.desc()).all()

    # 🛑 Debug pour voir ce qu'il y a en BDD
    print(f"🚨 DEBUG: {len(produits_keepa)} produits Keepa trouvés")
    print(f"🚨 DEBUG: {len(produits_scan)} produits Scan trouvés")

    return render_template('products.html', 
                         produits_keepa=produits_keepa,
                         produits_scan=produits_scan)


@products_bp.route('/scan_barcode', methods=['POST'])
def scan_barcode():
    try:
        ean = request.json.get('ean')
        prix_retail = request.json.get('prix_retail')
        
        if not ean:
            return jsonify({'success': False, 'message': 'Code-barres non fourni'}), 400
            
        if not prix_retail:
            return jsonify({'success': False, 'message': 'Prix retail non fourni'}), 400

        # Vérifier si le produit existe déjà dans la table scan
        existing_product = Scan.query.filter_by(ean=ean).first()
        if existing_product:
            return jsonify({
                'success': False, 
                'message': f'Ce produit (EAN: {ean}) existe déjà dans la base de données',
                'data': {
                    'nom': existing_product.nom,
                    'prix_retail': existing_product.prix_retail,
                    'prix_amazon': existing_product.prix_amazon
                }
            }), 400

        # Récupérer les données Keepa
        print(f"Tentative de récupération des données Keepa pour l'EAN: {ean}")
        keepa_data = get_keepa_data(ean, prix_retail)
        if not keepa_data:
            return jsonify({
                'success': False, 
                'message': f'Impossible de récupérer les données Keepa pour l\'EAN: {ean}. Veuillez vérifier que le code-barres est correct.'
            }), 400

        # Vérifier si le prix Amazon n'est pas anormalement élevé
        prix_amazon = keepa_data.get('prix_amazon', 0)
        if prix_amazon > (float(prix_retail) * 40):
            return jsonify({
                'success': False,
                'message': f'Prix Amazon anormalement élevé ({prix_amazon}€) par rapport au prix retail ({prix_retail}€). Possible erreur de données.',
                'data': {
                    'prix_retail': prix_retail,
                    'prix_amazon': prix_amazon,
                    'ean': ean,
                    'nom': keepa_data.get('nom', 'Nom non trouvé')
                }
            }), 400

        # Créer une nouvelle entrée dans la table scan
        new_scan = Scan(
            nom=keepa_data.get('nom', 'Nom non trouvé'),
            ean=ean,
            prix_retail=keepa_data.get('prix_retail', 0),
            prix_amazon=keepa_data.get('prix_amazon', 0),
            difference=keepa_data.get('difference', 0),
            profit=keepa_data.get('profit', 0),
            url=keepa_data.get('url', ''),
            roi=keepa_data.get('roi', 0)
        )

        db.session.add(new_scan)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Produit ajouté avec succès',
            'data': {
                'nom': new_scan.nom,
                'prix_retail': new_scan.prix_retail,
                'prix_amazon': new_scan.prix_amazon,
                'roi': new_scan.roi
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


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
        return jsonify({'error': 'Aucun fichier trouve'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Aucun fichier selectionne'}), 400

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
                    product.updated_at = datetime.now(paris_tz)
                    db.session.add(product)
                    inserted_count += 1

            db.session.commit()
            return jsonify({'message': f'{inserted_count} produit(s) importe(s) avec succes!'}), 200

        except Exception as e:
            return jsonify({'error': f'Erreur lors de l\'importation : {str(e)}'}), 500
    else:
        return jsonify({'error': 'Format de fichier non pris en charge'}), 400
