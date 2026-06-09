import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'devkey')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'mysql+mysqlconnector://user:pass@localhost/helia')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret')
DB_HOST = "localhost3306"
DB_USER = "root"
DB_PASSWORD = "Vickey@2311"
DB_NAME = "heliosense_ai"