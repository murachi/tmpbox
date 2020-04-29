import secrets
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Boolean, Integer, Unicode, UnicodeText, LargeBinary, \
    Date, DateTime, CHAR, ForeignKey, PrimaryKeyConstraint, Index, true, false
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
        self.update(minutes)

    def update(self, minutes = None):
        self.secret_key = secrets.token_bytes(16)
        if minutes:
            self.session_expires_minutes = minutes

    def to_dict(self):
        return {
            "secret_key": self.secret_key,
            "session_expires_minutes": self.session_expires_minutes,
        }

class Account(Base):
    '''
    アカウント情報テーブルクラス
    '''
    __tablename__ = 'account_info'

    user_id = Column(Unicode(50), nullable = False, primary_key = True)
    display_name = Column(Unicode(100), nullable = False)
    password_hash = Column(Unicode(500), nullable = False)
    is_admin = Column(Boolean, nullable = False, server_default = false())

    session_states = relationship("SessionState", back_populates = "account", cascade = "all, delete-orphan")
    permissions = relationship("Permission", back_populates = "user", cascade = "all, delete-orphan")

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

        セッション状態情報は常に含めない。
        '''
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "password_hash": self.password_hash,
            "is_admin": self.is_admin,
        }

    def check_password(self, password):
        '''
        パスワードが一致するかを確認する

        :param str password: パスワード (平文)
        :return: パスワードが一致する場合は ``True`` を返す。
        '''
        return check_password_hash(self.password_hash, password)

class SessionState(Base):
    '''
    ユーザーログインセッション状態管理テーブルクラス
    '''
    __tablename__ = 'session_state'

    session_id = Column(CHAR(43), nullable = False, primary_key = True)
    user_id = Column(Unicode(50), ForeignKey('account_info.user_id', ondelete = "cascade"), nullable = False)
    access_dt = Column(DateTime, nullable = False, server_default = functions.now())

    account = relationship("Account", back_populates = "session_states")
    session_datas = relationship("SessionData", back_populates = "session_state", cascade = "all, delete-orphan")

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
                "account": self.account.to_dict(),
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

    session_id = Column(CHAR(43), ForeignKey("session_state.session_id", ondelete = "cascade"), nullable = False)
    name = Column(Unicode(50), nullable = False)
    value = Column(Unicode(1000), nullable = False)
    __table_args__ = (
        PrimaryKeyConstraint("session_id", "name"),
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

class Directory(Base):
    '''
    ディレクトリテーブルクラス
    '''
    __tablename__ = 'directory'

    directory_id = Column(Integer, nullable = False, primary_key = True)
    directory_name = Column(Unicode(100), nullable = False)
    create_date = Column(Date, nullable = False, server_default = functions.current_date())
    summary = Column(UnicodeText)
    expires_days = Column(Integer, nullable = False)
    is_deleted = Column(Boolean, nullable = False, server_default = false())

    __table_args__ = (
        Index("idx_directory_name_exists", directory_name, is_deleted),
    )

    permissions = relationship("Permission", back_populates = "directory", cascade = "all, delete-orphan")
    files = relationship("File", back_populates = "directory", cascade = "all, delete-orphan")

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

        ``with_relation == True`` であっても ``files`` は含めないものとする。
        ディレクトリに表示するファイルの一覧を取得するには、
        TmpboxDB.get_active_files() メソッドを使用すること。
        '''
        result = {
            "directory_id": self.directory_id,
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

    directory_id = Column(Integer, ForeignKey('directory.directory_id', ondelete = "cascade"), nullable = False)
    user_id = Column(Unicode(50), ForeignKey('account_info.user_id', ondelete = "cascade"), nullable = False)
    __table_args__ = (
        PrimaryKeyConstraint('directory_id', 'user_id'),
    )

    directory = relationship('Directory', back_populates = 'permissions')
    user = relationship('Account', back_populates = "permissions")

    def __init__(self, dir_id, user_id):
        '''
        コンストラクタ

        :param str dir_id: ディレクトリ ID
        :param str user_id: ユーザー ID
        '''
        self.directory_id = dir_id
        self.user_id = user_id

    def to_dict(self, with_relation = True):
        '''
        辞書に変換

        :param bool with_relation: リレーションメンバーの値を含めるか?
        :return: メンバー値を含む辞書を返す
        '''
        result = {
            "directory_id": self.directory_id,
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
    directory_id = Column(Integer, ForeignKey('directory.directory_id', ondelete = "cascade"), nullable = False)
    expires = Column(Date, nullable = False)
    registered_user_id = Column(Unicode(50), nullable = False)
    registered_date = Column(Date, nullable = False, server_default = functions.current_date())
    summary = Column(Unicode)
    is_deleted = Column(Boolean, nullable = False, server_default = false())

    __table_args__ = (
        Index("idx_file_active", directory_id, expires.desc(), is_deleted, file_id.desc()),
    )

    directory = relationship('Directory', back_populates = "files")

    def __init__(self, file_name, dir_id, expires, user_id):
        '''
        コンストラクタ

        :param str file_name: オリジナルファイル名
        :param str dir_id: 登録先のディレクトリ ID
        :param datetime.date expires: 保存期限
        :param str user_id: 登録者のアカウントユーザー ID
        '''
        self.origin_file_name = file_name
        self.directory_id = dir_id
        self.expires = expires
        self.registered_user_id = user_id

    def to_dict(self, with_relation = True):
        '''
        辞書に変換

        :return: メンバー値を含む辞書を返す
        '''
        result = {
            "file_id": self.file_id,
            "origin_file_name": self.origin_file_name,
            "directory_id": self.directory_id,
            "expires": self.expires,
            "registered_user_id": self.registered_user_id,
            "registered_date": self.registered_date,
            "summary": self.summary,
            "is_deleted": self.is_deleted,
        }
        if with_relation:
            result.update({
                "directory": self.directory.to_dict(with_relation = False),
            })

        return result

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

    def setup_system(self, minutes = None):
        '''
        システム共通データを設定する

        :param int minutes: ログインセッションの有効期間 (分単位)、変更しない場合は None を指定
        '''
        self.session_scope(
            lambda s: self.__session_setup_system(s, minutes), True)

    def __session_setup_system(self, session, minutes):
        '''
        システム共通データを設定する

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param int minutes: ログインセッションの有効期間 (分単位)、変更しない場合は None を指定
        '''
        sys_data = session.query(SystemData).one_or_none()
        if sys_data:
            sys_data.update(minutes)
        else:
            sys_data = SystemData(minutes)
            session.add(sys_data)

    def get_secret_key(self):
        '''
        Flask の Session 機能で使用するシークレットキーを取得する

        :return: シークレットキーの byte 列
        '''
        return self.session_scope(lambda s: s.query(SystemData.secret_key).scalar())

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
        :return: 認証を確認できた場合、ログインセッションを生成し、セッション ID を返す。
            それ以外の場合は ``None`` を返す。

        ``password`` に ``None`` を指定すると ``TypeError`` 例外が送出されるので注意すること。
        '''
        return self.session_scope(
            lambda s: self.__session_check_authentication(s, user_id, password),
            True)

    def __session_check_authentication(self, session, user_id, password):
        '''
        アカウントの認証を確認するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str user_id: ユーザー ID
        :param str password: パスワード (平文)
        :return: 認証を確認できた場合、ログインセッションを生成し、セッション ID を返す。
            それ以外の場合は ``None`` を返す。
        '''
        acc_info = session.query(Account).filter(Account.user_id == user_id).one_or_none()
        if not acc_info or not acc_info.check_password(password): return

        # 同一ユーザーのログインセッションに関連する情報は全て削除する
        # (CASCADE 設定により、関連する SessionData も削除される)
        session.query(SessionState).filter(SessionState.user_id == user_id).delete();

        login_session = SessionState(user_id)
        session.add(login_session)
        return login_session.session_id

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

    def check_login_session(self, session_id):
        '''
        ログインセッションの状態を確認する

        :param str session_id: セッション ID
        :return: 有効なログインセッションが存在する場合、関連する情報を辞書化したものを返す。
            それ以外の場合は None を返す。

        ログインセッションが有効であれば、アクセス日時を更新し、有効期限を延長する。
        '''
        if not session_id:
            return None
        return self.session_scope(
            lambda s: self.__session_check_login_session(s, session_id), True)

    def __session_check_login_session(self, session, session_id):
        '''
        ログインセッションの状態を確認するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str session_id: セッション ID
        :return: 有効なログインセッションが存在する場合、関連する情報を辞書化したものを返す。
            それ以外の場合は None を返す。
        '''
        login_session = SessionState.filter_check_expires(
            self.engine,
            session.query(SessionState).join(SystemData, 1 == SystemData.dummy_id)
                .filter(SessionState.session_id == session_id)
        ).one_or_none()

        if not login_session:
            return None

        login_session.access_dt = functions.now()
        session.commit()
        session.refresh(login_session)

        return login_session.to_dict() if login_session else None

    def delete_login_session(self, session_id):
        '''
        ログインセッションを削除する (ログアウト処理)

        :param str session_id: セッション ID
        '''
        self.session_scope(
            lambda s: s.query(SessionState).filter(SessionState.session_id == session_id).delete(),
            True)

    def modify_session_data(self, session_id, data):
        '''
        ログインセッションデータを変更する

        :param str session_id: ログインセッション ID
        :param dict data: ログインセッションデータの辞書
        '''
        self.session_scope(lambda s: self.__session_modify_session_data(s, session_id, data), True)

    def __session_modify_session_data(self, session, session_id, data):
        '''
        ログインセッションデータを変更するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str session_id: ログインセッション ID
        :param dict data: ログインセッションデータの辞書
        '''
        session.query(SessionData).filter(SessionData.session_id == session_id).delete()
        session.add_all([SessionData(session_id, k, v) for k, v in data.items()])

    def delete_session_data(self, session_id, data_name):
        '''
        特定の名前のログインセッションデータを削除する

        :param str session_id: ログインセッション ID
        :param dict data_name: ログインセッションデータのキー名称
        '''
        self.session_scope(
            lambda s: s.query(SessionData)
                .filter(SessionData.session_id == session_id, SessionData.name == data_name)
                .delete(),
            True)

    def register_directory(self, dir_name, expires_days, summary = None):
        '''
        ディレクトリの情報を登録する

        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        :return: ディレクトリ ID
        :rtype: int
        '''
        return self.session_scope(
            lambda s: self.__session_register_directory(s, dir_name, expires_days, summary),
            True)

    def __session_register_directory(self, session, dir_name, expires_days, summary):
        '''
        ディレクトリの情報を登録するセッション処理

        :param sqlalchemy.orm.session.Session: セッションオブジェクト
        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        :return: ディレクトリ ID
        :rtype: int
        '''
        # 既存ディレクトリ名のチェック
        existing_dir = session.query(Directory.directory_id) \
            .filter(Directory.directory_name == dir_name, Directory.is_deleted == false()) \
            .scalar()
        if existing_dir:
            raise TmpboxDBDuplicatedException("'{0}' という名前のディレクトリは既に存在します。".format(dir_name))
        dir = Directory(dir_name, expires_days)
        if summary:
            dir.summary = summary
        session.add(dir)
        session.commit()
        session.refresh(dir)
        return dir.directory_id

    def update_directory(self, dir_id, dir_name, expires_days, summary = None):
        '''
        ディレクトリの情報を更新する

        :param int dir_id: ディレクトリ ID
        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        :return: ディレクトリ情報の辞書
        '''
        return self.session_scope(
            lambda s: self.__session_update_directory(s, dir_id, dir_name, expires_days, summary),
            True)

    def __session_update_directory(self, session, dir_id, dir_name, expires_days, summary):
        '''
        ディレクトリの情報を更新する

        :param sqlalchemy.orm.session.Session: セッションオブジェクト
        :param int dir_id: ディレクトリ ID
        :param str dir_name: ディレクトリ名
        :param int expires_days: デフォルトのファイル保存期間
        :param str summary: ディレクトリの説明
        :return: ディレクトリ情報の辞書
        '''
        directory = session.query(Directory) \
            .filter(Directory.directory_id == dir_id, Directory.is_deleted == false()) \
            .one()
        directory.directory_name = dir_name
        directory.expires_days = expires_days
        directory.summary = summary or None

        return directory.to_dict(with_relation = False)

    def update_permission(self, dir_id, user_ids):
        '''
        ディレクトリの参照権限ユーザーを更新する

        :param str dir_id: ディレクトリ ID
        :param list user_ids: ディレクトリへのアクセスを許可するユーザー ID のリスト
        '''
        self.session_scope(lambda s: self.__session_update_permission(s, dir_id, user_ids), True)

    def __session_update_permission(self, session, dir_id, user_ids):
        '''
        ディレクトリの参照権限ユーザーを更新するセッション処理

        :param sqlalchemy.orm.session.Session: セッションオブジェクト
        :param str dir_id: ディレクトリ ID
        :param list user_ids: ディレクトリへのアクセスを許可するユーザー ID のリスト
        '''
        # 一旦全部消してから挿入し直す
        session.query(Permission).filter(Permission.directory_id == dir_id).delete()
        session.add_all([Permission(dir_id, n) for n in user_ids])

    def get_directories(self):
        '''
        ディレクトリの一覧を取得する

        :return: ディレクトリ情報辞書のリスト
        '''
        return self.session_scope(
            lambda s: [
                n.to_dict(with_relation = False) for n
                in s.query(Directory)
                    .filter(Directory.is_deleted == false())
                    .order_by(Directory.directory_name)
            ]
        )

    def get_directories_for(self, user_id):
        '''
        特定ユーザーがアクセス可能なディレクトリの一覧を取得する

        :param str user_id: ユーザー ID
        :return: パーミッション情報の辞書
        '''
        return self.session_scope(
            lambda s: [
                n.to_dict(with_relation = False) for n
                in s.query(Directory).join(Permission)
                    .filter(Directory.is_deleted == false(), Permission.user_id == user_id)
                    .order_by(Directory.directory_name)
            ]
        )

    def get_directory(self, dir_id, only_active = True):
        '''
        特定のディレクトリの情報を取得する

        :param int dir_id: ディレクトリ ID
        :param bool only_active: 有効な (削除されていない) ディレクトリのみを対象とする場合は
            ``True`` を指定する。
        :return: hit した場合はディレクトリ情報の辞書を、それ以外の場合は None を返す。
        '''
        q = Query(Directory).filter(Directory.directory_id == dir_id)
        if only_active:
            q = q.filter(Directory.is_deleted == false())
        return self.session_scope(
            lambda s: (lambda d: d.to_dict() if d else None)(q.with_session(s).one_or_none())
        )

    def register_file(self, file_name, dir_id, expires, user_id, summary = None):
        '''
        ファイルを登録する

        :param str file_name: オリジナルファイル名
        :param str dir_id: 登録先ディレクトリ ID
        :param datetime.date expires: 有効期限
        :param str user_id: 登録者ユーザー ID
        :param str summary: ファイルの説明
        :return: 登録に成功した場合、ファイル ID を返す。
        :rtype: int
        '''
        return self.session_scope(
            lambda s: self.__session_register_file(s, file_name, dir_id, expires, user_id, summary),
            True)

    def __session_register_file(self, session, file_name, dir_id, expires, user_id, summary):
        '''
        ファイルを登録するセッション処理

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str file_name: オリジナルファイル名
        :param str dir_id: 登録先ディレクトリ ID
        :param datetime.date expires: 有効期限
        :param str user_id: 登録者ユーザー ID
        :param str summary: ファイルの説明
        :return: 登録に成功した場合、ファイル ID を返す。
        :rtype: int
        '''
        file = File(file_name, dir_id, expires, user_id)
        if summary is not None:
            file.summary = summary
        session.add(file)
        session.commit()
        session.refresh(file)
        return file.file_id

    def delete_file(self, dir_id, file_id):
        '''
        ファイルを論理削除する

        :param str dir_id: ファイルが存在するディレクトリ ID
        :param int file_id: ファイル ID
        :return: 成功した場合、削除されたファイルのファイル名を返す。それ以外の場合は ``None`` を返す。

        ``file_id`` のファイルが ``dir_id`` のディレクトリに存在しない場合、削除は行われない。
        '''
        return self.session_scope(
            lambda s: self.__session_delete_file(s, dir_id, file_id),
            True)

    def __session_delete_file(self, session, dir_id, file_id):
        '''
        ファイルを論理削除する

        :param sqlalchemy.orm.session.Session session: セッションオブジェクト
        :param str dir_id: ファイルが存在するディレクトリ ID
        :param int file_id: ファイル ID
        :return: 成功した場合、削除されたファイルのファイル名を返す。それ以外の場合は ``None`` を返す。
        '''
        file = session.query(File) \
            .filter(File.file_id == file_id, File.directory_id == dir_id, File.is_deleted == false()) \
            .one_or_none()
        if file:
            file.is_deleted = True
            return file.origin_file_name

    def get_active_files(self, dir_id):
        '''
        特定のディレクトリに含まれる有効なファイルの一覧を取得する

        :param int dir_id: ディレクトリ ID
        :return: ファイル情報辞書のリスト
        '''
        return self.session_scope(
            lambda s: [
                n.to_dict() for n
                in s.query(File)
                    .filter(File.directory_id == dir_id,
                        File.expires >= functions.current_date(),
                        File.is_deleted == False)
                    .order_by(File.file_id.desc())
            ]
        )

    def get_file(self, dir_id, file_id, only_active = True):
        '''
        ファイルの情報を取得する

        :param str dir_id: ディレクトリ名
        :param int file_id: ファイル ID
        :param bool only_active: 有効なファイルの場合にのみ取得したい場合は
            ``True`` を指定する。
        :return: hit した場合はファイル情報の辞書を、それ以外の場合は ``None`` を返す。

        ファイルが ``dir_name`` のディレクトリに含まれるものでない場合は無効となる。
        '''
        q = Query(File).filter(File.file_id == file_id, File.directory_id == dir_id)
        if only_active:
            q = q.filter(File.expires >= functions.current_date(), File.is_deleted == False)
        return self.session_scope(
            lambda s: (lambda f: f.to_dict() if f else None)(q.with_session(s).one_or_none())
        )
