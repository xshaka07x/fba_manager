# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from app.models import Product, Stock, ProductKeepa, Magasin, Travel
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure
from flask import jsonify
from app.utils.fetch_selleramp import fetch_selleramp_info
import uuid
from scraping.scraper import insert_or_update_product
from app.utils.fetch_keepa import get_keepa_data

main_bp = Blueprint('main', __name__)
from app import db
depenses_total = 0  # ✅ Valeur par défaut si aucun calcul n'est fait

# Import des fonctions après la création du Blueprint
from app.utils.fetch_keepa import get_keepa_data
from scraping.scraper import insert_or_update_product

@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main_bp.route('/dashboard')
def dashboard():
    # Récupération des produits de la table products_keepa
    nb_produits_keepa = db.session.query(ProductKeepa).count()
    
    # Calcul du profit total des produits scrapés
    profit_scrapes_total = db.session.query(db.func.sum(ProductKeepa.profit)).scalar() or 0
    
    # Calcul de la quantité totale en stock
    total_quantite_stock = db.session.query(db.func.sum(Stock.quantite)).filter(Stock.statut == "Acheté/en stock").scalar() or 0
    
    # Calcul du profit potentiel du stock
    stock_items = db.session.query(Stock).filter(Stock.statut == "Acheté/en stock").all()
    profit_stock_total = sum((item.prix_amazon - item.prix_achat) * item.quantite if item.prix_amazon else 0 for item in stock_items)
    
    # Calcul des dépenses (prix_achat * quantité pour tous les produits en stock)
    depenses_total = db.session.query(db.func.sum(Stock.prix_achat * Stock.quantite)).scalar() or 0
    
    # Calcul des recettes (prix_amazon * quantité pour les produits vendus)
    stock_vendus = db.session.query(Stock).filter(Stock.statut == "Vendu").all()
    recettes_total = sum((item.prix_amazon * item.quantite if item.prix_amazon else 0) for item in stock_vendus)
    
    # Top 50 produits avec le meilleur ROI
    top_roi_items = db.session.query(ProductKeepa).filter(
        ProductKeepa.roi.isnot(None),
        ProductKeepa.roi > 0
    ).order_by(ProductKeepa.roi.desc()).limit(50).all()
    
    # 5 derniers produits scrapés
    recent_items = db.session.query(ProductKeepa).order_by(ProductKeepa.updated_at.desc()).limit(5).all()

    return render_template("dashboard.html",
                        profit_scrapes_total=profit_scrapes_total,
                        profit_stock_total=profit_stock_total,
                        nb_produits_keepa=nb_produits_keepa,
                        total_quantite_stock=total_quantite_stock,
                        top_roi_items=top_roi_items,
                        recent_items=recent_items,
                        depenses_total=depenses_total,
                        recettes_total=recettes_total)




@main_bp.route('/delete_stock/<int:stock_id>', methods=['POST'])
def delete_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        db.session.delete(stock_item)
        db.session.commit()
    return redirect(url_for('main.stock'))

@main_bp.route('/edit_stock/<int:stock_id>', methods=['GET', 'POST'])
def edit_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if request.method == 'POST':
        stock_item.nom = request.form.get('nom')
        stock_item.magasin = request.form.get('magasin')
        stock_item.prix_achat = float(request.form.get('prix_achat'))
        stock_item.quantite = int(request.form.get('quantite'))
        db.session.commit()
        return redirect(url_for('main.stock'))
    return render_template('edit_stock.html', stock_item=stock_item)



@main_bp.route('/settings')
def settings():
    """⚙️ Route des paramètres de l'application."""
    return render_template('settings.html')


@main_bp.route('/organisation')
def organisation():
    """📈 Route de la page d'organisation."""
    return render_template('organisation.html')


@main_bp.route('/stock')
def stock():
    """📦 Route de la page de gestion du stock."""
    magasins = db.session.query(Magasin).all()
    stock_items = db.session.query(Stock).order_by(Stock.date_achat.desc()).all()
    return render_template('stock.html', stock_items=stock_items, magasins=magasins)


@main_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # Recherche dans les produits
    products = db.session.query(Product).filter(Product.nom.ilike(f"%{query}%")).all()

    # Recherche dans le stock
    stocks = db.session.query(Stock).filter(Stock.nom.ilike(f"%{query}%")).all()

    # Formatage des résultats
    results = [
        {"type": "Produit", "nom": p.nom, "url": url_for('products.show_products')} for p in products
    ] + [
        {"type": "Stock", "nom": s.nom, "url": url_for('main.stock')} for s in stocks
    ]

    return jsonify(results)

