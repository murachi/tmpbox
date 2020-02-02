import os, configparser
from flask import Flask, url_for, render_template, redirect, Markup, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

from tmpbox_db_accessor import TmpboxDB

app = Flask(__name__)
auth = HTTPBasicAuth()

conf = configparser.ConfigParser()
conf.read('conf.d/tmpbox.ini')

db = TmpboxDB(conf["DB"]["ConnectionString"])

@auth.verify_password
def verify_password(username, password):
    return db.check_authentication(username, password)

@app.route('/')
def index():
    '''
    トップページ

    :return: トップページテンプレート

    ログイン済みであればアカウントに参照権限のあるディレクトリのリストを表示する。
    それ以外の場合、ログインページへのリンクを表示する。
    '''
    user_id, acc_info = auth.username(), None
    if user_id:
        acc_info = db.get_account(user_id)

    return render_template('index.html', **acc_info)

@app.route('/login')
@auth.login_required
def login():
    '''
    認証 URL

    :return: トップページへのリダイレクト
    '''
    return redirect('/', 303)
