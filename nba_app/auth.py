from flask import Blueprint, redirect, url_for, session, flash, render_template, request
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask_dance.consumer import oauth_authorized
from flask_dance.contrib.google import google
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.orm.exc import NoResultFound
from werkzeug.security import generate_password_hash
from .models import db, User, OAuth
from .forms import LoginForm, RegisterForm
from nba_app import google_bp
from backend.scraper_client import refresh_latest_daily_games_if_needed

import os
from .config import Config
auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if request.method == "GET":
        refresh_latest_daily_games_if_needed(background=True)

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        if user:
            if user.verify_password(password):
                login_user(user, remember=form.remember.data)
                refresh_latest_daily_games_if_needed(background=True)
                flash("Logged in successfully!", "success")
                return redirect(url_for("views.home"))
            elif not user.password_hash:
                flash("You logged in via Google. Please set a password to login traditionally.", "info")
                return redirect(url_for("auth.register", email=user.email))
        
        flash("Invalid email or password", "danger")
        return redirect(url_for("auth.login"))
    
    return render_template("login.html", form=form)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        if user:
            user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash("Password set successfully! You can now login with your password.", "success")
        else:
            user = User(email=email, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully!", "success")

        return redirect(url_for("auth.login"))

    # Pre-fill email if coming from Google
    if not form.email.data:
        email = request.args.get("email") or session.get("email")
        if email:
            form.email.data = email

    return render_template("register.html", form=form)

@auth.route("/logout")
@login_required
def logout():
    # Clear OAuth token for Google when logging out
    oauth = OAuth.query.filter_by(user_id=current_user.id, provider="google").first()
    if oauth:
        db.session.delete(oauth)
        db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))

@oauth_authorized.connect_via(google_bp)
def google_logged_in(blueprint, token):
    if not token:
        return False  # No token means login failed

    # Use the Google OAuth session to get user info
    resp = blueprint.session.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return False

    info = resp.json()
    email = info.get("email")
    if not email:
        return False

    # Find or create your user
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=info.get("name"))
        db.session.add(user)
        db.session.commit()

    # Find or create OAuth token entry
    oauth = OAuth.query.filter_by(provider="google", user_id=user.id).first()
    if not oauth:
        oauth = OAuth(provider="google", token=token, user_id=user.id)
        db.session.add(oauth)
        db.session.commit()
    else:
        # Update token if needed
        oauth.token = token
        db.session.commit()

    # Log in the user
    login_user(user)

    # Return False to prevent Flask-Dance from saving token again
    return False




