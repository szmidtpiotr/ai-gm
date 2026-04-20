let toastHost = null;

function ensureToastHost() {
  if (toastHost) {
    return toastHost;
  }

  toastHost = document.createElement("div");
  toastHost.className = "toast-host";
  document.body.appendChild(toastHost);
  return toastHost;
}

export function showToast(message, type = "info") {
  const host = ensureToastHost();
  const toast = document.createElement("div");
  const normalizedType = ["success", "error", "info"].includes(type) ? type : "info";

  toast.className = `toast toast-${normalizedType}`;
  toast.textContent = String(message || "");
  host.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.add("visible");
  });

  const dismiss = () => {
    toast.classList.remove("visible");
    setTimeout(() => {
      toast.remove();
    }, 220);
  };

  setTimeout(dismiss, 4000);
  toast.addEventListener("click", dismiss);
}
