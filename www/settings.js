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
 el("export-data").disabled=counts.every(([,count])=>count===0);
}
el("export-data").onclick=async()=>{
 const button=el("export-data");button.disabled=true;
 try{
  // Download from this origin only. No cloud upload and no destructive operation.
  const stores={};
  for(const name of Database.stores)stores[name]=await db.all(name);
  const backup={format:"yorika-browser-data-v1",exported_at:new Date().toISOString(),origin:location.origin,stores};
  const json=JSON.stringify(backup,null,2);
  const blob=new Blob([json],{type:"application/json;charset=utf-8"});
  const url=URL.createObjectURL(blob);
  try{
   const link=document.createElement("a");
   link.href=url;link.download="yorika-browser-backup-"+new Date().toISOString().slice(0,10)+".json";
   document.body.append(link);link.click();link.remove();
  }finally{setTimeout(()=>URL.revokeObjectURL(url),60000)}
  el("data-status").textContent="Копия подготовлена для скачивания. Храните файл в безопасном месте: он может содержать личные данные.";
 }catch(e){el("data-status").textContent="Ошибка экспорта: "+e.message}
 finally{button.disabled=false}
};
// Browser restore accepts both export formats. No server upload or implicit overwrite.
let stagedImport=null;
el("import-data-file").onchange=async event=>{
 stagedImport=null;
 el("import-preview").hidden=true;
 const file=event.target.files?.[0];event.target.value="";
 if(!file)return;
 try{
  if(file.size>50*1024*1024)throw Error("Файл больше 50 МиБ");
  const backup=JSON.parse(await file.text());
  const report=await db.restoreSnapshot(backup,{dryRun:true});
  stagedImport=backup;
  const other=backup.origin&&backup.origin!==location.origin;
  el("import-summary").textContent=`Записей: ${report.records}; разделов: ${report.stores}.`+
   (other?` Исходный адрес ${backup.origin} отличается от текущего ${location.origin}. Данные старого порта будут скопированы в текущий.`:"")+
   " Существующие записи не заменяются; при конфликте восстановление целиком отменится.";
  el("import-preview").hidden=false;
  el("data-status").textContent="Файл проверен. Данные пока не изменены.";
 }catch(e){el("data-status").textContent="Ошибка проверки копии: "+e.message}
};
el("apply-import").onclick=async()=>{
 if(!stagedImport||!db)return;
 if(!confirm("Восстановить записи из копии в текущий браузер? При конфликте всё восстановление будет отменено."))return;
 const button=el("apply-import");button.disabled=true;
 try{
  const report=await db.restoreSnapshot(stagedImport,{dryRun:false});
  el("data-status").textContent=`Восстановлено записей: ${report.applied}. Перезагрузите страницу, чтобы увидеть данные.`;
  el("import-preview").hidden=true;stagedImport=null;
  await showStores();
 }catch(e){el("data-status").textContent="Не удалось восстановить: "+e.message}
 finally{button.disabled=false}
};
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
  el("token-state").textContent=r.hasToken?"Сохранён на компьютере":"Не нужен для публичного репозитория";
 }catch(e){
  el("updates-status").textContent="Нет связи с Yorika: "+e.message;el("token-state").textContent="Неизвестно";
  radios("update-channel").concat(radios("update-interval")).forEach(input=>input.disabled=true);
 }
})();
(async()=>{
 try{db=await Database.open();await showStores()}
 catch(e){const li=document.createElement("li");li.className="store-empty";li.textContent="Хранилище недоступно: "+e.message;el("store-list").replaceChildren(li)}
})();

