/* Conversation C4: user-initiated capture, owner-confirmed send. */
(() => {
  "use strict";
  const init = (form) => {
    const find = name => form.querySelector("[data-" + name + "]");
    const state = find("media-state"), retry = find("media-retry");
    const start = find("voice-start"), pause = find("voice-pause");
    const resume = find("voice-resume"), stop = find("voice-stop");
    const cancel = find("voice-cancel"), send = find("voice-send");
    const preview = find("voice-preview"), ref = find("media-ref");
    const kindField = find("media-kind");
    let recorder, stream, chunks = [], file, kind, busy = false;
    let status = "idle", discarded = false, previewUrl;
    const newRef = () => "web-c4-" + (globalThis.crypto?.randomUUID?.() ||
      Date.now() + "-" + Math.random().toString(16).slice(2));
    const say = message => { if (state) state.textContent = message; };
    const show = (item, visible) => item?.classList.toggle("hidden", !visible);
    const draw = () => {
      const running = status === "recording", paused = status === "paused";
      const ready = status === "ready";
      show(start, !running && !paused && !ready && !busy);
      show(pause, running); show(resume, paused);
      show(stop, running || paused); show(cancel, running || paused || ready);
      show(send, ready && !busy); show(preview, ready);
      show(retry, !!file && !busy && !running && !paused &&
        state?.dataset.failed === "true");
    };
    const release = () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
        stream = null;
      }
    };
    const reset = () => {
      file = null; kind = null; chunks = []; status = "idle";
      if (preview) {
        preview.pause(); preview.removeAttribute("src"); preview.load();
      }
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      previewUrl = null;
      if (state) state.dataset.failed = "false";
      ref.value = newRef(); draw();
    };
    const upload = async (selection, mediaKind) => {
      if (!selection || busy) return;
      busy = true; file = selection; kind = mediaKind;
      kindField.value = mediaKind;
      if (state) state.dataset.failed = "false";
      say("Envoi…"); draw();
      try {
        const data = new FormData(form);
        data.delete("file"); data.append("file", file, file.name);
        data.set("kind", kind);
        const response = await fetch(form.action.split("#")[0], {
          method: "POST", credentials: "same-origin", body: data,
          headers: {"X-Requested-With": "XMLHttpRequest"},
        });
        const result = await response.json();
        if (!response.ok || !result.point_id) throw Error(result.detail || "Envoi impossible.");
        const pointId = encodeURIComponent(result.point_id);
        reset();
        window.location.assign(form.dataset.mediaFocus + "?focus=" + pointId + "#point-" + pointId);
      } catch {
        say("Envoi non confirmé. Le fichier est conservé pour réessayer.");
        if (state) state.dataset.failed = "true";
      } finally { busy = false; draw(); }
    };
    const end = (discard = false) => {
      discarded = discard;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      else { release(); if (discard) reset(); }
    };
    const begin = async () => {
      if (busy || recorder && recorder.state !== "inactive") return;
      discarded = false; chunks = [];
      if (state) state.dataset.failed = "false";
      try {
        if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) throw Error();
        const mime = ["audio/webm;codecs=opus", "audio/mp4"].find(
          item => MediaRecorder.isTypeSupported(item));
        if (!mime) throw Error();
        stream = await navigator.mediaDevices.getUserMedia({audio: true});
        recorder = new MediaRecorder(stream, {mimeType: mime});
        recorder.ondataavailable = event => {
          if (event.data?.size) chunks.push(event.data);
        };
        recorder.onerror = () => end(true);
        recorder.onstop = () => {
          release();
          if (discarded) { reset(); say("Enregistrement annulé."); return; }
          const type = recorder.mimeType.split(";")[0];
          const blob = new Blob(chunks, {type});
          file = new File([blob], type === "audio/mp4" ? "vocal.m4a" : "vocal.webm", {type});
          kind = "voice"; status = "ready";
          previewUrl = URL.createObjectURL(blob);
          preview.src = previewUrl;
          say("Vocal prêt."); draw();
        };
        recorder.start(700);
        status = "recording"; say("Enregistrement…"); draw();
      } catch {
        release(); status = "idle";
        say("Micro indisponible. Vérifiez son autorisation."); draw();
      }
    };
    start?.addEventListener("click", begin);
    pause?.addEventListener("click", () => {
      if (recorder?.state === "recording") {
        recorder.pause(); status = "paused"; say("En pause."); draw();
      }
    });
    resume?.addEventListener("click", () => {
      if (recorder?.state === "paused") {
        recorder.resume(); status = "recording"; say("Enregistrement…"); draw();
      }
    });
    stop?.addEventListener("click", () => end());
    cancel?.addEventListener("click", () => {
      if (status === "ready") { reset(); say("Enregistrement annulé."); }
      else end(true);
    });
    send?.addEventListener("click", () => upload(file, "voice"));
    retry?.addEventListener("click", () => upload(file, kind));
    form.querySelectorAll("[data-media-file]").forEach(input => {
      input.addEventListener("change", () => {
        const selected = input.files?.[0];
        if (selected) { ref.value = newRef(); upload(selected, input.dataset.mediaFile); }
      });
    });
    window.addEventListener("pagehide", () => {
      if (recorder && recorder.state !== "inactive") end(true);
      release();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    }, {once: true});
    ref.value = newRef(); draw();
  };
  document.querySelectorAll("[data-conversation-media-form]").forEach(init);
  document.querySelectorAll("[data-conversation-form-version]").forEach(select => {
    select.addEventListener("change", () => {
      const field = select.form.querySelector("[data-conversation-form-title]");
      const option = select.selectedOptions[0];
      if (field && option?.dataset.formTitle) field.value = option.dataset.formTitle;
    });
  });
})();