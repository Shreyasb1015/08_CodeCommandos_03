import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager




app=Flask(__name__)
app.config['SECRET_KEY']='611b3d683d34077144500505e7afc60f'
app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///C:\\code-files\\Ai-hackathon-pre\\site.db'
db=SQLAlchemy(app)
bcrypt=Bcrypt(app)
login_manager=LoginManager(app)
login_manager.login_view='login'  # type: ignore
login_manager.login_message_category='info'



import routes