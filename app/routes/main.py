# app/routes/main.py
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from app.models import Product, Stock, ProductKeepa, Magasin, Travel, Todo, Top100
from datetime import datetime
from datetime import timedelta  # ✅ Pour ajouter une heure
from flask import jsonify
from app.utils.fetch_selleramp import fetch_selleramp_info
import uuid
from scraping.scraper import insert_or_update_product
from app.utils.fetch_keepa import get_keepa_data
from sqlalchemy import extract  # Ajout de l'import manquant
import os

main_bp = Blueprint('main', __name__)
from app import db
depenses_total = 0  # ✅ Valeur par défaut si aucun calcul n'est fait

# Import des fonctions après la création du Blueprint
from app.utils.fetch_keepa import get_keepa_data
from scraping.scraper import insert_or_update_product

@main_bp.route('/')
def index():
    return redirect(url_for('main.dashboard'))  # 🚀 Redirection vers /dashboard

@main_bp.route('/dashboard')
def dashboard():
    # Calcul des dépenses (prix_achat * quantité pour tous les produits)
    depenses_total = db.session.query(db.func.sum(Stock.prix_achat * Stock.quantite)).scalar() or 0
    
    # Calcul des recettes (prix_amazon * quantité pour les produits vendus)
    stock_vendus = db.session.query(Stock).filter(Stock.statut == "Vendu").all()
    recettes_total = sum((item.prix_amazon * item.quantite if item.prix_amazon else 0) for item in stock_vendus)
    
    # Statistiques des produits en stock (chez nous)
    produits_en_stock = db.session.query(Stock).filter(Stock.statut == "Acheté/en stock").all()
    nb_produits_en_stock = sum(item.quantite for item in produits_en_stock)
    profit_potentiel_stock = 0
    for item in produits_en_stock:
        if item.prix_amazon:
            # Calcul des frais FBA
            frais_vente = item.prix_amazon * 0.13  # 13% du prix de vente
            frais_digital = 0.25
            frais_gestion = frais_vente + frais_digital
            frais_expedition = 5.87  # Tarif d'expédition de base
            frais_stockage = 0.10  # Coût de stockage mensuel par unité
            frais_totaux = frais_gestion + frais_expedition + frais_stockage
            tva_frais = frais_totaux * 0.20
            
            # Calcul du profit en tenant compte des frais FBA
            profit_unitaire = item.prix_amazon - item.prix_achat - frais_totaux - tva_frais
            profit_potentiel_stock += profit_unitaire * item.quantite
    
    # Statistiques des produits chez Amazon
    produits_amazon = db.session.query(Stock).filter(Stock.statut == "Chez Amazon").all()
    nb_produits_amazon = sum(item.quantite for item in produits_amazon)
    profit_potentiel_amazon = 0
    for item in produits_amazon:
        if item.prix_amazon:
            # Calcul des frais FBA
            frais_vente = item.prix_amazon * 0.13
            frais_digital = 0.25
            frais_gestion = frais_vente + frais_digital
            frais_expedition = 5.87
            frais_stockage = 0.10
            frais_totaux = frais_gestion + frais_expedition + frais_stockage
            tva_frais = frais_totaux * 0.20
            
            profit_unitaire = item.prix_amazon - item.prix_achat - frais_totaux - tva_frais
            profit_potentiel_amazon += profit_unitaire * item.quantite
    
    # Statistiques des produits vendus
    produits_vendus = db.session.query(Stock).filter(Stock.statut == "Vendu").all()
    nb_produits_vendus = sum(item.quantite for item in produits_vendus)
    profit_produits_vendus = 0
    for item in produits_vendus:
        if item.prix_amazon:
            frais_vente = item.prix_amazon * 0.13
            frais_digital = 0.25
            frais_gestion = frais_vente + frais_digital
            frais_expedition = 5.87
            frais_stockage = 0.10
            frais_totaux = frais_gestion + frais_expedition + frais_stockage
            tva_frais = frais_totaux * 0.20
            
            profit_unitaire = item.prix_amazon - item.prix_achat - frais_totaux - tva_frais
            profit_produits_vendus += profit_unitaire * item.quantite
    
    # Top 50 produits avec le meilleur ROI
    top_roi_items = db.session.query(ProductKeepa).filter(
        ProductKeepa.roi.isnot(None),
        ProductKeepa.roi > 0
    ).order_by(ProductKeepa.roi.desc()).limit(50).all()
    
    return render_template("dashboard.html",
                        nb_produits_en_stock=nb_produits_en_stock,
                        profit_potentiel_stock=profit_potentiel_stock,
                        nb_produits_amazon=nb_produits_amazon,
                        profit_potentiel_amazon=profit_potentiel_amazon,
                        nb_produits_vendus=nb_produits_vendus,
                        profit_produits_vendus=profit_produits_vendus,
                        top_roi_items=top_roi_items,
                        depenses_total=depenses_total,
                        recettes_total=recettes_total)




