from flask import Flask, render_template, redirect, url_for, g, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc, asc
import sqlite3
import jwt
import uuid
from pyhunter import PyHunter
import clearbit
import re
from datetime import datetime, timedelta


app = Flask(__name__)


###########################################################

def connect_db():  # database connection
    sql = sqlite3.connect('database.db')
    sql.row_factory = sqlite3.Row
    return sql


def get_db():  # get database
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.teardown_appcontext
def close_db(error):  # close database
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()


###########################################################

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'mysecret'

db = SQLAlchemy(app)

# Global variable Token
token_glob = None


#############################################################
##					Database    					       ##
#############################################################

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(50), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(30))
    email = db.Column(db.String(30))
    password = db.Column(db.String(30))
    bio = db.Column(db.String(300))
    role = db.Column(db.String(100))
    location = db.Column(db.String(100))


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    recipe_name = db.Column(db.String(50))
    recipe_text = db.Column(db.String(1000))
    rating = db.Column(db.String(30))
    user_email = db.Column(db.String(30))
    ingredient_list = db.Column(db.String(100))
    avg_rating = db.Column(db.Numeric(10, 2))
    counter = db.Column(db.Integer)


class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ingredient_name = db.Column(db.String(50))
    used = db.Column(db.Integer)


# Get current user if the token is valid
def get_current_user():
    token = token_glob

    if token is not None:
        if not token:  # checks if a token has been entered, if not returns a response
            return jsonify({'message': 'Token is missing !!'}), 401
        try:
            # gets data from token
            data = jwt.decode(
                token, app.config['SECRET_KEY']
            )

            # checks if user exists in database
            current_user = User.query.filter_by(
                public_id=data['public_id']
            ).first()

        except:
            return (
                jsonify({'message': 'Token is invalid !!'}),
                401,
            )

        return current_user

    else:
        current_user = None
        return current_user


@app.route('/', methods=['GET', 'POST'])
def index():
    user = get_current_user()

    # recipes search
    if request.method == "POST":
        search = request.form['search']

        # checks if recipe name, text or ingredients exist
        recipes = Recipe.query.filter(Recipe.recipe_name.ilike('%' + search + '%')).all()
        if len(recipes) == 0:
            recipes = Recipe.query.filter(Recipe.recipe_text.ilike('%' + search + '%')).all()
            if len(recipes) == 0:
                recipes = Recipe.query.filter(Recipe.ingredient_list.ilike('%' + search + '%')).all()

        return render_template('listall.html', user=user, recipes=recipes)

    return render_template('index.html', user=user)


#############################################################
##				    	User     					       ##
#############################################################

# user login and creating JWT token
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        # checks if an email has been entered, if not returns a response
        if not user:
            return render_template('notuser.html')

        # checks if the password is correct and creates token, if not returns a response
        if user.password == password:
            token = jwt.encode({
                'first_name': user.first_name,
                'last_name': user.last_name,
                'public_id': user.public_id,
                'email': user.email,
                'exp': datetime.utcnow() + timedelta(minutes=30)
            },
                app.config['SECRET_KEY'])

            # returns users token to a global token variable
            global token_glob
            token_glob = token
            print(token_glob)

            return render_template('index.html', user=user)

        return render_template('wrongpass.html')

    return render_template('login.html')


# User Sign up, checking if email is valid using hunter
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        email = request.form['email']

        # checks if email exists in database
        user = User.query.filter_by(email=email).first()

        if not user:
            email_db = ''
        else:
            email_db = user.email

        if email != email_db:
            try:
                # validate email using hunter
                hunter = PyHunter('fce98eff8d99f93fe14df75bf06d0713d73f406a')
                hunter.email_verifier(email)

                # gets additional information for a user using clearbit
                clearbit.key = 'sk_074ad5265e753838e4bc9993b1a1473f'
                person = clearbit.Person.find(email=email, stream=True)

                bio = None
                if person is not None and person['bio'] is not None:
                    bio = person['bio']

                role = None
                if person is not None and person['employment']['role'] is not None:
                    role = person['employment']['role']

                location = None
                if person is not None and person['location'] is not None:
                    location = person['location']

                # inserts new user into database
                new_user = User(public_id=str(uuid.uuid4()), first_name=request.form['first_name'],
                                last_name=request.form['last_name'], email=email, password=request.form['password'],
                                bio=bio, role=role, location=location)

                db.session.add(new_user)
                db.session.commit()

                return render_template('login.html')

            except:
                return render_template('invalid.html')

        else:
            return render_template('userexists.html')

    return render_template('register.html')


