from datetime import  datetime
from email.policy import default
from typing import final
from flask import Flask, render_template, redirect, url_for, request, flash
from app.forms import RegisterForm, TweetForm, LoginForm, SearchbarForm
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import select, text
from sqlalchemy.orm import relationship
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from flask_bootstrap import Bootstrap
from flask_gravatar import Gravatar
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

import os
from dotenv import load_dotenv

load_dotenv()

# Flask App
app = Flask(__name__)
Bootstrap(app)
app.config["SECRET_KEY"] = os.environ['SECRET_KEY']

# Gravatar
Gravatar(app,
         size=100,
         rating='g',
         default='monsterid',
         force_default=False,
         force_lower=False,
         use_ssl=False,
         base_url=None)

# Crear base de datos

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


followed = db.Table('users_followed',
    db.Column('follower_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('users.id'))
)

follower = db.Table('users_following',
    db.Column('follower_id', db.Integer, db.ForeignKey('users.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('users.id'))
)


class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    username = db.Column(db.String(20), unique=True)
    password = db.Column(db.String(100))
    tweets = relationship("Tweet", back_populates="author")
    likes = relationship("Likes", back_populates="user")
    retweets = relationship("Retweet", back_populates="user")
    notifications = relationship("Notification", back_populates="user")
    users_followed = db.relationship(
        'User', secondary=followed,
        primaryjoin=(followed.c.follower_id == id),
        secondaryjoin=(followed.c.followed_id == id),
        backref=db.backref('followed', lazy='dynamic'), lazy='dynamic')
    users_following = db.relationship(
        'User', secondary=follower,
        primaryjoin=(follower.c.followed_id == id),
        secondaryjoin=(follower.c.follower_id == id),
        backref=db.backref('follower', lazy='dynamic'), lazy='dynamic')

    def is_authenticated(self):
        return True

    def is_active(self):   
        return True           

    def is_anonymous(self):
        return False          

    def get_id(self):         
        return str(self.id)
    
    def follow(self, user):
        if not self.is_following(user):
            self.users_followed.append(user)
            return self
        
    def add_follower(self, user):
        if not user.is_following(self):
            self.users_following.append(user)
            return self

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
            return self

    def is_following(self, user):
        return self.followed.filter(
            followed.c.followed_id == user.id).count() > 0
        
    def get_tweets(self):
        followed_users_id = [user.id for user in self.users_followed.all()]
        tweets = db.session.query(Tweet).limit(100).all()
        retweets = db.session.query(Retweet).limit(100).all()
        final_tweets_list = []
        # Tweets de seguidores
        for tweet in tweets:
            if tweet.author_id in followed_users_id: 
                final_tweets_list.append(tweet)
        for retweet in retweets:
            if retweet.user_id in followed_users_id:
                final_tweets_list.append(retweet)
        final_tweets_list = sorted(final_tweets_list, key=lambda x: x.time_created)
        return reversed(final_tweets_list)

    def get_user_tweets(self):
        tweets = db.session.query(Tweet).filter(Tweet.author_id==self.id).limit(100).all()
        retweets = db.session.query(Retweet).filter(Retweet.user_id==self.id).limit(100).all()
        final_tweets_list = []
        for tweet in tweets:
            final_tweets_list.append(tweet)
        for retweet in retweets:
            final_tweets_list.append(retweet)  
        final_tweets_list = sorted(final_tweets_list, key=lambda x: x.time_created)
        final_tweets_list = reversed(final_tweets_list)
        return final_tweets_list    
    
    def notification_seen(self):
        for noti in self.notifications:
            noti.is_seen = True
            db.session.commit()


tweet_comment = db.Table('comments',
    db.Column('comment_id', db.Integer, db.ForeignKey('tweets.id')),
    db.Column('tweet_id', db.Integer, db.ForeignKey('tweets.id')))

tweet_commented = db.Table('commented',
    db.Column('comment_id', db.Integer, db.ForeignKey('tweets.id')),
    db.Column('tweet_id', db.Integer, db.ForeignKey('tweets.id')))


class Tweet(db.Model):
    __tablename__ = "tweets"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="tweets")
    text = db.Column(db.Text, nullable=False)
    time_created = db.Column(db.DateTime())
    time = db.Column(db.String(50), nullable=False)
    likes = relationship("Likes", back_populates="tweet") 
    retweets = relationship("Retweet", back_populates="tweet")
    is_retweet = db.Column(db.Boolean, default=False)
    is_comment = db.Column(db.Boolean, default=False)
    tweet_to_comment_username = db.Column(db.String(50), nullable=True)
    comments = db.relationship(
        'Tweet', secondary=tweet_comment,
        primaryjoin=(tweet_comment.c.comment_id == id),
        secondaryjoin=(tweet_comment.c.tweet_id == id),
        backref=db.backref('tweet_comment', lazy='dynamic'), lazy='dynamic')
    commented = db.relationship(
        'Tweet', secondary=tweet_commented,
        primaryjoin=(tweet_commented.c.tweet_id == id),
        secondaryjoin=(tweet_commented.c.comment_id == id),
        backref=db.backref('tweet_commented', lazy='dynamic'), lazy='dynamic')
    
    def is_liked(self, user):
        user_liked_tweet_id = [like.tweet_id for like in user.likes]
        if self.id in user_liked_tweet_id:
            return True
        return False
    
    def is_retweeted(self, user):
        user_retweets_tweet_id = [retweet.tweet_id for retweet in user.retweets]
        if self.id in user_retweets_tweet_id:
            return True
        return False
    
    def add_comment(self, comment):
        self.comments.append(comment)
        return self
    
    def add_commented(self, comment):
        self.commented.append(comment)
        return self
    
    def check_mention(self):
        twot_to_list = self.text.split(" ")
        for word in twot_to_list:
            if "@" in word:
                username = word.split("@")[1]
                return username
        return ""
    
    
class Likes(db.Model):
    __tablename__ = "likes"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship("User", back_populates="likes")
    tweet_id = db.Column(db.Integer, db.ForeignKey("tweets.id"))
    tweet = relationship("Tweet", back_populates="likes")
    

class Retweet(db.Model):
    __tablename__ = "retweet"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship("User", back_populates="retweets")
    tweet_id = db.Column(db.Integer, db.ForeignKey("tweets.id"))
    tweet = relationship("Tweet", back_populates="retweets")
    time_created = db.Column(db.DateTime(), default=datetime.now())
    time = db.Column(db.String(50))
    is_retweet = db.Column(db.Boolean, default=True)
    is_comment = db.Column(db.Boolean, default=False)
    
    
class Notification(db.Model):
    __tablename__ = "like_notification"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship("User", back_populates="notifications")
    user_from = db.Column(db.String(50))
    tweet_id = db.Column(db.Integer, db.ForeignKey("tweets.id"))
    tweet = relationship("Tweet")
    time_created = db.Column(db.DateTime(), default=datetime.now())
    is_follow = db.Column(db.Boolean, default=False)
    is_like = db.Column(db.Boolean, default=False)
    is_retweet = db.Column(db.Boolean, default=False)
    is_comment = db.Column(db.Boolean, default=False)
    is_mention = db.Column(db.Boolean, default=False)
    is_seen = db.Column(db.Boolean, default=False)

try:
    db.create_all()
except:
    pass  

try:
    new_user = User(
        email="testuser@gmail.com",
        username="testuser",
        password="1234"
    )
    db.session.add(new_user)
    follow = new_user.follow(new_user)
    db.session.add(follow)
    db.session.commit()
except:
    pass

@app.route('/', methods=["POST", "GET"])
def index():
    """Pagina principal"""
    return render_template('index.html')

    
@app.route("/home", methods=["POST", "GET"])
@login_required
def mainpage():
    """Pagina principal donde aparecen los tweets de los usuarios seguidos y los propios
    y el area de texto para crear tweets"""
    twots_form = TweetForm()
    searchbar_form = SearchbarForm()
    all_tweets = current_user.get_tweets()
    user_likes = [like.tweet_id for like in current_user.likes]
    user_rt = [rt.tweet_id for rt in current_user.retweets]
    not_seen_notifications = [noti for noti in current_user.notifications if noti.is_seen == False]

    if twots_form.validate_on_submit():
        now = datetime.now()
        current_date = now.strftime("%m/%d/%Y, %H:%M:%S")       
        twot_text = twots_form.text.data
        new_tweet = Tweet(
            text=twot_text,
            author=current_user,
            time_created=datetime.now(),
            time=current_date
            )
        db.session.add(new_tweet)
        db.session.commit()
        user = User.query.filter_by(username=new_tweet.check_mention()).first()
        if user:
            new_notification = Notification(
            user=user,
            user_from=current_user.username,
            tweet=new_tweet,
            is_mention=True
        )
            db.session.add(new_notification)
            db.session.commit()
            print(f"Hola {user.username}, {current_user.username} te ha dicho: {new_tweet.text}")
            pass
        
        return redirect(url_for("mainpage"))
        
    return render_template("mainpage.html", twots_form=twots_form, searchbar_form=searchbar_form,
                             tweets=all_tweets, user_likes=user_likes,
                             user_rt=user_rt, not_seen_notifications=not_seen_notifications)


@app.route("/perfil/<username>", methods=["GET", "POST"])
def user_profile(username):
    searchbar_form = SearchbarForm()
    user = User.query.filter_by(username=username).first()
    if user:
        all_tweets = user.get_user_tweets()
        user_likes = [like.tweet_id for like in current_user.likes]
        user_rt = [rt.tweet_id for rt in current_user.retweets]
        return render_template("user_profile.html", user=user, tweets=all_tweets,
                            user_likes=user_likes, user_rt=user_rt, searchbar_form=searchbar_form)
    else:
        return render_template("user_profile.html", searchbar_form=searchbar_form, username=username)


@app.route("/search", methods=["GET", "POST"])
def search_user():
    searchbar_form = SearchbarForm()
    if searchbar_form.validate_on_submit():
        username = searchbar_form.username.data
        user = User.query.filter_by(username=username).first()
        return redirect(url_for("user_profile", username=username))


@app.route("/notificaciones", methods=["POST", "GET"])
@login_required
def notifications_page():
    searchbar_form = SearchbarForm()
    user_likes = [like.tweet_id for like in current_user.likes]
    user_rt = [rt.tweet_id for rt in current_user.retweets]
    user_notifications = current_user.notifications
    all_notifications = reversed(sorted(user_notifications, key=lambda x: x.time_created))
    print(user_notifications)
    current_user.notification_seen()
    return render_template("notifications-page.html", all_notifications=all_notifications, 
                           user_likes=user_likes, user_rt=user_rt, searchbar_form=searchbar_form)


@app.route("/follow/<username>", methods=["GET", "POST"])
def follow_user(username):
    user = User.query.filter_by(username=username).first()
    if current_user.is_following(user) == False:
        print("Siguiendo Usuario")
        user_followed = current_user.follow(user)
        new_notification = Notification(
            user=user,
            user_from=current_user.username,
            is_follow=True
        )
        db.session.add(user_followed)
        db.session.commit()
    if user.is_following(current_user) == False:
        user_follower = user.add_follower(current_user)
        db.session.add(user_follower)
        db.session.commit()

    return ('', 204)

    
@app.route("/delete/<tweet_id>", methods=["POST", "GET"])
def delete_tweet(tweet_id):
    tweet_to_delete = Tweet.query.filter_by(id=tweet_id).first()
    if len(tweet_to_delete.likes) > 0:
        for like in tweet_to_delete.likes:
            Likes.query.filter_by(id=like.id).delete()
    if len(tweet_to_delete.retweets) > 0:
        for rt in tweet_to_delete.retweets:
            Retweet.query.filter_by(id=rt.id).delete()
    for notification in current_user.notifications:
        if notification.tweet_id == tweet_to_delete.id:
            Notification.query.filter_by(user_from=current_user.username, id=notification.id).delete()
            continue
    Tweet.query.filter_by(id=tweet_id).delete()
    db.session.commit()
    print("Tweet Deleted")
    return redirect(url_for("mainpage"))
    
    
@app.route("/like/<tweet_id>", methods=["POST", "GET"])
def add_like(tweet_id):
    liked_tweet = Tweet.query.filter_by(id=tweet_id).first()
    user = User.query.filter_by(id=liked_tweet.author_id).first()

    if liked_tweet.is_liked(current_user) == False:
        new_like = Likes(
        user=current_user,
        tweet=liked_tweet
    )
        print("Liking Tweet")
        if user.id != current_user.id:
            new_notification = Notification(
                user=user,
                user_from=current_user.username,
                tweet=liked_tweet,
                is_like=True
            )
            db.session.add(new_notification)
        db.session.add(new_like)
        db.session.commit()
                
    return ('', 204)


@app.route("/delete-like/<tweet_id>", methods=["POST", "GET"])
def delete_like(tweet_id):
    Likes.query.filter_by(tweet_id=tweet_id, user_id=current_user.id).delete()
    db.session.commit()
    print("Like Deleted")
    return ('', 204)


@app.route("/retweet/<tweet_id>", methods=["POST", "GET"])
def add_retweet(tweet_id):
    tweet_to_rt = Tweet.query.filter_by(id=tweet_id).first()
    user = User.query.filter_by(id=tweet_to_rt.author_id).first()

    if tweet_to_rt.is_retweeted(current_user) == False:
        print("Retweeting")
        new_retweet = Retweet(
        user=current_user,
        tweet=tweet_to_rt,
    )
        
        if user.id != current_user.id:
            new_notification = Notification(
                user=user,
                user_from=current_user.username,
                tweet=tweet_to_rt,
                is_retweet=True
            )
            db.session.add(new_notification)
        db.session.add(new_retweet)
        db.session.commit()
                
    return ('', 204)


@app.route("/delete-retweet/<tweet_id>", methods=["POST", "GET"])
def delete_retweet(tweet_id):
    Retweet.query.filter_by(tweet_id=tweet_id, user_id=current_user.id).delete()
    db.session.commit()
    print("Retweet deleted")
    return ('', 204)


@app.route("/tweet/<tweet_id>", methods=["POST", "GET"])
def comment_tweet(tweet_id):
    searchbar_form = SearchbarForm()
    twots_form = TweetForm()
    tweet_to_comment = Tweet.query.filter_by(id=tweet_id).first()
    comments = tweet_to_comment.comments.all()
    comments = reversed(sorted(comments, key=lambda x: x.time_created))
    user_likes = [like.tweet_id for like in current_user.likes]
    user_rt = [rt.tweet_id for rt in current_user.retweets]
    if twots_form.validate_on_submit():
        now = datetime.now()
        current_date = now.strftime("%m/%d/%Y, %H:%M:%S")
        twot_text = f"@{tweet_to_comment.author.username} {twots_form.text.data}"
        new_tweet = Tweet(
            text=twot_text,
            author=current_user,
            time_created=datetime.now(),
            time=current_date,
            is_comment=True,
            tweet_to_comment_username=tweet_to_comment.author.username
            )
        comment = tweet_to_comment.add_comment(new_tweet)
        commented = new_tweet.add_commented(tweet_to_comment)
        db.session.add(new_tweet)
        db.session.add(comment)
        db.session.add(commented)
        db.session.commit()
        
        user = User.query.filter_by(username=new_tweet.check_mention()).first()
        if user and user.id != current_user.id:
            new_notification = Notification(
            user=user,
            user_from=current_user.username,
            tweet=new_tweet,
            is_comment=True
        )
            db.session.add(new_notification)
            db.session.commit()
            pass
        return redirect(url_for("comment_tweet", tweet_id=tweet_to_comment.id, comments=comments, searchbar_form=searchbar_form))
        
    return render_template("tweet-page.html", tweet=tweet_to_comment, twots_form=twots_form, comments=comments,
                           user_likes=user_likes, user_rt=user_rt, searchbar_form=searchbar_form)


@app.route('/register', methods=["POST", "GET"])
def register():
    """ Maneja el formulario de registro """
    register_form = RegisterForm()

    if register_form.validate_on_submit():
        username = register_form.user.data
        email = register_form.email.data
        password = register_form.password.data
        
        # Comprobar si el usuario ya esta registrado
        if User.query.filter_by(email=email).first():
            flash("El usuario ya existe, inicia sesion.")
            return redirect(url_for("login"))
        
        # Anadir usuario a la base de datos
        
        hash_and_salted_password = generate_password_hash(
            password,
            method='pbkdf2:sha256',
            salt_length=8
        )
            
        new_user = User(
            email=email,
            username=username,
            password=hash_and_salted_password
        )
        
        db.session.add(new_user)
        follow = new_user.follow(new_user)
        db.session.add(follow)
        db.session.commit()
        
        user = User.query.filter_by(username=username).first()
        login_user(user)
        
        return redirect(url_for("mainpage"))
        
    return render_template('register.html', register_form=register_form)


@app.route('/login', methods=["POST", "GET"])
def login():
    """ Maneja el formulario de log-in """
    login_form = LoginForm()

    if login_form.validate_on_submit():
        username = login_form.login_user.data
        password = login_form.login_password.data
        
        # COmprobar si el usuario esta en la base de datos
        user = User.query.filter_by(username=username).first()
        testuser = User.query.filter_by(username=username).first()
        
        # Si esta en la base de datos iniciar sesion con login_user
        if testuser:
            login_user(user)
            return redirect(url_for('mainpage'))
        if not user:
            flash("Usuario no encontrado, prueba otra vez.")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, password):
            flash("Contrasena incorrecta, prueba otra vez.")
            return redirect(url_for("login"))
        else:
            login_user(user)
            return redirect(url_for('mainpage'))
            
            
    return render_template('login.html', login_form=login_form)


@app.route('/logout')
@login_required
def logout():
    """Cerrar sesion"""
    logout_user()
    return redirect(url_for('index'))


if __name__ == "__main__":
    app.run(debug=True)
