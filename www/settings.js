import { api } from "./api.js";
import { Database } from "./core/database.js";
const el=id=>document.getElementById(id);
const radios=name=>[...document.querySelectorAll(`input[name="${name}"]`)];
const value=name=>radios(name).find(input=>input.checked)?.value;
const select=(name,v)=>radios(name).forEach(input=>{input.checked=input.value===String(v)});
const storeNames={settings:"Настройки",projects:"Проекты",memories:"Память",conversations:"Диалоги",messages:"Сообщения",tasks:"Задачи"};
let db=null;

// Same server-side settings as updates.html, so both pages always show one value.
async function saveUpdates(){
 el("updates-status").textContent="Сохранение…";
 try{await api("/api/updates/settings",{method:"POST",body:JSON.stringify({channel:value("update-channel"),interval:Number(value("update-interval"))})});el("updates-status").textContent="Сохранено"}
 catch(e){el("updates-status").textContent="Не удалось сохранить: "+e.message}
}
radios("update-channel").forEach(input=>input.onchange=saveUpdates);
radios("update-interval").forEach(input=>input.onchange=saveUpdates);

el("local-address").value=location.origin+"/";
el("copy-address").onclick=async()=>{
 try{await navigator.clipboard.writeText(el("local-address").value);el("copy-status").textContent="Адрес скопирован"}
 catch{el("local-address").select();el("copy-status").textContent="Не удалось скопировать автоматически, адрес выделен"}
};

async function showStores(){
 const list=el("store-list");
 const counts=await Promise.all(Database.stores.map(async name=>[name,(await db.all(name)).length]));
 list.replaceChildren(...counts.map(([name,count])=>{const li=document.createElement("li");li.append(storeNames[name]||name);const b=document.createElement("b");b.textContent=count;li.append(b);return li}));
 el("clear-data").disabled=counts.every(([,count])=>count===0);
}
el("clear-data").onclick=async()=>{
 if(!confirm("Удалить все данные Yorika из этого браузера для текущего адреса? Настройки обновлений и токен на компьютере не затрагиваются."))return;
 el("clear-data").disabled=true;
 try{for(const name of Database.stores)await db.clear(name);el("data-status").textContent="Данные браузера очищены";await showStores()}
 catch(e){el("data-status").textContent="Не удалось очистить: "+e.message;el("clear-data").disabled=false}
};

(async()=>{
 try{
  const r=await api("/api/updates/settings");
  select("update-channel",r.channel);select("update-interval",r.interval);
  el("updates-status").textContent="";
  el("token-state").textContent=r.hasToken?"Сохранён на компьютере":"Не задан (нужен только для приватного репозитория)";
 }catch(e){
  el("updates-status").textContent="Нет связи с Yorika: "+e.message;el("token-state").textContent="Неизвестно";
  radios("update-channel").concat(radios("update-interval")).forEach(input=>input.disabled=true);
 }
})();
(async()=>{
 try{db=await Database.open();await showStores()}
 catch(e){const li=document.createElement("li");li.className="store-empty";li.textContent="Хранилище недоступно: "+e.message;el("store-list").replaceChildren(li)}
})();
