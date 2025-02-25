# app/routes/main.py
from flask import Blueprint, render_template
from app.models import Product
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    produits = Product.query.order_by(Product.id.desc()).limit(10).all()  # Derniers 10 produits
    return render_template('index.html', produits=produits)

@main_bp.route('/dashboard')
def dashboard():
    """🏠 Route du dashboard principal avec les derniers produits ajoutés."""
    recent_items = Product.query.order_by(Product.id.desc()).limit(5).all()
    recent_items_data = [
        {
            "name": item.nom,
            "sku": item.ean,
            "price": item.prix_retail,
            "scanned_at": datetime.now().strftime("%Y-%m-%d")
        } for item in recent_items
    ]
    return render_template('dashboard.html', recent_items=recent_items_data)



@main_bp.route('/settings')
def settings():
    """⚙️ Route des paramètres de l'application."""
    return render_template('settings.html')


@main_bp.route('/analytics')
def analytics():
    """📈 Route de la page analytique."""
    return render_template('analytics.html')
