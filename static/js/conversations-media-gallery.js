(() => {
  "use strict";

  // Only first-party, owner-authorized endpoints may enter this viewer.
  function sameOriginAttachment(raw) {
    try {
      const url = new URL(raw, document.baseURI);
      if (url.origin !== window.location.origin ||
          !url.pathname.includes("/attachments/") ||
          !/^\/[a-z0-9/_-]+\/$/i.test(url.pathname)) return null;
      return url.href;
    } catch (_) {
      return null;
    }
  }

  for (const group of document.querySelectorAll("[data-conversation-media-group]")) {
    const items = [...group.querySelectorAll("[data-conversation-media-item]")];
    const dialog = group.querySelector("[data-conversation-media-dialog]");
    if (!dialog || !items.length || typeof dialog.showModal !== "function") continue;

    const body = dialog.querySelector("[data-media-dialog-body]");
    const title = dialog.querySelector("[data-media-dialog-title]");
    const status = dialog.querySelector("[data-media-dialog-status]");
    const download = dialog.querySelector("[data-media-dialog-download]");
    const share = dialog.querySelector("[data-media-dialog-share]");
    const previous = dialog.querySelector("[data-media-dialog-prev]");
    const next = dialog.querySelector("[data-media-dialog-next]");
    let index = 0;

    // Keep photo/video collections compact without hiding audio, PDF or other
    // documents that should remain readable directly in the conversation.
    const visualItems = items.filter((item) =>
      item.dataset.mediaKind === "image" || item.dataset.mediaKind === "video");
    if (visualItems.length > 4) {
      for (const item of visualItems.slice(4)) item.hidden = true;
      const lastVisible = visualItems[3];
      lastVisible.style.position = "relative";
      const more = document.createElement("button");
      more.type = "button";
      more.setAttribute("data-conversation-media-open", "");
      more.setAttribute("aria-label", "Voir les autres médias");
      more.textContent = "+" + (visualItems.length - 3);
      Object.assign(more.style, {
        position: "absolute",
        inset: "0",
        background: "rgba(0,0,0,.6)",
        color: "white",
        fontWeight: "700",
        fontSize: "1.6rem",
        width: "100%",
        height: "100%",
        borderRadius: "0.75rem",
      });
      lastVisible.append(more);
    }

    function show(indexToShow) {
      index = Math.max(0, Math.min(items.length - 1, indexToShow));
      const item = items[index];
      const inline = sameOriginAttachment(item.dataset.mediaUrl);
      const file = sameOriginAttachment(item.dataset.mediaDownload);
      const kind = item.dataset.mediaKind;
      const mime = item.dataset.mediaMime;
      title.textContent = (item.dataset.mediaName || "Média") + " · " +
        (index + 1) + "/" + items.length;
      status.textContent = "";
      body.replaceChildren();
      if (!inline && !file) {
        body.textContent = "Ce média n'est plus disponible.";
      } else if (kind === "image" && inline) {
        const image = document.createElement("img");
        image.src = inline;
        image.alt = item.dataset.mediaName || "Photo";
        image.className = "max-w-full object-contain";
        image.style.maxHeight = "70vh";
        body.append(image);
      } else if ((kind === "voice" || kind === "audio") && inline) {
        const audio = document.createElement("audio");
        audio.src = inline;
        audio.controls = true;
        audio.preload = "metadata";
        audio.className = "w-full";
        body.append(audio);
      } else if (kind === "video" && inline) {
        const video = document.createElement("video");
        video.src = inline;
        video.controls = true;
        video.preload = "metadata";
        video.className = "max-w-full";
        video.style.maxHeight = "70vh";
        body.append(video);
      } else if ((mime === "application/pdf" || mime === "text/plain") && inline) {
        const frame = document.createElement("iframe");
        frame.src = inline;
        frame.title = item.dataset.mediaName || "Document";
        frame.setAttribute("sandbox", "allow-same-origin");
        frame.setAttribute("referrerpolicy", "no-referrer");
        frame.className = "w-full bg-white";
        frame.style.height = "65vh";
        body.append(frame);
      } else {
        const message = document.createElement("p");
        message.className = "p-5 text-sm";
        message.textContent =
          "Ce format s'ouvre avec une application compatible. Téléchargez le document.";
        body.append(message);
      }
      download.href = file || "#";
      download.hidden = !file;
      previous.disabled = index === 0;
      next.disabled = index === items.length - 1;
      share.hidden = !file || !navigator.share || !navigator.canShare || !window.File;
    }

    group.addEventListener("click", (event) => {
      const trigger = event.target.closest("[data-conversation-media-open]");
      if (!trigger || !group.contains(trigger)) return;
      const item = trigger.closest("[data-conversation-media-item]");
      const requested = items.indexOf(item);
      if (requested < 0) return;
      for (const player of group.querySelectorAll("video,audio")) {
        player.pause();
      }
      show(requested);
      if (!dialog.open) dialog.showModal();
    });
    dialog.querySelector("[data-media-dialog-close]").addEventListener("click", () => dialog.close());
    previous.addEventListener("click", () => show(index - 1));
    next.addEventListener("click", () => show(index + 1));
    dialog.addEventListener("close", () => body.replaceChildren());
    share.addEventListener("click", async () => {
      const item = items[index];
      const url = sameOriginAttachment(item.dataset.mediaDownload);
      if (!url || !navigator.share || !navigator.canShare) return;
      share.disabled = true;
      status.textContent = "Préparation du partage…";
      try {
        const response = await fetch(url, {
          method: "GET",
          credentials: "same-origin",
          cache: "no-store",
          redirect: "error",
        });
        if (!response.ok) throw new Error("Média inaccessible.");
        const data = await response.blob();
        if (data.size > 50 * 1024 * 1024) {
          throw new Error("Ce fichier est trop volumineux pour le partage direct.");
        }
        const name = (item.dataset.mediaName || "media").split(/[\\/]/).pop();
        const file = new File([data], name, {
          type: item.dataset.mediaMime || "application/octet-stream",
        });
        if (!navigator.canShare({ files: [file] })) {
          throw new Error("Le partage de fichiers n'est pas pris en charge.");
        }
        await navigator.share({ files: [file] });
        status.textContent = "";
      } catch (error) {
        if (error && error.name !== "AbortError") {
          status.textContent = error.message || "Partage indisponible.";
        } else {
          status.textContent = "";
        }
      } finally {
        share.disabled = false;
      }
    });
  }
})();
