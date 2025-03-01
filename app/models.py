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
    nom = db.Column(db.String(255), nullable=False)
    ean = db.Column(db.String(13), nullable=False, unique=True)
    magasin = db.Column(db.String(100), nullable=False)
    prix_achat = db.Column(db.Float, nullable=False)
    date_achat = db.Column(db.DateTime, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    facture_url = db.Column(db.String(255), nullable=True)
    statut = db.Column(db.String(50), nullable=False, default="Acheté/en stock")
    seuil_alerte = db.Column(db.Integer, default=5)  # ✅ Ajout d'un seuil d'alerte


    def __repr__(self):
        return f"<Stock {self.ean} - {self.magasin}>"
    
class HistoriquePrix(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)  # Assure-toi que c'est bien "product"
    prix_retail = db.Column(db.Float, nullable=False)
    prix_amazon = db.Column(db.Float, nullable=True)
    date_enregistrement = db.Column(db.DateTime, default=datetime.utcnow)

    produit = db.relationship("Product", backref=db.backref("historique", lazy=True))
