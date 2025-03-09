# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, request  # ✨ Ajout de redirect et url_for
from app.models import Product, Stock, ProductKeepa
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure
from app.models import Product, Stock
from flask import jsonify
from app.utils.fetch_selleramp import fetch_selleramp_info
import uuid

main_bp = Blueprint('main', __name__)
from app import db
depenses_total = 0  # ✅ Valeur par défaut si aucun calcul n'est fait


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


@main_bp.route('/analytics')
def analytics():
    """📈 Route de la page analytique."""
    return render_template('analytics.html')


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
        
        # Utilisation de la fonction de scraping pour récupérer les données
        from scraping.scraper import insert_or_update_product
        
        # Récupération des données via la fonction de scraping
        success = insert_or_update_product(nom, ean, prix_achat, None, None, None, None)
        
        if not success:
            return "Erreur : Impossible de récupérer les données du produit.", 500
            
        # Récupération des données mises à jour
        product = db.session.query(ProductKeepa).filter_by(ean=ean).first()
        
        if not product:
            return "Erreur : Produit non trouvé après scraping.", 500

        # Création de l'entrée dans le stock
        new_stock = Stock(
            group_id=str(uuid.uuid4()),  # Génération d'un nouveau UUID
            ean=ean,
            nom=nom,
            magasin=magasin,
            prix_achat=prix_achat,
            prix_amazon=product.prix_amazon,
            roi=product.roi,
            profit=product.profit,
            sales_estimation=product.sales_estimation,
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
    
    
# app/routes/main.py
from app.utils.fetch_selleramp import fetch_selleramp_info

def add_product_to_stock(ean, magasin, prix_achat, quantite, facture_url=None):
    """Ajoute un produit dans le stock en récupérant les données depuis SellerAmp."""
    try:
        # Récupérer les données SellerAmp
        prix_amazon, roi, profit, sales_estimation = fetch_selleramp_info(ean, prix_achat)

        if not prix_amazon:
            raise ValueError(f"Impossible de récupérer les données SellerAmp pour l'EAN {ean}")

        # Insérer le produit dans la base de données
        insert_into_stock_db(ean, magasin, prix_achat, prix_amazon, roi, profit, sales_estimation, quantite, facture_url)
        print(f"✅ Produit ajouté dans le stock avec l'EAN {ean}")

    except Exception as e:
        print(f"❌ Erreur lors de l'ajout du produit: {e}")

def insert_into_stock_db(ean, magasin, prix_achat, prix_amazon, roi, profit, sales_estimation, quantite, facture_url):
    """Insère les informations dans la table stock."""
    try:
        cursor.execute("""
            INSERT INTO stock (ean, magasin, prix_achat, prix_amazon, roi, profit, sales_estimation, quantite, facture_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (ean, magasin, prix_achat, prix_amazon, roi, profit, sales_estimation, quantite, facture_url))
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"⚠️ Erreur lors de l'insertion dans la base de données: {e}")

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
            quantity = int(request.form.get('quantity', 0))
            if quantity <= 0 or quantity > stock_item.quantite:
                return jsonify({'success': False, 'message': 'Quantité invalide'}), 400

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
                sales_estimation=stock_item.sales_estimation,
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
