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
    available=r.available?r:null;
    el("update-dot").hidden=!r.available;
    el("stage-update").disabled=!r.available;
    status(r.available?"Доступно обновление":"Новая версия не найдена",r.detail||"");
  }catch(e){status("Не удалось проверить",e.message)}
}
async function configure(){try{await api("/api/updates/settings",{method:"POST",body:JSON.stringify({channel:el("update-channel").value,interval:Number(el("update-interval").value)})});schedule()}catch(e){status("Ошибка настроек",e.message)}}
function schedule(){if(timer)clearInterval(timer);const ms=Number(el("update-interval").value);if(ms>0)timer=setInterval(check,ms)}
el("menu-toggle").onclick=()=>{el("side-menu").hidden=!el("side-menu").hidden;el("menu-toggle").setAttribute("aria-expanded",String(!el("side-menu").hidden))};
el("open-updates").onclick=()=>{el("side-menu").hidden=true;el("update-panel").hidden=false};
el("close-updates").onclick=()=>el("update-panel").hidden=true;
el("check-update").onclick=check;
el("update-channel").onchange=configure;el("update-interval").onchange=configure;
el("save-token").onclick=async()=>{try{await api("/api/updates/token",{method:"POST",body:JSON.stringify({token:el("github-token").value})});el("github-token").value="";el("token-status").textContent="Токен сохранён на компьютере"}catch(e){el("token-status").textContent=e.message}};
el("delete-token").onclick=async()=>{try{await api("/api/updates/token",{method:"DELETE"});el("github-token").value="";el("token-status").textContent="Токен удалён"}catch(e){el("token-status").textContent=e.message}};
el("stage-update").onclick=async()=>{if(!available)return;el("stage-update").disabled=true;status("Скачивание и проверка…");try{const r=await api("/api/updates/stage",{method:"POST",body:JSON.stringify({channel:el("update-channel").value})});stagedSha=r.sha;el("apply-update").disabled=true;status("Архив проверен и подготовлен",r.detail)}catch(e){status("Не удалось подготовить пакет",e.message)}finally{el("stage-update").disabled=false}};
el("apply-update").onclick=async()=>{if(!stagedSha)return;if(!confirm("Yorika завершит работу, создаст резервную копию и заменит файлы. Продолжить?"))return;el("apply-update").disabled=true;try{const r=await api("/api/updates/apply",{method:"POST",body:JSON.stringify({sha:stagedSha})});status("Установка запущена",r.detail)}catch(e){status("Не удалось начать установку",e.message)}};
try{await core.start();const r=await api("/api/updates/settings");el("update-channel").value=r.channel;el("update-interval").value=String(r.interval);el("token-status").textContent=r.hasToken?"Токен сохранён":"Токен не задан";schedule();if(r.interval>0)check()}catch(e){console.error(e);el("status").textContent="Не удалось инициализировать Yorika"}
