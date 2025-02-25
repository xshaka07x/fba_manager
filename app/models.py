# app/models.py
from app import db  # ✅ Après correction app.py, cette ligne fonctionnera

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
