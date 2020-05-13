import os, sys, locale, pwd, grp, re, configparser
from getpass import getpass
from sqlalchemy import create_engine
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from tmpbox_db_accessor import TmpboxDB

default_unix_user = "tmpbox"
default_file_dir = "/var/tmpbox"

default_auto_password_length = 12
default_session_expires_minutes = 120
default_file_expires_days = 14
max_form_length = 10000
max_form_length_with_file = 200 * 1024 * 1024
default_debug_url_port = "6543"

prompt_msg = {
    "ja_JP": {
        "UNIX-user": [
            "tmpbox Web アプリケーションを実行する UNIX アカウントのユーザー名を指定してください。",
            "([{0}]) >> ",
        ],
        "UNIX-group": [
            "UNIX アカウントのグループ名も指定してください。",
            "([{0}]) >> ",
        ],
        "confirm-usermod": [
            "ユーザー {user} はグループ {group} に属していません。",
            "指定したグループに属するようにユーザー情報を変更してよろしいですか?",
            "([Y]/n) >> ",
        ],
        "repository-root": [
            "アプリケーションが使用するファイル (アップロードされたファイルやログファイル等) を",
            "保存するディレクトリを指定してください。",
            "([{0}]) >> ",
        ],
        "DB-connection-string": [
            "DB 接続文字列を driver://user:password@host/dbname 形式で指定してください。",
            "ex) mysql://tmpbox_master:password@localhost/tmpbox",
            ">> ",
        ],
        "admin-user-id": [
            "管理者アカウントの設定を行います。",
            "ユーザーID >> ",
        ],
        "admin-display-name": [
            "表示名 >> ",
        ],
        "admin-password": [
            "パスワード >> ",
        ],
        "admin-password-repeat": [
            "念のため、もう一度 >> ",
        ],
        "debug-url-port": [
            "uWSGI を用いてデバッグ実行を行う際に使用するポート番号を指定してください。",
            "([{0}]) >> ",
        ],
        "error-useradd": [
            "UNIX アカウントの追加または変更に失敗しました。",
            "管理者権限が必要です。 sudo をお試しください。",
        ],
        "error-unix-group": [
            "指定された UNIX ユーザーとグループの組み合わせでは処理を続行できません。",
            "最初からやり直してください。",
        ],
        "error-makedirs": [
            "ディレクトリの作成に失敗しました。権限がありません。 sudo をお試しください。",
        ],
        "error-DB-module": [
            "対応する DB モジュールがインストールされていません。",
        ],
        "error-admin-password-repeat": [
            "入力したパスワードが一致しません。",
        ],
        "error-url-port": [
            "ポート番号は 1024 〜 65535 の範囲内の整数を指定してください。",
        ],
    },
    "C": {
        "UNIX-user": [
            "Enter an UNIX user name for executing `tmpbox` web-application.",
            "([{0}]) >> ",
        ],
        "UNIX-group": [
            "Enter an UNIX group name too.",
            "([{0}]) >> ",
        ],
        "confirm-usermod": [
            "User {user} is not member in group of {group}.",
            "Shall I modify the user to join into the group?",
            "([Y]/n) >> ",
        ],
        "repository-root": [
            "Set directory path for saving files what is used by this application",
            "(uploaded files, log files, etc...).",
            "([{0}]) >> ",
        ],
        "DB-connection-string": [
            "Enter DB connection string formatted like `driver://user:password@host/dbname`.",
            "ex) mysql://tmpbox_master:password@localhost/tmpbox",
            ">> ",
        ],
        "admin-user-id": [
            "Enter administrator account.",
            "User ID >> ",
        ],
        "admin-display-name": [
            "Administrator's name for displaying >> ",
        ],
        "admin-password": [
            "Password >> ",
        ],
        "admin-password-repeat": [
            "Password again >> ",
        ],
        "debug-url-port": [
            "Enter the port number to be used when performing debug execution using uWSGI.",
            "([{0}]) >> ",
        ],
        "error-useradd": [
            "Adding or modifying UNIX user account failed.",
            "You need to change superuser. Retry with sudo.",
        ],
        "error-unix-group": [
            "Setting Can't continue with the specified UNIX user and group combination.",
            "Please try again from the beginning.",
        ],
        "error-makedirs": [
            "Permission error to make directory. Retry with sudo.",
        ],
        "error-DB-module": [
            "No DB module.",
        ],
        "error-admin-password-repeat": [
            "There's no match between your entered password.",
        ],
        "error-url-port": [
            "You need to specify digit between 1024 <= N <= 65535 for port number.",
        ],
    }
}

