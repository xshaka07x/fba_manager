# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from dotenv import load_dotenv
import os

db = SQLAlchemy()

def create_app():
    """🚀 Crée et configure l'application Flask."""
    # 🔒 Chargement des variables d'environnement
    load_dotenv()

    app = Flask(__name__)
    CORS(app)

    # 🔗 Configuration de la BDD
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL', 
        'mysql+pymysql://root:GdZwRdaftiYhhrbXyyVQNFynnKAUDymv@mysql.railway.internal/railway'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # 🌐 Enregistrement des Blueprints
    from app.routes.main import main_bp
    from app.routes.products import products_bp
    from app.routes.analytics import analytics_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    return app
