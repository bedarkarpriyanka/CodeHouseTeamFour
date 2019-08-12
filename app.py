import os
from flask import Flask, url_for, redirect, render_template, request
from flask_mongoengine.wtf import model_form
from flask_mongoengine import MongoEngine
from wtforms import form, fields, validators
import flask_admin as admin
import flask_login as login
from flask_admin import helpers, expose
from werkzeug.security import generate_password_hash, check_password_hash
from flask_admin.contrib.mongoengine import ModelView
from bson.objectid import ObjectId
import string
import random
import datetime
import json


app = Flask(__name__)
app.config['SECRET_KEY'] = '123456790'
app.config['MONGODB_SETTINGS'] = {'db': 'test'}
db = MongoEngine(app)

app.static_folder = 'static'

class User(db.Document):
    first_name = db.StringField(required=True, max_length=50)
    last_name = db.StringField(required=True, max_length=50)
    login = db.StringField(required=True, max_length=80, unique=True)
    email = db.StringField(required=True, max_length=100)
    password = db.StringField(required=True, max_length=64)
    status = db.StringField(required=True, max_length=30)
    org_name = db.StringField(required=True, max_length=100)
    interest = db.StringField(required=True, max_length=100)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)

    # Required for administrative interface
    def __unicode__(self):
        return self.login


class Question(db.Document):
    q_created_at = db.StringField(required=True, max_length=10)
    q_upvotes = db.IntField(required=True)
    q_string = db.StringField(required=True, max_length=10000)
    q_tags = db.ListField(db.StringField(max_length=300))
    q_description = db.StringField(max_length=100000)
    q_user = db.ReferenceField(User)

    @classmethod
    def search_class(cls,keywords):
        return cls.objects.search_text(keywords).order_by('$text_score')

    meta = {
    'allow_inheritance' : True,
    'indexes' : [{'fields': ['$q_created_at', '$q_upvotes', '$q_string', '$q_tags', '$q_description', '$q_user'],
            'cls': False} ]
    }


class Answer(db.Document):
    a_created_at = db.StringField(required=True, max_length=10)
    a_upvotes = db.IntField(required=True, max_length=100)
    a_string = db.StringField(required=True, max_length=4096)
    a_user = db.ReferenceField(User)
    a_question = db.ReferenceField(Question)


class LoginForm(form.Form):
    login = fields.StringField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])
    def validate_login(self, field):
        user = self.get_user()
        if user is None:
            raise validators.ValidationError('Invalid user')
        if user.password != self.password.data:
            raise validators.ValidationError('Invalid password')
    def get_user(self):
        return User.objects(login=self.login.data).first()


class RegistrationForm(form.Form):
    first_name = fields.StringField(validators=[validators.required()])
    last_name = fields.StringField(validators=[validators.required()])
    login = fields.StringField(validators=[validators.required()])
    email = fields.StringField(validators=[validators.required(), validators.Email("Invalid Email")])
    status = fields.StringField(validators=[validators.required(),
                validators.AnyOf(message="Choose Status among 'High School', 'College', 'Industry'",
                values=['High School', 'College', 'Industry'])])
    org_name = fields.StringField(validators=[validators.required()])
    interest = fields.StringField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])
    def validate_login(self, field):
        if User.objects(login=self.login.data):
            raise validators.ValidationError('Duplicate username')



def init_login():
    login_manager = login.LoginManager()
    login_manager.init_app(app)
    @login_manager.user_loader
    def load_user(user_id):
        return User.objects(id=user_id).first()


class MyModelView(ModelView):
    def is_accessible(self):
        return login.current_user.is_authenticated


