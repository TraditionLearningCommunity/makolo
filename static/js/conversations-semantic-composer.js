(() => {
  "use strict";

  const allowedExtensions =
    ".jpg,.jpeg,.png,.pdf,.txt,.doc,.docx,.m4a,.mp3,.wav,.ogg,.webm,.mp4";

  function kindFor(file) {
    const type = (file.type || "").toLowerCase();
    const name = file.name.toLowerCase();
    if (type.startsWith("image/") || /\.(jpe?g|png)$/.test(name)) return "image";
    if (type.startsWith("video/") || /\.mp4$/.test(name)) return "video";
    if (type.startsWith("audio/") || /\.(m4a|mp3|wav|ogg)$/.test(name)) return "voice";
    if (/\.webm$/.test(name)) return type.startsWith("audio/") ? "voice" : "video";
    return "file";
  }

  function mimeFor(file, kind) {
    if (file.type && file.type !== "application/octet-stream") return file.type;
    const name = file.name.toLowerCase();
    if (/\.png$/.test(name)) return "image/png";
    if (/\.jpe?g$/.test(name)) return "image/jpeg";
    if (/\.pdf$/.test(name)) return "application/pdf";
    if (/\.txt$/.test(name)) return "text/plain";
    if (/\.mp3$/.test(name)) return "audio/mpeg";
    if (/\.m4a$/.test(name)) return "audio/mp4";
    if (/\.wav$/.test(name)) return "audio/wav";
    if (/\.ogg$/.test(name)) return "audio/ogg";
    if (/\.webm$/.test(name)) return kind === "video" ? "video/webm" : "audio/webm";
    if (/\.mp4$/.test(name)) return "video/mp4";
    return "application/octet-stream";
  }

  function captionFields(input, destination) {
    destination.replaceChildren();
    for (const [index, file] of [...input.files].entries()) {
      const label = document.createElement("label");
      label.className = "block text-xs";
      const title = document.createElement("span");
      title.className = "mb-1 block";
      title.textContent = file.name;
      const field = document.createElement("input");
      field.type = "text";
      field.maxLength = 5000;
      field.className = "mk-input w-full";
      field.placeholder = "Légende de ce média (facultatif)";
      field.dataset.semanticCaptionIndex = index.toString();
      label.append(title, field);
      destination.append(label);
    }
  }

  function makeChoiceRow(index, label) {
    const row = document.createElement("section");
    row.dataset.semanticOptionRow = index.toString();
    row.className = "rounded-xl border p-3 space-y-2";
    row.style.borderColor = "var(--mk-border)";
    const heading = document.createElement("p");
    heading.className = "text-sm font-semibold";
    heading.dataset.semanticOptionLabel = "";
    heading.textContent = label;
    const fieldLabel = document.createElement("label");
    fieldLabel.className = "block text-xs";
    fieldLabel.textContent = "Médias de ce choix";
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;
    input.accept = allowedExtensions;
    input.className = "mk-input mt-1 w-full";
    input.dataset.semanticOptionFiles = index.toString();
    const captions = document.createElement("div");
    captions.className = "mt-2 space-y-2";
    captions.dataset.semanticOptionCaptions = "";
    input.addEventListener("change", () => captionFields(input, captions));
    fieldLabel.append(input);
    row.append(heading, fieldLabel, captions);
    return row;
  }

  function errorMessage(payload) {
    if (!payload || typeof payload !== "object") return "Envoi non confirmé.";
    const values = Object.values(payload);
    const first = values[0];
    if (Array.isArray(first)) return String(first[0] || "Envoi non confirmé.");
    if (typeof first === "string") return first;
    return "Envoi non confirmé, réessayez avec le même contenu.";
  }

  for (const form of document.querySelectorAll("[data-semantic-media-form]")) {
    const controls = form.querySelector("[data-semantic-media-controls]");
    if (!controls || !form.dataset.semanticMediaUrl) continue;
    controls.hidden = false;
    const main = controls.querySelector("[data-semantic-point-files]");
    const mainCaptions = controls.querySelector("[data-semantic-point-captions]");
    const choices = controls.querySelector("[data-semantic-option-uploads]");
    const optionsField = form.querySelector("[data-semantic-options]");
    const status = controls.querySelector("[data-semantic-media-status]");
    const submit = form.querySelector('button[type="submit"]');
    let busy = false;
    let priorCount = 0;
    main.accept = allowedExtensions;
    main.addEventListener("change", () => captionFields(main, mainCaptions));

    if (choices && optionsField) {
      const syncChoices = () => {
        const labels = optionsField.value.split(/\r?\n/)
          .map((label) => label.trim()).filter(Boolean);
        const existing = [...choices.querySelectorAll("[data-semantic-option-row]")];
        if (existing.length !== labels.length) {
          if (priorCount && existing.some((row) =>
            row.querySelector("[data-semantic-option-files]").files.length)) {
            status.textContent =
              "La liste des choix a changé. Rejoignez les médias aux bons choix.";
          }
          existing.forEach((row) => row.remove());
          labels.forEach((label, index) => choices.append(makeChoiceRow(index, label)));
        } else {
          existing.forEach((row, index) => {
            row.querySelector("[data-semantic-option-label]").textContent = labels[index];
          });
        }
        priorCount = labels.length;
      };
      optionsField.addEventListener("input", syncChoices);
      syncChoices();
    }

    form.addEventListener("submit", async (event) => {
      const chosen = [...main.files].length +
        [...controls.querySelectorAll("[data-semantic-option-files]")]
          .reduce((sum, input) => sum + input.files.length, 0);
      if (!chosen) return; // Ordinary text-only, existing owner-backed form.
      event.preventDefault();
      if (busy) return;
      if (chosen > 24) {
        status.textContent = "Maximum 24 médias dans une publication.";
        return;
      }
      const opts = optionsField
        ? optionsField.value.split(/\r?\n/).map((v) => v.trim()).filter(Boolean)
        : [];
      if (optionsField &&
          (opts.length < 2 || opts.length > 12 || new Set(opts).size !== opts.length)) {
        status.textContent = "Prévoyez entre 2 et 12 choix distincts.";
        return;
      }
      if (!form.reportValidity()) return;
      const data = new FormData();
      const original = new FormData(form);
      for (const field of ["kind", "title", "body", "client_reference", "audience_id",
        "represented_space_id", "multiple_choice"]) {
        const value = original.get(field);
        if (value != null) data.append(field, String(value));
      }
      data.append("options", JSON.stringify(opts));
      const manifest = [];
      function addFiles(input, scope, optionIndex) {
        const captionContainer = input.parentElement.nextElementSibling;
        const captionInputs = captionContainer
          ? [...captionContainer.querySelectorAll("[data-semantic-caption-index]")]
          : [];
        for (const [index, file] of [...input.files].entries()) {
          const field = "media_" + manifest.length;
          const mediaKind = kindFor(file);
          const caption = captionInputs[index]?.value || "";
          data.append(field, file, file.name);
          manifest.push({
            field,
            scope,
            ...(scope === "option" ? { option_index: optionIndex } : {}),
            kind: mediaKind,
            caption,
            mime_type: mimeFor(file, mediaKind),
          });
        }
      }
      addFiles(main, "point", null);
      for (const input of controls.querySelectorAll("[data-semantic-option-files]")) {
        addFiles(input, "option", Number(input.dataset.semanticOptionFiles));
      }
      data.append("media_manifest", JSON.stringify(manifest));
      busy = true;
      if (submit) submit.disabled = true;
      status.textContent = "Publication des médias en cours…";
      try {
        const response = await fetch(form.dataset.semanticMediaUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": form.querySelector('input[name="csrfmiddlewaretoken"]').value,
          },
          body: data,
          cache: "no-store",
          redirect: "error",
        });
        const result = await response.json();
        if (!response.ok || !result.point_id) throw new Error(errorMessage(result));
        const target = new URL(form.dataset.semanticMediaFocus || "", window.location.href);
        target.searchParams.set("focus", result.point_id);
        target.hash = "point-" + result.point_id;
        window.location.assign(target.href);
      } catch (error) {
        status.textContent = error.message || "Envoi non confirmé. Votre saisie est conservée.";
      } finally {
        busy = false;
        if (submit) submit.disabled = false;
      }
    });
  }
})();
