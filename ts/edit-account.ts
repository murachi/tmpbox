import { validator } from "./validator";

window.addEventListener("DOMContentLoaded", function() {
  let account_form: HTMLFormElement = document.forms["account"];
  account_form.addEventListener("submit", function(ev) {
    // validation
    if (!validator.validateNameToken(this.elements["id"].value)) {
      window.alert("ユーザーID は半角英字で始まり半角英数字とアンダーバー _ のみで構成される名前にしてください。");
      ev.stopPropagation();
      ev.preventDefault();
    }
  });
});
