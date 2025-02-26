# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for  # ✨ Ajout de redirect et url_for
from app.models import Product
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure


main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main_bp.route('/dashboard')
def dashboard():
    recent_items = Product.query.order_by(Product.updated_at.desc()).limit(5).all()


    
    top_roi_items = Product.query.order_by(Product.roi.desc()).limit(10).all()
    
    formatted_items = [
        {
            "name": item.nom,
            "sku": item.ean,
            "prix_retail": item.prix_retail,
            "prix_amazon": item.prix_amazon,  # ✅ Ajouté ici
            "roi": item.roi,
            "profit": item.profit,
            "sales_estimation": item.sales_estimation,
            "url": item.url,
            # ✅ On ajoute une heure ici
            "scanned_at": datetime.strptime(item.updated_at + timedelta(hours=1), "%Y-%m-%d %H:%M:%S") if isinstance(item.updated_at, str) else item.updated_at
        }
        for item in recent_items
    ]

    return render_template('dashboard.html',top_roi_items=top_roi_items, recent_items=formatted_items)




@main_bp.route('/settings')
def settings():
    """⚙️ Route des paramètres de l'application."""
    return render_template('settings.html')


@main_bp.route('/analytics')
def analytics():
    """📈 Route de la page analytique."""
    return render_template('analytics.html')
