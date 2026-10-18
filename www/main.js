import { YorikaCore } from "./core/app.js";
const core = new YorikaCore();
const el=id=>document.getElementById(id);
const api=async(path,options={})=>{
  const r=await fetch(path,{cache:"no-store",...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});
  const text=await r.text();let data;try{data=JSON.parse(text)}catch{throw Error("Неверный ответ сервера")}
  if(!r.ok)throw Error(data.error||"Ошибка сервера");return data;
};
let available=null, timer=null, stagedSha=null;
const status=(value,details="")=>{el("update-status").textContent=value;el("update-details").textContent=details};
async function check(){
  status("Проверка GitHub…");available=null;stagedSha=null;el("apply-update").disabled=true;el("stage-update").disabled=true;
  try{const r=await api("/api/updates/check",{method:"POST",body:JSON.stringify({channel:el("update-channel").value})});
    available=(r.available||r.untracked)?r:null;
    el("update-dot").hidden=!r.available;
    el("stage-update").disabled=!(r.available||r.untracked);
    status(r.untracked?"Локальная версия не определена":(r.available?"Доступно обновление":"Новая версия не найдена"),r.detail||"");
  }catch(e){status("Не удалось проверить",e.message)}
}
async function configure(){try{await api("/api/updates/settings",{method:"POST",body:JSON.stringify({channel:el("update-channel").value,interval:Number(el("update-interval").value)})});schedule()}catch(e){status("Ошибка настроек",e.message)}}
function schedule(){if(timer)clearInterval(timer);const ms=Number(el("update-interval").value);if(ms>0)timer=setInterval(check,ms)}
const toggleUpdates = open => {
  el("update-panel").hidden = !open;
  el("shade").hidden = !open;
  el("menu-toggle").setAttribute("aria-expanded", String(open));
  if(open) { el("close-updates").focus(); } else { el("menu-toggle").focus(); }
};
el("menu-toggle").onclick = () => toggleUpdates(el("update-panel").hidden);
el("shade").onclick = () => toggleUpdates(false);
el("close-updates").onclick = () => toggleUpdates(false);
document.addEventListener("keydown", event => {
  if (event.key === "Escape") toggleUpdates(false);
});
el("toggle-token").onclick=()=>{
 const field=el("github-token"), button=el("toggle-token");
 const visible=field.type==="password";
 field.type=visible?"text":"password";
 button.textContent=visible?"Скрыть":"Показать";
 button.setAttribute("aria-pressed",String(visible));
 button.setAttribute("aria-label",visible?"Скрыть токен":"Показать токен");
};
el("check-update").onclick=check;
el("update-channel").onchange=configure;el("update-interval").onchange=configure;
el("save-token").onclick=async()=>{try{const result=await api("/api/updates/token",{method:"POST",body:JSON.stringify({token:el("github-token").value})});el("github-token").value="";el("token-status").textContent=result.detail||"Токен проверен и сохранён";check()}catch(e){el("token-status").textContent=e.message}};
el("delete-token").onclick=async()=>{try{await api("/api/updates/token",{method:"DELETE"});el("github-token").value="";el("token-status").textContent="Токен удалён"}catch(e){el("token-status").textContent=e.message}};
el("stage-update").onclick=async()=>{if(!available)return;el("stage-update").disabled=true;status("Скачивание и проверка…");try{const r=await api("/api/updates/stage",{method:"POST",body:JSON.stringify({channel:el("update-channel").value})});stagedSha=r.sha;el("apply-update").disabled=true;status("Архив проверен и подготовлен",r.detail)}catch(e){status("Не удалось подготовить пакет",e.message)}finally{el("stage-update").disabled=false}};
el("apply-update").onclick=async()=>{if(!stagedSha)return;if(!confirm("Yorika завершит работу, создаст резервную копию и заменит файлы. Продолжить?"))return;el("apply-update").disabled=true;try{const r=await api("/api/updates/apply",{method:"POST",body:JSON.stringify({sha:stagedSha})});status("Установка запущена",r.detail)}catch(e){status("Не удалось начать установку",e.message)}};
// UI and updater operate independently of the experimental browser database.
core.start().catch(error=>console.warn("Не удалось открыть браузерное хранилище:",error));
(async()=>{
 try{
  const r=await api("/api/updates/settings");
  el("update-channel").value=r.channel;
  el("update-interval").value=String(r.interval);
  el("token-status").textContent=r.hasToken?"Токен есть на компьютере (доступ проверяется отдельно)":"Токен не задан";
  schedule();
  if(r.interval>0)check();
 }catch(error){
  console.error("Не удалось получить настройки обновления:",error);
  el("token-status").textContent="Не удалось загрузить настройки: "+error.message;
  status("Ошибка соединения",error.message);
 }
})();
