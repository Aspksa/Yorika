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

// Appearance lives in this browser only; appearance.js applies it on every page.
const look=window.YorikaAppearance;
const lookKeys=["theme","accent","radius","size"];
const showLook=s=>lookKeys.forEach(key=>select("look-"+key,s[key]));
if(look){
 showLook(look.read());
 lookKeys.forEach(key=>radios("look-"+key).forEach(input=>input.onchange=()=>look.save({...look.read(),[key]:input.value})));
 el("reset-look").onclick=()=>{look.save({...look.defaults});showLook(look.defaults)};
}

// Avatar pictures, choice and size live in this browser; avatar.js shows them on every page.
const avatar=window.YorikaAvatar;
const MAX_PICTURES=50,MAX_SIDE=360;
const avatarStatus=text=>{el("avatar-status").textContent=text};
function saveAvatar(v){
 try{avatar.write(v);return true}
 catch{avatarStatus("Не хватает места в хранилище браузера. Удалите одну из загруженных картинок.");return false}
}
function showAvatars(){
 const v=avatar.read(),list=el("avatar-list");
 const card=(id,src,name,removable)=>{
  const label=document.createElement("label");label.className="avatar-choice";
  const input=document.createElement("input");input.type="radio";input.name="avatar-pick";input.value=id;input.checked=v.selected===id;
  input.onchange=()=>{saveAvatar({...avatar.read(),selected:id});avatarStatus("")};
  const box=document.createElement("span");
  const img=document.createElement("img");img.src=src;img.alt="";img.loading="lazy";
  const caption=document.createElement("small");caption.textContent=name;
  box.append(img,caption);label.append(input,box);
  if(removable){
   const del=document.createElement("button");del.type="button";del.className="avatar-remove";del.textContent="×";
   del.title="Удалить картинку";del.setAttribute("aria-label","Удалить картинку "+name);
   del.onclick=e=>{e.preventDefault();const now=avatar.read();saveAvatar({...now,items:now.items.filter(i=>i.id!==id)});showAvatars();avatarStatus("Картинка удалена")};
   label.append(del);
  }
  return label;
 };
 list.replaceChildren(card("default",avatar.defaultSrc,"Yorika",false),...v.items.map(i=>card(i.id,i.src,i.name||"Своя",true)));
 el("avatar-size").value=v.size;el("avatar-size-value").textContent=v.size+" px";
}
// Pictures are scaled down before saving so fifty of them fit in browser storage.
function shrink(file){
 return new Promise((resolve,reject)=>{
  const url=URL.createObjectURL(file),img=new Image();
  img.onload=()=>{
   const k=Math.min(1,MAX_SIDE/Math.max(img.naturalWidth,img.naturalHeight));
   const canvas=document.createElement("canvas");canvas.width=Math.max(1,Math.round(img.naturalWidth*k));canvas.height=Math.max(1,Math.round(img.naturalHeight*k));
   canvas.getContext("2d").drawImage(img,0,0,canvas.width,canvas.height);URL.revokeObjectURL(url);
   let data=canvas.toDataURL("image/webp",0.82);
   if(!data.startsWith("data:image/webp"))data=canvas.toDataURL("image/png");
   resolve(data);
  };
  img.onerror=()=>{URL.revokeObjectURL(url);reject(Error("не удалось прочитать картинку"))};
  img.src=url;
 });
}
if(avatar){
 el("avatar-size").min=avatar.size.min;el("avatar-size").max=avatar.size.max;
 el("avatar-size").oninput=e=>{const size=Number(e.target.value);el("avatar-size-value").textContent=size+" px";saveAvatar({...avatar.read(),size})};
 el("avatar-file").onchange=async e=>{
  const files=[...e.target.files];e.target.value="";
  let added=0,lastId=null,full=false;
  for(const file of files){
   const now=avatar.read();
   if(now.items.length>=MAX_PICTURES){full=true;break}
   try{
    const src=await shrink(file),id="a"+Date.now().toString(36)+Math.random().toString(36).slice(2,6);
    const name=file.name.replace(/\.[^.]+$/,"").slice(0,40)||"Своя";
    if(!saveAvatar({...now,items:[...now.items,{id,name,src}],selected:id}))break;
    added++;lastId=id;
   }catch(err){avatarStatus(`${file.name}: ${err.message}`)}
  }
  showAvatars();
  const limit=full?`Можно хранить до ${MAX_PICTURES} картинок. Удалите лишние, чтобы добавить новые.`:"";
  if(added)avatarStatus((added===1?"Картинка загружена и выбрана.":`Загружено картинок: ${added}, выбрана последняя.`)+(limit?" "+limit:""));
  else if(limit)avatarStatus(limit);
  if(lastId)document.querySelector(`input[name="avatar-pick"][value="${lastId}"]`)?.focus();
 };
 el("reset-avatar").onclick=()=>{saveAvatar({...avatar.read(),selected:"default",size:avatar.size.def});showAvatars();avatarStatus("")};
 window.addEventListener("storage",e=>{if(e.key==="yorika.avatars")showAvatars()});
 showAvatars();
}else document.querySelector(".avatar-panel").hidden=true;

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
