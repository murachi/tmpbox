/**
フォーム入力値のバリデーションを行う関数群

@packageDocumentation
*/

/**
バリデーション関数群の名前空間
*/
export namespace validator {
  /**
  シンボル名用のバリデーション関数

  @param val 入力値
  @return 問題がなければ `true` を、それ以外の場合は `false` を返す。

  シンボル名は先頭が半角英字、 2文字目以降は半角英数字またはアンダーバー `_` でなければならない。
  主にユーザー ID に使用する名前で用いるルールとしている。
  */
  export function validateNameToken(val: string): boolean {
    return /^[a-z][\w\-]*$/i.test(val);
  }
};
