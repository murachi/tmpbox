from flask import Flask, url_for, render_template, Markup, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
auth = HTTPBasicAuth()

@auth.verify_password
def verify_password(username, password):
    return False

@app.route('/')
def index():
    '''
    トップページ

    :return: トップページテンプレート

    ログイン済みであればアカウントに参照権限のあるディレクトリのリストを表示する。
    それ以外の場合、ログインページへのリンクを表示する。
    '''
    return render_template('index.html', username = auth.username())

@app.route('/login')
@auth.login_required
def login():
    '''
    認証 URL

    :return: トップページへのリダイレクト
    '''
    return app.redirect('/', 303)
