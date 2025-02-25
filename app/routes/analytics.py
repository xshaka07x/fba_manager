# app/routes/analytics.py
from flask import Blueprint, render_template

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics')
def analytics():
    """📈 Page d’analyse des données produits."""
    return render_template('analytics.html')
