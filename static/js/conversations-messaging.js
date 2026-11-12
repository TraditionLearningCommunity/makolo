/* Owner-confirmed REST mutations and resumable deltas, shared by all Web modes. */
(() => {
  'use strict';
  if (window.MakoloMessaging) return;
  const host = document.getElementById('mk-messaging-host');
  if (!host) return;
  const api = host.dataset.api, web = host.dataset.web, profile = host.dataset.profile;
  const windows = host.querySelector('.mk-messaging-windows');
  const panel = host.querySelector('#mk-messaging-panel');
  const launch = host.querySelector('.mk-messaging-launch');
  const views = new Set(), floating = new Map();
  const csrf = () => decodeURIComponent(document.cookie.split('; ').find(x => x.startsWith('csrftoken='))?.split('=').slice(1).join('=') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '');
  const uid = () => crypto.randomUUID();
  function el(tag, text, cls) { const node = document.createElement(tag); if (text != null) node.textContent = text; if (cls) node.className = cls; return node; }
  function button(text, action) { const node = el('button', text); node.type = 'button'; node.addEventListener('click', action); return node; }
  function safePath(path) { if (typeof path !== 'string' || path.startsWith('//')) return null; const url = new URL(path.startsWith('/') ? path : '/' + path, location.origin); return url.origin === location.origin ? url.href : null; }
  async function request(path, method = 'GET', body) {
    const response = await fetch(api + path, { method, credentials: 'same-origin', cache: 'no-store', headers: { 'Accept': 'application/json', 'X-Makolo-Profile':profile, ...(method !== 'GET' ? { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' } : {}) }, body: body == null ? undefined : JSON.stringify(body) });
    if (!response.ok) { const error = new Error(response.status === 409 ? 'Le contenu a changé. Rechargez avant de réessayer.' : 'Action non confirmée. Réessayez.'); error.status = response.status; throw error; }
    return response.json();
  }
  class Realtime {
    constructor() { this.socket = null; this.attempt = 0; this.timer = null; this.closed = false; }
    async connect() {
      if (this.closed || !views.size || this.socket) return;
      try {
        const ticket = await request('realtime-ticket/', 'POST', {});
        if (this.closed || !views.size) return;
        const uri = new URL(ticket.websocket_path, location.origin); uri.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socket = this.socket = new WebSocket(uri);
        socket.onopen = () => socket.send(JSON.stringify({ type: 'authenticate', ticket: ticket.ticket }));
        socket.onmessage = event => {
          let data; try { data = JSON.parse(event.data); } catch { socket.close(); return; }
          if (data.type === 'authenticated') { this.attempt = 0; for (const point of new Set([...views].map(v => v.point).filter(Boolean))) this.send('subscribe', point); for (const view of views) view.sync(); }
          for (const view of views) {
            if (data.point_id !== view.point) continue;
            if (data.type === 'point_changed') view.sync();
            if (data.type === 'receipt_changed') view.receipts();
            if (data.code === 'access_revoked') view.revoke();
            if (['typing_changed', 'presence_changed'].includes(data.type) && data.profile_id !== profile) view.ephemeral(data);
          }
        };
        socket.onerror = () => socket.close();
        socket.onclose = () => { if (this.socket === socket) this.socket = null; this.retry(); };
      } catch { this.retry(); }
    }
    retry() { clearTimeout(this.timer); if (!this.closed && views.size) this.timer = setTimeout(() => this.connect(), Math.min(60000, 1000 * 2 ** Math.min(this.attempt++, 6)) * (.75 + Math.random() / 2)); }
    send(type, point_id) { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type, ...(point_id ? { point_id } : {}) })); }
  }
  const realtime = new Realtime();
  setInterval(() => { if (!document.hidden && views.size) { realtime.send('ping'); for (const view of views) { view.sync(); if (view.point && !view.minimized) realtime.send('presence', view.point); } } }, 20000);

  class ExchangeView {
    constructor(container, conversationId, title, onClose, initialPoint) {
      this.conversation = conversationId; this.point = null; this.rows = new Map(); this.version = 0; this.before = null; this.busy = false; this.syncing = false; this.destroyed = false; this.reply = null; this.edit = null; this.reference = null; this.file = null; this.mentions = []; this.links = []; this.minimized = false;
      this.restoreFocus = document.activeElement;
      this.root = el('section', null, 'mk-exchange-window'); this.root.setAttribute('aria-label', title || 'Discussion');
      const header = el('header'); this.heading = el('strong', title || 'Discussion'); header.append(this.heading);
      const full = el('a', 'Ouvrir'); full.href = web + conversationId + '/'; header.append(full);
      header.append(button('−', () => { this.minimized = !this.minimized; this.root.dataset.minimized = this.minimized; }));
      header.append(button('×', () => { this.dispose(); onClose?.(); if(this.restoreFocus?.isConnected && this.restoreFocus.offsetParent)this.restoreFocus.focus();else launch.focus(); }));
      header.lastChild.setAttribute('aria-label', 'Fermer la discussion'); header.children[2].setAttribute('aria-label', 'Réduire ou restaurer la discussion');
      this.select = el('select'); this.select.setAttribute('aria-label', 'Choisir la Discussion'); this.select.addEventListener('change', () => this.openPoint(this.select.value));
      const controls = el('div', null, 'mk-exchange-controls'); this.search = el('input'); this.search.type = 'search'; this.search.placeholder = 'Dans les messages…'; this.search.setAttribute('aria-label', 'Rechercher dans les messages');
      controls.append(this.search, button('Rechercher', () => this.find()), button('Effacer', () => { this.search.value = ''; this.render(); }));
      this.status = el('p', '', 'mk-messaging-status'); this.status.setAttribute('role', 'status');
      this.log = el('div', null, 'mk-exchange-log'); this.log.setAttribute('role', 'log'); this.log.setAttribute('aria-label', 'Messages'); this.log.tabIndex = 0;
      this.newMessages = button('Nouveaux messages ↓', () => { this.log.scrollTop = this.log.scrollHeight; this.newMessages.hidden = true; }); this.newMessages.hidden = true;
      this.older = button('Messages précédents', () => this.history()); this.older.hidden = true;
      this.form = el('form'); this.context = el('div', null, 'mk-exchange-compose-context'); this.context.hidden = true;
      this.input = el('textarea'); this.input.rows = 2; this.input.maxLength = 5000; this.input.placeholder = 'Écrire un message…'; this.input.setAttribute('aria-label', 'Message');
      this.input.addEventListener('input', () => { this.reference = null; this.saveDraft(); realtime.send('typing', this.point); });
      this.input.addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && matchMedia('(pointer:fine)').matches) { event.preventDefault(); this.form.requestSubmit(); } });
      this.submit = el('button', 'Envoyer'); this.submit.type = 'submit';
      this.attach = el('input'); this.attach.type = 'file'; this.attach.hidden = true; this.attach.addEventListener('change', () => this.chooseFile(this.attach.files[0]));
      this.voiceButton = button('Vocal', () => this.voice()); this.voiceButton.hidden = true;
      this.referenceButton = button('Référence', () => this.referenceOptions());
      this.attachButton = button('Joindre', () => this.attach.click()); this.attachButton.hidden = true;
      this.mentionButton = button('@', () => this.mention()); this.mentionButton.setAttribute('aria-label', 'Mentionner une personne');
      this.cancelUpload = button('Annuler le transfert', () => this.upload?.abort()); this.cancelUpload.hidden = true;
      this.progress = el('progress'); this.progress.max = 100; this.progress.hidden = true; this.progress.setAttribute('aria-label', 'Transfert du média');
      this.form.append(this.context, this.input, this.attach, this.attachButton, this.voiceButton, this.referenceButton, this.mentionButton, this.submit, this.cancelUpload, this.progress);
      this.form.addEventListener('submit', event => { event.preventDefault(); this.send(); });
      this.root.append(header, this.select, controls, this.status, this.older, this.log, this.newMessages, this.form); container.append(this.root);
      this.root.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); header.lastChild.click(); } });
      this.root.addEventListener('dragover', event => { if ([...event.dataTransfer.types].some(t => t === 'Files' || t === 'application/makolo-reference')) event.preventDefault(); });
      this.root.addEventListener('drop', event => { event.preventDefault(); const ref = event.dataTransfer.getData('application/makolo-reference'); if (ref) { try { const item = JSON.parse(ref); if (['journey_artifact', 'requirement_definition', 'journey_requirement_assessment'].includes(item.kind) && /^[\da-f-]{36}$/i.test(item.id)) { this.links = [{ kind: item.kind, id: item.id }]; this.showContext('Référence à joindre'); this.saveDraft(); } } catch { this.status.textContent = 'Référence invalide.'; } } else this.chooseFile(event.dataTransfer.files[0]); });
      views.add(this); this.load(initialPoint);
    }
    draftKey() { return `makolo:${profile}:exchange:${this.point}`; }
    saveDraft() { if (!this.point) return; try { sessionStorage.setItem(this.draftKey(), JSON.stringify({ body: this.input.value, reference: this.reference, reply: this.reply?.id, edit: this.edit ? {id:this.edit.id,edit_version:this.edit.edit_version} : null, links: this.links, mentions: this.mentions })); } catch { this.status.textContent = 'Le brouillon reste dans cette fenêtre. Le stockage local est indisponible.'; } }
    restoreDraft() { try { const value = JSON.parse(sessionStorage.getItem(this.draftKey()) || '{}'); this.input.value = value.body || ''; this.reference = value.reference || null; this.reply = value.reply ? { id: value.reply } : null; this.links = value.links || []; this.mentions = value.mentions || []; this.edit=value.edit||null;if(this.edit)this.showContext('Modifier le message'); if (this.reply) this.showContext('Réponse citée'); } catch { this.status.textContent = 'Brouillon local indisponible.'; } }
    showContext(text) { this.context.hidden = false; this.context.replaceChildren(el('span', text), button('Annuler', () => { this.reply = this.edit = null; this.file = null; this.links = []; this.context.hidden = true; this.saveDraft(); })); }
    async load(initialPoint) {
      try {
        const detail = await request(this.conversation + '/'); if (this.destroyed) return;
        this.heading.textContent = detail.title; this.capabilities = detail.composer || {};
        const targets = new Map((this.capabilities.exchange_targets || []).map(p => [p.id, p]));
        for (const section of ['points', 'essential', 'elsewhere', 'timeline']) for (const p of detail[section] || []) if (p.kind === 'exchange') targets.set(p.id, p);
        if (detail.focused_point?.kind === 'exchange') targets.set(detail.focused_point.id, detail.focused_point);
        for (const p of targets.values()) { const option = el('option', p.title || 'Discussion'); option.value = p.id; this.select.append(option); }
        if (!targets.size) { this.status.textContent = 'Aucune Discussion accessible. Ouvrez la conversation pour consulter ses Points.'; this.form.hidden = true; return; }
        await this.openPoint(targets.has(initialPoint) ? initialPoint : targets.keys().next().value);
      } catch (error) { this.failure(error); }
    }
    async openPoint(point) {
      if (this.point) { this.saveDraft(); if (![...views].some(v => v !== this && v.point === this.point)) realtime.send('unsubscribe', this.point); }
      this.point = point; this.scope = null; this.select.value = point; this.rows.clear(); this.version = 0; this.before = null; this.reply = this.edit = null; this.context.hidden = true; this.render(); this.restoreDraft();
      this.form.hidden = !(this.capabilities.exchange_targets || []).some(p => p.id === point);
      this.attachButton.hidden = !(this.capabilities.media_kinds || []).length;
      this.voiceButton.hidden = !(this.capabilities.media_kinds || []).some(k => ['voice','audio'].includes(k)) || !window.MediaRecorder || !navigator.mediaDevices;
      realtime.send('subscribe', point); realtime.connect();
      await this.history(true); await this.sync();
    }
    failure(error) { if ([401, 403, 404].includes(error.status)) this.revoke(); else this.status.textContent = error.message || 'Actualisation interrompue. Votre saisie est conservée.'; }
    revoke() { this.rows.clear(); this.log.replaceChildren(); this.form.hidden = true; this.status.textContent = 'Cette Discussion n’est plus accessible.'; this.revoked = true; }
    async history(initial = false) {
      if (!this.point || this.destroyed) return;
      const point = this.point, oldHeight = this.log.scrollHeight, oldTop = this.log.scrollTop;
      try {
        const page = await request(`points/${point}/entries/?order=latest&limit=50${!initial && this.before ? '&before_sequence=' + this.before : ''}`);
        if (this.destroyed || point !== this.point) return;
        if (this.scope && this.scope !== page.scope) { this.rows.clear(); this.version = 0; }
        this.scope = page.scope;
        for (const row of page.results) this.rows.set(row.id, row);
        this.before = page.before_sequence; this.older.hidden = !page.has_more; this.render();
        this.log.scrollTop = initial ? this.log.scrollHeight : oldTop + this.log.scrollHeight - oldHeight;
      } catch (error) { this.failure(error); }
    }
    async sync() {
      if (!this.point || this.destroyed || this.syncing || this.revoked || document.hidden) return;
      this.syncing = true; const point = this.point;
      try {
        let more;
        do {
          const page = await request(`points/${point}/entries/sync/?after_version=${this.version}&limit=50`);
          if (this.destroyed || point !== this.point) return;
          if (this.scope && this.scope !== page.scope) { this.rows.clear(); this.version = 0; this.scope = page.scope; more = true; continue; }
          this.scope = page.scope;
          const atBottom = this.log.scrollHeight - this.log.scrollTop - this.log.clientHeight < 80;
          for (const row of page.results) this.rows.set(row.id, row);
          // Web only ACKs delivered after materialization; it has no durable message cache.
          this.version = page.next_version; more = page.has_more;
          if (page.results.length) { this.render(); if (atBottom) this.log.scrollTop = this.log.scrollHeight; else this.newMessages.hidden = false; }
        } while (more);
        await this.receipts();
        this.status.textContent = navigator.onLine ? '' : 'Hors connexion. Votre saisie est conservée.';
      } catch (error) { this.failure(error); } finally { this.syncing = false; }
    }
    render(rows = [...this.rows.values()].sort((a,b) => a.sequence - b.sequence)) {
      const focused = document.activeElement?.dataset?.messageAction;
      const fragment = document.createDocumentFragment(); let date = '';
      for (const row of rows) {
        const day = new Date(row.created_at).toLocaleDateString('fr');
        if (day !== date) { fragment.append(el('p', day, 'mk-message-date')); date = day; }
        const bubble = el('article', null, 'mk-message'); bubble.dataset.own = row.own; bubble.id = `exchange-${this.point}-${row.id}`;
        bubble.append(el('small', row.own ? 'Vous' : row.author?.label));
        if (row.represented_space) bubble.append(el('small', row.represented_space.label));
        if (row.reply_to) { const quote = el('blockquote', row.reply_to.removed ? 'Message supprimé' : row.reply_to.body); quote.tabIndex = 0; quote.title = 'Rejoindre le message cité'; const jump = () => this.root.querySelector(`#exchange-${this.point}-${row.reply_to.id}`)?.scrollIntoView({block:'center'}); quote.onclick = jump; quote.onkeydown = e => { if (e.key === 'Enter') jump(); }; bubble.append(quote); }
        bubble.append(el('p', row.removed ? 'Message supprimé' : row.body));
        for (const mention of row.mentions || []) bubble.append(el('small', '@' + mention.label));
        for (const file of row.attachments || []) {
          const path = safePath(file.download_path); if (!path) continue;
          if (file.kind === 'image') { const image = el('img'); image.src = path; image.alt = file.name; image.loading = 'lazy'; bubble.append(image); }
          if (['voice', 'audio'].includes(file.kind)) { const audio = el('audio'); audio.controls = true; audio.preload = 'none'; audio.src = path; bubble.append(audio); }
          const link = el('a', `${file.name} · ${Math.ceil(file.size/1024)} Ko`); link.href = path; link.target = '_blank'; link.rel = 'noopener'; link.title = file.mime_type; bubble.append(link);
        }
        for (const reference of row.references || []) { const path = safePath(reference.download_url); if (reference.available && path) { const link = el('a', reference.label); link.href = path; link.target = '_blank'; link.rel = 'noopener'; bubble.append(link); } else bubble.append(el('small', reference.available ? reference.label : 'Référence inaccessible')); }
        bubble.append(el('small', new Date(row.created_at).toLocaleTimeString('fr',{hour:'2-digit',minute:'2-digit'}) + (row.edited_at ? ' · Modifié' : '') + (row.own ? row.delivery?.read_count > 0 ? ` · Lu (${row.delivery.read_count})` : row.delivery?.delivered_count > 0 ? ` · Livré (${row.delivery.delivered_count})` : ' · Confirmé' : '')));
        if (!row.removed) {
          const menu = el('details'), summary = el('summary', 'Actions'); menu.append(summary); const actions = el('div', null, 'mk-message-actions');
          const add = (label, fn) => { const b = button(label, fn); b.dataset.messageAction = row.id + label; actions.append(b); };
          add('Copier', async () => { try { await navigator.clipboard.writeText(row.body); } catch { this.status.textContent = 'Copie indisponible. Sélectionnez le texte.'; } });
          if (row.capabilities?.reply) add('Répondre', () => { this.reply = row; this.edit = null; this.showContext('Réponse à ' + row.body.slice(0,80)); this.saveDraft(); this.input.focus(); });
          if (row.capabilities?.edit) add('Modifier', () => { this.edit = row; this.reply = null; this.input.value = row.body; this.showContext('Modifier le message'); this.input.focus(); });
          if (row.capabilities?.delete) add('Supprimer', async () => { if (!window.confirm('Supprimer ce message pour cette Discussion ?')) return; await this.mutate(`entries/${row.id}/`, 'DELETE'); });
          if (row.capabilities?.react) for (const emoji of ['👍','❤️','🙏','✅','👀','🎉']) add(emoji, () => this.mutate(`entries/${row.id}/reactions/`, 'POST', {emoji, selected: !row.reactions.some(r => r.emoji === emoji && r.selected), client_reference: uid()}));
          menu.append(actions); bubble.append(menu);
          if (row.reactions?.length) bubble.append(el('small', row.reactions.map(r => r.emoji + ' ' + r.count).join('  ')));
        }
        fragment.append(bubble);
      }
      this.log.replaceChildren(fragment);
      if (focused) [...this.log.querySelectorAll('[data-message-action]')].find(n => n.dataset.messageAction === focused)?.focus({preventScroll:true});
    }
    async receipts() {
      if (!this.point || this.destroyed || this.revoked) return;
      try { const result = await request(`points/${this.point}/receipts/`); for (const state of result.entries || []) { const row = this.rows.get(state.id); if (row) this.rows.set(row.id, {...row,delivery:state.delivery}); } const top=this.log.scrollTop; this.render();this.log.scrollTop=top; }
      catch(error) { this.failure(error); }
    }
    async mutate(path, method, body) { try { const result = await request(path, method, body); if (result.entry) this.rows.set(result.entry.id, result.entry); this.render(); await this.sync(); return true; } catch (error) { this.failure(error); return false; } }
    async send() {
      if (this.busy || !this.point || (!this.input.value.trim() && !this.file && !this.links.length)) return;
      this.busy = true; this.submit.disabled = true;
      const text = this.input.value, point = this.point;
      this.reference ||= uid(); this.saveDraft();
      try {
        let result;
        if (this.file) result = await this.sendFile();
        else if (this.edit) result = await request(`entries/${this.edit.id}/`, 'PATCH', {body:text, expected_edit_version:this.edit.edit_version, client_reference:this.reference, mention_profile_ids:this.mentions});
        else result = await request(`points/${point}/entries/`, 'POST', {body:text, client_reference:this.reference, reply_to_id:this.reply?.id || null, mention_profile_ids:this.mentions, references:this.links});
        if (result.status !== 'confirmed' && !result.attachment) throw new Error('Envoi non confirmé. Réessayez avec le même contenu.');
        if (this.input.value === text) { this.input.value = ''; this.reference = null; this.reply = this.edit = this.file = null; this.links = []; this.mentions = []; this.context.hidden = true; this.saveDraft(); }
        if(this.voicePreviewUrl){URL.revokeObjectURL(this.voicePreviewUrl);this.voicePreviewUrl=null;}
        await this.sync();
      } catch (error) { this.failure(error); } finally { this.busy = false; this.submit.disabled = false; }
    }
    chooseFile(file) {
      if (!file) return;if(this.busy){this.status.textContent='Un transfert est déjà en cours.';return;} this.file = file; this.reference = null; this.showContext(`${file.name} · ${Math.ceil(file.size/1024)} Ko`);
      if (file.type.startsWith('image/')) { const image = el('img', null, 'mk-message-preview'); const url = URL.createObjectURL(file); image.src = url; image.alt = 'Aperçu avant envoi'; image.onload = () => URL.revokeObjectURL(url); this.context.prepend(image); }
    }
    sendFile() {
      const file = this.file; const kind = file.type.startsWith('image/') ? 'image' : file.type.startsWith('audio/') ? ((this.capabilities.media_kinds || []).includes('voice') ? 'voice' : 'audio') : 'file';
      if (!(this.capabilities.media_kinds || []).includes(kind)) return Promise.reject(new Error('Ce type de média n’est pas autorisé ici.'));
      return new Promise((resolve,reject) => {
        const data = new FormData(); data.append('file', file); data.append('kind',kind); data.append('body',this.input.value); data.append('point_id',this.point); data.append('client_reference',this.reference);
        const xhr = this.upload = new XMLHttpRequest(); xhr.open('POST',api + this.conversation + '/media/'); xhr.setRequestHeader('X-CSRFToken',csrf());xhr.setRequestHeader('X-Makolo-Profile',profile); xhr.responseType = 'json'; this.progress.hidden = this.cancelUpload.hidden = false; this.progress.removeAttribute('value');
        xhr.upload.onprogress = event => { if (event.lengthComputable) this.progress.value = event.loaded / event.total * 100; };
        xhr.onloadend = () => { this.progress.hidden = this.cancelUpload.hidden = true; this.upload = null; };
        xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve(xhr.response) : reject(new Error('Transfert non confirmé. Réessayez.'));
        xhr.onerror = () => reject(new Error('Transfert interrompu. Le fichier reste sélectionné.')); xhr.onabort = () => reject(new Error('Transfert annulé.')); xhr.send(data);
      });
    }
    async voice() {
      if (this.recorder?.state === 'recording') { this.recorder.stop(); return; }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({audio:true});
        if(this.destroyed){stream.getTracks().forEach(t=>t.stop());return;}
        const mime = ['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
        const recorder = this.recorder = new MediaRecorder(stream, mime ? {mimeType:mime}:{}); const parts=[];
        this.voiceCancelled=false; const started=performance.now();
        recorder.ondataavailable=event=>{if(event.data.size)parts.push(event.data);};
        recorder.onerror=()=>{this.status.textContent='Enregistrement interrompu.';stream.getTracks().forEach(t=>t.stop());};
        recorder.onstop=()=>{stream.getTracks().forEach(t=>t.stop());this.voiceButton.textContent='Vocal';this.recorder=null;if(this.voiceCancelled||this.destroyed)return;const type=recorder.mimeType.split(';')[0];const extension=type.includes('ogg')?'ogg':type.includes('mp4')?'m4a':'webm';const file=new File(parts,'vocal.'+extension,{type});this.chooseFile(file);this.voicePreviewUrl=URL.createObjectURL(file);const audio=el('audio');audio.controls=true;audio.src=this.voicePreviewUrl;this.context.prepend(audio,el('small',Math.round((performance.now()-started)/1000)+' s'));};
        recorder.start(); this.voiceButton.textContent='Arrêter'; this.context.hidden=false;this.context.replaceChildren(el('span','Enregistrement en cours'),button('Annuler',()=>{this.voiceCancelled=true;recorder.stop();this.context.hidden=true;}));
      }catch{this.status.textContent='Microphone indisponible. Vérifiez son autorisation.';}
    }
    async referenceOptions() {
      try {const page=await request(`points/${this.point}/references/options/`);this.context.hidden=false;this.context.replaceChildren(el('span',page.results.length?'Joindre une référence':'Aucune référence accessible dans ce contexte.'));for(const ref of page.results)this.context.append(button(ref.label,()=>{this.links=[{kind:ref.kind,id:ref.id}];this.showContext(ref.label);this.saveDraft();}));this.context.append(button('Fermer',()=>{this.context.hidden=true;}));}catch(error){this.failure(error);}
    }
    async mention() {
      try { const page = await request(`points/${this.point}/mentions/?q=${encodeURIComponent(this.input.value.split('@').pop().slice(0,80))}`); const chooser = el('div'); for (const p of page.results) chooser.append(button(p.label, () => { if (!this.mentions.includes(p.id)) this.mentions.push(p.id); this.showContext('Mention : ' + p.label); this.saveDraft(); this.input.focus(); })); this.context.hidden = false; this.context.replaceChildren(chooser,button('Fermer',()=>{this.context.hidden=true;})); } catch (error) { this.failure(error); }
    }
    async find() { if (!this.search.value.trim()) { this.render(); return; } try { const page = await request(`points/${this.point}/entries/search/?q=${encodeURIComponent(this.search.value)}`); this.render(page.results); this.status.textContent = page.next_cursor ? '50 résultats. Précisez votre recherche.' : `${page.results.length} résultat(s)`; } catch (error) { this.failure(error); } }
    ephemeral(data) { clearTimeout(this.ephemeralTimer); this.status.textContent = data.type === 'typing_changed' ? 'Une personne écrit…' : 'Actif dans cette discussion'; this.ephemeralTimer = setTimeout(() => { this.status.textContent = ''; }, data.ttl * 1000); }
    dispose() { this.saveDraft(); this.destroyed = true; views.delete(this); if (![...views].some(v => v.point === this.point)) realtime.send('unsubscribe',this.point); clearTimeout(this.ephemeralTimer); this.upload?.abort();this.voiceCancelled=true;if(this.recorder?.state==='recording')this.recorder.stop();if(this.voicePreviewUrl)URL.revokeObjectURL(this.voicePreviewUrl); this.root.remove(); }
  }
  function open(conversation, title, point, container) {
    if (container) { for (const view of views) if (view.root.parentElement === container) view.dispose(); return new ExchangeView(container,conversation,title,null,point); }
    if (floating.has(conversation)) { const view=floating.get(conversation); view.minimized=false; view.root.dataset.minimized=false; windows.append(view.root); view.input.focus(); return view; }
    if (floating.size >= 3) { panel.querySelector('[role=status]').textContent='Trois discussions sont ouvertes. Fermez-en une pour continuer.'; panel.hidden=false; return; }
    const view = new ExchangeView(windows,conversation,title,()=>floating.delete(conversation),point); floating.set(conversation,view); panel.hidden=true; launch.setAttribute('aria-expanded','false'); return view;
  }
  async function list(query='') { const status=panel.querySelector('[role=status]'); status.textContent='Chargement…'; try { const page=await request('?limit=50&q='+encodeURIComponent(query)); const list=panel.querySelector('[data-discussion-list]'); list.replaceChildren(); for(const row of page.results) { const b=button(row.title,()=>open(row.id,row.title)); b.className='mk-messaging-row'; list.append(b); } status.textContent=page.results.length?'':'Aucune discussion accessible.'; } catch(error) { status.textContent=error.message; } }
  launch.onclick=()=>{panel.hidden=!panel.hidden;launch.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden){list();panel.querySelector('input').focus();}};
  panel.querySelector('[data-panel-close]').onclick=()=>{panel.hidden=true;launch.setAttribute('aria-expanded','false');launch.focus();};
  panel.querySelector('form').onsubmit=event=>{event.preventDefault();list(panel.querySelector('input').value);};
  function mount() {
    for(const view of [...views]) if(!view.root.isConnected) view.dispose();
    document.querySelectorAll('[data-exchange-page]:not([data-messaging-mounted])').forEach(node=>{node.dataset.messagingMounted='true';open(node.dataset.conversation,node.dataset.title,node.dataset.point,node);});
  }
  document.addEventListener('click',event=>{const link=event.target.closest('[data-messaging-conversation]');if(!link||event.ctrlKey||event.metaKey||event.shiftKey)return;const container=document.querySelector('[data-messaging-page]');if(container){event.preventDefault();open(link.dataset.messagingConversation,link.textContent.trim(),null,container);container.scrollIntoView({block:'nearest'});}});
  document.addEventListener('htmx:afterSwap',mount);document.addEventListener('visibilitychange',()=>{if(!document.hidden){for(const view of views)view.sync();realtime.connect();}});
  window.MakoloMessaging={open};mount();
})();