lang = locale.getlocale()[0]
prompt_msg = prompt_msg.get(lang, prompt_msg["C"])

def prompt(msg, validator = None, default = None, want_secret = False):
    '''
    プロンプトメッセージを表示して入力を受け取る

    :param list msg: 表示するメッセージのシーケンス
    :param function validator: 入力内容のチェックを行う関数
    :param str default: 何も入力しなかった場合のデフォルト値
    :param bool want_secret: パスワード入力等、エコーバックしたくないケースか
    :return: 入力され、 ``validator()`` によるチェックを通過した値
    :rtype: str

    ``validator`` は入力値を引数として受け取り、チェック結果を ``bool`` 値で返す
    関数を指定する (問題がなければ ``True`` を返すこと)。
    '''
    msg = "\n".join(msg).format(default)
    result = getpass(msg) if want_secret else input(msg)
    result = result or default
    while not result or validator and not validator(result):
        notice(["Invalid input value. Please try again."])
        result = getpass(msg) if want_secret else input(msg)
        result = result or default

    return result

def notice(msg):
    '''
    プロンプトメッセージを出力する

    :param list msg: 表示するメッセージのシーケンス
    '''
    msg = "{}: {}".format(__file__, "\n{}: ".format(__file__).join(msg))
    print(msg, file = sys.stderr)

def validate_unix_group(grname):
    '''
    UNIX グループ名を検証する

    :param str grname: UNIX グループ名として入力された名前
    :param str uname: UNIX ユーザー名として入力された名前
    :return: 問題なければ ``True`` を、それ以外の場合は ``False`` を返す

    この関数では、指定されたグループ名が実在することを確認する。
    指定したユーザーがグループに属しているかどうかの確認は別途行うこと。
    '''
    if not re.match(r"\w[\w\d_]*\Z", grname, re.A | re.I):
        return False
    gr_info = grp.getgrnam(grname)
    if not gr_info:
        return False
    return True

def validate_yn(val):
    '''
    回答が Y か N のどちらかになっていることを確認する。

    :param str val: ユーザー入力値
    :return 問題なければ ``True`` を、それ以外の場合は ``False`` を返す
    '''
    return isinstance(val, str) and len(val) == 1 and val in 'yYnN'

def validate_DB_connection(conn_str):
    '''
    DB 接続文字列を検証する

    :param str conn_str: DB 接続文字列として入力された値
    :return 問題なければ ``True`` を、それ以外の場合は ``False`` を返す

    実際に SQLAlchemy を用いて接続を試みます。
    '''
    try:
        conn = create_engine(conn_str)
        conn.execute("select 1").scalar()
    except ModuleNotFoundError:
        notice(prompt_msg["error-DB-module"])
        return False
    except Exception:
        return False
    return True

def validate_URL_port(port_num):
    '''
    通信ポート番号として入力された値を検証する

    :param str port_num: 通信ポート番号として入力された値
    :return: 問題なければ ``True`` を、それ以外の場合は ``False`` を返す。

    ポート番号は 1024 〜 65535 の範囲内の整数でなければならない。
    '''
    if port_num.isdigit() and 1024 <= int(port_num) <= 65535:
        return True
    else:
        notice(prompt_msg["error-url-port"])
        return False

