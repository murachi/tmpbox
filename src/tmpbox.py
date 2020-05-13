import os, sys, configparser, secrets, urllib.parse, logging, logging.config, tempfile
from datetime import datetime, date, timedelta
from flask import Flask, url_for, render_template, redirect, abort, send_file, Markup, request, session
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from jinja2 import Markup

from tmpbox_db_accessor import TmpboxDB, TmpboxDBDuplicatedException
import tmpbox_validator as validator

upload_files_dir = "upfiles"
log_dir = "log"
temp_dir = "temp"

app = Flask(__name__)

conf = configparser.ConfigParser()
conf.read('conf.d/tmpbox.ini')

repository_root = conf["Repository"]["DirectoryRoot"]
os.makedirs(os.path.join(repository_root, upload_files_dir), mode = 0o2750, exist_ok = True)
os.makedirs(os.path.join(repository_root, log_dir), mode = 0o2750, exist_ok = True)
os.makedirs(os.path.join(repository_root, temp_dir), mode = 0o2750, exist_ok = True)

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

    ``<span>`` タグに包んだ HTML テキストを返す。
    ``text`` が 2行以上ある場合、 ``<span>`` タグにはクラス ``multilines``
    が設定される。 CSS はこれを見て 3点リーダーを表示する等の制御を行う。
    '''
    text = text if text else ""
    lines = text.split("\n")
    return Markup('<span' + (' class="multilines"' if len(lines) > 1 else '') + '>') \
        + lines[0] + Markup('</span>')

@app.template_filter('markup_summary')
def filter_markup_summary(text, default_summary = "(no summary text)"):
    '''
    概要テキストを HTML 化するフィルター

    :param str text: テキスト
    :return: 全文を含む HTML テキスト

    ``<p>`` タグに包んだ HTML テキストを返す。
    ``text`` 中の改行は ``<br>`` タグに変換される。
    '''
    return (Markup('<p>') + (text or default_summary)
        + Markup('</p>')).replace("\n", Markup("<br>"))

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
    token = secrets.token_urlsafe(8)
    login_session["session_datas"].append({
        "session_id": login_session["session_id"],
        "name": "{}-token".format(form_name),
        "value": token,
    })
    data = {n["name"]: n["value"] for n in login_session["session_datas"]}
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

@app.errorhandler(Exception)
def log_by_exception(exc):
    if not isinstance(exc, HTTPException):
        logger_err.exception("Not handled error was raised.")
    return exc

@app.route('/')
def page_index():
    '''
    トップページ

    :return: トップページテンプレート

    ログイン済みであればアカウントに参照権限のあるディレクトリのリストを表示する。
    それ以外の場合、ログインページへのリンクを表示する。
    '''
    # ログイン状態チェック
    login_session, _ = verify_login_session()

    acc_info, dirs = {}, []
    if login_session:
        acc_info = db.get_account(login_session["user_id"])
        dirs = db.get_directories_for(login_session["user_id"])

    return render_template('index.html', **acc_info, directories = dirs)

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
            "Authentication failed. Accessed from <%s> (tried id = '%s', pass = '%s')",
            request.remote_addr, user_id, password)
        return render_template('login.html', url = location_path, user_id = user_id,
            message_contents = Markup('<p class="error">ユーザー ID またはパスワードが一致しません。</p>'))

@app.route('/logout')
def page_logout():
    '''
    ログアウトページ

    :return: トップページへのリダイレクト
    '''
    # ログイン状態チェック
    login_session, _ = verify_login_session()
    if login_session:
        db.delete_login_session(login_session["session_id"])

    return redirect("/")

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

    user_id = request.form["id"].strip()
    display_name = request.form["dn"].strip()
    password = secrets.token_urlsafe(int(conf["Security"]["AutoPasswordLength"]))

    def error_page(msg):
        return render_template("edit-account.html", is_new = True,
            target_user = { "user_id": user_id, "display_name": display_name },
            message_contents = Markup('<p class="error">') + msg + Markup('</p>'))

    if not validator.validateNameToken(user_id):
        return error_page(
            "ユーザーID は半角英字で始まり半角英数字とアンダーバー _ 、ハイフン - のみで構成される名前にしてください。")

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

    display_name = request.form["dn"].strip()
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

    dir_name = request.form["nm"].strip()
    summary = request.form["sm"].strip()
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

    if dir_name == "":
        return error_page("ディレクトリ名を入力してください。")
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

    # ID のディレクトリ情報を取得 (取れない場合は 404)
    target_dir = db.get_directory(dir_id)
    if not target_dir:
        return abort(404)

    raw_form = urllib.parse.parse_qsl(request.get_data(as_text = True))

    # フォームトークンの検証に失敗した場合は Bad Request
    form_token = request.form["tk"]
    if not verify_form_token(login_session, "edit-directory", form_token):
        return abort(400)

    dir_name = request.form["nm"].strip()
    summary = request.form["sm"].strip()
    expires_days = int(request.form["ed"])
    target_dir.update({
        "directory_name": dir_name,
        "summary": summary,
        "expires_days": expires_days,
    })
    permissions = [n[1] for n in raw_form if n[0] == "pm"]

    users = db.get_all_accounts()
    for user in users:
        user["allow"] = user["user_id"] in permissions

    def error_page(msg):
        form_token = gen_form_token(login_session, "edit-directory")
        return render_template("edit-directory.html", is_new = False, form_token = form_token,
            target_dir = target_dir, users = users,
            message_contents = Markup('<p class="error">') + msg + Markup('</p>'))

    if not permissions:
        return error_page("参照権限ユーザーを一人以上選択してください。")
    try:
        directory = db.update_directory(dir_id, dir_name, expires_days, summary)
    except TmpboxDBDuplicatedException as exc:
        return error_page("".join(exc.args))

    db.update_permission(dir_id, permissions)

    return render_template("edit-directory.html", is_new = False, form_token = form_token,
        target_dir = directory, users = users,
        message_contents = Markup('<p class="info">ディレクトリの情報を更新しました。</p>'))

@app.route('/<int:dir_id>', methods = ['GET'])
def page_directory(dir_id):
    '''
    ディレクトリページ

    :param int dir_id: ディレクトリ ID
    :return: ディレクトリページテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    dir = db.get_directory(dir_id)
    if not dir or login_session["user_id"] not in [n["user_id"] for n in dir["permissions"]]:
        return abort(404)

    return render_page_directory(login_session, dir)

