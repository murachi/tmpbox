import os, configparser
from flask import Flask, url_for, render_template, redirect, abort, Markup, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import Markup

from tmpbox_db_accessor import TmpboxDB

app = Flask(__name__)
auth = HTTPBasicAuth()

conf = configparser.ConfigParser()
conf.read('conf.d/tmpbox.ini')

db = TmpboxDB(conf["DB"]["ConnectionString"])

@app.template_filter('dispdate')
def filter_dispdate(d):
    '''
    表示用の日付文字列に変換するフィルター

    :param datetime.date dispdate: 日付
    :return: 表示用の日付文字列
    '''
    return f"{d:%Y}/{d.month}/{d.day}"

@app.template_filter('firstline')
def filter_firstline(text):
    '''
    テキストの概略として、最初の行のみを表示に用いるフィルター

    :param str text: テキスト
    :return: 最初の 1行を含む HTML テキスト

    ``<span>`` タグに来るんだ HTML テキストを返す。
    ``text`` が 2行以上ある場合、 ``<span>`` タグにはクラス ``multilines``
    が設定される。 CSS はこれを見て 3点リーダーを表示する等の制御を行う。
    '''
    lines = text.split("\n")
    return Markup('<span' + (' class="multilines"' if len(lines) > 1 else '') + '>') \
        + lines[0] + Markup('</span>')

@auth.verify_password
def verify_password(username, password):
    return db.check_authentication(username, password)

@app.route('/')
def page_index():
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
def page_login():
    '''
    認証 URL

    :return: トップページへのリダイレクト
    '''
    return redirect('/', 303)

@app.route('/admin')
@auth.login_required
def page_admin():
    '''
    管理者ページ

    :return: 管理者ページテンプレート
    '''
    users = db.get_all_accounts()
    if not [n for n in users if n['user_id'] == auth.username()][0]['is_admin']:
        return abort(403)
    directories = db.get_directories()
    return render_template("admin.html", users = users, directories = directories)
