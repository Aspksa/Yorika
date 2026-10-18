import { YorikaCore } from "./core/app.js";
import { api } from "./api.js";
const core = new YorikaCore();
const el=id=>document.getElementById(id);
// The full updater lives on updates.html; here we only mark the launcher when a new version exists.
async function check(channel){
  try{const r=await api("/api/updates/check",{method:"POST",body:JSON.stringify({channel})});el("update-dot").hidden=!r.available}
  catch(e){console.warn("Не удалось проверить обновления:",e.message)}
}
// UI and updater operate independently of the experimental browser database.
core.start().catch(error=>console.warn("Не удалось открыть браузерное хранилище:",error));
(async()=>{
 try{
  const r=await api("/api/updates/settings");
  if(r.interval>0){check(r.channel);setInterval(()=>check(r.channel),r.interval)}
 }catch(error){console.error("Не удалось получить настройки обновления:",error)}
})();