@app.route('/<int:dir_id>', methods = ['POST'])
def post_directory(dir_id):
    '''
    ファイルアップロードまたはファイル削除受信処理

    :param int dir_id: ディレクトリ ID
    :return: ディレクトリページテンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    dir = db.get_directory(dir_id)
    if not dir or login_session["user_id"] not in [n["user_id"] for n in dir["permissions"]]:
        return abort(404)

    raw_form = urllib.parse.parse_qsl(request.get_data(as_text = True))
    logger_err.debug("Raw form URL = '{}'".format(raw_form))

    command = request.form["c"]
    form_token = request.form["tk"]

    if (command == "up"):   # ファイルアップロード
        if not verify_form_token(login_session, "upload", form_token):
            return abort(400)

        # 受信データサイズをチェック (でかすぎる場合はけんもほろろに Bad Request)
        if request.content_length > int(conf["Security"]["MaxFormLengthWithFile"]):
            return abort(400)

        file = request.files["fp"]
        with tempfile.NamedTemporaryFile(dir = os.path.join(repository_root, temp_dir), delete = False) as fout:
            file.save(fout)
            tmp_path = fout.name
        expires = datetime.strptime(request.form["ep"], "%Y-%m-%d").date()
        summary = request.form["sm"].strip()
        file_id = db.register_file(file.filename, dir_id, expires, login_session["user_id"], summary)
        os.rename(tmp_path, os.path.join(repository_root, upload_files_dir, str(file_id)))
        message = 'ファイル "{}" を登録しました。'.format(file.filename)

    elif (command == "del"):    # ファイル削除
        if not verify_form_token(login_session, "delete", form_token):
            return abort(400)

        file_id = int(request.form["fid"])
        file_name = db.delete_file(dir_id, file_id)
        if not file_name:
            return abort(404)

        message = 'ファイル "{}" を削除しました。'.format(file_name)

    return render_page_directory(login_session, dir,
        Markup('<p class="info">') + message + Markup('</p>'))

def render_page_directory(login_session, dir, message = ''):
    files = db.get_active_files(dir["directory_id"])
    default_expires = date.today() + timedelta(days = dir["expires_days"])
    accounts = {n["user_id"]: n for n in db.get_all_accounts()}

    upload_form_token = gen_form_token(login_session, "upload")
    delete_form_token = gen_form_token(login_session, "delete")
    return render_template("directory.html",
        dir = dir, files = files, user_id = login_session["user_id"],
        expires = default_expires, accounts = accounts,
        upload_form_token = upload_form_token, delete_form_token = delete_form_token,
        message_contents = message)

@app.route("/<int:dir_id>/<int:file_id>", methods = ["GET"])
def get_download_file(dir_id, file_id):
    '''
    ファイルダウンロード処理

    :param int dir_id: ディレクトリ ID
    :param int file_id: ファイル ID
    :return: ファイル送信レスポンス
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    dir = db.get_directory(dir_id)
    if not dir or login_session["user_id"] not in [n["user_id"] for n in dir["permissions"]]:
        logger_err.error("Permission failed for directory <%s> by user <%s>",
            "{}: {}".format(dir["directory_id"], dir["directory_name"]), login_session["user_id"])
        return abort(404)

    file = db.get_file(dir_id, file_id)
    if not file:
        logger_err.error("File not found in directory <%s> (file_id = <%d>)",
            "{}: {}".format(dir["directory_id"], dir["directory_name"]), file_id)
        return abort(404)

    return send_file(os.path.join(repository_root, upload_files_dir, str(file["file_id"])),
        as_attachment = True, attachment_filename = file["origin_file_name"])

