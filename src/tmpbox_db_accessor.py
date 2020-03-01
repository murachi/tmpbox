import secrets
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Boolean, Integer, Unicode, LargeBinary, Date, \
    DateTime, CHAR, ForeignKey, PrimaryKeyConstraint, Index
from sqlalchemy.orm import Query, relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import functions, extract
from werkzeug.security import generate_password_hash, check_password_hash

Base = declarative_base()

class SystemData(Base):
    '''
    システム共通データテーブルクラス

    :var secret_key: Flask の Session 機能で使用するシークレットキー
    :var session_expires_minutes: ログインセッションの有効期間 (分単位)
    '''
    __tablename__ = 'system_data'

    dummy_id = Column(Integer, nullable = False, primary_key = True)
    secret_key = Column(LargeBinary(16), nullable = False)
    session_expires_minutes = Column(Integer, nullable = False)

    def __init__(self, minutes):
        self.secret_key = secrets.token_bytes(16)
        self.session_expires_minutes = minutes

    def to_dict(self):
        return {
            "secret_key": self.secret_key,
            "session_expires_minutes": self.session_expires_minutes,
        }

class SessionState(Base):
    '''
    ユーザーログインセッション状態管理テーブルクラス
    '''
    __tablename__ = 'session_state'

    session_id = Column(CHAR(43), nullable = False, primary_key = True)
    user_id = Column(Unicode(50), nullable = False)
    access_dt = Column(DateTime, nullable = False, server_default = functions.now())

    session_datas = relationship("SessionData", back_populates = "session_state")

    def __init__(self, user_id):
        self.session_id = secrets.token_urlsafe(32)
        self.user_id = user_id

    def to_dict(self, with_relation = True):
        '''
        辞書に変換

        :param bool with_relation: リレーションメンバーの値を含めるか?
        :return: メンバー値を含む辞書を返す
        '''
        result = {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "access_dt": self.access_dt,
        }
        if with_relation:
            result.update({
                "session_datas": [n.to_dict(with_relation = False) for n in self.session_datas],
            })
        return result

    @staticmethod
    def filter_check_expires(engine, query):
        '''
        クエリーに期限切れ判定のフィルターを付加する

        :param sqlalchemy.engine.base.Engine engine: SQLAlchemy エンジンオブジェクト
        :param sqlalchemy.orm.query.Query query: SQLAlchemy クエリーオブジェクト
        :return: フィルターを付加したクエリーオブジェクト

        ``query`` に渡すクエリーは既に ``SessionState`` を SELECT し、
        ``SystemData`` を JOIN しているものとする。
        '''
        if engine.name == 'postgresql':
            query = query.filter(
                extract('epoch', functions.now() - SessionState.access_dt)
                    < SystemData.session_expires_minutes * 60)
        elif engine.name == 'mysql':
            query = query.filter(
                func.timestampdiff(text('minute'), SessionState.access_dt, functions.now())
                    < SystemData.session_expires_minutes)
        elif engine.name == 'mssql':
            #memo: そもそも MSSQL って functions.now() 使えるの? func.getdate() とかにしないとダメなんじゃ…
            query = query.filter(
                func.dateadd(text('minute'), SystemData.session_expires_minutes, SessionState.access_dt)
                    > functions.now())
        elif engine.name == 'oracle':
            #memo: Oracle も functions.now() じゃなくて func.sysdate() とかにしないとダメな気がする…
            query = query.filter(
                SessionState.access_dt + SystemData.session_expires_minutes / 1440 > functions.now())
        else:
            raise NotImplementedError("{} はサポート対象外です".format(engine.name))

        return query

class SessionData(Base):
    '''
    セッションデータテーブルクラス
    '''
    __tablename__ = 'session_data'

    session_id = Column(CHAR(43), ForeignKey("session_state.session_id"), nullable = False)
    name = Column(Unicode(50), nullable = False)
    value = Column(Unicode(1000), nullable = False)
    __table_args__ = (
        PrimaryKeyConstraint("session_id", "name")
    )

    session_state = relationship("SessionState", back_populates = "session_datas")

    def __init__(self, session_id, name, value):
        self.session_id = session_id
        self.name = name
        self.value = value

    def to_dict(self, with_relation = True):
        '''
        辞書に変換

        :param bool with_relation: リレーションメンバーの値を含めるか?
        :return: メンバー値を含む辞書を返す
        '''
        result = {
            "session_id": self.session_id,
            "name": self.name,
            "value": self.value,
        }
        if with_relation:
            result.update({
                "session_state": self.session_state.to_dict(with_relation = False),
            })
        return result

