import * as zxcvbn from "zxcvbn";
import { show_message as sm } from "./show-message";

window.addEventListener("DOMContentLoaded", function() {
  const acc_form: HTMLFormElement = document.forms["account"];
  acc_form.addEventListener("submit", function(ev) {
    sm.clear();
    sm.clearHighlight(this);
    // trimming
    const disp_name_input = this.elements["dn"] as HTMLInputElement;
    disp_name_input.value = disp_name_input.value.trim();
    // validation
    const want_mod_pw = (document.querySelector("#password_modify_yes") as HTMLInputElement).checked;
    if (want_mod_pw) {
      const npw = this.elements["npw"] as HTMLInputElement;
      const npw2 = this.elements["npw2"] as HTMLInputElement;
      if (npw.value !== npw2.value) {
        sm.highlight(npw2);
        sm.addMessage("確認用パスワードが一致しません。", sm.MessageType.error);
        ev.stopPropagation();
        ev.preventDefault();
        return;
      }
      const chk_result = zxcvbn(npw.value);
      if (chk_result.score <= 2) {
        sm.highlight(npw);
        sm.addMessage("強度が弱いパスワードを許容することはできません。", sm.MessageType.error);
        ev.stopPropagation();
        ev.preventDefault();
        return;
      }
    }
  });
  const pw_inputs =
    document.querySelectorAll('table.password input[type="password"]') as NodeListOf<HTMLInputElement>;
  (document.querySelector("#password_modify_no") as HTMLInputElement).addEventListener(
    "click", function(){
      pw_inputs.forEach(n => n.disabled = true);
    });
  (document.querySelector("#password_modify_yes") as HTMLInputElement).addEventListener(
    "click", function(){
      pw_inputs.forEach(n => n.disabled = false);
    });

  let pwd_last_input = "";
  let pwd_check_timer: number = null;
  (acc_form.elements["npw"] as HTMLInputElement).addEventListener("keyup", function(ev) {
    if (this.value == pwd_last_input) return;
    pwd_last_input = this.value;
    if (pwd_check_timer) window.clearTimeout(pwd_check_timer);
    pwd_check_timer = window.setTimeout(() => {
      const chk_result = zxcvbn(this.value);
      const p = document.querySelector("#pwchk_strength") as HTMLParagraphElement;
      p.className = chk_result.score.toString();
      p.innerText = {
        "0": "不可"
        , "1": "非常に弱い"
        , "2": "弱い"
        , "3": "まあまあ"
        , "4": "強い"
      }[chk_result.score.toString()];

      const div = document.querySelector("#pwchk_feedback") as HTMLDivElement;
      while (div.childNodes.length > 0) div.removeChild(div.lastChild);
      if (chk_result.feedback.warning) {
        const p_warn = document.createElement("p") as HTMLParagraphElement;
        p_warn.className = "warning";
        p_warn.innerText = chk_result.feedback.warning;
        div.appendChild(p_warn);
      }
      if (chk_result.feedback.suggestions) {
        const ul = document.createElement("ul") as HTMLUListElement;
        ul.className = "suggestions";
        chk_result.feedback.suggestions.forEach(t => {
          const li = document.createElement("li") as HTMLLIElement;
          li.innerText = t;
          ul.appendChild(li);
        })
        div.appendChild(ul);
      }
    }, 1000);
  });
});
