import os, configparser, secrets
from flask import Flask, url_for, render_template, redirect, abort, Markup, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import Markup

from tmpbox_db_accessor import TmpboxDB, TmpboxDBDuplicatedException

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
    user_id, acc_info = auth.username(), {}
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
    # ユーザーが管理者でなければ forbidden
    if not [n for n in users if n['user_id'] == auth.username()][0]['is_admin']:
        return abort(403)
    directories = db.get_directories()
    return render_template("admin.html", users = users, directories = directories)

@app.route('/admin/new-account', methods = ['GET'])
@auth.login_required
def page_new_account():
    '''
    アカウント新規登録フォームページ

    :return: アカウント編集フォームページテンプレート
    '''
    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(auth.username())
    if not acc or not acc["is_admin"]:
        return abort(403)

    return render_template("edit-account.html", is_new = True)

@app.route('/admin/new-account', methods = ['POST'])
@auth.login_required
def post_new_account():
    '''
    アカウント新規登録受信処理

    :return: 登録完了のアナウンスページ
    '''
    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(auth.username())
    if not acc or not acc["is_admin"]:
        return abort(403)

    user_id = request.form["id"]
    display_name = request.form["dn"]
    password = secrets.token_urlsafe(int(conf["Security"]["AutoPasswordLength"]))

    try:
        new_user = db.register_account(user_id, display_name, password)
    except TmpboxDBDuplicatedException as exc:
        return render_template("edit-account.html", is_new = True,
            target_user = { "user_id": user_id, "display_name": display_name },
            message_contents = Markup('<p class="error">ユーザー ID <code class="user_id">')
                + user_id + Markup('</code> は既に存在しています。'))

    return render_template("easy-info.html", summary = "アカウント登録完了",
        content = Markup('<p>ユーザー ID <code class="user_id">') + user_id
            + Markup('</code> でアカウントを登録しました。</p>\n')
            + Markup('<p>パスワードは <code class="password">') + password
            + Markup('</code> です (ユーザーにお伝えし、速やかに変更するようご案内願います…)。</p>'),
        prev_url = "/admin", prev_page = "管理者ページ")

@app.route('/admin/account/<user_id>', methods = ['GET'])
@auth.login_required
def page_edit_account(user_id):
    '''
    アカウント編集フォームページ

    :param str user_id: 編集対象のユーザー ID
    :return: アカウント編集フォームページテンプレート
    '''
    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(auth.username())
    if not acc or not acc["is_admin"]:
        return abort(403)

    return render_template("edit-account.html", is_new = False, is_new_password = False,
        target_user = db.get_account(user_id))

@app.route('/admin/account/<user_id>', methods = ['POST'])
@auth.login_required
def post_edit_account(user_id):
    '''
    アカウント編集受信処理

    :param str user_id: 編集対象のユーザー ID
    :return: アカウント編集フォームページテンプレート
    '''
    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(auth.username())
    if not acc or not acc["is_admin"]:
        return abort(403)

    display_name = request.form["dn"]
    want_new_password = request.form["pwr"] == "1"
    password = secrets.token_urlsafe(int(conf["Security"]["AutoPasswordLength"])) if want_new_password else None

    user = db.modify_account(user_id, display_name, password)

    return render_template("edit-account.html", is_new = False, target_user = user,
        is_new_password = want_new_password, password = password,
        message_contents = Markup('<p class="info"><code class="user_id">') + user_id
            + Markup('</code> のアカウント情報を更新しました。'))