class Account(Base):
    '''
    アカウント情報テーブルクラス
    '''
    __tablename__ = 'account_info'

    user_id = Column(Unicode(50), nullable = False, primary_key = True)
    display_name = Column(Unicode(100), nullable = False)
    password_hash = Column(Unicode(500), nullable = False)
    is_admin = Column(Boolean, nullable = False, server_default = False)

    def __init__(self, user_id, display_name, password):
        '''
        コンストラクタ

        :param str user_id: ユーザー ID
        :param str display_name: 表示名
        :param str password: パスワード

        ``password`` にはハッシュ化する前の平文を渡すこと。
        '''
        self.user_id = user_id
        self.display_name = display_name
        self.password_hash = generate_password_hash(password)

    def to_dict(self):
        '''
        辞書に変換

        :return: メンバー値を含む辞書を返す
        '''
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "is_admin": self.is_admin,
        }

    def check_password(self, password):
        '''
        パスワードが一致するかを確認する

        :param str password: パスワード (平文)
        :return: パスワードが一致する場合は ``True`` を返す。
        '''
        return check_password_hash(self.password_hash, password)

class Directory(Base):
    '''
    ディレクトリテーブルクラス
    '''
    __tablename__ = 'directory'

    directory_name = Column(Unicode(100), nullable = False, primary_key = True)
    create_date = Column(Date, nullable = False, server_default = functions.current_date())
    summary = Column(Unicode)
    expires_days = Column(Integer, nullable = False)

    permissions = relationship("Permission", back_populates = "directory")

    def __init__(self, dir_name, expires_days):
        '''
        コンストラクタ

        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間

        ファイルのデフォルトの保存期限は、ファイル登録日の `expires_days` 日後となる。

        `summary` はインスタンス生成後に呼び出し側で格納すること。
        '''
        self.directory_name = dir_name
        self.expires_days = expires_days

    def to_dict(self, with_relation = True):
        '''
        辞書に変換

        :param bool with_relation: リレーションメンバーの値を含めるか?
        :return: メンバー値を含む辞書を返す
        '''
        result = {
            "directory_name": self.directory_name,
            "create_date": self.create_date,
            "summary": self.summary,
            "expires_days": self.expires_days,
        }
        if with_relation:
            result.update({
                "permissions": [n.to_dict(with_relation = False) for n in self.permissions],
            })
        return result

class Permission(Base):
    '''
    ディレクトリ参照権限テーブルクラス

    ディレクトリ名とユーザー ID の組み合わせが存在すれば、そのユーザーはそのディレクトリにアクセスできることを示す。
    '''
    __tablename__ = 'permission'

    directory_name = Column(Unicode(100), ForeignKey('directory.directory_name'), nullable = False)
    user_id = Column(Unicode(50), ForeignKey('account_info.user_id'), nullable = False)
    __table_args__ = (
        PrimaryKeyConstraint('directory_name', 'user_id'),
    )

    directory = relationship('Directory', back_populates = 'permissions')
    user = relationship('Account')

    def __init__(self, dir_name, user_id):
        '''
        コンストラクタ

        :param str dir_name: ディレクトリ名
        :param str user_id: ユーザー ID
        '''
        self.directory_name = dir_name
        self.user_id = user_id

    def to_dict(self, with_relation = True):
        '''
        辞書に変換

        :param bool with_relation: リレーションメンバーの値を含めるか?
        :return: メンバー値を含む辞書を返す
        '''
        result = {
            "directory_name": self.directory_name,
            "user_id": self.user_id,
        }
        if (with_relation):
            result.update({
                "directory": self.directory.to_dict(with_relation = False),
                "user": self.user.to_dict(with_relation = False),
            })
        return result

