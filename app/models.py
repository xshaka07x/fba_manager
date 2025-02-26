# app/models.py
from app import db  # ✅ Après correction app.py, cette ligne fonctionnera
from datetime import datetime

class Product(db.Model):
    __tablename__ = 'products'  # ✅ Forcer le nom exact de la table

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    ean = db.Column(db.String(50), unique=True)
    prix_retail = db.Column(db.Float)
    prix_amazon = db.Column(db.Float)
    roi = db.Column(db.Float)
    profit = db.Column(db.Float)
    sales_estimation = db.Column(db.String(50))
    alerts = db.Column(db.String(255))
    url = db.Column(db.String(500))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Product {self.nom} - EAN: {self.ean}>'

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)  # ✅ Colonne "nom" ajoutée
    ean = db.Column(db.String(20), nullable=False)
    magasin = db.Column(db.String(100), nullable=False)
    prix_achat = db.Column(db.Float, nullable=False)
    date_achat = db.Column(db.DateTime, default=datetime.utcnow)
    quantite = db.Column(db.Integer, nullable=False)
    facture_url = db.Column(db.String(255), nullable=True)
    statut = db.Column(db.String(50), default='Acheté/en stock')

    def __repr__(self):
        return f"<Stock {self.ean} - {self.magasin}>"