from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from flask_wtf.file import FileField, FileRequired
from wtforms.validators import DataRequired, Email, Optional

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Register')

class UploadForm(FlaskForm):
    file = FileField('Upload File', validators=[FileRequired()])
    submit = SubmitField('Upload and Predict')

class PredictionForm(FlaskForm):
    file = FileField('Upload CSV', validators=[Optional()])
    player_name = StringField('Player Name', validators=[Optional()])
    submit = SubmitField('Predict')