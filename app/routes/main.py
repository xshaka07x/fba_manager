# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for  # ✨ Ajout de redirect et url_for
from app.models import Product
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure
from app.models import Product, Stock

main_bp = Blueprint('main', __name__)
from app import db


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main_bp.route('/dashboard')
def dashboard():
    # Récupération des 5 derniers produits scrapés
    recent_items = db.session.query(Product).order_by(Product.updated_at.desc()).limit(5).all()

    # Récupération des 10 meilleurs ROI
    top_roi_items = db.session.query(Product).order_by(Product.roi.desc()).limit(10).all()

    # Formatage commun pour les deux listes
    def format_items(items):
        return [{
            'nom': item.nom,
            'ean': item.ean,
            'prix_retail': item.prix_retail,
            'prix_amazon': item.prix_amazon,
            'roi': item.roi,
            'profit': item.profit,
            'sales_estimation': item.sales_estimation,
            'url': item.url,
            'updated_at': item.updated_at.strftime("%d/%m/%y") if item.updated_at else 'N/A'
        } for item in items]

    return render_template('dashboard.html',
                           recent_items=format_items(recent_items),
                           top_roi_items=format_items(top_roi_items))



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


@main_bp.route('/update_stock/<int:stock_id>', methods=['POST'])
def update_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        stock_item.statut = request.form.get('statut')
        db.session.commit()
    return redirect(url_for('main.stock'))

