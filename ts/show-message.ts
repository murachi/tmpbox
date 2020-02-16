export namespace show_message {
  export function clear(): void {
    let message_area = document.querySelector("#message_area");
    message_area.innerHTML = "";
  }

  export enum MessageType {
    info = "info"
    , error = "error"
  }

  export function addMessage(msg: string, type: MessageType): void {
    let message_elem = document.createElement("p");
    message_elem.className = type.toString();
    message_elem.innerText = msg;
    let message_area = document.querySelector("#message_area");
    message_area.appendChild(message_elem);
  }

  export function clearHighlight(form: HTMLFormElement): void {
    for (let i = 0; i < form.elements.length; ++i) {
      let elem = form[i] as HTMLInputElement;
      if (elem && elem.classList.contains("error")) {
        elem.classList.remove("error");
      }
    }
  }

  export function highlight(elem: HTMLInputElement): void {
    elem.classList.add("error");
  }
}