@main_bp.route('/delete_stock/<int:stock_id>', methods=['POST'])
def delete_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        db.session.delete(stock_item)
        db.session.commit()
    return redirect(url_for('main.stock'))

@main_bp.route('/edit_stock/<int:stock_id>', methods=['GET', 'POST'])
def edit_stock(stock_id):
    try:
        stock_item = db.session.query(Stock).get_or_404(stock_id)
        
        if request.method == 'POST':
            # Récupération des données du formulaire
            stock_item.nom = request.form.get('nom')
            stock_item.magasin = request.form.get('magasin')
            stock_item.prix_achat = float(request.form.get('prix_achat'))
            stock_item.quantite = int(request.form.get('quantite'))
            stock_item.seuil_alerte = int(request.form.get('seuil_alerte', 0))
            stock_item.facture_url = request.form.get('facture_url')
            
            db.session.commit()
            return redirect(url_for('main.stock'))
            
        # Pour GET, on récupère la liste des magasins pour le formulaire
        magasins = db.session.query(Magasin).all()
        return render_template('edit_stock.html', stock_item=stock_item, magasins=magasins)
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'édition du stock : {e}")
        return render_template('error.html', error=str(e)), 500



@main_bp.route('/settings')
def settings():
    """⚙️ Route des paramètres de l'application."""
    return render_template('settings.html')


@main_bp.route('/organisation')
def organisation():
    """📈 Route de la page d'organisation."""
    todos = Todo.query.order_by(Todo.created_at.desc()).all()
    return render_template('organisation.html', todos=todos)


@main_bp.route('/stock')
def stock():
    """📦 Route de la page de gestion du stock."""
    magasins = db.session.query(Magasin).all()
    
    # Récupérer tous les items triés par date d'achat et ID
    stock_items = db.session.query(Stock).order_by(Stock.date_achat.desc(), Stock.id.asc()).all()
    
    # Fusionner les lignes ayant le même statut et le même group_id
    merged_items = []
    seen_groups = {}
    
    for item in stock_items:
        if item.group_id not in seen_groups:
            seen_groups[item.group_id] = item
            merged_items.append(item)
        else:
            # Si l'item a le même group_id et le même statut que l'item précédent, fusionner
            if item.statut == seen_groups[item.group_id].statut:
                seen_groups[item.group_id].quantite += item.quantite
                db.session.delete(item)
            else:
                # Si le statut est différent, ajouter comme nouvelle ligne
                merged_items.append(item)
    
    db.session.commit()
    
    return render_template('stock.html', stock_items=merged_items, magasins=magasins)


@main_bp.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    # Recherche dans les produits
    products = db.session.query(Product).filter(Product.nom.ilike(f"%{query}%")).all()

    # Recherche dans le stock
    stocks = db.session.query(Stock).filter(Stock.nom.ilike(f"%{query}%")).all()

    # Formatage des résultats
    results = [
        {"type": "Produit", "nom": p.nom, "url": url_for('products.show_products')} for p in products
    ] + [
        {"type": "Stock", "nom": s.nom, "url": url_for('main.stock')} for s in stocks
    ]

    return jsonify(results)

@main_bp.route('/stock_alerts', methods=['GET'])
def stock_alerts():
    produits_alertes = db.session.query(Stock).filter(Stock.quantite <= Stock.seuil_alerte).all()
    
    data = [
        {
            "nom": produit.nom,
            "quantite": produit.quantite,
            "seuil": produit.seuil_alerte
        } for produit in produits_alertes
    ]
    
    return jsonify(data)



