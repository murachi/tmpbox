import os, sys, configparser, secrets, urllib.parse, logging, logging.config
from flask import Flask, url_for, render_template, redirect, abort, Markup, request, session
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from jinja2 import Markup

from tmpbox_db_accessor import TmpboxDB, TmpboxDBDuplicatedException
import tmpbox_validator as validator

upload_files_dir = "upfiles"
log_dir = "log"

app = Flask(__name__)

conf = configparser.ConfigParser()
conf.read('conf.d/tmpbox.ini')

os.makedirs(os.path.join(conf["Repository"]["DirectoryRoot"], upload_files_dir), mode = 0o2750, exist_ok = True)
os.makedirs(os.path.join(conf["Repository"]["DirectoryRoot"], log_dir), mode = 0o2750, exist_ok = True)

logging.config.fileConfig("conf.d/logging.ini")
logger_acc = logging.getLogger("access")
logger_err = logging.getLogger("debug" if app.debug else "error")

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

def verify_login_session():
    '''
    ログインセッションの状態を確認するデコレータ

    :param function page_func: ログイン状態を確認したいページの処理
    :return: ログインセッション状態情報の辞書
    '''
    login_session = db.check_login_session(session.get('token', None))
    if not login_session:
        logger_err.info(
            "Login session failed (or expired). Accessed from <{}>.".format(request.remote_addr))
    return (
        login_session,
        None if login_session
            else redirect("/login?url={}".format(urllib.parse.quote(request.path, safe = ""))),
    )

def gen_form_token(login_session, form_name):
    '''
    フォーム受信用のワンタイムトークンを生成する

    :param dict login_session: ログインセッション状態の辞書
    :param str form_name: セッションデータキーに用いるフォーム名称
    '''
    data = {n["name"]: n["value"] for n in login_session["session_datas"]}
    token = secrets.token_urlsafe(8)
    data.update({"{}-token".format(form_name): token})
    db.modify_session_data(login_session["session_id"], data)
    return token

def verify_form_token(login_session, form_name, token):
    '''
    フォーム受信時のワンタイムトークンを検証する

    :param dict login_session: ログインセッション状態の辞書
    :param str form_name: セッションデータキーに用いるフォーム名称
    :param str token: フォームデータに含まれるトークン
    :return: トークンの照合に成功した場合は ``True`` を、それ以外の場合は ``False`` を返す。
    '''
    key_name = "{}-token".format(form_name)
    target_token = [n["value"] for n in login_session["session_datas"] if n["name"] == key_name]
    if not target_token or target_token[0] != token:
        logger_err.error("Invalid form token. Accessed from <{}>.".format(request.remote_addr))
        return False

    db.delete_session_data(login_session["session_id"], key_name)
    return True

@app.before_request
def log_by_access():
    '''
    アクセスログを出力する
    '''
    logger_acc.info(
        "[{method}]{path} - {rmt_addr}".format(
            path = request.path, method = request.method, rmt_addr = request.remote_addr))

@app.route('/')
def page_index():
    '''
    トップページ

    :return: トップページテンプレート

    ログイン済みであればアカウントに参照権限のあるディレクトリのリストを表示する。
    それ以外の場合、ログインページへのリンクを表示する。
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()

    acc_info = {}
    if login_session:
        acc_info = db.get_account(login_session["user_id"])

    return render_template('index.html', **acc_info)

@app.route('/login', methods = ['GET'])
def page_login():
    '''
    認証 URL

    :return: 認証フォーム
    '''
    location_path = request.args.get('url', '')
    return render_template('login.html', url = location_path)

@app.route('/login', methods = ['POST'])
def post_login():
    '''
    認証受信処理

    :return: 遷移元ロケーションへのリダイレクト
    '''
    location_path = request.form.get('loc', '') or '/'
    user_id = request.form['id']
    password = request.form['pw']

    token = db.check_authentication(user_id, password)

    if token:
        logger_err.info("User '{}' successed to log in.".format(user_id))
        session["token"] = token
        return redirect(location_path)
    else:
        logger_err.error(
            "Authentication failed. Accessed from <{}> (tried id = '{}', pass = '{}')"
                .format(request.remote_addr, user_id, password))
        return render_template('login.html', url = location_path, user_id = user_id,
            message_contents = Markup('<p class="error">ユーザー ID またはパスワードが一致しません。</p>'))

@app.route('/admin')
def page_admin():
    '''
    管理者ページ

    :return: 管理者ページテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    users = db.get_all_accounts()
    # ユーザーが管理者でなければ forbidden
    if not [n for n in users if n['user_id'] == login_session["user_id"]][0]['is_admin']:
        return abort(403)
    directories = db.get_directories()
    return render_template("admin.html", users = users, directories = directories)