@app.route("/profile", methods = ["GET"])
def page_profile():
    '''
    ユーザー設定画面

    :return: ユーザー設定画面テンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    user = db.get_account(login_session["user_id"])
    token = gen_form_token(login_session, "profile")
    return render_template("profile.html", form_token = token, user = user)

@app.route("/profile", methods = ["POST"])
def post_profile():
    '''
    ユーザー設定を登録する処理

    :return: ユーザー設定画面テンプレート
    '''
    # ログイン状態チェック
    login_session, redirect_obj = verify_login_session()
    if not login_session: return redirect_obj

    # フォームトークンの検証に失敗した場合は Bad Request
    form_token = request.form["tk"]
    if not verify_form_token(login_session, "profile", form_token):
        return abort(400)

    user = db.get_account(login_session["user_id"])
    token = gen_form_token(login_session, "profile")

    display_name = request.form["dn"].strip()
    new_password = None
    want_change_password = request.form["pwm"] == "1"
    if want_change_password:
        if not check_password_hash(user["password_hash"], request.form["cpw"]):
            logger_err.error(
                "Authentication failed at change password request. "
                    + "Accessed from <%s> (tried id = '%s', pass = '%s')",
                request.remote_addr, user_id, password)
            return render_template("profile.html", form_token = token, user = user,
                message_contents = Markup('<p class="error">')
                    + "現在のパスワードが正しくありません。入力し直してください。"
                    + Markup('</p>'))
        new_password = request.form["npw"]
        new_password_for_validation = request.form["npw2"]
        if new_password != new_password_for_validation:
            logger_err.error("Unmatched new passwords ('%s' and '%s').",
                new_password, new_password_for_validation)
            return render_template("profile.html", form_token = token, user = user,
                message_contents = Markup('<p class="error">')
                    + "確認用パスワードが一致しません。入力し直してください。"
                    + Markup('</p>'))

    user = db.modify_account(login_session["user_id"], display_name, new_password)
    return render_template("profile.html", form_token = token, user = user,
        message_contents = Markup('<p class="info">')
            + "アカウント情報を更新しました。"
            + Markup('</p>'))
