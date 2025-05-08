CREATE TABLE top_100 (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    ean VARCHAR(13) UNIQUE,
    prix_retail DECIMAL(10,2) NOT NULL,
    prix_amazon DECIMAL(10,2) NOT NULL,
    profit_potentiel DECIMAL(10,2) NOT NULL,
    ventes_mois INT NOT NULL,
    magasin VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (magasin) REFERENCES magasin(nom)
); 