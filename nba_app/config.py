import os, random, string
from dotenv import load_dotenv


load_dotenv()  # load variables from .env
class Config(object):
    basedir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(basedir, '..'))
    instance_dir = os.path.join(project_root, 'instance')
    # Set up the App SECRET_KEY
    SECRET_KEY = os.getenv('SECRET_KEY', None)
    if not SECRET_KEY:
        SECRET_KEY = ''.join(random.choice(string.ascii_lowercase) for i in range(32))
    # Social AUTH context
    SOCIAL_AUTH_GOOGLE = False

    # Google Oauth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', None)
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', None)
    SESSION_TYPE = "filesystem"
    # Enable/Disable Google  Login
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET:
        SOCIAL_AUTH_GOOGLE = True
    
    # This will create a local SQLite database in the Flask instance folder.
    DB_NAME = os.getenv('DB_NAME', 'nba_oracleDB.db')
    DATABASE_URL = os.getenv('DATABASE_URL')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or f"sqlite:///{os.path.join(instance_dir, DB_NAME)}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'nba_app/static/uploads')
