from flask import Flask, app
from flask_login import LoginManager, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_dance.contrib.google import make_google_blueprint, google
from flask_session import Session
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask_wtf import CSRFProtect
import os
from os import path
from datetime import timedelta
import logging
from dotenv import load_dotenv
from .models import db, User, OAuth
from .config import Config
from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

load_dotenv()
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
csrf = CSRFProtect()

# Google OAuth blueprint (define at top-level)
google_bp = make_google_blueprint(
    client_id=Config.GOOGLE_CLIENT_ID,
    client_secret=Config.GOOGLE_CLIENT_SECRET,
    scope=["openid", "email", "profile"],
    # **No storage argument here!**
)


def create_app():
    app = Flask(__name__)
    # Config
    app.config.from_object(Config)
    # Init extensions
    db.init_app(app)              
    Session(app)
    migrate = Migrate(app, db)
    csrf.init_app(app)
    app.permanent_session_lifetime = timedelta(minutes=90)
    # Load environment variables
    app.config['GOOGLE_CLIENT_ID'] = Config.GOOGLE_CLIENT_ID
    app.config['GOOGLE_CLIENT_SECRET'] = Config.GOOGLE_CLIENT_SECRET
    app.config['SECRET_KEY'] = Config.SECRET_KEY
    app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
    # Initialize the database
    app.config['SQLALCHEMY_DATABASE_URI'] = Config.SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = Config.SQLALCHEMY_TRACK_MODIFICATIONS
    app.config['SESSION_TYPE'] = 'filesystem'
    

    from .models import User
    create_database(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    #Load our routes
    from .views import views
    from .auth import auth

    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')
    app.register_blueprint(google_bp, url_prefix="/login")
    # Print URL map to debug routes
    print(app.url_map)

    dash_app = create_dash_app(app)
    return app

def create_dash_app(flask_app):
    dash_app = Dash(__name__, server=flask_app, url_base_pathname='/stats/')

    # Load your shooting data CSV
    shooting_avg = pd.read_csv('data/shooting/shooting_avg.csv')
    adj_shooting_avg = pd.read_csv('data/adj_shooting/adj_shooting_avg.csv')

    # Convert to long format for plotting (assuming 'Year' column exists)
    long_shooting = shooting_avg.melt(id_vars='Year', var_name='Stat', value_name='Average')
    long_adj_shooting = adj_shooting_avg.melt(id_vars='Year', var_name='Stat', value_name='Average')
    scaler = MinMaxScaler()
    long_shooting['ScaledAverage'] = scaler.fit_transform(long_shooting[['Average']])
    long_adj_shooting['ScaledAverage'] = scaler.fit_transform(long_adj_shooting[['Average']])

    dash_app.layout = html.Div([
        html.H4('Raw Shooting Averages Over Years'),
        dcc.Graph(
            id='raw-shooting-graph',
            figure=px.line(long_shooting, x='Year', y='ScaledAverage', color='Stat', title='Raw Shooting Averages (scaled)')
        ),
        
        html.H4('Adjusted Shooting Averages Over Years'),
        dcc.Graph(
            id='adj-shooting-graph',
            figure=px.line(long_adj_shooting, x='Year', y='ScaledAverage', color='Stat', title='Adjusted Shooting Averages (scaled)')
        ),
    ])

    return dash_app


def create_database(app):
    if not path.exists(os.path.join('nba_oracle', Config.DB_NAME)):
        with app.app_context():
            db.create_all()
        print('Created Database!')