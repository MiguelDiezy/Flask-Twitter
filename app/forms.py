from wtforms import StringField, EmailField, TextAreaField, PasswordField, SubmitField
from wtforms import validators
from wtforms.validators import InputRequired, email
from flask_wtf import FlaskForm
from flask_login import UserMixin
from flask_ckeditor import CKEditorField


class RegisterForm(UserMixin, FlaskForm):
    user = StringField("Usuario", validators=[InputRequired()])
    email = EmailField("Email", validators=[InputRequired()])
    password = PasswordField("Contraseña", validators=[InputRequired()])
    submit1 = SubmitField("Enviar")
    

class LoginForm(FlaskForm):
    login_user = StringField("Usuario", validators=[InputRequired()])
    login_password = PasswordField("Contraseña", validators=[InputRequired()])
    submit2 = SubmitField("Enviar")
    

class TweetForm(FlaskForm):
    text = CKEditorField(validators=[InputRequired()], render_kw={"placeholder": "Escribe un Tweet", "class": "text-form-class"})
    

class SearchbarForm(FlaskForm):
    username = StringField("Usuario", render_kw={"placeholder": "Buscar Usuario", "class": "text-form-class"})