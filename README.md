# tmpbox

[あぷろだを作ります](https://github.com/murachi/nop/issues/4)。

ディレクトリごとに参加できるユーザーを決めて、ファイルを一時的に置いて共有できるようなものを目指します。

## 設定方法

### 想定環境

全てがこの通りでなければならない訳ではないかもしれません (確認はしていません)。但し、以下の説明では下記の環境のみを想定しております。あしからず。

- プラットフォーム: **Linux**
  - Ubuntu 16.04 / 18.04 にて動作確認済み
- **Python3.8** を使用します。
  - Python 言語環境は [Pipenv](https://pypi.org/project/pipenv/) にて整備・仮想化できるようにしてあります。ちゃんと確認はできていませんが、 [pyenv](https://github.com/pyenv/pyenv) がインストール済みである場合、必ずしも自力で Python3.8 をセットアップする必要はないはずです。
  - Web アプリケーションフレームワークに [Flask](https://palletsprojects.com/p/flask/) を、データベースの O/R マッパーに [SQLAlchemy](https://www.sqlalchemy.org/) を使用しています (後述の手順でセットアップする場合、これらを事前にインストールする必要はありません)。
- クライアントサイドスクリプティングの環境整備のために **[npm](https://www.npmjs.com/)** を使用します。 TypeScript や scss を用いるためのトランスパイルツールと、多少のクライアントサイドライブラリを使用しています。
  - なるべく新しいバージョンのものを事前にインストールしてください。 Ubuntu の場合、[この辺の記事](https://qiita.com/seibe/items/36cef7df85fe2cefa3ea)が参考になると思います。
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
   - tmpbox を動かす UNIX ユーザーとグループを指定します。通常はデフォルトの `tmpbox` のままにしておくべきです。
   - tmpbox が使用するファイルを置く場所を指定します。ここに、アップロードされたファイルの実体、ログファイル、デーモン実行時の PID やソケットファイルなどが書き出されます。
   - DB への接続文字列を URI 形式で入力します。書式は以下のとおりです。
     ```
     {driver}://{DB account id}:{password}@{host name}/{DB name}
     ```
     - `{driver}` ... DB 接続に使用するドライバ名を指定します。
       - PostgreSQL を使用する場合、単に `postgresql` と記述すれば ok です。
       - MySQL を使用する場合、 (コンソールに表示される例とは裏腹に) `mysql+pymysql` と記述してください。
       - それ以外のドライバを使用したい場合は、独自にライブラリをインストールする等の対応をお願いします。
     - 例えば同一ホスト上で動作する MySQL サーバーに、 DB 名 `tmpbox` で DB を作成し、 DB ユーザー名が `tb-master`、パスワードが `tbpass123` である場合、接続文字列は以下のとおりになります。
       ```
       mysql+pymysql://tb-master:tbpass123@localhost/tmpbox
       ```
   - tmpbox で使用する管理者用アカウントを登録します。アカウント情報として、ユーザー ID、表示名、パスワードの入力を求められます。
   - tmpbox をデバッグ実行する際に使用するポート番号を指定します。実際にデバッグ実行を行い、それを別のホストから接続して試す場合、当該ポートによる通信を事前に開放しておく必要があります。
1. 静的コンテンツのためのセットアップを行います。具体的には、プロジェクトディレクトリ下にて以下のコマンドを実行します。
   ```console
   $ npm ci
   $ ./build.sh
   ```
   `npm ci` コマンドにより、 TypeScript および scss のトランスパイラ環境構築と、いくつかのクライアントサイドライブラリのセットアップが実行されます。 `build.sh` を実行することにより、トランスパイルの実行、および必要となる JavaScript ファイルのコピーなどが行われます。
1. 動作確認の為、 tmpbox をデバッグ実行してみましょう。リモートサーバー上で実行する場合は、まず `setup.sh` 実行時に最後に入力したデバッグ用のポートが開放されていることを確認してください。その後、以下のコマンドを実行してください。
   ```console
   $ cd src/
   $ sudo ./run.sh
   ```
   uWSGI が非デーモンモードで起動します。この状態で、 http://example.jp:6543 のようなアドレス指定にて tmpbox Web アプリケーションにアクセスできるはずです (リモートサーバーではなく実端末上での実行であれば http://localhost:6543 のようなアドレス指定でアクセスできると思います)。起動中は Web から操作するたびに都度コンソールにログが出力されます。停止したい場合は Ctrl-C キーを押下します。
1. tmpbox をサービスに登録します。以下に、 systemd を用いたサービス登録の設定ファイル例を示します。
   ```ini
   [Unit]
   Description=Tmpbox service on uWSGI
   After=network.target
   ConditionPathExists=/path/to/project-of/tmpbox

   [Service]
   Environment="PIPENV_VENV_IN_PROJECT=1"
   WorkingDirectory=/path/to/project-of/tmpbox
   ExecStart=/usr/local/bin/pipenv run uwsgi --ini src/conf.d/uwsgi-daemon.ini
   ExecReload=/usr/local/bin/pipenv run uwsgi --stop /var/tmpbox/run/uwsgi-tmpbox.pid
   ExecStop=/usr/local/bin/pipenv run uwsgi --stop /var/tmpbox/run/uwsgi-tmpbox.pid
   Restart=on-failure
   Type=forking

   [Install]
   WantedBy=multi-user.target
   ```
   `ConditionPathExists` にはプロジェクトディレクトリを指定してください。

   `ExecReload` および `ExecStop` に指定するコマンドの引数で PID ファイルへのパスを指定していますが、 `setup.sh` 実行時に「tmpbox が使用するファイルを置く場所」としてデフォルト値以外の場所を指定していた場合は、このパス名が指定した場所に応じて解決するよう適宜修正してください。

   これを `/etc/system.d/system/tmpbox.service` ファイルとして保存した場合、以下のコマンドにてサービスに登録し、起動することで、以後、 OS 再起動後も自動的に起動するようになります。
   ```console
   $ sudo systemctl enable tmpbox.service
   $ sudo systemctl start tmpbox.service
   ```
1. Nginx の設定を行います。以下は、 tmpbox 用にサブドメイン `tmpbox.example.jp` を設定すると仮定した設定例になります。これを `/etc/nginx/sites-available/tmpbox` ファイルとして保存し、更にそのファイルへのシンボリックリンクを `/etc/nginx/sites-enabled/tmpbox` として張っておきます。
   ```nginx
   server {
     listen 80;
     listen [::]:80;
     server_name tmpbox.example.jp;

     location / {
       include uwsgi_params;
       uwsgi_pass unix:/var/tmpbox/run/uwsgi-tmpbox.sock;
       client_max_body_size 200M;
     }

     location ^~ /static/ {
       include /etc/nginx/mime.types;
       root /path/to/project-of/tmpbox/src/;
       try_files $uri $uri/ =404;
     }
   }
   ```
   `location / {...}` ディレクティブ内の `uwsgi_pass` 変数には、 uWSGI アプリケーションサーバーとして動作している tmpbox が通信用に生成している UNIX ソケットファイルのパスを指定します。 `setup.sh` 実行時に「tmpbox が使用するファイルを置く場所」としてデフォルト値以外の場所を指定していた場合は、このパス名が指定した場所に応じて解決するよう適宜修正してください。 `client_max_body_size` には想定されるアップロードファイルサイズの上限相当の値を指定します (ここで指定するのは POST 送信可能なサイズの上限なので、実際のファイルサイズの上限はこれよりもう少し小さくなるでしょう)。

   `location ^~ /static/ {...}` ディレクティブの設定は、プロジェクトの `src/static/` ディレクトリ下に展開される静的アクセス用のファイルにアクセスするために必要な設定です。 `root` 変数はプロジェクトディレクトリ下の `src/` ディレクトリを指す絶対パスを指定してください。

   設定内容の書式チェックを行い、 Nginx を再起動します。

   ```console
   $ sudo nginx -t
   $ sudo systemctl restart nginx
   ```

Web サーバーに Nginx ではなく Apache2.x + mod_wsgi を使用する場合、上記の 6 以降の手順の代わりに、 Apache2 側で適切な設定を行うようにしてください (設定方法については割愛します…)。 mod_wsgi を用いた設定で pipenv による仮想環境を参照するうまい方法をご提示してくださる方がいらっしゃれば歓迎します…。

本稿では SSL に対応する手順については記載していません。上記手順にて設定後、 [certbot](https://certbot.eff.org/) を用いることで SSL に対応させることが可能ですが、それ以外の方法を用いる場合 (認証局にて取得した認証を独自に設定する等) は、認証局にて提示される手順等を参考に適宜設定を施してください。
