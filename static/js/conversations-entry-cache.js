/* A committed IndexedDB page is a cache fact, never an authorization grant. */
(() => {
  'use strict';
  let opening;
  function database() {
    return opening ||= new Promise((resolve,reject)=>{
      const request=indexedDB.open('makolo-exchange-cache',1);
      request.onupgradeneeded=()=>{const db=request.result;db.createObjectStore('streams',{keyPath:'key'});const rows=db.createObjectStore('entries',{keyPath:'key'});rows.createIndex('owner','owner');};
      request.onsuccess=()=>resolve(request.result);request.onerror=()=>{opening=null;reject(new Error('Cache indisponible'));};
      request.onblocked=()=>reject(new Error('Cache occupé'));
    });
  }
  async function transaction(owner,scope,rows,version,purge=false,complete=false) {
    const db=await database();
    return new Promise((resolve,reject)=>{
      let tx;try{tx=db.transaction(['streams','entries'],'readwrite',{durability:'strict'});}catch{tx=db.transaction(['streams','entries'],'readwrite');}
      const streams=tx.objectStore('streams'),entries=tx.objectStore('entries');
      const prior=streams.get(owner);
      prior.onsuccess=()=>{
        function write(){
          if(purge){streams.delete(owner);return;}
          for(const row of rows){
            if(typeof row.id!=='string'||!Number.isSafeInteger(row.sequence)||!Number.isSafeInteger(row.last_change_version)){tx.abort();return;}
            const key=owner+':'+row.id,previous=entries.get(key);
            previous.onsuccess=()=>{if(!previous.result || previous.result.row.last_change_version<=row.last_change_version)entries.put({key,owner,row});};
          }
          streams.put({key:owner,scope,version,complete:complete||!!(prior.result?.scope===scope&&prior.result?.complete)});
        }
        if(purge || (prior.result && prior.result.scope!==scope)){
          const cursor=entries.index('owner').openCursor(IDBKeyRange.only(owner));cursor.onsuccess=()=>{if(cursor.result){cursor.result.delete();cursor.result.continue();}else write();};
        }else write();
      };
      tx.oncomplete=()=>resolve();tx.onerror=tx.onabort=()=>reject(new Error('Cache non confirmé'));
    });
  }
  window.MakoloExchangeCache={
    async persist(){try{return !!(await navigator.storage?.persist?.());}catch{return false;}},
    async commit(profile,point,scope,rows,version,complete=false){await transaction(`${profile}:${point}`,scope,rows,version,false,complete);return !!(await navigator.storage?.persisted?.());},
    async complete(profile,point,scope,version){const db=await database();return new Promise((resolve,reject)=>{const request=db.transaction('streams').objectStore('streams').get(`${profile}:${point}`);request.onsuccess=()=>resolve(!!(request.result?.scope===scope&&request.result?.version===version&&request.result?.complete));request.onerror=()=>reject(new Error('Cache indisponible'));});},
    purge(profile,point){return transaction(`${profile}:${point}`,'',[],0,true);},
  };
})();
