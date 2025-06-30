import os, random, string
from dotenv import load_dotenv


load_dotenv()  # load variables from .env
class Config(object):
    basedir = os.path.abspath(os.path.dirname(__file__))
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
    
    # This will create a file in <app> FOLDER
    DB_NAME     = os.getenv('DB_NAME'     , None)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'nba_app/static/uploads')