@main_bp.route('/update_stock/<int:stock_id>', methods=['POST'])
def update_stock(stock_id):
    stock_item = db.session.query(Stock).get(stock_id)
    if stock_item:
        stock_item.statut = request.form.get('statut')
        db.session.commit()
    return redirect(url_for('main.stock'))

@main_bp.route('/add_stock', methods=['POST'])
def add_stock():
    try:
        # Récupération des données du formulaire
        nom = request.form.get('nom')
        ean = request.form.get('ean')
        magasin = request.form.get('magasin')
        autre_magasin = request.form.get('autre_magasin')
        prix_achat = float(request.form.get('prix_achat'))
        quantite = int(request.form.get('quantite'))
        facture_url = request.form.get('facture_url') or None
        
        # Si un nouveau magasin est saisi manuellement, l'ajouter à la table Magasin
        if autre_magasin and autre_magasin.strip():
            # Vérifier si le magasin existe déjà
            existing_magasin = db.session.query(Magasin).filter_by(nom=autre_magasin.strip()).first()
            if not existing_magasin:
                new_magasin = Magasin(nom=autre_magasin.strip())
                db.session.add(new_magasin)
                db.session.commit()
            magasin = autre_magasin.strip()
        
        # Création de l'entrée dans le stock
        new_stock = Stock(
            group_id=str(uuid.uuid4()),
            ean=ean,
            nom=nom,
            magasin=magasin,
            prix_achat=prix_achat,
            date_achat=datetime.now(),
            quantite=quantite,
            facture_url=facture_url,
            statut="Acheté/en stock"
        )

        db.session.add(new_stock)
        db.session.commit()

        return redirect(url_for('main.stock'))

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'ajout de stock : {e}")
        return f"Erreur lors de l'ajout : {str(e)}", 500
    
    
@main_bp.route('/scrap')
def scrap():
    products = ProductKeepa.query.order_by(ProductKeepa.updated_at.desc()).all()
    return render_template('scrap.html', products=products)

@main_bp.route('/update_stock_quantity', methods=['POST'])
def update_stock_quantity():
    try:
        stock_id = request.form.get('stockId')
        new_status = request.form.get('newStatus')
        quantity_type = request.form.get('quantityType')
        
        stock_item = Stock.query.get(stock_id)
        if not stock_item:
            return jsonify({'success': False, 'message': 'Article non trouvé'}), 404

        # Validation du statut
        valid_statuses = ["Acheté/en stock", "Chez Amazon", "Vendu"]
        if new_status not in valid_statuses:
            return jsonify({'success': False, 'message': 'Statut invalide'}), 400

        if quantity_type == 'all':
            # Mise à jour du statut pour tout le stock
            stock_item.statut = new_status
            db.session.commit()
            return jsonify({'success': True})
        
        elif quantity_type == 'partial':
            try:
                quantity = int(request.form.get('quantity', 0))
            except ValueError:
                return jsonify({'success': False, 'message': 'La quantité doit être un nombre entier'}), 400

            # Validation stricte de la quantité
            if quantity < 1:
                return jsonify({'success': False, 'message': 'La quantité doit être au minimum 1'}), 400
            if quantity >= stock_item.quantite:
                return jsonify({'success': False, 
                              'message': f'La quantité doit être inférieure à la quantité en stock ({stock_item.quantite})'}), 400

            # Si c'est le premier split, générer un UUID pour le groupe
            if not stock_item.group_id:
                import uuid
                stock_item.group_id = str(uuid.uuid4())

            # Créer une nouvelle entrée pour la quantité partielle
            new_stock = Stock(
                group_id=stock_item.group_id,  # Même groupe que le parent
                parent_id=stock_item.id,  # Référence au parent
                ean=stock_item.ean,
                magasin=stock_item.magasin,
                prix_achat=stock_item.prix_achat,
                prix_amazon=stock_item.prix_amazon,
                roi=stock_item.roi,
                profit=stock_item.profit,
                date_achat=stock_item.date_achat,
                quantite=quantity,
                facture_url=stock_item.facture_url,
                statut=new_status,
                nom=stock_item.nom,
                seuil_alerte=stock_item.seuil_alerte
            )
            
            # Mettre à jour la quantité de l'article original
            stock_item.quantite -= quantity
            
            db.session.add(new_stock)
            db.session.commit()
            
            return jsonify({'success': True})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/get_product_info/<ean>', methods=['GET'])
