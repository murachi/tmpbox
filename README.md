# tmpbox

[あぷろだを作ります](https://github.com/murachi/nop/issues/4)。

ディレクトリごとに参加できるユーザーを決めて、ファイルを一時的に置いて共有できるようなものを目指します。

## 設定方法

### 想定環境

全てがこの通りでなければならない訳ではないかもしれません (確認はしていません)。但し、以下の説明では下記の環境のみを想定しております。あしからず。

- プラットフォーム: **Linux**
  - Ubuntu 16.04 / 18.04 にて動作確認済み
- **Python3.8** を使用します。
  - Python 言語環境は [Pipenv](https://pypi.org/project/pipenv/) にて整備・仮想化できるようにしてあります。ちゃんと確認はできていませんが、 [pyenv](https://github.com/pyenv/pyenv) のインストールができるようであれば、必ずしも自力で Python3.8 をセットアップする必要はないはずです。
  - Web アプリケーションフレームワークに [Flask](https://palletsprojects.com/p/flask/) を、データベースの O/R マッパーに [SQLAlchemy](https://www.sqlalchemy.org/) を使用しています。
- クライアントサイドスクリプティングの環境整備のために **[npm](https://www.npmjs.com/)** を使用します。 TypeScript や scss を用いるためのトランスパイルツールと、多少のクライアントサイドライブラリを使用しています。
  - なるべく新しいバージョンのものを使用してください。 Ubuntu の場合、[この辺の記事](https://qiita.com/seibe/items/36cef7df85fe2cefa3ea)が参考になると思います。
  - この小さなプロジェクトを構築するには割に合わない webpack などのモジュールバンドラは使用していません。モジュール解決はごくごくアナクロな方法で済ませています。
- Web アプリケーションインタフェースは **WSGI** を使用します。
  - Web サーバーに [Nginx](http://nginx.org/) を使用する場合、 Web アプリケーションサーバーに [uWSGI](https://uwsgi-docs.readthedocs.io/en/latest/) を使用します。
  - [Apache HTTP Server (2.x)](http://httpd.apache.org/) での動作は確認しておりませんが、 [mod_wsgi](https://modwsgi.readthedocs.io/en/develop/) を用いることで動作させることは可能なはずです。
- DBMS は [PostgreSQL](https://www.postgresql.org/) および [MariaDB](https://mariadb.org/) にて動作確認済みです。
  - PostgreSQL は 10.12 にて動作確認済みです。それ以降のバージョンであれば恐らく問題ないでしょう。
  - MariaDB は 10.4.12 にて動作確認済みです。こちらは [10.2.1 以降のバージョンでなければ正しく動作しないことがわかっています](https://github.com/murachi/tmpbox/issues/21#issuecomment-626444918)。 MySQL を使用する場合、おそらく 8.0.13 以降である必要があるはずです。

### セットアップ手順

想定環境が整っている前提での手順を記します。

1. tmpbox で使用する DB をあらかじめ構築しておいてください。
   - DB は任意の Linux アカウントからパスワード認証にてアクセスできる必要があります。 PostgreSQL の場合、普通に DB アカウントを作ると peer 認証でしかアクセスできなかったりするのでご注意ください。基本的な手順は[この辺](https://github.com/murachi/nop/wiki/postgres-password-authentication)にメモしてあります…。
1. 本プロジェクトの master ブランチを clone してください。
   ```console
   $ git clone https://github.com/murachi/tmpbox.git
   ```
1. プロジェクトディレクトリ下に移動し、 `setup.sh` を実行します。これにより、 pipenv による Python 仮想環境の構築と依存ライブラリのインストールが行われ、さらに `setup.py` スクリプトが起動して対話式でのセットアップが実行されます。
   - UNIX アカウントのユーザー名またはグループ名は、 Web サーバーから UNIX ソケット通信が可能になるように設定する必要があります。
