# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, request  # ✨ Ajout de redirect et url_for
from app.models import Product, Stock
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure
from app.models import Product, Stock
from flask import jsonify
from app.utils.fetch_selleramp import fetch_selleramp_info

main_bp = Blueprint('main', __name__)
from app import db
depenses_total = 0  # ✅ Valeur par défaut si aucun calcul n'est fait


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main_bp.route('/dashboard')

def dashboard():
    # Récupère les produits scrapés (par ex: ceux qui ont un prix Amazon)
    produits_scrapes = db.session.query(Product).filter(Product.prix_amazon.isnot(None)).all()

    # Calcule la somme des profits
    profit_scrapes_total = sum(p.profit for p in produits_scrapes if p.profit is not None)

    # Nombre de produits scrapés et en stock
    nb_produits_scrapes = len(produits_scrapes)
    nb_produits_stock = db.session.query(Stock).filter(Stock.statut == "Acheté/en stock").count()


    # Récupérer les 30 meilleurs produits en fonction du ROI
    top_roi_items = db.session.query(Product).filter(Product.roi.isnot(None)).order_by(Product.roi.desc()).limit(50).all()

    # Récupérer les 5 derniers produits scrapés
    recent_items = db.session.query(Product).order_by(Product.updated_at.desc()).limit(5).all()

   # Calcul des dépenses
    depenses_total = db.session.query(db.func.sum(Stock.prix_achat)).scalar()
    depenses_total = float(depenses_total) if depenses_total else 0  # ✅ Conversion en float

    # Calcul des recettes (ajoute ici la logique selon ton modèle)
    recettes_total = db.session.query(db.func.sum(Product.profit)).scalar()
    recettes_total = float(recettes_total) if recettes_total else 0  # ✅ Conversion en float

    # Calcul de la balance
    balance_total = recettes_total - depenses_total




    return render_template("dashboard.html",
                        profit_scrapes_total=profit_scrapes_total,
                        nb_produits_scrapes=nb_produits_scrapes,
                        nb_produits_stock=nb_produits_stock,
                        top_roi_items=top_roi_items,
                        recent_items=recent_items,
                        depenses_total=depenses_total,
                        recettes_total=recettes_total,  # ✅ Ajout ici
                        balance_total=balance_total)    # ✅ Ajout ici




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

@main_bp.route('/add_stock', methods=['POST'])
def add_stock():
    try:
        ean = request.form.get('ean')
        magasin = request.form.get('magasin')
        prix_achat = float(request.form.get('prix_achat'))
        quantite = int(request.form.get('quantite'))
        facture_url = request.form.get('facture_url') or None
        statut = "Acheté/en stock"

        print(f"🛒 Ajout de stock - EAN: {ean}, Magasin: {magasin}, Prix: {prix_achat}, Quantité: {quantite}")

        # ✅ Récupération des données SellerAmp
        prix_amazon, roi, profit, sales_estimation, alerts = fetch_selleramp_info(ean, prix_achat)

        if prix_amazon is None:
            return "Erreur : Impossible de récupérer les données SellerAmp.", 500

        # ✅ Insérer en base de données
        new_stock = Stock(
            ean=ean,
            magasin=magasin,
            prix_achat=prix_achat,
            prix_amazon=prix_amazon,
            roi=roi,
            profit=profit,
            sales_estimation=sales_estimation,
            date_achat=request.form.get('date_achat'),
            quantite=quantite,
            facture_url=facture_url,
            statut=statut,
            nom=f"Produit {ean}",  # ⚠️ À remplacer si SellerAmp permet de récupérer le nom
            seuil_alerte=5  # Valeur par défaut
        )

        db.session.add(new_stock)
        db.session.commit()

        print(f"✅ Stock ajouté : {new_stock}")
        return redirect(url_for('main.stock'))

    except Exception as e:
        print(f"❌ Erreur lors de l'ajout de stock : {e}")
        return f"Erreur lors de l'ajout : {str(e)}", 500