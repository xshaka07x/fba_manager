# db.py

import mysql.connector
from mysql.connector import Error
import logging

def get_db_connection():
    """📡 Crée et retourne une connexion MySQL Railway avec gestion améliorée des erreurs."""
    try:
        conn = mysql.connector.connect(
            host="ballast.proxy.rlwy.net",
            user="root",
            password="GdZwRdaftiYhhrbXyyVQNFynnKAUDymv",
            database="railway",
            port=15578,
            connection_timeout=10  # ✅ Timeout pour éviter les blocages
        )
        if conn.is_connected():
            logging.info("✅ Connexion MySQL Railway établie.")
            return conn
    except Error as e:
        logging.error(f"❌ Erreur de connexion MySQL: {e}")
        print(f"❌ Détails de l'erreur: {e}")
        raise

