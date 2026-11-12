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
  let activeCard;
  function hoverCard(node,lines){
    node.tabIndex=0;const id='mk-card-'+uid();
    const hide=()=>{if(activeCard?.id===id){activeCard.remove();activeCard=null;node.removeAttribute('aria-describedby');}};
    const show=()=>{activeCard?.remove();const card=el('div',lines.filter(Boolean).join(' · '),'mk-messaging-hover-card');card.id=id;card.setAttribute('role','tooltip');host.append(card);const box=node.getBoundingClientRect();card.style.left=Math.min(box.left,innerWidth-280)+'px';card.style.top=Math.max(8,box.top-card.offsetHeight-8)+'px';activeCard=card;node.setAttribute('aria-describedby',id);};
    node.addEventListener('mouseenter',show);node.addEventListener('mouseleave',hide);node.addEventListener('focus',show);node.addEventListener('blur',hide);node.addEventListener('pointerdown',event=>{if(event.pointerType==='touch')activeCard?.id===id?hide():show();});
  }
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&activeCard){activeCard.remove();activeCard=null;event.stopImmediatePropagation();}},true);
  async function request(path, method = 'GET', body) {
    const response = await fetch(api + path, { method, credentials: 'same-origin', cache: 'no-store', headers: { 'Accept': 'application/json', 'X-Makolo-Profile':profile, ...(method !== 'GET' ? { 'X-CSRFToken': csrf(), 'Content-Type': 'application/json' } : {}) }, body: body == null ? undefined : JSON.stringify(body) });
    if (!response.ok) { const error = new Error(response.status === 409 ? 'Le contenu a changé. Rechargez avant de réessayer.' : 'Action non confirmée. Réessayez.'); error.status = response.status; throw error; }
    return response.json();
  }
  class Realtime {
    constructor() { this.socket = null; this.attempt = 0; this.timer = null; this.closed = false; this.connecting=false; this.authenticated=false; }
    async connect() {
      if (this.closed || this.connecting || this.socket) return;
      this.connecting=true;
      try {
        const ticket = await request('realtime-ticket/', 'POST', {});
        if (this.closed) return;
        const uri = new URL(ticket.websocket_path, location.origin); uri.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socket = this.socket = new WebSocket(uri);
        socket.onopen = () => socket.send(JSON.stringify({ type: 'authenticate', ticket: ticket.ticket }));
        socket.onmessage = event => {
          let data; try { data = JSON.parse(event.data); } catch { socket.close(); return; }
          if (data.type === 'authenticated') { this.authenticated=true; scheduleList(); this.attempt = 0; for (const point of new Set([...views].map(v => v.point).filter(Boolean))) this.send('subscribe', point);for(const id of new Set([...views].map(v=>v.conversation)))this.sendConversation('subscribe',id); for (const view of views) view.sync(); }
          if(data.type==='conversation_changed')scheduleList();if(data.code==='access_revoked'&&data.conversation_id){for(const view of views)if(view.conversation===data.conversation_id)view.revoke();scheduleList();}
          for (const view of views) {
            if (data.point_id !== view.point) continue;
            if (data.type === 'point_changed') view.sync();
            if (data.type === 'receipt_changed') view.receipts();
            if (data.code === 'access_revoked') view.revoke();
            if (['typing_changed', 'presence_changed'].includes(data.type) && data.profile_id !== profile) view.ephemeral(data);
          }
        };
        socket.onerror = () => socket.close();
        socket.onclose = () => { if (this.socket === socket) this.socket = null; this.authenticated=false; this.retry(); };
      } catch { this.retry(); } finally {this.connecting=false;}
    }
    retry() { clearTimeout(this.timer); if (!this.closed) this.timer = setTimeout(() => this.connect(), Math.min(60000, 1000 * 2 ** Math.min(this.attempt++, 6)) * (.75 + Math.random() / 2)); }
    sendConversation(type,conversation_id){if(this.authenticated&&this.socket?.readyState===WebSocket.OPEN)this.socket.send(JSON.stringify({type,conversation_id}));}
    send(type, point_id) { if (this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type, ...(point_id ? { point_id } : {}) })); }
  }
  const realtime = new Realtime();
  let listTimer,listRunning=false,listAgain=false;
  function scheduleList(){clearTimeout(listTimer);listTimer=setTimeout(()=>list(panel.querySelector('input').value),150);}
  setInterval(() => { if (!document.hidden) { realtime.send('ping'); scheduleList();for (const view of views) { view.sync(); if (view.point && !view.minimized) realtime.send('presence', view.point); } } }, 20000);

  class ExchangeView {
    constructor(container, conversationId, title, onClose, initialPoint) {
      this.conversation = conversationId; this.point = null; this.rows = new Map(); this.version = 0; this.before = null; this.busy = false; this.syncing = false; this.destroyed = false; this.reply = null; this.edit = null; this.reference = null; this.file = null; this.mentions = []; this.links = []; this.minimized = false;this.rowHeights=new Map();this.userReading=false;this.durableSequence=0;this.readSequence=0;this.receiptBusy=false;
      this.scrollPositions=new Map();this.mediaDrafts=new Map();
      this.restoreFocus = document.activeElement;
      this.root = el('section', null, 'mk-exchange-window'); this.root.setAttribute('aria-label', title || 'Discussion');
      const header = el('header'); this.heading = el('strong', title || 'Discussion'); header.append(this.heading);
      const full = el('a', 'Ouvrir');hoverCard(full,[title||'Conversation']); full.href = web + conversationId + '/'; header.append(full);
      header.append(button('−', () => { if(!this.minimized)this.savedScroll=this.log.scrollTop;this.minimized = !this.minimized; this.root.dataset.minimized = this.minimized;if(!this.minimized)requestAnimationFrame(()=>{this.log.scrollTop=this.savedScroll||0;this.render();}); }));
      header.append(button('×', () => { this.dispose(); onClose?.(); if(this.restoreFocus?.isConnected && this.restoreFocus.offsetParent)this.restoreFocus.focus();else launch.focus(); }));
      header.lastChild.setAttribute('aria-label', 'Fermer la discussion'); header.children[2].setAttribute('aria-label', 'Réduire ou restaurer la discussion');this.closeButton=header.lastChild;
      this.select = el('select'); this.select.setAttribute('aria-label', 'Choisir la Discussion'); this.select.addEventListener('change', () => this.openPoint(this.select.value));
      const controls = el('div', null, 'mk-exchange-controls');this.controls=controls; this.search = el('input'); this.search.type = 'search'; this.search.placeholder = 'Dans les messages…'; this.search.setAttribute('aria-label', 'Rechercher dans les messages');
      controls.append(this.search, button('Rechercher', () => this.find()), button('Effacer', () => { this.search.value = '';this.searchResults.replaceChildren();this.moreSearch.hidden=true;this.render(); }));
      this.status = el('p', '', 'mk-messaging-status'); this.status.setAttribute('role', 'status');
      this.log = el('div', null, 'mk-exchange-log'); this.log.setAttribute('role', 'log'); this.log.setAttribute('aria-label', 'Messages');this.log.setAttribute('aria-busy','true'); this.log.tabIndex = 0;
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
      this.searchResults=el('div',null,'mk-exchange-search-results');this.searchResults.setAttribute('aria-live','polite');
      this.moreSearch=button('Résultats suivants',()=>this.find(true));this.moreSearch.hidden=true;controls.after(this.searchResults);
      this.log.addEventListener('scroll',()=>{cancelAnimationFrame(this.renderFrame);this.renderFrame=requestAnimationFrame(()=>{this.render();if(this.userReading)this.confirmRead();});});
      for(const kind of ['pointerdown','keydown','wheel','touchstart'])this.log.addEventListener(kind,event=>{if(event.isTrusted){this.userReading=true;setTimeout(()=>this.confirmRead(),100);}});
      this.form.addEventListener('submit', event => { event.preventDefault(); this.send(); });
      header.append(button('Agrandir',()=>{this.root.classList.toggle('mk-exchange-expanded');this.render();}));
      this.resizeObserver=new ResizeObserver(entries=>{if(this.minimized||this.destroyed)return;let changed=false;for(const entry of entries){const id=entry.target.dataset.slot;if(id&&Math.abs((this.rowHeights.get(id)||0)-entry.target.getBoundingClientRect().height)>1){this.rowHeights.set(id,entry.target.getBoundingClientRect().height);changed=true;}}if(changed){this.lastRender=null;cancelAnimationFrame(this.renderFrame);this.renderFrame=requestAnimationFrame(()=>this.render());}});
      this.root.append(header, this.select, controls, this.searchResults,this.moreSearch, this.status, this.older, this.log, this.newMessages, this.form); container.append(this.root);
      this.root.addEventListener('keydown', event => { if (event.key === 'Escape') { event.stopPropagation(); this.closeButton.click(); } });
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
        this.heading.textContent = detail.title;
        const options=el('details');options.append(el('summary','Options'));let personal=detail.personal_state||{};
        for(const [key,label,field] of [['pinned','Épingler','pinned'],['mute','Sourdine','muted'],['share_read_receipts','Partager les lectures','share_read_receipts']]){
          const control=el('input');control.type='checkbox';control.checked=personal[field]===true;
          control.onchange=async()=>{control.disabled=true;try{personal=await request(this.conversation+'/personal-state/','POST',{[key]:control.checked});scheduleList();}catch(error){control.checked=!control.checked;this.failure(error);}finally{control.disabled=false;}};
          const labelNode=el('label',label);labelNode.prepend(control);options.append(labelNode);
        }this.controls.append(options);
        this.capabilities = detail.composer || {};
        const targets = new Map((this.capabilities.exchange_targets || []).map(p => [p.id, p]));
        for (const section of ['points', 'essential', 'elsewhere', 'timeline']) for (const p of detail[section] || []) if (p.kind === 'exchange') targets.set(p.id, p);
        if (detail.focused_point?.kind === 'exchange') targets.set(detail.focused_point.id, detail.focused_point);
        for (const p of targets.values()) { const option = el('option', p.title || 'Discussion'); option.value = p.id; this.select.append(option); }
        if (!targets.size) { this.status.textContent = 'Aucune Discussion accessible. Ouvrez la conversation pour consulter ses Points.'; this.form.hidden = true; return; }
        await this.openPoint(targets.has(initialPoint) ? initialPoint : targets.keys().next().value);
      } catch (error) { this.failure(error); }
    }
    async openPoint(point) {
      if (this.point) {this.scrollPositions.set(this.point,this.log.scrollTop);this.mediaDrafts.set(this.point,this.file); this.saveDraft(); if (![...views].some(v => v !== this && v.point === this.point)) realtime.send('unsubscribe', this.point); }
      this.point = point;this.input.value='';this.mentions=[];this.links=[];this.reference=null;this.file=this.mediaDrafts.get(point)||null;this.userReading=false;this.durableSequence=0;this.readSequence=0;this.lastRender=null;this.rowHeights.clear();this.scope = null; this.select.value = point; this.rows.clear(); this.version = 0; this.before = null; this.reply = this.edit = null; this.context.hidden = true; this.render(); this.restoreDraft();if(this.file)this.showContext(this.file.name);
      this.form.hidden = !(this.capabilities.exchange_targets || []).some(p => p.id === point);
      this.attachButton.hidden = !(this.capabilities.media_kinds || []).length;
      this.voiceButton.hidden = !(this.capabilities.media_kinds || []).some(k => ['voice','audio'].includes(k)) || !window.MediaRecorder || !navigator.mediaDevices;
      realtime.send('subscribe', point);realtime.sendConversation('subscribe',this.conversation); realtime.connect();
      await this.history(true); await this.sync();
    }
    failure(error) { if ([401, 403, 404].includes(error.status)) this.revoke(); else this.status.textContent = error.message || 'Actualisation interrompue. Votre saisie est conservée.'; }
    revoke() { this.rows.clear(); this.log.replaceChildren(); this.form.hidden = true; this.status.textContent = 'Cette Discussion n’est plus accessible.'; this.revoked = true;window.MakoloExchangeCache?.purge(profile,this.point).catch(()=>{this.status.textContent='Accès révoqué. Fermez ce navigateur pour supprimer son cache temporaire.';}); }
    async history(initial = false) {
      if (!this.point || this.destroyed) return;
      const point = this.point, oldHeight = this.log.scrollHeight, oldTop = this.log.scrollTop;
      try {
        const page = await request(`points/${point}/entries/?order=latest&limit=50${!initial && this.before ? '&before_sequence=' + this.before : ''}`);
        if (this.destroyed || point !== this.point) return;
        if (this.scope && this.scope !== page.scope) { this.rows.clear(); this.version = 0; }
        this.scope = page.scope;
        await this.materialize(page);
        this.log.setAttribute('aria-busy','false');this.historyLoaded=true;this.before = page.before_sequence; this.older.hidden = !page.has_more; this.render();
        this.log.scrollTop = initial ? (this.scrollPositions.get(point)??this.log.scrollHeight) : oldTop + this.log.scrollHeight - oldHeight;
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
          await this.materialize(page);
          // Advance only after the page was materialized; delivery requires durable storage.
          this.version = page.next_version; more = page.has_more;
          if (page.results.length) { this.render(); if (atBottom) this.log.scrollTop = this.log.scrollHeight; else this.newMessages.hidden = false; }
        } while (more);
        await this.confirmDelivered();
        await this.receipts();
        this.status.textContent = navigator.onLine ? '' : 'Hors connexion. Votre saisie est conservée.';
      } catch (error) { this.failure(error); } finally { this.syncing = false; }
    }
    render(rows = [...this.rows.values()].sort((a,b) => a.sequence - b.sequence)) {
      if(this.minimized||this.destroyed)return;
      const focused = document.activeElement?.dataset?.messageAction;
      const anchor=[...this.log.querySelectorAll('[data-slot]')].find(node=>node.getBoundingClientRect().bottom>this.log.getBoundingClientRect().top);
      const anchorId=anchor?.dataset.slot, anchorOffset=anchor?anchor.getBoundingClientRect().top-this.log.getBoundingClientRect().top:0;
      const prefix=[0];for(const row of rows)prefix.push(prefix.at(-1)+(this.rowHeights.get(row.id)||150));
      const top=this.log.scrollTop,bottom=top+this.log.clientHeight;let start=0;while(start<rows.length&&prefix[start+1]<top)start++;start=Math.max(0,start-5);let end=start;while(end<rows.length&&prefix[end]<bottom+800)end++;end=Math.min(rows.length,Math.max(end,start+15));
      const signature=JSON.stringify([start,end,this.historyLoaded,rows.slice(start,end)]);if(this.lastRender===signature)return;this.lastRender=signature;
      const fragment = document.createDocumentFragment();const spacer=el('div');spacer.style.height=prefix[start]+'px';spacer.setAttribute('aria-hidden','true');fragment.append(spacer);let date=start?new Date(rows[start-1].created_at).toLocaleDateString('fr'):'';
      for (const row of rows.slice(start,end)) {
        const slot=el('div');slot.dataset.slot=row.id;
        const day = new Date(row.created_at).toLocaleDateString('fr');
        if (day !== date) { slot.append(el('p', day, 'mk-message-date')); date = day; }
        const bubble = el('article', null, 'mk-message'); bubble.dataset.own = row.own; bubble.id = `exchange-${this.point}-${row.id}`;
        const author=el('small',row.own?'Vous':row.author?.label);hoverCard(author,[row.author?.label,row.represented_space?.label]);author.tabIndex=0;author.title=row.represented_space?.label||row.author?.label||'Vous';bubble.append(author);
        const previous=rows[rows.indexOf(row)-1];if(previous&&previous.author?.id===row.author?.id&&new Date(row.created_at)-new Date(previous.created_at)<300000&&new Date(row.created_at).toDateString()===new Date(previous.created_at).toDateString())author.hidden=true;
        if (row.represented_space) bubble.append(el('small', row.represented_space.label));
        if (row.reply_to) { const quote = el('blockquote', row.reply_to.available===false?'Message indisponible':row.reply_to.removed ? 'Message supprimé' : row.reply_to.body); quote.tabIndex = 0; quote.title = 'Rejoindre le message cité'; const jump = () => {if(row.reply_to.available!==false)this.jump(row.reply_to.id);}; quote.onclick = jump; quote.onkeydown = e => { if (e.key === 'Enter') jump(); }; bubble.append(quote); }
        bubble.append(el('p', row.removed ? 'Message supprimé' : row.body));
        for (const mention of row.mentions || []) bubble.append(el('small', '@' + mention.label));
        for (const file of row.attachments || []) {
          const path = safePath(file.download_path); if (!path) continue;
          if (file.kind === 'image') { const image = el('img'); image.src = path; image.alt = file.name; image.loading = 'lazy'; bubble.append(image); }
          if (['voice', 'audio'].includes(file.kind)) { const audio = el('audio'); audio.controls = true; audio.preload = 'none'; audio.src = path; bubble.append(audio); }
          const link = el('a', `${file.name} · ${Math.ceil(file.size/1024)} Ko`); link.href = path; link.target = '_blank'; link.rel = 'noopener'; link.title = file.mime_type;hoverCard(link,[file.name,file.mime_type,Math.ceil(file.size/1024)+' Ko']); bubble.append(link);
        }
        for (const reference of row.references || []) bubble.append(reference.available?button(reference.label,()=>this.openReference(reference.id)):el('small','Référence inaccessible'));
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
        slot.append(bubble);fragment.append(slot);
      }
      const tail=el('div');tail.style.height=(prefix.at(-1)-prefix[end])+'px';tail.setAttribute('aria-hidden','true');fragment.append(tail);this.resizeObserver.disconnect();if(!rows.length)fragment.append(el('p',this.historyLoaded?'Aucun message pour le moment.':'Chargement…'));this.log.replaceChildren(fragment);
      for(const node of this.log.querySelectorAll('[data-slot]'))this.resizeObserver.observe(node);
      for(const node of this.log.querySelectorAll('[data-slot]'))this.rowHeights.set(node.dataset.slot,node.getBoundingClientRect().height);
      const restored=[...this.log.querySelectorAll('[data-slot]')].find(node=>node.dataset.slot===anchorId);if(restored)this.log.scrollTop+=restored.getBoundingClientRect().top-this.log.getBoundingClientRect().top-anchorOffset;
      if(this.highlightId){const node=this.log.querySelector(`#exchange-${this.point}-${this.highlightId}`);node?.classList.add('mk-message-highlight');}
      if (focused) [...this.log.querySelectorAll('[data-message-action]')].find(n => n.dataset.messageAction === focused)?.focus({preventScroll:true});
    }
    async receipts() {
      if (!this.point || this.destroyed || this.revoked) return;
      try { const result = await request(`points/${this.point}/receipts/`);this.readSequence=result.read_sequence||0; for (const state of result.entries || []) { const row = this.rows.get(state.id); if (row) this.rows.set(row.id, {...row,delivery:state.delivery}); } const top=this.log.scrollTop; this.render();this.log.scrollTop=top; }
      catch(error) { this.failure(error); }
    }
    async mutate(path, method, body) { try { const result = await request(path, method, body); if (result.entry) this.rows.set(result.entry.id, result.entry); this.render(); await this.sync(); return true; } catch (error) { this.failure(error); return false; } }
    async send() {
      if (this.busy || !this.point || (!this.input.value.trim() && !this.file && !this.links.length)) return;
      this.busy = true;this.select.disabled=true; this.submit.disabled = true;
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
      } catch (error) { this.failure(error); } finally { this.busy = false;this.select.disabled=false; this.submit.disabled = false; }
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
    async find(append=false) {
      const query=this.search.value.trim();if(query.length<2){this.searchResults.replaceChildren();this.moreSearch.hidden=true;return;}
      const generation=this.searchGeneration=(this.searchGeneration||0)+1;
      try{const page=await request(`points/${this.point}/entries/search/?q=${encodeURIComponent(query)}${append&&this.searchCursor?'&cursor='+this.searchCursor:''}`);if(generation!==this.searchGeneration||this.search.value.trim()!==query)return;
        if(!append){this.searchResults.replaceChildren();this.searchSeen=new Set();}for(const row of page.results){if(this.searchSeen.has(row.id))continue;this.searchSeen.add(row.id);this.searchResults.append(button(row.body.slice(0,120),()=>this.jump(row.id)));}
        this.searchCursor=page.next_cursor;this.moreSearch.hidden=!page.next_cursor;this.status.textContent='Résultats serveur actualisés';
      }catch(error){this.failure(error);}
    }
    async materialize(page) {
      if(!Array.isArray(page.results))throw new Error('Réponse de synchronisation invalide.');
      for(const row of page.results){if(row.point_id!==this.point||!Number.isSafeInteger(row.sequence))throw new Error('Portée de message invalide.');const prior=this.rows.get(row.id);if(!prior||prior.last_change_version<=row.last_change_version)this.rows.set(row.id,row);}
      try{await window.MakoloExchangeCache?.commit(profile,this.point,page.scope,page.results,page.next_version??this.version);}
      catch{this.status.textContent='Cache non confirmé · Aucun reçu de livraison émis';}
    }
    async confirmDelivered(){
      const rows=[...this.rows.values()];if(!rows.length)return;
      try{const cache=window.MakoloExchangeCache;if(!cache)return;let durable;if(await cache.complete(profile,this.point,this.scope,this.version))durable=!!(await navigator.storage?.persisted?.());else durable=await cache.commit(profile,this.point,this.scope,rows,this.version,true);if(!durable)return;
        const sequence=rows.reduce((maximum,row)=>Math.max(maximum,row.sequence),0);if(sequence<=this.durableSequence)return;await request(`points/${this.point}/receipts/`,'POST',{delivered_sequence:sequence,read_sequence:0});this.durableSequence=sequence;
      }catch{this.status.textContent='Cache non confirmé · Aucun reçu de livraison émis';}
    }

    async confirmRead() {
      if(this.receiptBusy||!this.userReading||document.hidden||this.minimized||this.revoked||!this.durableSequence||!this.root.offsetParent)return;
      const bounds=this.log.getBoundingClientRect();const visible=new Set([...this.log.querySelectorAll('[data-slot]')].filter(node=>{const box=node.getBoundingClientRect();return box.top>=bounds.top&&box.bottom<=bounds.bottom;}).map(node=>node.dataset.slot));
      let sequence=this.readSequence;for(const row of [...this.rows.values()].sort((a,b)=>a.sequence-b.sequence)){if(row.sequence<=sequence)continue;if(row.sequence>this.durableSequence)break;if(!row.own&&!row.removed&&!visible.has(row.id))break;sequence=row.sequence;}
      if(sequence<=this.readSequence)return;this.receiptBusy=true;
      try{const receipt=await request(`points/${this.point}/receipts/`,'POST',{delivered_sequence:this.durableSequence,read_sequence:sequence});this.readSequence=receipt.read_sequence;scheduleList();}catch(error){this.failure(error);}finally{this.receiptBusy=false;}
    }
    async jump(id) {
      this.userReading=false;
      try{const page=await request(`entries/${id}/`);if(page.point_id!==this.point||page.target_id!==id||!Array.isArray(page.results))throw new Error('Message inaccessible.');
        if(this.scope&&page.scope!==this.scope){this.rows.clear();this.version=0;}this.scope=page.scope;await this.materialize(page);this.before=page.before_sequence;this.older.hidden=!page.has_more;
        const rows=[...this.rows.values()].sort((a,b)=>a.sequence-b.sequence);const index=rows.findIndex(row=>row.id===id);let offset=0;for(const row of rows.slice(0,index))offset+=this.rowHeights.get(row.id)||150;
        this.highlightId=id;this.lastRender=null;this.log.scrollTop=offset;this.render();this.log.querySelector(`#exchange-${this.point}-${id}`)?.scrollIntoView({block:'center',behavior:'instant'});setTimeout(()=>{this.highlightId=null;this.root.querySelectorAll('.mk-message-highlight').forEach(n=>n.classList.remove('mk-message-highlight'));},2000);
      }catch(error){this.status.textContent=[403,404].includes(error.status)?'Message indisponible.':error.message;}
    }
    async openReference(id) {
      try{const ref=await request(`references/${id}/`);const dialog=el('dialog',null,'mk-reference-dialog');dialog.append(el('h2',ref.label),el('p',ref.description||''),el('p',[ref.state_label,ref.version?'Version '+ref.version:'',ref.mode_label,ref.mime_type].filter(Boolean).join(' · ')));
        if(ref.view_url){const link=el('a','Ouvrir le document');link.href=safePath(ref.view_url);link.target='_blank';link.rel='noopener';dialog.append(link);}
        if(ref.can_download)dialog.append(button('Télécharger',()=>{if(!ref.export_warning||confirm('Ce document peut contenir des données personnelles. Confirmer l’export ?'))window.open(safePath(ref.download_url)+'&confirm=1','_blank','noopener');}));
        dialog.append(button('Fermer',()=>dialog.close()));dialog.addEventListener('close',()=>{dialog.remove();this.input.focus();},{once:true});this.root.append(dialog);dialog.showModal();
      }catch{this.status.textContent='Référence inaccessible.';}
    }

    ephemeral(data) { clearTimeout(this.ephemeralTimer); this.status.textContent = data.type === 'typing_changed' ? 'Une personne écrit…' : 'Actif dans cette discussion'; this.ephemeralTimer = setTimeout(() => { this.status.textContent = ''; }, data.ttl * 1000); }
    dispose() { this.saveDraft(); this.destroyed = true; views.delete(this);if(![...views].some(v=>v.conversation===this.conversation))realtime.sendConversation('unsubscribe',this.conversation); if (![...views].some(v => v.point === this.point)) realtime.send('unsubscribe',this.point); clearTimeout(this.ephemeralTimer); this.resizeObserver.disconnect();cancelAnimationFrame(this.renderFrame);this.upload?.abort();this.voiceCancelled=true;if(this.recorder?.state==='recording')this.recorder.stop();if(this.voicePreviewUrl)URL.revokeObjectURL(this.voicePreviewUrl); this.root.remove(); }
  }
  function open(conversation, title, point, container) {
    if (container) { for (const view of views) if (view.root.parentElement === container) view.dispose(); return new ExchangeView(container,conversation,title,null,point); }
    if (floating.has(conversation)) { const view=floating.get(conversation); view.minimized=false; view.root.dataset.minimized=false; windows.append(view.root); view.input.focus(); return view; }
    if (floating.size >= 3) { panel.querySelector('[role=status]').textContent='Trois discussions sont ouvertes. Fermez-en une pour continuer.'; panel.hidden=false; return; }
    const view = new ExchangeView(windows,conversation,title,()=>floating.delete(conversation),point); floating.set(conversation,view); panel.hidden=true; launch.setAttribute('aria-expanded','false'); return view;
  }
  async function list(query='') {
    if(listRunning){listAgain=true;return;}listRunning=true;const status=panel.querySelector('[role=status]');
    try{const page=await request('?limit=50&q='+encodeURIComponent(query));const filter=panel.querySelector('[data-discussion-filter]').value;
      let pageRows=[];const pageList=document.querySelector('[data-messaging-live-list]');if(pageList){const owned=await request('?limit=50&'+new URLSearchParams(location.search));const pageFilter=document.querySelector('[data-messaging-page-filter]')?.value||'all';pageRows=owned.results.filter(row=>pageFilter==='all'||pageFilter==='unread'&&row.unread_count>0||pageFilter==='groups'&&row.group_discussion);document.querySelector('[data-messaging-fallback]')?.setAttribute('hidden','');}
      const rows=page.results.filter(row=>filter==='all'||filter==='unread'&&row.unread_count>0||filter==='groups'&&row.group_discussion);
      rows.sort((a,b)=>Number(b.personal_state?.pinned)-Number(a.personal_state?.pinned)||new Date(b.last_message?.created_at||b.updated_at)-new Date(a.last_message?.created_at||a.updated_at));
      for(const list of [panel.querySelector('[data-discussion-list]'),document.querySelector('[data-messaging-live-list]')].filter(Boolean)){
        const focus=document.activeElement?.dataset?.conversation;list.replaceChildren();for(const row of (list.hasAttribute('data-messaging-live-list')?pageRows:rows)){const b=button('',()=>open(row.id,row.title,row.last_message?.point_id,list.closest('[data-messaging-live-list]')?document.querySelector('[data-messaging-page]'):null));b.dataset.conversation=row.id;b.className='mk-messaging-row';b.append(el('strong',row.title));if(row.attention_count)b.append(el('small',row.attention_count+' à traiter'));if(row.unread_count)b.append(el('small',row.unread_count+' non lu(s)'));if(row.last_message)b.append(el('p',row.last_message.removed?'Message supprimé':row.last_message.body),el('small',new Date(row.last_message.created_at).toLocaleString('fr')));if(row.personal_state?.pinned)b.append(el('small','Épinglée'));if(row.personal_state?.muted)b.append(el('small','Sourdine'));list.append(b);}if(focus)[...list.querySelectorAll('[data-conversation]')].find(n=>n.dataset.conversation===focus)?.focus({preventScroll:true});
      }status.textContent=rows.length?'':'Aucune discussion accessible.';
    }catch(error){status.textContent=error.message;if([401,403].includes(error.status)){for(const view of views)view.revoke();}}
    finally{listRunning=false;if(listAgain){listAgain=false;scheduleList();}}
  }

  document.addEventListener('change',event=>{if(event.target.matches('[data-messaging-page-filter]'))scheduleList();});
  panel.querySelector('[data-discussion-filter]').onchange=()=>scheduleList();
  launch.onclick=()=>{window.MakoloExchangeCache?.persist();panel.hidden=!panel.hidden;launch.setAttribute('aria-expanded',String(!panel.hidden));if(!panel.hidden){list();panel.querySelector('input').focus();}};
  panel.querySelector('[data-panel-close]').onclick=()=>{panel.hidden=true;launch.setAttribute('aria-expanded','false');launch.focus();};
  panel.querySelector('form').onsubmit=event=>{event.preventDefault();list(panel.querySelector('input').value);};
  function mount() {
    for(const view of [...views]) if(!view.root.isConnected) view.dispose();
    document.querySelectorAll('[data-exchange-page]:not([data-messaging-mounted])').forEach(node=>{node.dataset.messagingMounted='true';open(node.dataset.conversation,node.dataset.title,node.dataset.point,node);});
  }
  document.addEventListener('click',event=>{const link=event.target.closest('[data-messaging-conversation]');if(!link||event.ctrlKey||event.metaKey||event.shiftKey)return;const container=document.querySelector('[data-messaging-page]');if(container){event.preventDefault();open(link.dataset.messagingConversation,link.textContent.trim(),null,container);container.scrollIntoView({block:'nearest'});}});
  document.addEventListener('htmx:afterSwap',()=>{mount();scheduleList();});document.addEventListener('visibilitychange',()=>{if(!document.hidden){for(const view of views)view.sync();realtime.connect();}});
  window.MakoloMessaging={open};mount();realtime.connect();scheduleList();
})();