def get_product_info(ean):
    """Récupère les informations d'un produit à partir de son EAN."""
    try:
        # Chercher d'abord dans la table ProductKeepa
        product = db.session.query(ProductKeepa).filter_by(ean=ean).first()
        
        if not product:
            # Si pas trouvé, chercher dans la table Product
            product = db.session.query(Product).filter_by(ean=ean).first()
            
        if not product:
            # Si toujours pas trouvé, essayer de récupérer via l'API Keepa
            keepa_data = get_keepa_data(ean, 0)  # prix_retail = 0 car on ne le connaît pas encore
            if keepa_data and keepa_data.get('status') == 'OK':
                return jsonify({
                    'success': True,
                    'nom': keepa_data.get('nom', ''),
                    'ean': ean,
                    'prix_amazon': keepa_data.get('prix_amazon', 0)
                })
            return jsonify({'success': False, 'message': 'Produit non trouvé'})
            
        return jsonify({
            'success': True,
            'nom': product.nom,
            'ean': product.ean,
            'prix_amazon': product.prix_amazon
        })
        
    except Exception as e:
        print(f"Erreur lors de la récupération des informations du produit : {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@main_bp.route('/add_scanned_stock', methods=['POST'])
def add_scanned_stock():
    """Ajoute un produit scanné au stock."""
    try:
        # Récupération des données du formulaire
        nom = request.form.get('nom')
        ean = request.form.get('ean')
        magasin = request.form.get('magasin')
        autre_magasin = request.form.get('autre_magasin')
        prix_achat = float(request.form.get('prix_achat'))
        quantite = int(request.form.get('quantite'))
        prix_amazon = float(request.form.get('prix_amazon', 0))
        url = request.form.get('url', '')
        
        # Si un nouveau magasin est saisi manuellement, l'ajouter à la table Magasin
        if autre_magasin:
            # Vérifier si le magasin existe déjà
            existing_magasin = db.session.query(Magasin).filter_by(nom=autre_magasin).first()
            if not existing_magasin:
                new_magasin = Magasin(nom=autre_magasin)
                db.session.add(new_magasin)
                db.session.commit()
            magasin = autre_magasin
        
        # Calcul du profit et du ROI
        profit = prix_amazon - prix_achat if prix_amazon > 0 else 0
        roi = (profit * 100 / prix_achat) if prix_achat > 0 else 0
        
        # Création de l'entrée dans le stock
        new_stock = Stock(
            group_id=str(uuid.uuid4()),
            ean=ean,
            nom=nom,
            magasin=magasin,
            prix_achat=prix_achat,
            prix_amazon=prix_amazon,
            roi=roi,
            profit=profit,
            date_achat=datetime.now(),
            quantite=quantite,
            statut="Acheté/en stock"
        )

        db.session.add(new_stock)
        db.session.commit()

        return redirect(url_for('main.stock'))

    except Exception as e:
        db.session.rollback()
        print(f"❌ Erreur lors de l'ajout du produit scanné : {e}")
        return f"Erreur lors de l'ajout : {str(e)}", 500

@main_bp.route('/gestion')
def gestion():
    try:
        # Récupération des paramètres de filtrage
        current_month = request.args.get('month', type=int, default=datetime.now().month)
        current_year = request.args.get('year', type=int, default=datetime.now().year)

        # Liste des mois pour les sélecteurs
        months = [
            {'value': i, 'label': datetime(2000, i, 1).strftime('%B')} 
            for i in range(1, 13)
        ]

        # Liste des années disponibles (de 2023 à l'année en cours)
        years = list(range(2023, datetime.now().year + 1))

        # Récupération des déplacements
        travels = Travel.query.filter(
            extract('year', Travel.date) == current_year
        ).order_by(Travel.date.desc()).all()

        # Calcul des statistiques mensuelles pour Thomas
        thomas_monthly_travels = Travel.query.filter(
            extract('year', Travel.date) == current_year,
            extract('month', Travel.date) == current_month,
            Travel.person == 'Thomas'
        ).count()

        thomas_monthly_km = db.session.query(
            db.func.sum(Travel.kilometers)
        ).filter(
            extract('year', Travel.date) == current_year,
            extract('month', Travel.date) == current_month,
            Travel.person == 'Thomas'
        ).scalar() or 0

        # Calcul des statistiques mensuelles pour Olivier
        olivier_monthly_travels = Travel.query.filter(
            extract('year', Travel.date) == current_year,
            extract('month', Travel.date) == current_month,
            Travel.person == 'Olivier'
        ).count()

        olivier_monthly_km = db.session.query(
            db.func.sum(Travel.kilometers)
        ).filter(
            extract('year', Travel.date) == current_year,
            extract('month', Travel.date) == current_month,
            Travel.person == 'Olivier'
        ).scalar() or 0

        # Calcul des statistiques annuelles
        yearly_travels = Travel.query.filter(
            extract('year', Travel.date) == current_year
        ).count()

        yearly_km = db.session.query(
            db.func.sum(Travel.kilometers)
        ).filter(
            extract('year', Travel.date) == current_year
        ).scalar() or 0

        # Calcul des indemnités selon la formule officielle
        def calculate_compensation(km):
            km = float(km)  # Conversion en float
            if km <= 5000:
                return km * 0.603
            else:
                return (5000 * 0.603) + ((km - 5000) * 0.340)

        thomas_monthly_compensation = calculate_compensation(thomas_monthly_km)
        olivier_monthly_compensation = calculate_compensation(olivier_monthly_km)
        yearly_compensation = calculate_compensation(yearly_km)

        return render_template('gestion.html',
                             travels=travels,
                             months=months,
                             years=years,
                             current_month=current_month,
                             current_year=current_year,
                             thomas_monthly_travels=thomas_monthly_travels,
                             thomas_monthly_km=thomas_monthly_km,
                             thomas_monthly_compensation=thomas_monthly_compensation,
                             olivier_monthly_travels=olivier_monthly_travels,
                             olivier_monthly_km=olivier_monthly_km,
                             olivier_monthly_compensation=olivier_monthly_compensation,
                             yearly_travels=yearly_travels,
                             yearly_km=yearly_km,
                             yearly_compensation=yearly_compensation)
    except Exception as e:
        print(f"Erreur dans la route gestion : {str(e)}")
        return render_template('error.html', error=str(e)), 500

@main_bp.route('/api/travels', methods=['GET'])
def get_travels():
    travels = Travel.query.order_by(Travel.date.desc()).all()
    return jsonify([{
        'id': travel.id,
        'date': travel.date.strftime('%Y-%m-%d'),
        'person': travel.person,
        'kilometers': travel.kilometers,
        'comment': travel.comment
    } for travel in travels])

@main_bp.route('/api/travels', methods=['POST'])
def add_travel():
    data = request.get_json()
    try:
        travel = Travel(
            date=datetime.strptime(data['date'], '%Y-%m-%d'),
            person=data['person'],
            kilometers=data['kilometers'],
            comment=data['comment']
        )
        db.session.add(travel)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Déplacement ajouté avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main_bp.route('/api/travels/<int:travel_id>', methods=['PUT'])
def update_travel(travel_id):
    travel = Travel.query.get_or_404(travel_id)
    data = request.get_json()
    try:
        travel.date = datetime.strptime(data['date'], '%Y-%m-%d')
        travel.person = data['person']
        travel.kilometers = data['kilometers']
        travel.comment = data['comment']
        db.session.commit()
        return jsonify({'success': True, 'message': 'Déplacement mis à jour avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main_bp.route('/api/travels/<int:travel_id>', methods=['DELETE'])
def delete_travel(travel_id):
    travel = Travel.query.get_or_404(travel_id)
    try:
        db.session.delete(travel)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Déplacement supprimé avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 400

@main_bp.route('/api/travels/<int:travel_id>', methods=['GET'])
def get_travel(travel_id):
    travel = Travel.query.get_or_404(travel_id)
    return jsonify({
        'id': travel.id,
        'date': travel.date.strftime('%Y-%m-%d'),
        'person': travel.person,
        'kilometers': float(travel.kilometers) if travel.kilometers else None,
        'comment': travel.comment
    })

@main_bp.route('/api/todos', methods=['GET'])
def get_todos():
    """Récupère toutes les tâches."""
    todos = Todo.query.order_by(Todo.created_at.desc()).all()
    return jsonify([{
        'id': todo.id,
        'texte': todo.texte,
        'status': todo.status,
        'created_at': todo.created_at.strftime('%Y-%m-%d %H:%M:%S')
    } for todo in todos])

@main_bp.route('/api/todos', methods=['POST'])
def add_todo():
    """Ajoute une nouvelle tâche."""
    try:
        texte = request.form.get('texte')
        if not texte:
            return jsonify({'success': False, 'message': 'Le texte est requis'}), 400
            
        todo = Todo(texte=texte, status=0)
        db.session.add(todo)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Tâche ajoutée avec succès',
            'todo': {
                'id': todo.id,
                'texte': todo.texte,
                'status': todo.status,
                'created_at': todo.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/api/todos/<int:todo_id>/toggle', methods=['POST'])
def toggle_todo(todo_id):
    """Change le statut d'une tâche."""
    try:
        todo = Todo.query.get_or_404(todo_id)
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status is not None:
            todo.status = new_status
            db.session.commit()
            return jsonify({'success': True, 'message': 'Statut mis à jour avec succès'})
        else:
            return jsonify({'success': False, 'message': 'Statut non spécifié'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Supprime une tâche."""
    try:
        todo = Todo.query.get_or_404(todo_id)
        db.session.delete(todo)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Tâche supprimée avec succès'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@main_bp.route('/top100')
def top100():
    products = Top100.query.order_by(Top100.ventes_mois.desc()).all()
    magasins = Magasin.query.order_by(Magasin.nom).all()
    return render_template('top100.html', products=products, magasins=magasins)

@main_bp.route('/add_top100', methods=['POST'])
def add_top100():
    nom = request.form.get('nom')
    ean = request.form.get('ean')
    prix_retail = float(request.form.get('prix_retail'))
    prix_amazon = float(request.form.get('prix_amazon'))
    profit_potentiel = float(request.form.get('profit_potentiel'))
    ventes_mois = int(request.form.get('ventes_mois'))
    magasin = request.form.get('magasin')
    autre_magasin = request.form.get('autre_magasin')

    # Si un nouveau magasin est fourni, l'ajouter à la table magasin
    if autre_magasin:
        magasin_existant = Magasin.query.filter_by(nom=autre_magasin).first()
        if not magasin_existant:
            nouveau_magasin = Magasin(nom=autre_magasin)
            db.session.add(nouveau_magasin)
            db.session.commit()
        magasin = autre_magasin

    nouveau_produit = Top100(
        nom=nom,
        ean=ean,
        prix_retail=prix_retail,
        prix_amazon=prix_amazon,
        profit_potentiel=profit_potentiel,
        ventes_mois=ventes_mois,
        magasin=magasin
    )

    db.session.add(nouveau_produit)
    db.session.commit()

    return redirect(url_for('main.top100'))

@main_bp.route('/edit_top100/<int:product_id>', methods=['GET', 'POST'])
def edit_top100(product_id):
    product = Top100.query.get_or_404(product_id)
    magasins = Magasin.query.order_by(Magasin.nom).all()

    if request.method == 'POST':
        product.nom = request.form.get('nom')
        product.ean = request.form.get('ean')
        product.prix_retail = float(request.form.get('prix_retail'))
        product.prix_amazon = float(request.form.get('prix_amazon'))
        product.profit_potentiel = float(request.form.get('profit_potentiel'))
        product.ventes_mois = int(request.form.get('ventes_mois'))
        
        magasin = request.form.get('magasin')
        autre_magasin = request.form.get('autre_magasin')

        if autre_magasin:
            magasin_existant = Magasin.query.filter_by(nom=autre_magasin).first()
            if not magasin_existant:
                nouveau_magasin = Magasin(nom=autre_magasin)
                db.session.add(nouveau_magasin)
                db.session.commit()
            product.magasin = autre_magasin
        else:
            product.magasin = magasin

        db.session.commit()
        return redirect(url_for('main.top100'))

    return render_template('edit_top100.html', product=product, magasins=magasins)

@main_bp.route('/delete_top100/<int:product_id>', methods=['POST'])
def delete_top100(product_id):
    product = Top100.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('main.top100'))
