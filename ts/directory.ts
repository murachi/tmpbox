import { show_message as sm } from "./show-message";

window.addEventListener("DOMContentLoaded", function() {
  let upload_form: HTMLFormElement = document.forms["upload"];
  upload_form.addEventListener("submit", function(ev) {
    sm.clear();
    sm.clearHighlight(this);
    // trimming
    const summary_input = this.elements["sm"] as HTMLInputElement;
    summary_input.value = summary_input.value.trim();
    // validation
    if (!this.elements["fp"].value) {
      sm.addMessage("ファイルを選択してください。", sm.MessageType.error);
      sm.highlight(this.elements["fp"] as HTMLInputElement);
      ev.stopPropagation();
      ev.preventDefault();
    }
  });
  let delete_buttons: NodeList = document.querySelectorAll('button.delete');
  delete_buttons.forEach(bt => bt.addEventListener("click", function(ev) {
    let file_id = (this as HTMLButtonElement).id.match(/^filedel-(\d+)/)[1];
    let file_name = (document.querySelector(`#filename-${file_id}`) as HTMLTableColElement).innerText;
    if (!window.confirm(`ファイル "${file_name}" を削除します。よろしいですか?`)) {
      ev.stopPropagation();
      ev.preventDefault();
      return;
    }

    let delete_form: HTMLFormElement = document.forms["file-delete"];
    delete_form.elements["fid"].value = file_id;
    delete_form.submit();
  }));
});