class File(Base):
    '''
    ファイルテーブルクラス
    '''
    __tablename__ = 'file_info'

    file_id = Column(Integer, nullable = False, primary_key = True, autoincrement = True)
    origin_file_name = Column(Unicode(500), nullable = False)
    registered_user_id = Column(Unicode(50), ForeignKey('account_info.user_id'), nullable = False)
    registered_date = Column(Date, nullable = False, server_default = functions.current_date())
    summary = Column(Unicode)
    directory_name = Column(Unicode(100), ForeignKey('directory.directory_name'), nullable = False)
    expires = Column(Date, nullable = False)
    is_deleted = Column(Boolean, nullable = False, server_default = False)

    __table_args__ = (
        Index("idx_file_active", directory_name, expires.desc(), is_deleted, file_id.desc()),
    )

    registered_user = relationship('Account')
    directory = relationship('Directory')

    def __init__(self, file_name, user_id, dir_name, expires):
        '''
        コンストラクタ

        :param str file_name: オリジナルファイル名
        :param str user_id: 登録者のアカウントユーザー ID
        :param str dir_name: 登録先のディレクトリ名
        :param datetime.date expires: 保存期限
        '''
        self.origin_file_name = file_name
        self.registered_user_id = user_id
        self.directory_name = dir_name
        self.expires = expires

    def to_dict(self):
        '''
        辞書に変換

        :return: メンバー値を含む辞書を返す
        '''
        return {
            "file_id": self.file_id,
            "origin_file_name": self.origin_file_name,
            "registered_user_id": self.registered_user_id,
            "registered_user_display_name": self.registered_user.display_name,
            "registered_date": self.registered_date,
            "summary": self.summary,
            "directory_name": self.directory_name,
            "expires": self.expires,
            "is_deleted": self.is_deleted,
        }

class TmpboxDBDuplicatedException(ValueError):
    '''
    主キー重複に相当する操作例外クラス
    '''
    pass