@app.route('/admin/new-account', methods = ['GET'])
def page_new_account():
    '''
    アカウント新規登録フォームページ

    :return: アカウント編集フォームページテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(login_session["user_id"])
    if not acc or not acc["is_admin"]:
        return abort(403)

    form_token = gen_form_token(login_session, "new-account")
    return render_template("edit-account.html", is_new = True, form_token = form_token)

@app.route('/admin/new-account', methods = ['POST'])
def post_new_account():
    '''
    アカウント新規登録受信処理

    :return: 登録完了のアナウンスページ
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(login_session["user_id"])
    if not acc or not acc["is_admin"]:
        return abort(403)

    # フォームトークンの検証に失敗した場合は Bad Request
    form_token = request.form["tk"]
    if not verify_form_token(login_session, "new-account", form_token):
        return abort(400)

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
def page_edit_account(user_id):
    '''
    アカウント編集フォームページ

    :param str user_id: 編集対象のユーザー ID
    :return: アカウント編集フォームページテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(login_session["user_id"])
    if not acc or not acc["is_admin"]:
        return abort(403)

    form_token = gen_form_token(login_session, "edit-account")
    return render_template("edit-account.html", is_new = False, form_token = form_token,
        is_new_password = False, target_user = db.get_account(user_id))

@app.route('/admin/account/<user_id>', methods = ['POST'])
def post_edit_account(user_id):
    '''
    アカウント編集受信処理

    :param str user_id: 編集対象のユーザー ID
    :return: アカウント編集フォームページテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(login_session["user_id"])
    if not acc or not acc["is_admin"]:
        return abort(403)

    # フォームトークンの検証に失敗した場合は Bad Request
    form_token = request.form["tk"]
    if not verify_form_token(login_session, "edit-account", form_token):
        return abort(400)

    display_name = request.form["dn"]
    want_new_password = request.form["pwr"] == "1"
    password = secrets.token_urlsafe(int(conf["Security"]["AutoPasswordLength"])) if want_new_password else None

    user = db.modify_account(user_id, display_name, password)

    form_token = gen_form_token(login_session, "edit-account")
    return render_template("edit-account.html", is_new = False, form_token = form_token,
        target_user = user, is_new_password = want_new_password, password = password,
        message_contents = Markup('<p class="info"><code class="user_id">') + user_id
            + Markup('</code> のアカウント情報を更新しました。'))

