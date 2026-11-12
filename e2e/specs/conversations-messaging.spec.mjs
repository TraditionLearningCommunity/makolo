import { test, expect } from '../fixtures/makolo.mjs';
import { login } from '../helpers/auth.mjs';

// UI contract fixtures are test-only. Django's Exchange tests exercise the real
// owner/ACL/transaction services independently; nothing is mocked in runtime.
const ids = [1,2,3].map(i => `00000000-0000-4000-8000-00000000000${i}`);
const points = [1,2,3].map(i => `10000000-0000-4000-8000-00000000000${i}`);

async function messagingOwner(page, { loseFirstAck = false } = {}) {
  const rows = new Map(points.map(point => [point, []]));
  const references = [];
  let revoked = false, lost = false;
  await page.route('**/api/v1/conversations/**', async route => {
    const request = route.request(), url = new URL(request.url());
    const path = url.pathname.replace('/api/v1/conversations/', '');
    const reply = (body, status=200) => route.fulfill({status, contentType:'application/json', body:JSON.stringify(body)});
    if (path === 'realtime-ticket/') return reply({available:false},503);
    if (!path) return reply({results:ids.map((id,i)=>({id,title:`Discussion ${i+1}`}))});
    const conversationIndex = ids.indexOf(path.slice(0,-1));
    if (conversationIndex >= 0) return reply({id:ids[conversationIndex],title:`Discussion ${conversationIndex+1}`,
      composer:{exchange_targets:[{id:points[conversationIndex],title:'Coordination'}],media_kinds:[]},points:[],essential:[],elsewhere:[],timeline:[]});
    const point = path.split('/')[1];
    if (revoked && path.startsWith('points/')) return reply({detail:'inaccessible'},404);
    if (path.endsWith('/receipts/')) return reply({delivered_sequence:0,read_sequence:0,entries:[]});
    if (path.endsWith('/entries/sync/')) {
      const after = Number(url.searchParams.get('after_version') || 0);
      return reply({scope:'scope-a',point_id:point,stream_version:rows.get(point).length,
        results:rows.get(point).filter(row=>row.last_change_version>after),next_version:rows.get(point).length,has_more:false});
    }
    if (path.endsWith('/entries/') && request.method() === 'GET') return reply({scope:'scope-a',results:rows.get(point),has_more:false,before_sequence:null});
    if (path.endsWith('/entries/') && request.method() === 'POST') {
      const data = request.postDataJSON(); references.push(data.client_reference);
      let entry = rows.get(point).find(row=>row.client_reference===data.client_reference);
      if (!entry) {
        const sequence=rows.get(point).length+1;
        entry={id:`20000000-0000-4000-8000-${String(sequence).padStart(12,'0')}`,point_id:point,sequence,last_change_version:sequence,
          body:data.body,own:true,removed:false,edit_version:1,created_at:'2026-11-12T10:00:00Z',author:{id:'self',label:'Vous'},
          client_reference:data.client_reference,attachments:[],references:[],mentions:[],reactions:[],capabilities:{reply:true,edit:true,delete:true,react:true}};
        rows.get(point).push(entry);
      }
      if(loseFirstAck&&!lost){lost=true;return route.abort('failed');}
      return reply({status:'confirmed',entry_id:entry.id,point_id:point,sequence:entry.sequence,entry});
    }
    return reply({detail:'unexpected test route'},400);
  });
  return {rows,references,revoke:()=>{revoked=true;}};
}

async function openDiscussion(page, index=0) {
  await page.locator('.mk-messaging-launch').click();
  await page.locator('#mk-messaging-panel').getByRole('button',{name:`Discussion ${index+1}`,exact:true}).click();
  const window=page.locator('.mk-messaging-windows .mk-exchange-window').nth(index);
  await expect(window.getByRole('textbox',{name:'Message',exact:true})).toBeVisible();
  return window;
}

test('global panel opens three independent windows and restores a minimized discussion',async({page})=>{
  await login(page,'owner@e2e.makolo.test');await messagingOwner(page);
  for(let index=0;index<3;index++)await openDiscussion(page,index);
  await expect(page.locator('.mk-messaging-windows .mk-exchange-window')).toHaveCount(3);
  const first=page.locator('.mk-messaging-windows .mk-exchange-window').first();
  await first.getByRole('button',{name:'Réduire ou restaurer la discussion'}).click();
  await expect(first).toHaveAttribute('data-minimized','true');
  await first.getByRole('button',{name:'Réduire ou restaurer la discussion'}).click();
  await expect(first.getByRole('textbox',{name:'Message',exact:true})).toBeVisible();
});

test('floating window and draft survive a real HTMX page swap',async({page})=>{
  await login(page,'owner@e2e.makolo.test');await messagingOwner(page);
  const window=await openDiscussion(page);
  await window.getByRole('textbox',{name:'Message',exact:true}).fill('Brouillon conservé');
  await page.evaluate(()=>window.htmx.ajax('GET','/conversations/',{target:'#main-content',select:'#main-content',swap:'outerHTML'}));
  await expect(window.getByRole('textbox',{name:'Message',exact:true})).toHaveValue('Brouillon conservé');
  await expect(page.locator('#mk-messaging-host')).toHaveCount(1);
});

test('lost ACK keeps the draft and reuses the same intention without a duplicate bubble',async({page})=>{
  await login(page,'owner@e2e.makolo.test');const owner=await messagingOwner(page,{loseFirstAck:true});
  const window=await openDiscussion(page),input=window.getByRole('textbox',{name:'Message',exact:true});
  await input.fill('Message fiable');await window.getByRole('button',{name:'Envoyer',exact:true}).click();
  await expect(input).toHaveValue('Message fiable');
  await expect(window.getByRole('button',{name:'Envoyer',exact:true})).toBeEnabled();
  await window.getByRole('button',{name:'Envoyer',exact:true}).click();
  await expect(input).toHaveValue('');
  await expect(window.locator('.mk-message')).toHaveCount(1);
  expect(owner.references).toHaveLength(2);expect(owner.references[0]).toBe(owner.references[1]);
  expect(owner.rows.get(points[0])).toHaveLength(1);
});

test('revocation removes visible private history and disables the composer',async({page})=>{
  await login(page,'owner@e2e.makolo.test');const owner=await messagingOwner(page);
  const window=await openDiscussion(page);
  await window.getByRole('textbox',{name:'Message',exact:true}).fill('Privé');
  await window.getByRole('button',{name:'Envoyer',exact:true}).click();await expect(window.locator('.mk-message')).toHaveCount(1);
  owner.revoke();await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
  await expect(window.locator('.mk-message')).toHaveCount(0);
  await expect(window.getByRole('textbox',{name:'Message',exact:true})).toBeHidden();
});

test('narrow screens show one active window and stay inside the viewport @mobile',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await login(page,'owner@e2e.makolo.test');await messagingOwner(page);
  await openDiscussion(page,0);await openDiscussion(page,1);
  const windows=page.locator('.mk-messaging-windows .mk-exchange-window');
  await expect(windows.first()).toBeHidden();await expect(windows.last()).toBeVisible();
  const box=await windows.last().boundingBox();expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(390);
});