// The pill in the panel header tells at a glance whether the avatar chat can answer.
function cloudPill(state,text){const pill=el("cloud-ru-pill");pill.dataset.state=state;pill.textContent=text}
async function cloudStatus(prefix=""){
 const result=await api("/api/cloud-ru/status");
 el("cloud-ru-model").value=result.model;savedModel=result.model;
 const picker=el("cloud-ru-model-select");if([...picker.options].some(o=>o.value===result.model))picker.value=result.model;
 el("cloud-ru-status").textContent=prefix+(result.configured?"Ключ зашифрован и сохранён на этом компьютере. Чат аватара отвечает через модель "+result.model+".":"Ключ пока не сохранён, поэтому чат аватара не может ответить. Вставьте API-ключ Cloud.ru и нажмите «Сохранить ключ и модель».");
 cloudPill(result.configured?"ready":"off",result.configured?"Ключ сохранён":"Не подключена");
}
el("cloud-ru-models-refresh").onclick=async()=>{
 const button=el("cloud-ru-models-refresh");button.disabled=true;
 el("cloud-ru-status").textContent="Загрузка моделей Cloud.ru…";
 try{
  const result=await api("/api/cloud-ru/models");
  const list=el("cloud-ru-model-suggestions");
  list.replaceChildren(...result.models.map(id=>{
   const option=document.createElement("option");option.value=id;option.textContent=id;return option;
  }));
  const picker=el("cloud-ru-model-select");
  const current=el("cloud-ru-model").value;
  picker.replaceChildren(...result.models.map(id=>{
   const option=document.createElement("option");option.value=id;option.textContent=id;return option;
  }));
  picker.disabled=result.models.length===0;
  if(result.models.includes(current))picker.value=current;
  else picker.selectedIndex=-1;
  el("cloud-ru-status").textContent="Доступно моделей: "+result.models.length+
    ". Выберите ID из списка и нажмите «Сохранить ключ и модель».";
 }catch(error){el("cloud-ru-status").textContent="Не удалось получить список моделей: "+error.message}
 finally{button.disabled=false}
};
// Picking a model saves it at once, like every other setting on this page; the key stays as stored.
let savedModel="";
el("cloud-ru-model-select").onchange=async event=>{
 const model=event.target.value;if(!model)return;
 el("cloud-ru-model").value=model;
 try{await api("/api/cloud-ru/save",{method:"POST",body:JSON.stringify({key:null,model})});await cloudStatus("Модель сохранена. ")}
 catch(error){el("cloud-ru-status").textContent="Не удалось сохранить модель: "+error.message}
};
el("cloud-ru-model").oninput=()=>{if(savedModel&&el("cloud-ru-model").value.trim()!==savedModel)el("cloud-ru-status").textContent="ID модели изменён, но ещё не сохранён. Сейчас чат использует "+savedModel+". Нажмите «Сохранить ключ и модель».";};
el("cloud-ru-form").onsubmit=async event=>{
 event.preventDefault();
 const key=el("cloud-ru-key").value,model=el("cloud-ru-model").value.trim();
 const button=el("cloud-ru-save");button.disabled=true;
 try{
  await api("/api/cloud-ru/save",{method:"POST",body:JSON.stringify({key:key||null,model})});
  el("cloud-ru-key").value="";
  await cloudStatus("Сохранено. ");
 }catch(error){el("cloud-ru-status").textContent="Не удалось сохранить настройки: "+error.message}
 finally{button.disabled=false}
};
el("cloud-ru-diagnostics").onclick=async()=>{
 const button=el("cloud-ru-diagnostics");button.disabled=true;
 try{
  const report=await api("/api/cloud-ru/diagnostics");
  el("cloud-ru-status").textContent=report.configured?
   "DPAPI: ключ доступен. Модель: "+report.model+". Для проверки авторизации нажмите «Проверить подключение».":
   "DPAPI: ключ не сохранён. Введите ключ Cloud.ru.";
 }catch(error){el("cloud-ru-status").textContent="Ошибка локальной диагностики: "+error.message}
 finally{button.disabled=false}
};
el("cloud-ru-check").onclick=async()=>{
 if(!confirm("Отправить короткий проверочный запрос в Cloud.ru? Запрос может тарифицироваться."))return;
 const button=el("cloud-ru-check");button.disabled=true;
 el("cloud-ru-status").textContent="Проверка Cloud.ru…";
 try{
  const result=await api("/api/cloud-ru/check",{method:"POST",body:"{}"});
  el("cloud-ru-status").textContent=result.connected?"Подключение работает. Модель: "+result.model:"Cloud.ru не подтвердил ответ.";
  if(result.connected)cloudPill("ok","Подключена");else cloudPill("error","Нет ответа");
 }catch(error){el("cloud-ru-status").textContent="Проверка не пройдена: "+error.message;cloudPill("error","Ошибка")}
 finally{button.disabled=false}
};
el("cloud-ru-delete").onclick=async()=>{
 if(!confirm("Удалить сохранённый ключ Cloud.ru с этого компьютера? На стороне Cloud.ru ключ останется действующим."))return;
 try{
  await api("/api/cloud-ru/delete",{method:"POST",body:"{}"});
  el("cloud-ru-key").value="";
  await cloudStatus("Ключ удалён с этого компьютера. ");
 }catch(error){el("cloud-ru-status").textContent="Ошибка удаления: "+error.message}
};
cloudStatus().catch(error=>{el("cloud-ru-status").textContent="Настройки Cloud.ru недоступны: "+error.message;cloudPill("error","Недоступна")});

