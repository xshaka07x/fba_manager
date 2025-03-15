import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from app.config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    CORS(app)
    db.init_app(app)

    with app.app_context():
        from app.routes.main import main_bp  # ✅ Lazy import pour éviter les problèmes circulaires
        from app.routes.products import products_bp
        from app.routes.analytics import analytics_bp

        app.register_blueprint(main_bp)  # ✅ Ne l'enregistrer qu'une seule fois
        app.register_blueprint(products_bp, url_prefix='/products')
        app.register_blueprint(analytics_bp, url_prefix='/analytics')

    return app
