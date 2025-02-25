import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'mon_secret_key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        "mysql+mysqlconnector://root:GdZwRdaftiYhhrbXyyVQNFynnKAUDymv@ballast.proxy.rlwy.net:15578/railway"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
