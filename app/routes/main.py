# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for  # ✨ Ajout de redirect et url_for
from app.models import Product
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure


main_bp = Blueprint('main', __name__)
from app import db


@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main_bp.route('/dashboard')
def dashboard():
    # Récupération des 5 derniers produits scrapés triés par date
    recent_items = db.session.query(Product).order_by(Product.updated_at.desc()).limit(5).all()

    # Formatage des données pour éviter les erreurs dans le template
    formatted_items = []
    for item in recent_items:
        formatted_items.append({
            'nom': item.nom,
            'ean': item.ean,
            'prix_retail': item.prix_retail,
            'prix_amazon': item.prix_amazon,
            'roi': item.roi,
            'profit': item.profit,
            'sales_estimation': item.sales_estimation,
            'url': item.url,
            'updated_at': item.updated_at.strftime("%d/%m/%y") if item.updated_at else 'N/A'
        })

    return render_template('dashboard.html', recent_items=formatted_items)





@main_bp.route('/settings')
def settings():
    """⚙️ Route des paramètres de l'application."""
    return render_template('settings.html')


@main_bp.route('/analytics')
def analytics():
    """📈 Route de la page analytique."""
    return render_template('analytics.html')




