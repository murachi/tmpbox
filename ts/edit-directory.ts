import { show_message as sm } from "./show-message";

window.addEventListener("DOMContentLoaded", function() {
  let directory_form: HTMLFormElement = document.forms["directory"];
  directory_form.addEventListener("submit", function(ev) {
    sm.clear();
    sm.clearHighlight(this);
    // validation
    let permission_elems = this.elements["pm"] as RadioNodeList;
    let checked_any = false;
    for (let i = 0; i < permission_elems.length; ++i) {
      let elem = permission_elems[i] as HTMLInputElement;
      if (elem.checked) {
        checked_any = true;
        break;
      }
    }
    if (!checked_any) {
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
