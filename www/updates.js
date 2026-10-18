import { api } from "./api.js";
const el=id=>document.getElementById(id);
// Channel and auto-check interval are edited on settings.html; this page only reads them.
let settings={channel:"fresh",interval:86400000};
const channel=()=>settings.channel;
const sources={git:"git-клон на этом компьютере",installed:"установлено через Yorika",folder:"по имени папки архива",files:"сверено по файлам"};
const states={idle:"Не проверено",checking:"Проверка",current:"Актуально",available:"Есть обновление",unknown:"Версия неизвестна",ready:"Готово к установке",installed:"Установлено",error:"Ошибка"};
let available=null, timer=null, stagedSha=null;
const status=(state,value,details="")=>{
  el("overview").dataset.state=state;el("state-pill").textContent=states[state];
  el("update-status").textContent=value;el("update-details").textContent=details;
};
const versions=(local="—",localNote="",remote="—")=>{
  el("local-version").textContent=local;el("local-version").classList.toggle("word",!/^[0-9a-f]+$/.test(local));el("local-source").textContent=localNote;el("remote-version").textContent=remote;
  el("remote-source").textContent=channel()==="stable"?"канал «Стабильный»":"канал «Свежий»";
};
async function check(){
  status("checking","Проверка GitHub…");available=null;stagedSha=null;el("apply-update").hidden=true;el("apply-update").disabled=true;el("stage-update").disabled=true;
  try{const r=await api("/api/updates/check",{method:"POST",body:JSON.stringify({channel:channel()})});
    available=(r.available||r.untracked)?r:null;
    el("stage-update").disabled=!available;
    versions(r.local,sources[r.localSource]||"не удалось определить",r.target);
    if(r.untracked)status("unknown","Не удалось определить вашу версию","Сравнить файлы с GitHub не получилось. Скачайте пакет, чтобы установить отслеживаемую версию.");
    else if(r.available)status("available","Доступна новая версия",r.localSource==="files"?"Ваши файлы отличаются от версии на GitHub. Скачайте пакет, чтобы обновиться.":"На GitHub есть более новая версия. Скачайте пакет, чтобы обновиться.");
    else status("current","У вас последняя версия","Версия совпадает с GitHub. Новых изменений нет.");
  }catch(e){status("error","Не удалось проверить",e.message)}
}
function schedule(){if(timer)clearInterval(timer);const ms=Number(settings.interval);if(ms>0)timer=setInterval(()=>{if(!stagedSha)check()},ms)}
el("toggle-token").onclick=()=>{
 const field=el("github-token"), button=el("toggle-token");
 const visible=field.type==="password";
 field.type=visible?"text":"password";
 button.textContent=visible?"Скрыть":"Показать";
 button.setAttribute("aria-pressed",String(visible));
 button.setAttribute("aria-label",visible?"Скрыть токен":"Показать токен");
};
el("check-update").onclick=check;
el("save-token").onclick=async()=>{try{const result=await api("/api/updates/token",{method:"POST",body:JSON.stringify({token:el("github-token").value})});el("github-token").value="";el("token-status").textContent=result.detail||"Токен проверен и сохранён";check()}catch(e){el("token-status").textContent=e.message}};
el("delete-token").onclick=async()=>{try{await api("/api/updates/token",{method:"DELETE"});el("github-token").value="";el("token-status").textContent="Токен удалён"}catch(e){el("token-status").textContent=e.message}};
el("stage-update").onclick=async()=>{if(!available)return;el("stage-update").disabled=true;status("checking","Скачивание и проверка…");try{const r=await api("/api/updates/stage",{method:"POST",body:JSON.stringify({channel:channel()})});stagedSha=r.sha;el("apply-update").hidden=false;el("apply-update").disabled=false;status("ready","Пакет готов к установке","Архив проверен. Новая версия установится рядом с текущей.")}catch(e){status("error","Не удалось подготовить пакет",e.message)}finally{el("stage-update").disabled=false}};
el("apply-update").onclick=async()=>{
 if(!stagedSha)return;
 if(!confirm("Установить проверенную версию в отдельную папку и переключить будущие запуски на неё? Старая версия останется на месте."))return;
 const install=el("apply-update"),stage=el("stage-update");
 install.disabled=true;stage.disabled=true;
 status("checking","Установка и проверка запуска…","Новая версия разворачивается отдельно. Текущая папка не изменяется.");
 try{
  const r=await api("/api/updates/apply",{method:"POST",body:JSON.stringify({sha:stagedSha})});
  status("installed","Обновление установлено",r.message||"Новая версия успешно запущена.");
  install.hidden=true;
  if(r.url&&/^http:\/\/127\.0\.0\.1:\d+\/$/.test(r.url)){window.location.assign(r.url+"updates.html");}
 }catch(e){status("error","Не удалось установить",e.message);install.disabled=false}
 finally{stage.disabled=false}
};
(async()=>{
 try{
  const r=await api("/api/updates/settings");
  settings={channel:r.channel==="stable"?"stable":"fresh",interval:Number(r.interval)||0};
  versions();
  el("token-status").textContent=r.hasToken?"Токен сохранён на компьютере (доступ проверяется при проверке)":"Токен не задан";
  schedule();
  check();
 }catch(error){
  console.error("Не удалось получить настройки обновления:",error);
  el("token-status").textContent="Не удалось загрузить настройки: "+error.message;
  status("error","Нет связи с Yorika",error.message);
 }
})();
