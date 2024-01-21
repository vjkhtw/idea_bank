# app.py
import re
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ideas.db'  # SQLite database file
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'


db = SQLAlchemy(app)

# Define the Idea model
class Idea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    # Change tags to a relationship with a Tag model (many-to-many relationship)
    tags = db.relationship('Tag', secondary='idea_tag', backref='ideas')  
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    twitter_link = db.Column(db.String(255))
    reports = db.Column(db.Integer, default=0)
    report_count = db.Column(db.Integer, default=0)
    date = db.Column(db.DateTime, default=datetime.utcnow)

# Create a Tag model to handle tags separately
class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

# Create an association table to establish the many-to-many relationship between Idea and Tag
idea_tag = db.Table('idea_tag',
    db.Column('idea_id', db.Integer, db.ForeignKey('idea.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

# Create the database tables within application context
with app.app_context():
    db.create_all()

# About page route
@app.route('/about')
def about():
    return render_template('index.html', page='about')

# Sponsor page route
@app.route('/sponsor')
def sponsor():
    return render_template('index.html', page='sponsor')

# Landing page with trending ideas
@app.route('/index', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def index():
    page = request.args.get('page', 1, type=int)  # Get the requested page, default to 1
    per_page = 20  # Number of ideas per page

    ideas = Idea.query.paginate(page=page, per_page=per_page)
    tgs = Tag.query.all()

    sort_option = request.args.get('sort', 'upvotes')  # Get the selected sort option

    # This part should be modified to sort the paginated ideas, not the full list of ideas
    if sort_option == 'upvotes':
        ideas = Idea.query.order_by(Idea.upvotes.desc()).paginate(page=page, per_page=per_page)
    elif sort_option == 'downvotes':
        ideas = Idea.query.order_by(Idea.downvotes.desc()).paginate(page=page, per_page=per_page)
    elif sort_option == 'latest':
        ideas = Idea.query.order_by(Idea.date.desc()).paginate(page=page, per_page=per_page)
    elif sort_option == 'past':
        ideas = Idea.query.order_by(Idea.date.asc()).paginate(page=page, per_page=per_page)
    else:
        ideas = Idea.query.order_by(Idea.upvotes.desc()).paginate(page=page, per_page=per_page)  # Default to sorting by upvotes

    tgs = Tag.query.all()
    return render_template('index.html', ideas=ideas, tgs=tgs, sort_option=sort_option)


#Route to upvote the idea
@app.route('/upvote/<int:idea_id>')
def upvote(idea_id):
    idea = Idea.query.get(idea_id)

    # Check if the user has already upvoted
    if 'upvoted_{}'.format(idea_id) not in session:
        idea.upvotes += 1
        session['upvoted_{}'.format(idea_id)] = True

        # If the user has already downvoted, decrement the downvote count
        if 'downvoted_{}'.format(idea_id) in session:
            idea.downvotes -= 1
            del session['downvoted_{}'.format(idea_id)]

        db.session.commit()

    # If the user had already upvoted, remove the upvote
    elif 'upvoted_{}'.format(idea_id) in session:
        idea.upvotes -= 1
        del session['upvoted_{}'.format(idea_id)]
        db.session.commit()

    return redirect(url_for('index'))

# Route to downvote an idea
@app.route('/downvote/<int:idea_id>')
def downvote(idea_id):
    idea = Idea.query.get(idea_id)

    # Check if the user has already downvoted
    if 'downvoted_{}'.format(idea_id) not in session:
        idea.downvotes += 1
        session['downvoted_{}'.format(idea_id)] = True

        # If the user has already upvoted, decrement the upvote count
        if 'upvoted_{}'.format(idea_id) in session:
            idea.upvotes -= 1
            del session['upvoted_{}'.format(idea_id)]

        db.session.commit()

    # If the user had already downvoted, remove the downvote
    elif 'downvoted_{}'.format(idea_id) in session:
        idea.downvotes -= 1
        del session['downvoted_{}'.format(idea_id)]
        db.session.commit()

    return redirect(url_for('index'))

# Ideas by category
@app.route('/ideas/<tags>')
def ideas_by_category(tags):
    tag_list = [tag.strip() for tag in re.split(r'[, ]', tags) if tag.strip()]
    page = request.args.get('page', 1, type=int)  # Get the requested page, default to 1
    per_page = 20  # Number of ideas per page

    # Filter ideas by tags and paginate the results
    tag_objects = Tag.query.filter(Tag.name.in_(tag_list)).all()
    tag_ids = [tag.id for tag in tag_objects]

    ideas = Idea.query.filter(Idea.tags.any(Tag.id.in_(tag_ids))).paginate(page=page, per_page=per_page)
    return render_template('index.html', ideas=ideas, tgs=tag_objects)


@app.route('/report/<int:idea_id>')
def report_idea(idea_id):
    idea = Idea.query.get(idea_id)

    # Check if the user has already reported
    if 'reported_{}'.format(idea_id) not in session:
        idea.reports += 1

        # Delete the idea if reported more than 10 times
        if idea.reports >= 10:
            db.session.delete(idea)

        session['reported_{}'.format(idea_id)] = True
        db.session.commit()

    return redirect(url_for('index'))


# Form to submit an idea
@app.route('/post_idea', methods=['GET', 'POST'])
def post_idea():
    if request.method == 'POST':
        title = request.form['title']
        tags = request.form['tags']
        twitter_link = request.form['twitter_link']

        tag_list = [tag.strip() for tag in re.split(r'[, ]', tags) if tag.strip()]
        print(tag_list)  # Print the tag_list directly to see the individual tags

        idea_tags = []
        for tag_name in tag_list:
            tag = Tag.query.filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                db.session.add(tag)
            idea_tags.append(tag)

        new_idea = Idea(title=title, twitter_link=twitter_link, tags=idea_tags)
        db.session.add(new_idea)
        db.session.commit()

        return redirect(url_for('index'))  # Redirect to homepage after submission

    return render_template('post_idea.html')

if __name__ == '__main__':
    app.run(debug=True)