class TmpboxDB:
    '''
    tmpbox DB アクセサ
    '''
    def __init__(self, con_str):
        '''
        コンストラクタ

        :param str con_str: SQLAlchemy 用 DB 接続文字列
        '''
        self.connection_string = con_str
        self.engine = None

    def session_scope(self, query_func, need_commit = False):
        '''
        セッションスコープ

        :param function query_func: クエリーを行う関数
        :param bool need_commit: コミットを行う必要のある処理か?

        ``query_func`` の第1引数には SQLAlchemy のセッションオブジェクトが渡される。
        '''
        if not self.engine:
            self.engine = create_engine(self.connection_string)
        session = Session(bind = self.engine)

        try:
            result = query_func(session)
            if need_commit:
                session.commit()
            else:
                session.rollback()
        except:
            session.rollback()
            raise
        finally:
            session.close()

        return result

    def create_tables(self):
        '''
        テーブルを作成する

        アプリのセットアップ時に一度だけ実行する。
        '''
        if not self.engine:
            self.engine = create_engine(self.connection_string)

        Base.metadata.create_all(self.engine)

    def register_account(self, user_id, display_name, password, is_admin = False):
        '''
        アカウントを登録する

        :param str user_id: ユーザー ID
        :param str display_name: 表示名
        :param str password: パスワード (平文)
        :param bool is_admin: 管理者権限か?
        :return: 登録したユーザーアカウント情報の辞書
        '''
        return self.session_scope(
            lambda s: self.__session_register_account(s, user_id, display_name, password, is_admin),
            True)

    def __session_register_account(self, session, user_id, display_name, password, is_admin):
        '''
        アカウントを登録するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str user_id: ユーザー ID
        :param str display_name: 表示名
        :param str password: パスワード (平文)
        :param bool is_admin: 管理者権限か?
        :return: 登録したユーザーアカウント情報の辞書
        '''
        # 既存 ID ではないか確認
        existing_user_id = session.query(Account.user_id).filter(Account.user_id == user_id).scalar()
        if existing_user_id is not None:
            raise TmpboxDBDuplicatedException("ユーザー ID '{0}' は既に使われています。".format(user_id))

        account = Account(user_id, display_name, password)
        if is_admin:
            account.is_admin = True
        session.add(account)

        return account.to_dict()

    def modify_account(self, user_id, display_name, password = None):
        '''
        アカウントの情報を変更する

        :param str user_id: ユーザー ID
        :param str display_name: 表示名
        :param str password: パスワード (平文) / 変更しない場合は None を指定する
        :return: 変更したユーザーアカウント情報の辞書
        '''
        return self.session_scope(
            lambda s: self.__session_modify_account(s, user_id, display_name, password),
            True)

    def __session_modify_account(self, session, user_id, display_name, password):
        '''
        アカウントの情報を変更するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str user_id: ユーザー ID
        :param str display_name: 表示名
        :param str password: パスワード (平文) / 変更しない場合は None を指定する
        :return: 変更したユーザーアカウント情報の辞書
        '''
        account = session.query(Account).filter(Account.user_id == user_id).one()
        account.display_name = display_name
        if password:
            account.password_hash = generate_password_hash(password)

        return account.to_dict()

    def check_authentication(self, user_id, password):
        '''
        アカウントの認証を確認する

        :param str user_id: ユーザー ID
        :param str password: パスワード (平文)
        :return: 認証を確認できた場合は ``True`` を、それ以外の場合は ``False`` を返す。

        ``password`` に ``None`` を指定すると ``TypeError`` 例外が送出されるので注意すること。
        '''
        return self.session_scope(
            lambda s: (lambda acc: acc.check_password(password) if acc else False)(
                s.query(Account).filter(Account.user_id == user_id).scalar())
        )

    def get_account(self, user_id):
        '''
        アカウント情報を取得する

        :param str user_id: ユーザー ID
        :return: アカウント情報の辞書
        '''
        return self.session_scope(
            lambda s: s.query(Account).filter(Account.user_id == user_id).one().to_dict()
        )

    def get_all_accounts(self):
        '''
        アカウント情報をすべて取得する

        :return: アカウント情報辞書のシーケンス
        '''
        return self.session_scope(
            lambda s: [n.to_dict() for n in s.query(Account).order_by(Account.user_id)]
        )

    def register_directory(self, dir_name, expires_days, summary = None):
        '''
        ディレクトリの情報を登録する

        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        '''
        self.session_scope(lambda s: self.__session_register_directory(s, dir_name, expires_days, summary), True)

    def __session_register_directory(self, session, dir_name, expires_days, summary):
        '''
        ディレクトリの情報を登録するセッション処理

        :param sqlalchemy.orm.session.Session: セッションオブジェクト
        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        '''
        # 既存ディレクトリのチェック
        existing_dir = session.query(Directory.directory_name).filter(Directory.directory_name == dir_name).scalar()
        if existing_dir:
            raise TmpboxDBDuplicatedException("'{0}' という名前のディレクトリは既に存在します。".format(dir_name))
        dir = Directory(dir_name, expires_days)
        if summary:
            dir.summary = summary
        session.add(dir)

    def update_directory(self, dir_name, expires_days, summary = None):
        '''
        ディレクトリの情報を更新する

        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        :return: ディレクトリ情報の辞書
        '''
        return self.session_scope(
            lambda s: self.__session_update_directory(s, dir_name, expires_days, summary),
            True)

    def __session_update_directory(self, session, dir_name, expires_days, summary):
        '''
        ディレクトリの情報を更新する

        :param sqlalchemy.orm.session.Session: セッションオブジェクト
        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        :return: ディレクトリ情報の辞書
        '''
        directory = session.query(Directory).filter(Directory.directory_name == dir_name).one()
        directory.expires_days = expires_days
        directory.summary = summary

        return directory.to_dict(with_relation = False)

    def update_permission(self, dir_name, user_ids):
        '''
        ディレクトリの参照権限ユーザーを更新する

        :param str dir_name: ディレクトリ名
        :param list user_ids: ディレクトリへのアクセスを許可するユーザー ID のリスト
        '''
        self.session_scope(lambda s: self.__session_update_permission(s, dir_name, user_ids), True)

    def __session_update_permission(self, session, dir_name, user_ids):
        '''
        ディレクトリの参照権限ユーザーを更新するセッション処理

        :param sqlalchemy.orm.session.Session: セッションオブジェクト
        :param str dir_name: ディレクトリ名
        :param list user_ids: ディレクトリへのアクセスを許可するユーザー ID のリスト
        '''
        # 一旦全部消してから挿入し直す
        session.query(Permission).filter(Permission.directory_name == dir_name).delete()
        session.add_all([Permission(dir_name, n) for n in user_ids])

    def get_directories(self):
        '''
        ディレクトリの一覧を取得する

        :return: ディレクトリ情報辞書のリスト
        '''
        return self.session_scope(
            lambda s: [n.to_dict() for n in s.query(Directory).order_by(Directory.directory_name)]
        )

    def get_directories_for(self, user_id):
        '''
        特定ユーザーがアクセス可能なディレクトリの一覧を取得する

        :param str user_id: ユーザー ID
        :return: パーミッション情報の辞書
        '''
        return self.session_scope(
            lambda s: [
                n.directory.to_dict(with_relation = False)
                for n in s.query(Permission).filter(Permission.user_id == user_id)
            ]
        )

    def get_directory(self, dir_name):
        '''
        特定のディレクトリの情報を取得する

        :return: ディレクトリ情報の辞書
        '''
        return self.session_scope(
            lambda s: (lambda d: d.to_dict() if d else None)(
                s.query(Directory).filter(Directory.directory_name == dir_name).one())
        )

    def register_file(self, file_name, user_id, dir_name, expires, summary = None):
        '''
        ファイルを登録する

        :param str file_name: オリジナルファイル名
        :param str user_id: 登録者ユーザー ID
        :param str dir_name: 登録先ディレクトリ名
        :param datetime.date expires: 有効期限
        :param str summary: ファイルの説明
        :return: 登録に成功した場合、ファイル ID を返す。
        :rtype: int
        '''
        return self.session_scope(
            lambda s: self.__session_register_file(s, file_name, user_id, dir_name, expires, summary),
            True)

    def __session_register_file(self, session, file_name, user_id, dir_name, expires, summary):
        '''
        ファイルを登録するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str file_name: オリジナルファイル名
        :param str user_id: 登録者ユーザー ID
        :param str dir_name: 登録先ディレクトリ名
        :param datetime.date expires: 有効期限
        :param str summary: ファイルの説明
        :return: 登録に成功した場合、ファイル ID を返す。
        :rtype: int
        '''
        file = File(file_name, user_id, dir_name, expires)
        if summary is not None:
            file.summary = summary
        session.add(file)
        session.commit()
        session.refresh(file)
        return file.file_id

    def delete_file(self, dir_name, file_id):
        '''
        ファイルを論理削除する

        :param str dir_name: ファイルが存在するディレクトリ名
        :param int file_id: ファイル ID

        ``file_id`` のファイルが ``dir_name`` のディレクトリに存在しない場合、削除は行われない。
        '''
        return self.session_scope(
            lambda s: self.__session_delete_file(s, dir_name, file_id),
            True)

    def __session_delete_file(self, session, dir_name, file_id):
        '''
        ファイルを論理削除する

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str dir_name: ファイルが存在するディレクトリ名
        :param int file_id: ファイル ID
        '''
        file = session.query(File).filter(File.file_id == file_id, File.directory_name == dir_name).one_or_none()
        if file:
            file.is_deleted = True

    def get_active_files(self, dir_name):
        '''
        特定のディレクトリに含まれる有効なファイルの一覧を取得する

        :return: ファイル情報辞書のリスト
        '''
        return self.session_scope(
            lambda s: [
                n.to_dict()
                for n
                in s.query(File)
                    .filter(File.directory_name == dir_name,
                        File.expires >= functions.current_date(),
                        File.is_deleted == False)
                    .order_by(File.file_id.desc())
            ]
        )

    def get_active_file(self, dir_name, file_id):
        '''
        ファイルが有効であれば、その情報を取得する

        :param str dir_name: ディレクトリ名
        :param int file_id: ファイル ID
        :return: 有効なファイルであれば、ファイル情報の辞書を返す

        ファイルが ``dir_name`` のディレクトリに含まれるものでない場合は無効となる。
        '''
        return self.session_scope(
            lambda s: (lambda f: f.to_dict() if f else None)(
                s.query(File)
                    .filter(File.file_id == file_id,
                        File.directory_name == dir_name,
                        File.expires >= functions.current_date(),
                        File.is_deleted == False)
                    .one_or_none()
            )
        )