async function refreshPersonaGrowth(){
 const report=await api("/api/cloud-ru/persona-status");
 el("persona-growth-enabled").checked=report.enabled;
 el("persona-growth-status").textContent="Сохранено новых реплик: "+report.count+"; различных слов: "+(report.vocabulary?.unique_words??0);
 const list=el("persona-growth-replies");
 list.replaceChildren(...report.replies.map(item=>{
  const li=document.createElement("li");
  const snippet=document.createElement("span");snippet.className="item-text";snippet.textContent=item.text.slice(0,180);
  const del=document.createElement("button");del.type="button";del.textContent="Удалить";del.className="ghost danger small";
  del.onclick=async()=>{del.disabled=true;try{
   await api("/api/cloud-ru/persona-delete",{method:"POST",body:JSON.stringify({id:item.id})});
   await refreshPersonaGrowth();
  }catch(err){el("persona-growth-status").textContent="Ошибка удаления: "+err.message;del.disabled=false}};
  li.append(snippet,del);return li;
 }));
}
el("persona-growth-refresh").onclick=()=>refreshPersonaGrowth().catch(error=>{
 el("persona-growth-status").textContent="Ошибка загрузки: "+error.message;
});
el("persona-growth-enabled").onchange=async event=>{
 const box=event.target;box.disabled=true;
 try{
  await api("/api/cloud-ru/persona-config",{method:"POST",body:JSON.stringify({enabled:box.checked})});
  await refreshPersonaGrowth();
 }catch(error){el("persona-growth-status").textContent="Ошибка сохранения: "+error.message}
 finally{box.disabled=false}
};
refreshPersonaGrowth().catch(error=>{
 el("persona-growth-status").textContent="Накопленные реплики недоступны: "+error.message;
});

async function refreshMemoryControls(){
 const report=await api("/api/cloud-ru/memory-status");
 const prefList=el("memory-preferences-list"), memList=el("memory-items-list");
 function entry(text,namespace,id,editable){
  const li=document.createElement("li"),label=document.createElement("span");
  label.className="item-text";label.textContent=text;
  const actions=document.createElement("span");actions.className="item-actions";
  const remove=document.createElement("button");remove.textContent="Удалить";remove.type="button";remove.className="ghost danger small";
  remove.onclick=async()=>{
   if(!confirm("Удалить выбранную запись из памяти?"))return;
   try{await api("/api/cloud-ru/memory-delete",{method:"POST",body:JSON.stringify({namespace,id})});
       await refreshMemoryControls()}catch(e){el("memory-controls-status").textContent=e.message}
  };
  li.append(label,actions);
  if(editable){const edit=document.createElement("button");edit.textContent="Исправить";edit.type="button";edit.className="ghost small";
   edit.onclick=async()=>{const value=prompt("Исправить текст воспоминания:",text);if(value===null)return;
    try{await api("/api/cloud-ru/memory-edit",{method:"POST",body:JSON.stringify({id,text:value})});
    await refreshMemoryControls()}catch(e){el("memory-controls-status").textContent=e.message}};
   actions.append(edit)}
  actions.append(remove);
  return li;
 }
 prefList.replaceChildren(...report.preferences.map(x=>entry(x.key+": "+x.text,"user_preferences",x.key,false)));
 memList.replaceChildren(...report.memories.map(x=>entry(x.text,"memories",x.id,true)));
 el("memory-controls-status").textContent="Предпочтений: "+report.preferences.length+"; показано воспоминаний: "+report.memories.length;
}
el("memory-controls-refresh").onclick=()=>refreshMemoryControls().catch(e=>{el("memory-controls-status").textContent=e.message});
el("memory-preference-save").onclick=async()=>{
 const key=el("memory-preference-key").value.trim(),text=el("memory-preference-text").value.trim();
 if(!/^[A-Za-z0-9_-]{1,64}$/.test(key)){el("memory-controls-status").textContent="Название: латинские буквы, цифры, _ или -, без пробелов.";el("memory-preference-key").focus();return}
 if(!text){el("memory-controls-status").textContent="Введите значение предпочтения.";el("memory-preference-text").focus();return}
 const button=el("memory-preference-save");button.disabled=true;
 try{await api("/api/cloud-ru/memory-set",{method:"POST",body:JSON.stringify({key,text})});
  el("memory-preference-key").value="";el("memory-preference-text").value="";
  await refreshMemoryControls()}catch(e){el("memory-controls-status").textContent="Не удалось сохранить: "+e.message}
 finally{button.disabled=false}
};
refreshMemoryControls().catch(e=>{el("memory-controls-status").textContent="Управление памятью недоступно: "+e.message});
