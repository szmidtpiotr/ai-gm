/**
 * @param {{ title: string, content: HTMLElement | string, footer?: Array<{ label: string, class?: string, onClick: (close: () => void) => void }> }} opts
 * @returns {{ el: HTMLElement, close: () => void }}
 */
export function openModal(opts) {
  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const box = document.createElement("div");
  box.className = "modal-box";

  const titleEl = document.createElement("h3");
  titleEl.className = "modal-title";
  titleEl.textContent = opts.title || "";

  const body = document.createElement("div");
  body.className = "modal-body";
  if (opts.content instanceof HTMLElement) {
    body.appendChild(opts.content);
  } else {
    body.innerHTML = String(opts.content || "");
  }

  const footerEl = document.createElement("div");
  footerEl.className = "modal-footer";

  const close = () => {
    overlay.remove();
  };

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) {
      close();
    }
  });

  box.appendChild(titleEl);
  box.appendChild(body);

  (opts.footer || []).forEach((btn) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = btn.label;
    if (btn.class) {
      b.className = btn.class;
    }
    b.addEventListener("click", () => {
      btn.onClick(close);
    });
    footerEl.appendChild(b);
  });

  if (footerEl.childElementCount) {
    box.appendChild(footerEl);
  }

  overlay.appendChild(box);
  document.body.appendChild(overlay);
  return { el: overlay, close };
}