@main_bp.route('/stock_alerts', methods=['GET'])
def stock_alerts():
    produits_alertes = db.session.query(Stock).filter(Stock.quantite <= Stock.seuil_alerte).all()
    
    data = [
        {
            "nom": produit.nom,
            "quantite": produit.quantite,
            "seuil": produit.seuil_alerte
        } for produit in produits_alertes
    ]
    
    return jsonify(data)



@main_bp.route('/update_stock/<int:stock_id>', methods=['POST'])
def update_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        stock_item.statut = request.form.get('statut')
        db.session.commit()
    return redirect(url_for('main.stock'))

@main_bp.route('/add_stock', methods=['POST'])
def add_stock():
    try:
        # Récupération des données du formulaire
        nom = request.form.get('nom')
        ean = request.form.get('ean')
        magasin = request.form.get('magasin')
        prix_achat = float(request.form.get('prix_achat'))
        quantite = int(request.form.get('quantite'))
        facture_url = request.form.get('facture_url') or None
        
        # Récupération des données Keepa
        keepa_data = get_keepa_data(ean, prix_achat)
        if not keepa_data:
            return "Erreur : Impossible de récupérer les données Keepa.", 500
            
        prix_amazon = keepa_data.get('prix_amazon', 0)
        difference = keepa_data.get('difference', 0)
        profit = keepa_data.get('profit', 0)
        
        # Calcul du ROI comme dans scraper.py
        roi = (profit * 100 / prix_achat) if prix_achat > 0 else 0
        
        # Création de l'entrée dans le stock
        new_stock = Stock(
            group_id=str(uuid.uuid4()),  # Génération d'un nouveau UUID
            ean=ean,
            nom=nom,
            magasin=magasin,
            prix_achat=prix_achat,
            prix_amazon=prix_amazon,
            roi=roi,
            profit=profit,
            date_achat=datetime.now(),
            quantite=quantite,
            facture_url=facture_url,
            statut="Acheté/en stock"
        )

        db.session.add(new_stock)
        db.session.commit()

        return redirect(url_for('main.stock'))

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'ajout de stock : {e}")
        return f"Erreur lors de l'ajout : {str(e)}", 500
    
    
@main_bp.route('/scrap')
def scrap():
    products = ProductKeepa.query.order_by(ProductKeepa.updated_at.desc()).all()
    return render_template('scrap.html', products=products)

@main_bp.route('/update_stock_quantity', methods=['POST'])
def update_stock_quantity():
    try:
        stock_id = request.form.get('stockId')
        new_status = request.form.get('newStatus')
        quantity_type = request.form.get('quantityType')
        
        stock_item = Stock.query.get(stock_id)
        if not stock_item:
            return jsonify({'success': False, 'message': 'Article non trouvé'}), 404

        if quantity_type == 'all':
            # Mise à jour du statut pour tout le stock
            stock_item.statut = new_status
            db.session.commit()
            return jsonify({'success': True})
        
        elif quantity_type == 'partial':
            try:
                quantity = int(request.form.get('quantity', 0))
            except ValueError:
                return jsonify({'success': False, 'message': 'La quantité doit être un nombre entier'}), 400

            # Validation stricte de la quantité
            if quantity < 1:
                return jsonify({'success': False, 'message': 'La quantité doit être au minimum 1'}), 400
            if quantity >= stock_item.quantite:
                return jsonify({'success': False, 
                              'message': f'La quantité doit être inférieure à la quantité en stock ({stock_item.quantite})'}), 400

            # Si c'est le premier split, générer un UUID pour le groupe
            if not stock_item.group_id:
                import uuid
                stock_item.group_id = str(uuid.uuid4())

            # Créer une nouvelle entrée pour la quantité partielle
            new_stock = Stock(
                group_id=stock_item.group_id,  # Même groupe que le parent
                parent_id=stock_item.id,  # Référence au parent
                ean=stock_item.ean,
                magasin=stock_item.magasin,
                prix_achat=stock_item.prix_achat,
                prix_amazon=stock_item.prix_amazon,
                roi=stock_item.roi,
                profit=stock_item.profit,
                date_achat=stock_item.date_achat,
                quantite=quantity,
                facture_url=stock_item.facture_url,
                statut=new_status,
                nom=stock_item.nom,
                seuil_alerte=stock_item.seuil_alerte
            )
            
            # Mettre à jour la quantité de l'article original
            stock_item.quantite -= quantity
            
            db.session.add(new_stock)
            db.session.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/get_product_info/<ean>', methods=['GET'])
