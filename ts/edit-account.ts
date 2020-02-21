import { validator } from "./validator";
import { show_message as sm } from "./show-message";

window.addEventListener("DOMContentLoaded", function() {
  let account_form: HTMLFormElement = document.forms["account"];
  account_form.addEventListener("submit", function(ev) {
    sm.clear();
    sm.clearHighlight(this);
    // validation
    let user_id_elem = this.elements["id"] as HTMLInputElement;
    if (user_id_elem && !validator.validateNameToken(user_id_elem.value)) {
      sm.highlight(user_id_elem);
      sm.addMessage(
        "ユーザーID は半角英字で始まり半角英数字とアンダーバー _ のみで構成される名前にしてください。",
        sm.MessageType.error);
      ev.stopPropagation();
      ev.preventDefault();
    }
  });
});