@app.route('/logout')
def logout():
    global token_glob
    token_glob = None
    return redirect(url_for('index'))


#############################################################
##				    Recipe + Ing   					       ##
#############################################################

@app.route('/create', methods=['GET', 'POST'])
def create():
    try:
        user = get_current_user()
        user_email = user.email

        if request.method == "POST":

            ingredients = request.form['ingredients'].replace(', ', ',').split(",")
            counter = len(ingredients)

            # inserts recipe into database
            new_recipe = Recipe(recipe_name=request.form['recipe_name'], recipe_text=request.form['recipe_text'],
                                user_email=user_email, ingredient_list=request.form['ingredients'],
                                counter=counter)

            db.session.add(new_recipe)

            # inserts ingredients into database
            n = 0
            while n < counter:
                def remove(list):
                    pattern = '[0-9]'
                    list = [re.sub(pattern, '', i) for i in list]
                    l1 = [i.strip() for i in list]
                    return l1

                ing = (remove(ingredients))[n]
                ing_db = Ingredient.query.filter_by(ingredient_name=ing).first()

                if ing_db is not None:
                    ing_db_name = ing_db.ingredient_name

                    if ing == ing_db_name:
                        used = ing_db.used
                        unew = used + 1
                        ing_db.used = unew

                else:
                    new_ing = Ingredient(ingredient_name=ing, used=1)

                    db.session.add(new_ing)

                db.session.commit()
                n = n + 1

            return redirect(url_for('listall', user=user))

        return render_template('create.html', user=user)

    except:
        return render_template('forbidden.html')


@app.route('/recipe/<id>', methods=['GET', 'POST'])
def recipe(id):
    user = get_current_user()
    recipe = Recipe.query.filter_by(id=id).first()

    # recipe rating
    if request.method == 'POST':
        rating = recipe.rating
        rate = int(request.form['rating'])

        if rating is not None:
            rating_list = rating.split(",")
            rating_list.append(rate)

            # calculates new average rating
            avg_new = sum(int(i) for i in rating_list) / len(rating_list)
            list_str = ','.join(str(v) for v in rating_list)

            recipe.rating = list_str
            recipe.avg_rating = avg_new

        else:
            recipe.rating = rate
            recipe.avg_rating = rate

        # update database
        db.session.commit()

    return render_template('recipe.html', recipe=recipe, user=user)


@app.route('/listall', methods=['GET'])
def listall():
    user = get_current_user()

    recipes = Recipe.query.order_by(Recipe.recipe_name).all()
    return render_template('listall.html', recipes=recipes, user=user)


@app.route('/mylist', methods=['GET', 'POST'])
def mylist():
    try:
        user = get_current_user()
        user_email = user.email

        recipes = Recipe.query.filter_by(user_email=user_email).all()

        return render_template('listall.html', recipes=recipes, user=user)
    except:
        return render_template('forbidden.html')


@app.route('/top5', methods=['GET', 'POST'])
def top5():
    user = get_current_user()
    ingredients = Ingredient.query.order_by(desc(Ingredient.used)).limit(5)

    return render_template('top5.html', ingredients=ingredients, user=user)


@app.route('/min', methods=['GET', 'POST'])
def min():
    user = get_current_user()
    recipes = Recipe.query.order_by(asc(Recipe.counter)).limit(3)

    return render_template('listall.html', recipes=recipes, user=user)


@app.route('/max', methods=['GET', 'POST'])
def max():
    user = get_current_user()
    recipes = Recipe.query.order_by(desc(Recipe.counter)).limit(3)

    return render_template('listall.html', recipes=recipes, user=user)


if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)
