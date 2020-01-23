import os, sys, locale
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from tmpbox_db_accessor import TmpboxDB

prompt_msg = {
    "ja_JP": {
        "save-file-directory": [
            "アップロードされたファイルを保存するディレクトリを指定してください。",
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
    },
    "C": {
        "save-file-directory": [
            "Set directory path for saving uploaded files.",
            "([{0}]) >> ",
        ],
        "DB-connection-string": [
            "Set DB connection string formatted like `driver://user:password@host/dbname`.",
            "ex) mysql://tmpbox_master:password@localhost/tmpbox",
            ">> ",
        ],
        "admin-user-id": [
            "Set administrator account.",
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
    }
}

lang = locale.getlocale()[0]
prompt_msg = prompt_msg.get(lang, prompt_msg["C"])
