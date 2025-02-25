# app/routes/main.py
from flask import Blueprint, render_template
from app.models import Product
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    produits = Product.query.order_by(Product.id.desc()).limit(10).all()  # Derniers 10 produits
    return render_template('dashboard.html', produits=produits)

@main_bp.route('/dashboard')
def dashboard():
    # Récupérer les 10 derniers produits par date de mise à jour
    recent_items = Product.query.order_by(Product.updated_at.desc()).limit(10).all()

    # Adapter les données pour le template avec les nouvelles colonnes
    formatted_items = [
        {
            "name": item.nom,
            "sku": item.ean,
            "prix_retail": item.prix_retail,
            "roi": f"{item.roi:.2f}%",
            "profit": f"${item.profit:.2f}",
            "sales_estimation": item.sales_estimation,
            "url": item.url,
            "scanned_at": item.updated_at.strftime("%d/%m/%Y %H:%M")
        }
        for item in recent_items
    ]

    return render_template('dashboard.html', recent_items=formatted_items)




@main_bp.route('/settings')
def settings():
    """⚙️ Route des paramètres de l'application."""
    return render_template('settings.html')


@main_bp.route('/analytics')
def analytics():
    """📈 Route de la page analytique."""
    return render_template('analytics.html')
