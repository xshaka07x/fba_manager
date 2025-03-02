# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, request  # ✨ Ajout de redirect et url_for
from app.models import Product, Stock
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure
from app.models import Product, Stock
from flask import jsonify


main_bp = Blueprint('main', __name__)
from app import db


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main.route('/dashboard')
def dashboard():
    # Récupère les produits scrapés (par ex: ceux qui ont un prix Amazon)
    produits_scrapes = db.session.query(Product).filter(Product.prix_amazon.isnot(None)).all()

    # Calcule la somme des profits
    profit_scrapes_total = sum(p.profit for p in produits_scrapes if p.profit is not None)

    # Nombre de produits scrapés et en stock
    nb_produits_scrapes = len(produits_scrapes)
    nb_produits_stock = db.session.query(Product).filter(Product.statut == "Acheté/en stock").count()

    # Récupérer les 30 meilleurs produits en fonction du ROI
    top_roi_items = db.session.query(Product).filter(Product.roi.isnot(None)).order_by(Product.roi.desc()).limit(30).all()

    # Récupérer les 5 derniers produits scrapés
    recent_items = db.session.query(Product).order_by(Product.updated_at.desc()).limit(5).all()

    return render_template("dashboard.html", 
                           profit_scrapes_total=profit_scrapes_total,
                           nb_produits_scrapes=nb_produits_scrapes,
                           nb_produits_stock=nb_produits_stock,
                           top_roi_items=top_roi_items,
                           recent_items=recent_items)


@main_bp.route('/edit_stock/<int:stock_id>', methods=['POST'])
def edit_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        stock_item.nom = request.form.get('nom')
        stock_item.ean = request.form.get('ean')
        stock_item.magasin = request.form.get('magasin')
        stock_item.prix_achat = float(request.form.get('prix_achat'))
        stock_item.date_achat = datetime.strptime(request.form.get('date_achat'), '%Y-%m-%d')
        stock_item.quantite = int(request.form.get('quantite'))
        stock_item.facture_url = request.form.get('facture_url')
        db.session.commit()
    return redirect(url_for('main.stock'))


@main_bp.route('/delete_stock/<int:stock_id>', methods=['POST'])
def delete_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        db.session.delete(stock_item)
        db.session.commit()
    return redirect(url_for('main.stock'))


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
    from app.models import Product, Stock  # ✅ Vérifie que Stock est bien importé

    stock_items = db.session.query(Stock).order_by(Stock.date_achat.desc()).all()

    return render_template('stock.html', stock_items=stock_items)


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

# ✅ Nouvelle route pour l'ajout de produit
@main_bp.route('/add_stock', methods=['POST'])
def add_stock():
    try:
        ean = request.form.get('ean')
        magasin = request.form.get('magasin')
        prix_achat = float(request.form.get('prix_achat'))
        date_achat = datetime.strptime(request.form.get('date_achat'), "%Y-%m-%d")
        quantite = int(request.form.get('quantite'))
        facture_url = request.form.get('facture_url') or None

        print(f"DEBUG - EAN: {ean}, Magasin: {magasin}, Prix: {prix_achat}, Date: {date_achat}, Quantité: {quantite}, Facture: {facture_url}")

        nouveau_stock = Stock(
            ean=ean,
            magasin=magasin,
            prix_achat=prix_achat,
            date_achat=date_achat,
            quantite=quantite,
            facture_url=facture_url
        )

        db.session.add(nouveau_stock)
        db.session.commit()

        return redirect(url_for('main.stock'))

    except Exception as e:
        print(f"ERROR - Impossible d'ajouter l'article : {str(e)}")
        return f"Erreur lors de l'ajout : {str(e)}", 500