@app.route('/admin/new-directory', methods = ['GET'])
def page_new_directory():
    '''
    新規ディレクトリ登録フォームページ

    :return: 新規ディレクトリ登録フォームテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    users = db.get_all_accounts()
    # ユーザーが管理者でなければ forbidden
    if not [n for n in users if n['user_id'] == login_session["user_id"]][0]['is_admin']:
        return abort(403)
    for user in users: user["allow"] = False

    form_token = gen_form_token(login_session, "new-directory")
    return render_template("edit-directory.html", is_new = True, form_token = form_token,
        target_dir = {
            "directory_name": "",
            "summary": "",
            "expires_days": conf["UploadFiles"]["DefaultExpiresDays"],
        },
        users = users)

@app.route('/admin/new-directory', methods = ['POST'])
def post_new_directory():
    '''
    新規ディレクトリ登録受信処理

    :return: 登録完了のアナウンスページ
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(login_session["user_id"])
    if not acc or not acc["is_admin"]:
        return abort(403)

    # 受信データサイズをチェック (でかすぎる場合はけんもほろろに Bad Request)
    if request.content_length > int(conf["Security"]["MaxFormLength"]):
        return abort(400)

    raw_form = urllib.parse.parse_qsl(request.get_data(as_text = True))

    # フォームトークンの検証に失敗した場合は Bad Request
    form_token = request.form["tk"]
    if not verify_form_token(login_session, "new-directory", form_token):
        return abort(400)

    dir_name = request.form["nm"]
    summary = request.form["sm"]
    expires_days = int(request.form["ed"])
    permissions = [n[1] for n in raw_form if n[0] == "pm"]

    def error_page(msg):
        users = db.get_all_accounts()
        for user in users:
            user["allow"] = user["user_id"] in permissions
        form_token = gen_form_token(login_session, "new-directory")
        return render_template("edit-directory.html", is_new = True, form_token = form_token,
            target_dir = {
                "directory_name": dir_name,
                "summary": summary,
                "expires_days": expires_days,
            },
            users = users,
            message_contents = Markup('<p class="error">') + msg + Markup('</p>'))

    if not permissions:
        return error_page("参照権限ユーザーを一人以上選択してください。")

    try:
        dir_id = db.register_directory(dir_name, expires_days, summary)
    except TmpboxDBDuplicatedException as exc:
        return error_page(''.join(exc.args))

    db.update_permission(dir_id, permissions)

    return render_template("easy-info.html", summary = "ディレクトリ作成完了",
        content = Markup('<p>ディレクトリ <code class="directory">') + dir_name
            + Markup("</code> の作成に成功しました。"),
        prev_url = "/admin", prev_page = "管理者ページ")

@app.route('/admin/directory/<int:dir_id>', methods = ['GET'])
def page_edit_directory(dir_id):
    '''
    ディレクトリ編集フォームページ

    :param int dir_id: ディレクトリ ID
    :return: ディレクトリ編集フォームテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    users = db.get_all_accounts()
    # ユーザーが管理者でなければ forbidden
    if not [n for n in users if n['user_id'] == login_session["user_id"]][0]['is_admin']:
        return abort(403)

    directory = db.get_directory(dir_id)
    permission = [n["user_id"] for n in directory["permissions"]]
    for user in users:
        user["allow"] = user["user_id"] in permission

    form_token = gen_form_token(login_session, "edit-directory")
    return render_template("edit-directory.html", is_new = False, form_token = form_token,
        target_dir = directory, users = users)

@app.route('/admin/directory/<int:dir_id>', methods = ['POST'])
def post_edit_directory(dir_id):
    '''
    ディレクトリ編集受信処理

    :param int dir_id: ディレクトリ ID
    :return: ディレクトリ編集フォームテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # ユーザーが管理者でなければ forbidden
    acc = db.get_account(login_session["user_id"])
    if not acc or not acc["is_admin"]:
        return abort(403)

    # 受信データサイズをチェック (でかすぎる場合はけんもほろろに Bad Request)
    if request.content_length > int(conf["Security"]["MaxFormLength"]):
        return abort(400)

    raw_form = urllib.parse.parse_qsl(request.get_data(as_text = True))

    # フォームトークンの検証に失敗した場合は Bad Request
    form_token = request.form["tk"]
    if not verify_form_token(login_session, "edit-directory", form_token):
        return abort(400)

    dir_name = request.form["nm"]
    summary = request.form["sm"]
    expires_days = int(request.form["ed"])
    permissions = [n[1] for n in raw_form if n[0] == "pm"]

    users = db.get_all_accounts()
    for user in users:
        user["allow"] = user["user_id"] in permissions

    form_token = gen_form_token(login_session, "edit-directory")
    if not permissions:
        return render_template("edit-directory.html", is_new = False, form_token = form_token,
            target_dir = {
                "directory_name": dir_name,
                "summary": summary,
                "expires_days": expires_days,
            },
            users = users,
            message_contents = Markup('<p class="error">参照権限ユーザーを一人以上選択してください。</p>'))

    directory = db.update_directory(dir_id, dir_name, expires_days, summary)
    db.update_permission(dir_id, permissions)

    return render_template("edit-directory.html", is_new = False, form_token = form_token,
        target_dir = directory, users = users,
        message_contents = Markup('<p class="info">ディレクトリの情報を更新しました。</p>'))
