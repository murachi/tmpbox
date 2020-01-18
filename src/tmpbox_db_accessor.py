from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Boolean, Integer, String, Date, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import functions

Base = declarative_base()

class Account(Base):
    '''
    アカウント情報テーブルクラス
    '''
    __tablename__ = 'account_info'

    user_id = Column(String(50), nullable = False, primary_key = True)
    display_name = Column(String(100), nullable = False)
    is_admin = Column(Boolean, nullable = False, default = False)

    def __init__(self, user_id, display_name):
        '''
        コンストラクタ

        :param str user_id: ユーザー ID
        :param str display_name: 表示名
        '''
        self.user_id = user_id
        self.display_name = display_name

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

class Directory(Base):
    '''
    ディレクトリテーブルクラス
    '''
    __tablename__ = 'directory'

    directory_name = Column(String(100), nullable = False, primary_key = True)
    create_date = Column(Date, nullable = False, default = functions.current_date())
    summary = Column(String)
    expires_days = Column(Integer, nullable = False)

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

    def to_dict(self):
        '''
        辞書に変換

        :return: メンバー値を含む辞書を返す
        '''
        return {
            "directory_name": self.directory_name,
            "expires_days": self.expires_days,
        }

class Permission(Base):
    '''
    ディレクトリ参照権限テーブルクラス

    ディレクトリ名とユーザー ID の組み合わせが存在すれば、そのユーザーはそのディレクトリにアクセスできることを示す。
    '''
    __tablename__ = 'permission'

    directory_name = Column(String(100), ForeignKey('directory.directory_name'), nullable = False)
    user_id = Column(String(50), ForeignKey('account_info.user_id'), nullable = False)
    __table_args__ = (
        PrimaryKeyConstraint('directory_name', 'user_id'),
    )

    directory = relationship('Directory')
    user = relationship('Account')

    def __init__(self, dir_name, user_id):
        '''
        コンストラクタ

        :param str dir_name: ディレクトリ名
        :param str user_id: ユーザー ID
        '''
        self.directory_name = dir_name
        self.user_id = user_id

    def to_dict(self):
        '''
        辞書に変換

        :return: メンバー値を含む辞書を返す
        '''
        return {
            "directory_name": self.directory_name,
            "user_id": self.user_id,
            "directory": self.directory.to_dict(),
            "user": self.user.to_dict(),
        }

class File(Base):
    '''
    ファイルテーブルクラス
    '''
    __tablename__ = 'file_info'

    file_id = Column(Integer, nullable = False, primary_key = True, autoincrement = True)
    origin_file_name = Column(String(500), nullable = False)
    registered_user_id = Column(String(50), ForeignKey('account_info.user_id'), nullable = False)
    registered_date = Column(Date, nullable = False, default = functions.current_date())
    summary = Column(String)
    directory_name = Column(String(100), ForeignKey('directory.directory_name'), nullable = False)
    expires = Column(Date, nullable = False)
    is_deleted = Column(Boolean, nullable = False, default = False)

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
            "registered_date": self.registered_date,
            "summary": self.summary,
            "directory_name": self.directory_name,
            "expires": self.expires,
            "is_deleted": self.is_deleted,
            "registered_user": self.registered_user.to_dict(),
            "directory": self.directory.to_dict(),
        }

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