class MyAdminIndexView(admin.AdminIndexView):
    @expose('/')
    def index(self):
        if not login.current_user.is_authenticated:
            return redirect(url_for('.login_view'))
        return super(MyAdminIndexView, self).index()

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            login.login_user(user)
        if login.current_user.is_authenticated:
            return redirect(url_for('.index'))
        link = '<p>Don\'t have an account? <a href="' + url_for('.register_view') + '">Click here to register.</a></p>'
        self._template_args['form'] = form
        self._template_args['link'] = link
        return super(MyAdminIndexView, self).index()

    @expose('/register/', methods=('GET', 'POST'))
    def register_view(self):
        form = RegistrationForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = User()
            form.populate_obj(user)
            user.password = form.password.data
            user.save()
            login.login_user(user)
            return redirect(url_for('.index'))
        link = '<p>Already have an account? <a href="' + url_for('.login_view') + '">Click here to log in.</a></p>'
        self._template_args['form'] = form
        self._template_args['link'] = link
        return super(MyAdminIndexView, self).index()

    @expose('/logout/')
    def logout_view(self):
        login.logout_user()
        return redirect(url_for('.index'))

    @expose('/post-form/', methods=('POST', 'GET'))
    def post_form(self):
        name = request.form.get('question_name')
        tag = request.form.get('question_tag')
        description = request.form.get('question_description')
        valid_tags=['academic', 'industry', 'admission', 'women in tech', 'internship' ]
        try:
            tag = valid_tags[int(tag) - 1]
        except:
            tag = valid_tags[1]
        q_created_at = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        q_upvotes = 1
        q_string = name
        q_tags = [tag]
        q_description = description
        q_user = User.objects(login=str(login.current_user)).first()

        add_new_question = Question(q_created_at=q_created_at,
                                    q_upvotes=q_upvotes,
                                    q_string=q_string,
                                    q_tags=q_tags,
                                    q_description=q_description,
                                    q_user=q_user)
        add_new_question.save()
        new_qid = Question.objects(q_string=q_string).first().id
        return self.get_answers(new_qid)

    @expose('/search-form/', methods=('POST', 'GET'))
    def search_form(self):
        question_input = request.form.get('search_input')
        question_list = Question.search_class(question_input)
        questions_list = [ob.to_mongo().to_dict() for ob in question_list]
        return render_template('newtemp/search_results.html', questions=questions_list)

    def helper_list_question(self, questions_list):
        for i in range(len(questions_list)):
            questions_list[i]['q_user'] = User.objects(id=questions_list[i]['q_user']).first().login
            #del questions_list[i]['_id']
        return questions_list

    def helper_list_answer(self, answer_list):
        for i in range(len(answer_list)):
            answer_list[i]['a_user'] = User.objects(id=answer_list[i]['a_user']).first().login
            #del answer_list[i]['_id']
        return answer_list

    @expose('/main/', methods=('POST', 'GET'))
    def main(self):
        questions_list = [ob.to_mongo().to_dict() for ob in Question.objects.all()]
        questions_list = self.helper_list_question(questions_list)
        return render_template('newtemp/index.html', questions=questions_list)

    @expose('/get_answers/<qid>', methods=('POST', 'GET'))
    def get_answers(self, qid):
        #qid = ObjectId("5d509299eb3eb7c632cd3817")
        final_dict = {'question':[], 'answers':[]}
        answers_list = [ob.to_mongo().to_dict() for ob in Answer.objects(a_question=ObjectId(qid)).all()]
        answers_list = self.helper_list_answer(answers_list)
        final_dict['answers'] = answers_list
        question = [Question.objects(id=ObjectId(qid)).first().to_mongo().to_dict()]
        question = self.helper_list_question(question)
        final_dict['question']=question
        return render_template('qna.html', this_question_info=final_dict)

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video')
def homepage():
    return """
    <h1>Welcome to the video!</h1>
    <iframe src="https://www.youtube.com/embed/YQHsXMglC9A" width="853" height="480" frameborder="0" allowfullscreen></iframe>
    """

@app.route('/post')
def postpage():
    return render_template('blog-post.html')

def build_sample_db():
    test_user = User(first_name='Priyanka',
                    last_name='Bedarkar',
                    login='psb',
                    email='pbedarkar@cs.stonybrook.edu',
                    password='123',
                    status='College',
                    org_name='Stony Brook University',
                    interest='Computer Science')
    test_user.save()
    test_question = Question(q_created_at=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                            q_upvotes=5,
                            q_string="How to win CodeHouse?",
                            q_tags=['CodeHouse', 'vmware'],
                            q_description="",
                            q_user=test_user)

    test_question.save()
    test_answer = Answer(a_created_at=datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                        a_upvotes=21,
                        a_string="Be unique",
                        a_user=test_user,
                        a_question=test_question)
    test_answer.save()
    return

if __name__ == '__main__':
    init_login()
    admin = admin.Admin(app, 'Team Four', index_view=MyAdminIndexView(), base_template='my_master.html')
    admin.add_view(MyModelView(User))
    admin.add_view(MyModelView(Question))
    admin.add_view(MyModelView(Answer))

    #build_sample_db()
    app.run(debug=True)