if __name__ == '__main__':
    # tmpbox を実行する UNIX アカウントを設定
    re_name_token = re.compile(r"[a-z][\w\-]*\Z", re.I | re.A)
    unix_user = prompt(prompt_msg["UNIX-user"], lambda x: re_name_token.match(x), default_unix_user)
    try:
        pwd.getpwnam(unix_user)
    except KeyError:
        # 存在しないアカウントなら追加を試みる
        res = os.system("useradd {}".format(unix_user))
        if res != 0:
            # アカウントの追加に失敗 - superuser ではない?
            notice(prompt_msg["error-useradd"])
            sys.exit(1)
    # UNIX グループ名も設定
    unix_group = prompt(prompt_msg["UNIX-group"], validate_unix_group, unix_user)
    # UNIX アカウントがグループに属しているか確認
    if unix_group != unix_user and unix_user not in grp.getgrnam(unix_group)[3]:
        # 属していない場合、グループに属するよう UNIX アカウントを変更してよいか確認する
        msg = prompt_msg["confirm-usermod"]
        msg[0] = msg[0].format(user = unix_user, group = unix_group)
        ans = prompt(msg, validate_yn, 'Y')
        if ans in 'nN':
            notice(prompt_msg["error-unix-group"])
            sys.exit(1)
        # UNIX アカウントの変更を試みる
        groups = [n[0] for n in grp.getgrall() if unix_user in n[3]]
        groups.append(unix_group)
        res = os.system("usermod -G '{0}' {1}".format(','.join(groups), unix_user))
        if res != 0:
            # アカウントの変更に失敗 - superuser ではない?
            notice(prompt_msg["error-useradd"])
            sys.exit(1)

    # アプリケーションが使用するファイルの保存先を決める
    uid, gid = pwd.getpwnam(unix_user)[2], grp.getgrnam(unix_group)[2]
    file_dir = prompt(prompt_msg["repository-root"], None, default_file_dir)
    try:
        os.makedirs(os.path.join(file_dir, "run"), exist_ok = True)
        os.makedirs(os.path.join(file_dir, "log"), exist_ok = True)
        os.chown(file_dir, uid, gid)
        os.chown(os.path.join(file_dir, "run"), uid, gid)
        os.chown(os.path.join(file_dir, "log"), uid, gid)
        os.chmod(file_dir, 0o2750)
        os.chmod(os.path.join(file_dir, "run"), 0o2750)
        os.chmod(os.path.join(file_dir, "log"), 0o2750)
    except PermissionError:
        notice(prompt_msg["error-makedirs"])
        sys.exit(1)

    # DB 接続設定
    conn_str = prompt(prompt_msg["DB-connection-string"], validate_DB_connection)

    # 管理者アカウントの設定
    admin_user = prompt(prompt_msg["admin-user-id"], lambda x: re_name_token.match(x))
    admin_disp_name = prompt(prompt_msg["admin-display-name"])
    while True:
        admin_pw = prompt(prompt_msg["admin-password"], want_secret = True)
        if admin_pw == prompt(prompt_msg["admin-password-repeat"], want_secret = True):
            break
        notice(prompt_msg["error-admin-password-repeat"])

    # DB の初期設定を行う
    db = TmpboxDB(conn_str)
    db.create_tables()
    db.setup_system(minutes = default_session_expires_minutes)
    db.register_account(admin_user, admin_disp_name, admin_pw, True)

    # 設定ファイル出力
    conf = configparser.ConfigParser()
    conf.optionxform = str  # オプション名が勝手に小文字に書き換えられてしまうのを防ぐ
    conf["User"] = {
        "User": unix_user,
        "Group": unix_group,
    }
    conf["DB"] = {
        "ConnectionString": conn_str,
    }
    conf["Repository"] = {
        "DirectoryRoot": file_dir,
    }
    conf["UploadFiles"] = {
        "DefaultExpiresDays": default_file_expires_days,
    }
    conf["Security"] = {
        "AutoPasswordLength": default_auto_password_length,
        "MaxFormLength": max_form_length,
        "MaxFormLengthWithFile": max_form_length_with_file,
    }
    with open(os.path.join("src", "conf.d", "tmpbox.ini"), "w") as fout:
        conf.write(fout)

    # ログ出力設定ファイル出力
    logconf = configparser.ConfigParser(interpolation = None)
    logconf.optionxform = str
    logconf["loggers"] = {
        "keys": "root, access, error, debug",
    }
    logconf["handlers"] = {
        "keys": "acc_cons, acc_file, err_cons, err_file, dbg_cons, dbg_file",
    }
    logconf["formatters"] = {
        "keys": "console, file",
    }
    logconf["logger_root"] = {
        "level": "NOTSET",
        "handlers": "",
    }
    logconf["logger_access"] = {
        "level": "INFO",
        "handlers": "acc_cons, acc_file",
        "qualname": "access",
    }
    logconf["logger_error"] = {
        "level": "WARNING",
        "handlers": "err_cons, err_file",
        "qualname": "error",
    }
    logconf["logger_debug"] = {
        "level": "DEBUG",
        "handlers": "dbg_cons, dbg_file",
        "qualname": "debug",
    }
    handler_kinds = (("acc", "access"), ("err", "error"), ("dbg", "debug"))
    for k, f in handler_kinds:
        logconf["handler_{}_cons".format(k)] = {
            "class": "StreamHandler",
            "level": "NOTSET",
            "formatter": "console",
        }
        logconf["handler_{}_file".format(k)] = {
            "class": "handlers.RotatingFileHandler",
            "level": "NOTSET",
            "formatter": "file",
            "args": (os.path.join(file_dir, "log", "{}.log".format(f)),),
            "kwargs": {"maxBytes": 5242880, "backupCount": 10},
        }
    logconf["formatter_console"] = {
        "format": "[%(levelname)s] %(name)s: %(message)s",
    }
    logconf["formatter_file"] = {
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S",
    }
    with open(os.path.join("src", "conf.d", "logging.ini"), "w") as fout:
        logconf.write(fout)

    # uWSGI 用設定ファイル出力
    uwsgi_conf = configparser.ConfigParser(interpolation = None)
    uwsgi_conf.optionxform = str
    uwsgi_conf["uwsgi"] = {
        "uid": unix_user,
        "gid": unix_group,
        "current_release": os.path.join(os.path.abspath(os.path.dirname(__file__)), 'src'),
        "chdir": "%(current_release)",
        "wsgi-file": "%(current_release)/tmpbox.py",
        "callable": "app",
        "socket": os.path.join(file_dir, "run", "uwsgi-tmpbox.sock"),
        "pidfile": os.path.join(file_dir, "run", "uwsgi-tmpbox.pid"),
        "chmod-socket": "666",
        "vacuum": "true",
        "daemonize": os.path.join(file_dir, "log", "uwsgi-tmpbox.log"),
        "log-reopen": "true",
        "log-maxsize": 5242880,
        "logfile-chown": "on",
        "logfile-chmod": "644",
        "processes": 1,
        "threads": 4,
        "max-requests": 500,
        "max-requests-delta": 300,
        "master": "true",
    }
    with open(os.path.join("src", "conf.d", "uwsgi-daemon.ini"), "w") as fout:
        uwsgi_conf.write(fout)

    debug_url_port = prompt(prompt_msg["debug-url-port"], validate_URL_port, default_debug_url_port)
    uwsgi_conf = configparser.ConfigParser(interpolation = None)
    uwsgi_conf.optionxform = str
    uwsgi_conf["uwsgi"] = {
        "uid": unix_user,
        "gid": unix_group,
        "current_release": os.path.join(os.path.abspath(os.path.dirname(__file__)), 'src'),
        "chdir": "%(current_release)",
        "wsgi-file": "tmpbox.py",
        "callable": "app",
        "http": "0.0.0.0:{}".format(int(debug_url_port)),
        "env": "FLASK_ENV=development",
    }
    with open(os.path.join("src", "conf.d", "uwsgi-debug.ini"), "w") as fout:
        uwsgi_conf.write(fout)