def get_product_info(ean):
    """Récupère les informations d'un produit à partir de son EAN."""
    try:
        # Chercher d'abord dans la table ProductKeepa
        product = db.session.query(ProductKeepa).filter_by(ean=ean).first()
        
        if not product:
            # Si pas trouvé, chercher dans la table Product
            product = db.session.query(Product).filter_by(ean=ean).first()
            
        if not product:
            # Si toujours pas trouvé, essayer de récupérer via l'API Keepa
            keepa_data = get_keepa_data(ean, 0)  # prix_retail = 0 car on ne le connaît pas encore
            if keepa_data and keepa_data.get('status') == 'OK':
                return jsonify({
                    'success': True,
                    'nom': keepa_data.get('nom', ''),
                    'ean': ean,
                    'prix_amazon': keepa_data.get('prix_amazon', 0)
                })
            return jsonify({'success': False, 'message': 'Produit non trouvé'})
            
        return jsonify({
            'success': True,
            'nom': product.nom,
            'ean': product.ean,
            'prix_amazon': product.prix_amazon
        })
        
    except Exception as e:
        print(f"Erreur lors de la récupération des informations du produit : {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/add_scanned_stock', methods=['POST'])
def add_scanned_stock():
    """Ajoute un produit scanné au stock."""
    try:
        # Récupération des données du formulaire
        nom = request.form.get('nom')
        ean = request.form.get('ean')
        magasin = request.form.get('magasin')
        prix_achat = float(request.form.get('prix_achat'))
        quantite = int(request.form.get('quantite'))
        
        # Récupération des données Keepa
        keepa_data = get_keepa_data(ean, prix_achat)
        if not keepa_data:
            return "Erreur : Impossible de récupérer les données Keepa.", 500
            
        prix_amazon = keepa_data.get('prix_amazon', 0)
        profit = keepa_data.get('profit', 0)
        roi = (profit * 100 / prix_achat) if prix_achat > 0 else 0
        
        # Création de l'entrée dans le stock
        new_stock = Stock(
            group_id=str(uuid.uuid4()),
            ean=ean,
            nom=nom,
            magasin=magasin,
            prix_achat=prix_achat,
            prix_amazon=prix_amazon,
            roi=roi,
            profit=profit,
            date_achat=datetime.now(),
            quantite=quantite,
            statut="Acheté/en stock"
        )

        db.session.add(new_stock)
        db.session.commit()

        return redirect(url_for('main.stock'))

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'ajout du produit scanné : {e}")
        return f"Erreur lors de l'ajout : {str(e)}", 500

@main_bp.route('/gestion')
def gestion():
    return render_template('gestion.html')

@main_bp.route('/api/travels', methods=['GET'])
def get_travels():
    """Récupère la liste des déplacements"""
    travels = Travel.query.order_by(Travel.date.desc()).all()
    return jsonify([travel.to_dict() for travel in travels])

@main_bp.route('/api/travels', methods=['POST'])
def add_travel():
    """Ajoute un nouveau déplacement"""
    try:
        data = request.get_json()
        new_travel = Travel(
            date=datetime.strptime(data['date'], '%Y-%m-%d'),
            person=data['person'],
            kilometers=data['kilometers'],
            comment=data['comment']
        )
        db.session.add(new_travel)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@main_bp.route('/api/travels/<int:travel_id>', methods=['PUT'])
def update_travel(travel_id):
    """Met à jour un déplacement existant"""
    try:
        travel = Travel.query.get_or_404(travel_id)
        data = request.get_json()
        travel.date = datetime.strptime(data['date'], '%Y-%m-%d')
        travel.person = data['person']
        travel.kilometers = data['kilometers']
        travel.comment = data['comment']
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@main_bp.route('/api/travels/<int:travel_id>', methods=['DELETE'])
def delete_travel(travel_id):
    """Supprime un déplacement"""
    try:
        travel = Travel.query.get_or_404(travel_id)
        db.session.delete(travel)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
