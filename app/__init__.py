import pymysql
pymysql.install_as_MySQLdb()

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.config import Config

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        from app.routes.main import main_bp  # Lazy import pour éviter les problèmes circulaires
        app.register_blueprint(main_bp)
        
    from app.routes.products import products_bp
    from app.routes.analytics import analytics_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(products_bp, url_prefix='/products')
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    return app
