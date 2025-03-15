# app/models.py
from datetime import datetime
from app import db
from sqlalchemy import DECIMAL

class Product(db.Model):
    __tablename__ = "products"  # ✅ Vérifie bien que c'est "products"
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    ean = db.Column(db.String(50), unique=True, nullable=False)
    prix_retail = db.Column(db.Float, nullable=False)
    prix_amazon = db.Column(db.Float, nullable=True)
    roi = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)
    sales_estimation = db.Column(db.Integer, nullable=True)
    url = db.Column(db.String(500), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    historique_prix = db.relationship("HistoriquePrix", backref="produit", lazy="dynamic", cascade="all, delete")



class HistoriquePrix(db.Model):
    __tablename__ = "historique_prix"

    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    prix_retail = db.Column(db.Float, nullable=False)
    prix_amazon = db.Column(db.Float, nullable=True)
    date_enregistrement = db.Column(db.DateTime, default=datetime.utcnow)


class Stock(db.Model):
    __tablename__ = "stock"

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(36), nullable=False)  # UUID pour grouper les parties d'un même produit
    parent_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=True)  # Pour tracer la relation parent-enfant
    ean = db.Column(db.String(13), nullable=False)
    magasin = db.Column(db.String(100), nullable=False)
    prix_achat = db.Column(db.Float, nullable=False)
    prix_amazon = db.Column(db.Float, nullable=True)
    roi = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)
    date_achat = db.Column(db.DateTime, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    facture_url = db.Column(db.String(255), nullable=True)
    statut = db.Column(db.String(50), nullable=False, default="Acheté/en stock")
    nom = db.Column(db.String(255), nullable=False)
    seuil_alerte = db.Column(db.Integer, default=5)

    # Relation pour les entrées enfants
    children = db.relationship('Stock', backref=db.backref('parent', remote_side=[id]),
                             cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Stock {self.nom} - {self.ean} - {self.magasin}>"

class ProductKeepa(db.Model):
    __tablename__ = 'products_keepa'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    ean = db.Column(db.String(13), nullable=False)
    prix_retail = db.Column(db.Float, nullable=False)
    prix_amazon = db.Column(db.Float, nullable=True)
    difference = db.Column(db.Float, nullable=True)
    profit = db.Column(db.Float, nullable=True)
    roi = db.Column(db.Float, nullable=True)
    url = db.Column(db.String(255), nullable=False)
    sales_estimation = db.Column(db.Integer, nullable=True, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ProductKeepa {self.nom}>'

class Magasin(db.Model):
    __tablename__ = "magasin"
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True, nullable=False)
    adresse = db.Column(db.String(255))
    ville = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Magasin {self.nom}>"

class Scan(db.Model):
    __tablename__ = 'scan'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(255), nullable=False)
    ean = db.Column(db.String(13), unique=True, nullable=False)
    prix_retail = db.Column(db.Float, nullable=False)
    prix_amazon = db.Column(db.Float)
    difference = db.Column(db.Float)
    profit = db.Column(db.Float)
    url = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    roi = db.Column(db.Float)

    def __repr__(self):
        return f'<Scan {self.nom}>'

class Travel(db.Model):
    """Modèle pour la gestion des déplacements"""
    __tablename__ = 'travels'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    person = db.Column(db.String(50), nullable=False)
    kilometers = db.Column(DECIMAL(10, 1), nullable=True)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'person': self.person,
            'kilometers': float(self.kilometers) if self.kilometers else None,
            'comment': self.comment,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<Travel {self.date} - {self.person}>'
