import { validator } from "./validator";
import { show_message as sm } from "./show-message";

window.addEventListener("DOMContentLoaded", function() {
  let directory_form: HTMLFormElement = document.forms["directory"];
  directory_form.addEventListener("submit", function(ev) {
    sm.clear();
    sm.clearHighlight(this);
    // validation
    let dir_name_elem = this.elements["nm"] as HTMLInputElement;
    if (dir_name_elem && !validator.validateURIUnreserved(dir_name_elem.value)) {
      sm.highlight(dir_name_elem);
      sm.addMessage(
        "ディレクトリ名に使用できる文字は半角英数字と次の記号文字のみです: " +
        "'.' (ピリオド)、 '_' (アンダーバー)、 '-' (ハイフン)、 '~' (チルダ)",
        sm.MessageType.error);
      ev.stopPropagation();
      ev.preventDefault();
      return;
    }
    let permission_elems = this.elements["pm"] as RadioNodeList;
    let checked_some = false;
    for (let i = 0; i < permission_elems.length; ++i) {
      let elem = permission_elems[i] as HTMLInputElement;
      if (elem.checked) {
        checked_some = true;
        break;
      }
    }
    if (!checked_some) {
      permission_elems.forEach(n => sm.highlight(n as HTMLInputElement));
      sm.addMessage(
        "参照権限ユーザーを一人以上選択してください。",
        sm.MessageType.error);
      ev.stopPropagation();
      ev.preventDefault();
      return;
    }
  });
});
