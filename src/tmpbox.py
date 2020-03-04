import os, configparser, secrets, urllib.parse
from flask import Flask, url_for, render_template, redirect, abort, Markup, request, session
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import Markup

from tmpbox_db_accessor import TmpboxDB, TmpboxDBDuplicatedException
import tmpbox_validator as validator

app = Flask(__name__)

conf = configparser.ConfigParser()
conf.read('conf.d/tmpbox.ini')

db = TmpboxDB(conf["DB"]["ConnectionString"])
app.secret_key = db.get_secret_key()

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

def verify_login_session(page_func):
    '''
    ログインセッションの状態を確認するデコレータ

    :param function page_func: ログイン状態を確認したいページの処理
    :return: ログインセッション状態の確認処理を含む関数を返す

    修飾する関数の第1引数にて、ログインセッション状態情報の辞書を受け取るものとする。
    '''
    login_session = db.check_login_session(session['token'])
    return (lambda *args, **kwargs: page_func(login_session, *args, **kwargs)) \
        if login_session else (lambda: redirect("/login?url={}".format(urllib.parse.quote(request.path, safe = ''))))

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

@app.route('/login', methods = ['GET'])
def page_login():
    '''
    認証 URL

    :return: 認証フォーム
    '''
    return redirect('/', 303)

@app.route('/admin')
@verify_login_session
def page_admin(sstate):
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
@verify_login_session
def page_new_account(sstate):
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
@verify_login_session
def post_new_account(sstate):
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

    def error_page(msg):
        return render_template("edit-account.html", is_new = True,
            target_user = { "user_id": user_id, "display_name": display_name },
            message_contents = Markup('<p class="error">') + msg + Markup('</p>'))

    if not validator.validateNameToken(user_id):
        return error_page(
            "ユーザーID は半角英字で始まり半角英数字とアンダーバー _ のみで構成される名前にしてください。")

    try:
        new_user = db.register_account(user_id, display_name, password)
    except TmpboxDBDuplicatedException as exc:
        return error_page(''.join(exc.args))

    return render_template("easy-info.html", summary = "アカウント登録完了",
        content = Markup('<p>ユーザー ID <code class="user_id">') + user_id
            + Markup('</code> でアカウントを登録しました。</p>\n')
            + Markup('<p>パスワードは <code class="password">') + password
            + Markup('</code> です (ユーザーにお伝えし、速やかに変更するようご案内願います…)。</p>'),
        prev_url = "/admin", prev_page = "管理者ページ")

@app.route('/admin/account/<user_id>', methods = ['GET'])
@verify_login_session
def page_edit_account(sstate, user_id):
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
@verify_login_session
def post_edit_account(sstate, user_id):
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

@app.route('/admin/new-directory', methods = ['GET'])
@verify_login_session
def page_new_directory(sstate):
    '''
    新規ディレクトリ登録フォームページ

    :return: 新規ディレクトリ登録フォームテンプレート
    '''
    users = db.get_all_accounts()
    # ユーザーが管理者でなければ forbidden
    if not [n for n in users if n['user_id'] == auth.username()][0]['is_admin']:
        return abort(403)

    for user in users: user["allow"] = False
    return render_template("edit-directory.html", is_new = True,
        target_dir = {
            "directory_name": "",
            "summary": "",
            "expires_days": conf["UploadFiles"]["DefaultExpiresDays"],
        },
        users = users)

@app.route('/admin/new-directory', methods = ['POST'])
@verify_login_session
def post_new_directory(sstate):
    '''
    新規ディレクトリ登録受信処理

    :return: 登録完了のアナウンスページ
    '''
    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(auth.username())
    if not acc or not acc["is_admin"]:
        return abort(403)

    # 受信データサイズをチェック (でかすぎる場合はけんもほろろに Bad Request)
    if request.content_length > int(conf["Security"]["MaxFormLength"]):
        return abort(400)

    raw_form = urllib.parse.parse_qsl(request.get_data(as_text = True))
    dir_name = request.form["nm"]
    summary = request.form["sm"]
    expires_days = int(request.form["ed"])
    permissions = [n[1] for n in raw_form if n[0] == "pm"]

    def error_page(msg):
        users = db.get_all_accounts()
        for user in users:
            user["allow"] = user["user_id"] in permissions
        return render_template("edit-directory.html", is_new = True,
            target_dir = {
                "directory_name": dir_name,
                "summary": summary,
                "expires_days": expires_days,
            },
            users = users,
            message_contents = Markup('<p class="error">') + msg + Markup('</p>'))

    if not validator.validateURIUnreserved(dir_name):
        return error_page(
            "ディレクトリ名に使用できる文字は半角英数字と次の記号文字のみです: " +
            "'.' (ピリオド)、 '_' (アンダーバー)、 '-' (ハイフン)、 '~' (チルダ)")
    if not permissions:
        return error_page("参照権限ユーザーを一人以上選択してください。")

    try:
        db.register_directory(dir_name, expires_days, summary)
    except TmpboxDBDuplicatedException as exc:
        return error_page(''.join(exc.args))
    os.makedirs(os.path.join(conf["UploadFiles"]["DirectoryRoot"], dir_name), exist_ok = True)

    db.update_permission(dir_name, permissions)

    return render_template("easy-info.html", summary = "ディレクトリ作成完了",
        content = Markup('<p>ディレクトリ <code class="directory">') + dir_name
            + Markup("</code> の作成に成功しました。"),
        prev_url = "/admin", prev_page = "管理者ページ")

@app.route('/admin/directory/<dir_name>', methods = ['GET'])
@verify_login_session
def page_edit_directory(sstate, dir_name):
    '''
    ディレクトリ編集フォームページ

    :return: ディレクトリ編集フォームテンプレート
    '''
    users = db.get_all_accounts()
    # ユーザーが管理者でなければ forbidden
    if not [n for n in users if n['user_id'] == auth.username()][0]['is_admin']:
        return abort(403)

    directory = db.get_directory(dir_name)
    permission = [n["user_id"] for n in directory["permissions"]]
    for user in users:
        user["allow"] = user["user_id"] in permission

    return render_template("edit-directory.html", is_new = False,
        target_dir = directory,
        users = users)

@app.route('/admin/directory/<dir_name>', methods = ['POST'])
@verify_login_session
def post_edit_directory(sstate, dir_name):
    '''
    ディレクトリ編集受信処理

    :return: ディレクトリ編集フォームテンプレート
    '''
    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(auth.username())
    if not acc or not acc["is_admin"]:
        return abort(403)

    # 受信データサイズをチェック (でかすぎる場合はけんもほろろに Bad Request)
    if request.content_length > int(conf["Security"]["MaxFormLength"]):
        return abort(400)

    raw_form = urllib.parse.parse_qsl(request.get_data(as_text = True))
    summary = request.form["sm"]
    expires_days = int(request.form["ed"])
    permissions = [n[1] for n in raw_form if n[0] == "pm"]

    users = db.get_all_accounts()
    for user in users:
        user["allow"] = user["user_id"] in permissions

    if not permissions:
        return render_template("edit-directory.html", is_new = False,
            target_dir = {
                "directory_name": dir_name,
                "summary": summary,
                "expires_days": expires_days,
            },
            users = users,
            message_contents = Markup('<p class="error">') + msg + Markup('</p>'))

    directory = db.update_directory(dir_name, expires_days, summary)
    db.update_permission(dir_name, permissions)

    return render_template("edit-directory.html", is_new = False,
        target_dir = directory, users = users,
        message_contents = Markup('<p class="info">ディレクトリの情報を更新しました。</p>'))
