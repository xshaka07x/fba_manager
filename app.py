# app.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.routes.main import main_bp  # Import des routes

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'  # Remplace si nécessaire
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Enregistrement du Blueprint
    app.register_blueprint(main_bp)

    return app

# 👇 Expose 'app' pour Gunicorn
app = create_app()
