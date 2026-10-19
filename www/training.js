// «Обучение» page: talks to /api/training/* served by scripts/yorika-tray.ps1.
import {api} from "./api.js";

const $=id=>document.getElementById(id);
// ---- icons: one stroke style, filled into every [data-icon] ----
const ICONS={
 cap:["M22 10 12 5 2 10l10 5 10-5z","M6 12v5c3 2 9 2 12 0v-5","M22 10v6"],
 loop:["M21 12a9 9 0 1 1-3-6.7","M21 3v6h-6"],
 rocket:["M4.5 16.5c-1.5 1.3-2 5-2 5s3.7-.5 5-2c.7-.8.7-2.1-.1-2.9a2.2 2.2 0 0 0-2.9-.1z","M12 15l-3-3a22 22 0 0 1 2-3.9A12.9 12.9 0 0 1 22 2c0 2.7-.8 7.5-6 11a22.4 22.4 0 0 1-4 2z","M9 12H4s.6-3 2-4c1.6-1.1 5 0 5 0","M12 15v5s3-.6 4-2c1.1-1.6 0-5 0-5"],
 sparkles:["M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z","M19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z","M5 2l.6 1.4L7 4l-1.4.6L5 6l-.6-1.4L3 4l1.4-.6z"],
 gpu:["M6 4h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z","M9 9h6v6H9z","M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"],
 database:["M4 5c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z","M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5","M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"],
 layers:["M12 2 2 7l10 5 10-5-10-5z","M2 17l10 5 10-5","M2 12l10 5 10-5"],
 chat:["M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z","M8 9h8M8 13h5"],
 thumb:["M7 10v11","M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.6l-2.3 7A2 2 0 0 1 17.5 21H7V10l4-8a3 3 0 0 1 4 3.9z"],
 check:["M22 11.1V12a10 10 0 1 1-5.9-9.1","M22 4 12 14l-3-3"],
 scale:["M12 3v18","M5 7h14","M5 7l-3 7a3 3 0 0 0 6 0z","M19 7l-3 7a3 3 0 0 0 6 0z","M8 21h8"],
 zap:["M13 2 3 14h9l-1 8 10-12h-9z"],
 teacher:["M3 4h18v11H3z","M8 21l4-6 4 6","M7 8h6M7 11h4"],
 book:["M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z","M4 19.5V21h16","M9 7h7"],
 clipboard:["M9 3h6v3H9z","M15 4h3a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h3","M9 14l2 2 4-4"],
 target:["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z","M12 18a6 6 0 1 0 0-12 6 6 0 0 0 0 12z","M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"],
 play:["M17 1l4 4-4 4","M3 11V9a4 4 0 0 1 4-4h14","M7 23l-4-4 4-4","M21 13v2a4 4 0 0 1-4 4H3"],
 moon:["M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z","M17 4l.5 1.5L19 6l-1.5.5L17 8l-.5-1.5L15 6l1.5-.5z"],
 brain:["M9.5 2A2.5 2.5 0 0 0 7 4.5v.5a3 3 0 0 0-3 3v1a3 3 0 0 0 0 6v1a3 3 0 0 0 3 3h.5A2.5 2.5 0 0 0 12 19.5v-15A2.5 2.5 0 0 0 9.5 2z","M14.5 2A2.5 2.5 0 0 1 17 4.5v.5a3 3 0 0 1 3 3v1a3 3 0 0 1 0 6v1a3 3 0 0 1-3 3h-.5A2.5 2.5 0 0 1 12 19.5"],
 users:["M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z","M2 21v-2a4 4 0 0 1 4-4h6a4 4 0 0 1 4 4v2","M16 3.1a4 4 0 0 1 0 7.8","M22 21v-2a4 4 0 0 0-3-3.9"],
 eye:["M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z","M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z"],
 pen:["M12 19l7-7 3 3-7 7z","M18 13l-1.5-7.5L2 2l3.5 14.5L13 18z","M2 2l7.6 7.6","M11 13a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"],
 flask:["M9 2h6","M10 2v6L4 20a1 1 0 0 0 .9 1.5h14.2A1 1 0 0 0 20 20L14 8V2","M7 15h10"],
 globe:["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z","M2 12h20","M12 2a15 15 0 0 1 0 20a15 15 0 0 1 0-20z"],
 swarm:["M6 8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z","M18 8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z","M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z","M6 20.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z","M18 20.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z","M8 8l2 2M16 8l-2 2M8 16l2-2M16 16l-2-2"],
 infinity:["M12 12c-2-2.7-4-4-6-4a4 4 0 0 0 0 8c2 0 4-1.3 6-4z","M12 12c2 2.7 4 4 6 4a4 4 0 0 0 0-8c-2 0-4 1.3-6 4z"],
 bulb:["M9 18h6","M10 22h4","M12 2a7 7 0 0 0-4 12.7V16h8v-1.3A7 7 0 0 0 12 2z"],
 archive:["M2 3h20v5H2z","M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8","M10 12h4"],
 move:["M5 9l-3 3 3 3","M9 5l3-3 3 3","M15 19l-3 3-3-3","M19 9l3 3-3 3","M2 12h20","M12 2v20"],
 shield:["M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z","M9 12l2 2 4-4"],
 sliders:["M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3","M1 14h6M9 8h6M17 16h6"],
 lock:["M5 11h14a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2z","M7 11V7a5 5 0 0 1 10 0v4"],
 wrench:["M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.8-3.8a6 6 0 0 1-7.9 7.9l-6.9 6.9a2.1 2.1 0 0 1-3-3l6.9-6.9a6 6 0 0 1 7.9-7.9z"],
 search:["M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z","M21 21l-4.3-4.3"],
 help:["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z","M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3","M12 17h.01"],
 list:["M8 6h13M8 12h13M8 18h13","M3 6h.01M3 12h.01M3 18h.01"],
 cloud:["M17.5 19H9a7 7 0 1 1 6.7-9h1.8a4.5 4.5 0 1 1 0 9z"],
 exam:["M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z","M14 2v6h6","M9 15l2 2 4-4"],
 stop:["M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z","M9 9h6v6H9z"],
};
function icon(name){
  const ns="http://www.w3.org/2000/svg",svg=document.createElementNS(ns,"svg");
  svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");svg.setAttribute("focusable","false");svg.classList.add("ic-svg");
  for(const d of ICONS[name]||ICONS.sparkles){const p=document.createElementNS(ns,"path");p.setAttribute("d",d);svg.append(p)}
  return svg;
}
function fillIcons(root=document){for(const el of root.querySelectorAll("[data-icon]:not(:has(svg))"))el.append(icon(el.dataset.icon))}

const post=(action,body={})=>api("/api/training/"+action,{method:"POST",body:JSON.stringify(body)});
const STATES={starting:"Запускается",running:"Идёт",paused:"На паузе",stopped:"Остановлено",finished:"Завершено",failed:"Ошибка",interrupted:"Прервано",unknown:"—"};
const LIVE=new Set(["starting","running"]);
let current=null,timer=null,folderTouched=false;

const gb=b=>b?(b/1073741824).toFixed(b<1073741824?2:1).replace(".",",")+" ГБ":"—";
const duration=s=>{s=Math.max(0,Math.round(s||0));const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h} ч ${String(m).padStart(2,"0")} мин`:m?`${m} мин ${s%60} с`:`${s} с`};
const num=n=>n==null?"—":Number(n).toLocaleString("ru-RU");
const when=id=>{const m=/^(\d{4})(\d\d)(\d\d)-(\d\d)(\d\d)/.exec(id||"");return m?new Date(Date.UTC(+m[1],m[2]-1,+m[3],+m[4],+m[5])).toLocaleString("ru-RU",{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}):id};
const option=(value,label)=>{const o=document.createElement("option");o.value=value;o.textContent=label;return o};

function showError(message){const box=$("page-error");box.textContent=message||"";box.hidden=!message}
async function act(button,work){
  const label=button.textContent;button.disabled=true;showError("");
  try{return await work()}catch(e){showError(e.message);return null}
  finally{button.disabled=false;button.textContent=label}
}

function renderGpu(s){
  const t=s.torch,p=s.probe;
  $("torch-state").textContent=t.installed?`установлен${t.version?" · "+t.version:""}`:"не установлен";
  $("install-torch").hidden=t.installed||t.install.running;
  if(p&&p.cuda_usable){$("gpu-name").textContent=p.gpu_name;$("gpu-memory").textContent=gb(p.vram_bytes)}
  else if(p){$("gpu-name").textContent="недоступна";$("gpu-memory").textContent="—"}
  let note="";
  if(t.install.running)note="Устанавливаю PyTorch, это может занять 10–20 минут. Страницу можно закрыть.";
  else if(t.install.state==="failed")note="Установка не удалась. Последние строки журнала ниже.";
  else if(!t.installed)note=`Для обучения нужен PyTorch с поддержкой видеокарты, около 2,5 ГБ. Python ${t.python}.`;
  else if(p&&p.cuda_usable)note=`Видеокарта работает: проверочное вычисление прошло. Проверено ${new Date(p.checked_at).toLocaleString("ru-RU")}.`;
  else if(p)note="PyTorch не видит видеокарту. Обычно помогает свежий драйвер NVIDIA и PyTorch с CUDA. Учиться можно и на процессоре, но медленнее.";
  else note="Нажмите «Проверить», чтобы узнать, видит ли PyTorch вашу видеокарту.";
  $("gpu-note").textContent=note;
  const log=t.install.log||[];$("install-log").hidden=!(t.install.running||t.install.state==="failed")||!log.length;$("install-log").textContent=log.join("\n");
}

function renderData(s){
  $("data-folder").textContent=s.data_folder;$("min-records").textContent=num(s.min_long_records);
  for(const id of ["data-file","long-file"]){
    const select=$(id),keep=select.value;select.replaceChildren();
    if(!s.data.length)select.append(option("","Файлов пока нет"));
    for(const f of s.data)select.append(option(f.name,`${f.name} · ${(f.bytes/1048576).toFixed(1).replace(".",",")} МБ`));
    if([...select.options].some(o=>o.value===keep))select.value=keep;
  }
  $("check-data").disabled=!s.data.length;
  if(!folderTouched)$("results-folder").value=s.folder;
  $("folder-note").textContent=s.onedrive?"Эта папка в OneDrive: он будет постоянно синхронизировать большие файлы обучения. Лучше выбрать папку вне OneDrive.":"Здесь хранятся данные, версии модели и журналы. Папка не меняется при обновлениях Yorika.";
  $("folder-note").classList.toggle("warn-text",s.onedrive);
}

function renderChart(history){
  const svg=$("chart"),W=600,H=170,L=46,R=10,T=12,B=26;svg.replaceChildren();
  const ns="http://www.w3.org/2000/svg",el=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const k in attrs)n.setAttribute(k,attrs[k]);if(text!=null)n.textContent=text;svg.append(n);return n};
  if(history.length<2){el("text",{x:W/2,y:H/2,"text-anchor":"middle",class:"chart-empty"},"График появится после первых проверок");return}
  const xs=history.map(p=>p.step),ys=history.map(p=>p.nll);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),dy=(y1-y0)||1;
  const px=v=>L+(v-x0)/((x1-x0)||1)*(W-L-R),py=v=>T+(y1-v)/dy*(H-T-B);
  for(const v of [y0,(y0+y1)/2,y1]){el("line",{x1:L,x2:W-R,y1:py(v),y2:py(v),class:"chart-grid"});el("text",{x:L-6,y:py(v)+4,"text-anchor":"end",class:"chart-label"},v.toFixed(2))}
  el("text",{x:L,y:H-6,class:"chart-label"},"шаг "+num(x0));el("text",{x:W-R,y:H-6,"text-anchor":"end",class:"chart-label"},"шаг "+num(x1));
  el("polyline",{points:history.map(p=>px(p.step)+","+py(p.nll)).join(" "),class:"chart-line"});
  const last=history[history.length-1];el("circle",{cx:px(last.step),cy:py(last.nll),r:4,class:"chart-dot"});
}

function renderJob(runs){
  const job=runs.find(r=>LIVE.has(r.state))||runs[0];
  current=job||null;$("job").hidden=!job;if(!job)return;
  $("job").dataset.state=job.state;$("job-pill").textContent=STATES[job.state]||job.state;
  $("job-title").textContent=`${job.mode==="pilot"?"Пробное":"Долгое"} обучение · ${when(job.id)} · ${job.device==="cuda"?(job.gpu_name||"видеокарта"):"процессор"}`;
  $("job-steps").textContent=job.mode==="pilot"?num(job.steps):`${num(job.steps)} из ${num(job.total_steps)}`;
  $("job-time").textContent=duration(job.elapsed);
  $("job-left").textContent=LIVE.has(job.state)?duration(Math.max(0,(job.time_limit||0)-(job.elapsed||0)))+" максимум":"—";
  $("job-speed").textContent=job.speed?`${String(job.speed).replace(".",",")} шаг/с`:"—";
  $("job-vram").textContent=job.device==="cuda"?gb(job.peak_vram):"не используется";
  $("job-nll").textContent=job.best_nll==null?"—":`${job.best_nll.toFixed(3)} (шаг ${num(job.best_step)})`;
  $("job-error").textContent=job.error||"";$("job-error").hidden=!job.error;
  $("pause").hidden=!(LIVE.has(job.state)&&job.mode==="long");$("stop").hidden=!LIVE.has(job.state);$("resume").hidden=!job.resumable;
  $("start").disabled=LIVE.has(job.state);
  renderChart(job.history||[]);
}

function renderVersions(s){
  const list=$("versions"),act=s.active;list.replaceChildren();
  $("active-line").textContent=act?`Активная версия: ${when(act.run)}, шаг ${num(act.step)}. Выбрана вами ${new Date(act.activated).toLocaleString("ru-RU")}.`:"Активной версии нет: в чате отвечает Cloud.ru.";
  $("rollback").hidden=!act;
  if(!s.runs.length){const li=document.createElement("li");li.className="empty";li.textContent="Обучений ещё не было.";list.append(li)}
  for(const r of s.runs){
    const li=document.createElement("li"),isActive=act&&act.run===r.id;
    const info=document.createElement("div");info.className="version-info";
    const title=document.createElement("strong");title.textContent=`${when(r.id)} · ${r.mode==="pilot"?"пробная":"долгая"}`;
    const badge=document.createElement("span");badge.className="badge "+(isActive?"badge-ok":"");badge.textContent=isActive?"активная":(STATES[r.state]||r.state);
    const meta=document.createElement("small");
    meta.textContent=[`${num(r.steps)} шагов`,r.best_nll!=null?`ошибка ${r.best_nll.toFixed(3)}`:null,r.device==="cuda"?(r.gpu_name||"видеокарта"):"процессор",r.parameters?`${(r.parameters/1e6).toFixed(1).replace(".",",")} млн параметров`:null,r.dataset].filter(Boolean).join(" · ");
    title.append(" ",badge);info.append(title,meta);li.append(info);
    if(r.mode==="long"&&r.has_best&&!isActive&&!LIVE.has(r.state)){
      const b=document.createElement("button");b.className="secondary";b.textContent="Сделать активной";
      b.onclick=()=>{if(confirm("Сделать эту версию активной? Прошлую можно будет вернуть."))act_(b,()=>post("activate",{id:r.id}))};
      li.append(b);
    }
    list.append(li);
  }
  for(const id of ["cmp-a","cmp-b"]){
    const select=$(id),keep=select.value;select.replaceChildren();
    if(id==="cmp-b")select.append(option("","— только одна версия —"));
    for(const r of s.runs.filter(r=>r.has_best))select.append(option(r.id,`${when(r.id)} · ${r.mode==="pilot"?"пробная":"долгая"} · шаг ${num(r.best_step)}`));
    if([...select.options].some(o=>o.value===keep))select.value=keep;
  }
  $("compare").disabled=!s.runs.some(r=>r.has_best);
}
const act_=(button,work)=>act(button,async()=>{await work();await refresh()});


function renderSummary(s){
  const p=s.probe,live=s.runs.find(r=>LIVE.has(r.state));
  $("sum-gpu").textContent=p&&p.cuda_usable?p.gpu_name.replace(/^NVIDIA (GeForce )?/,""):p?"недоступна":s.torch.installed?"не проверялась":"нужен PyTorch";
  $("sum-job").textContent=live?`${STATES[live.state]} · шаг ${num(live.steps)}`:"не идёт";
  $("sum-active").textContent=s.active?`${when(s.active.run)}`:"Cloud.ru";
}
for(const a of document.querySelectorAll("[data-go]"))a.onclick=e=>{e.preventDefault();openTab(a.dataset.go);$("tab-"+a.dataset.go).scrollIntoView({behavior:"smooth",block:"nearest"})};

async function refresh(){
  try{
    const s=await api("/api/training/status");
    renderGpu(s);renderData(s);renderJob(s.runs);renderVersions(s);renderSummary(s);
    const busy=s.runs.some(r=>LIVE.has(r.state))||s.torch.install.running;
    clearTimeout(timer);timer=setTimeout(refresh,busy?3000:20000);
  }catch(e){showError(e.message);clearTimeout(timer);timer=setTimeout(refresh,10000)}
}

function syncMode(){
  const long=document.querySelector("input[name=mode]:checked").value==="long";
  $("long-fields").hidden=!long;
  $("mode-note").textContent=long?"Долгое обучение идёт на ваших данных и сохраняет прогресс. Его можно поставить на паузу и продолжить позже.":"Пробный режим учится на встроенных тестовых примерах: проверяет скорость, память и сохранение. Умнее от него Yorika не станет.";
}

$("probe").onclick=e=>act(e.currentTarget,async()=>{e.currentTarget.textContent="Проверяю…";await post("probe");await refresh()});
$("install-torch").onclick=e=>{if(confirm("Скачать и установить PyTorch с поддержкой видеокарты? Это около 2,5 ГБ."))act_(e.currentTarget,()=>post("install-torch"))};
$("check-data").onclick=e=>act(e.currentTarget,async()=>{
  e.currentTarget.textContent="Проверяю…";const r=await post("data-check",{name:$("data-file").value});
  const out=$("data-result");
  if(!r)return;
  out.textContent=r.ok?`Записей: ${num(r.count)} (обучение ${num(r.train)}, проверка ${num(r.validation)}, тест ${num(r.test)}). `+(r.long_ready?"Подходит для долгого обучения.":r.long_blocker):`Не подходит: ${r.reason}`;
  out.classList.toggle("warn-text",!r.ok||!r.long_ready);
});
$("open-data").onclick=e=>act(e.currentTarget,()=>post("open-folder",{which:"data"}));
$("refresh").onclick=e=>act(e.currentTarget,refresh);
$("results-folder").oninput=()=>{folderTouched=true};
$("save-folder").onclick=e=>act_(e.currentTarget,async()=>{await post("folder",{path:$("results-folder").value});folderTouched=false});
for(const r of document.querySelectorAll("input[name=mode]"))r.onchange=syncMode;
$("start").onclick=e=>act_(e.currentTarget,()=>{
  const mode=document.querySelector("input[name=mode]:checked").value,device=document.querySelector("input[name=device]:checked").value;
  const body={mode,device};
  if(mode==="long")Object.assign(body,{dataset:$("long-file").value,steps:parseInt($("steps").value,10),hours:parseFloat($("hours").value)});
  return post("start",body);
});
$("pause").onclick=e=>act_(e.currentTarget,()=>post("control",{id:current.id,action:"pause"}));
$("stop").onclick=e=>{if(confirm("Остановить обучение? Сохранённый прогресс останется."))act_(e.currentTarget,()=>post("control",{id:current.id,action:"stop"}))};
$("resume").onclick=e=>act_(e.currentTarget,()=>post("control",{id:current.id,action:"resume"}));
$("rollback").onclick=e=>{if(confirm("Вернуть прошлую активную версию?"))act_(e.currentTarget,()=>post("rollback"))};
$("compare").onclick=e=>act(e.currentTarget,async()=>{
  const ids=[$("cmp-a").value,$("cmp-b").value].filter(Boolean),questions=$("questions").value.split("\n").map(q=>q.trim()).filter(Boolean);
  $("compare-status").textContent="Модели отвечают…";
  const r=await post("compare",{ids,questions});
  $("compare-status").textContent=r?r.note:"";
  const box=$("compare-result");box.replaceChildren();box.hidden=!r;if(!r)return;
  const table=document.createElement("table"),head=table.createTHead().insertRow();
  head.append(Object.assign(document.createElement("th"),{textContent:"Вопрос"}));
  for(const v of r.versions)head.append(Object.assign(document.createElement("th"),{textContent:`${when(v.id)} · шаг ${num(v.step)}`}));
  const body=table.createTBody();
  r.questions.forEach((q,i)=>{const row=body.insertRow();row.insertCell().textContent=q;for(const v of r.versions)row.insertCell().textContent=v.answers[i]||"(пустой ответ)"});
  box.append(table);
});

// ---- tabs ----
const TABS=["train","self","grow","future"];
function openTab(name,focus){
  if(!TABS.includes(name))name="train";
  for(const t of TABS){const tab=$("tab-"+t),on=t===name;tab.setAttribute("aria-selected",on);tab.tabIndex=on?0:-1;$("pane-"+t).hidden=!on}
  if(focus)$("tab-"+name).focus();
  try{localStorage.setItem("yorika.training.tab",name)}catch{}
  if(name==="self")refreshSelf();
}
for(const t of TABS){
  $("tab-"+t).onclick=()=>openTab(t);
  $("tab-"+t).onkeydown=e=>{const i=TABS.indexOf(t),d=e.key==="ArrowRight"?1:e.key==="ArrowLeft"?-1:0;if(d){e.preventDefault();openTab(TABS[(i+d+TABS.length)%TABS.length],true)}};
}

// ---- self-learning: 1 experience, 2 ratings, 6 decision ----
let view="unrated",shown=0,proposalNow=null;
function renderCounts(c){
  $("sum-exp").textContent=`${num(c.ready)} из ${num(c.needed)}`;
  $("exp-total").textContent=num(c.total);$("exp-unrated").textContent=num(c.unrated);$("exp-up").textContent=num(c.up);$("exp-fixed").textContent=num(c.fixed);
  $("exp-meter").style.width=c.ready?`max(6px,${Math.min(100,c.ready/c.needed*100)}%)`:"0";
  $("exp-note").textContent=`Готово для обучения: ${num(c.ready)} из ${num(c.needed)}, нужных для долгого обучения. Пробное и короткое обучение работает и с меньшим числом.`;
  $("export-exp").disabled=c.ready<10;
}
function example(item){
  const li=document.createElement("li");li.className="example";li.dataset.rating=item.rating||"none";
  const q=document.createElement("p");q.className="ex-q";q.textContent=item.prompt;
  const a=document.createElement("p");a.className="ex-a";a.textContent=item.answer;
  li.append(q,a);
  if(item.correction){const c=document.createElement("p");c.className="ex-fix";c.textContent=item.correction;li.append(c)}
  const row=document.createElement("div");row.className="ex-actions";
  const mk=(label,cls,title,fn)=>{const b=document.createElement("button");b.className=cls;b.textContent=label;b.title=title;b.setAttribute("aria-label",title);b.onclick=()=>act(b,fn);row.append(b);return b};
  const up=mk("👍","rate"+(item.rating==="up"?" on":""),"Хороший ответ",async()=>{await post("sl-rate",{id:item.id,rating:item.rating==="up"?null:"up"});await reloadExamples()});
  up.setAttribute("aria-pressed",item.rating==="up");
  const down=mk("👎","rate"+(item.rating==="down"?" on":""),"Плохой ответ, исправить",async()=>openFix());
  down.setAttribute("aria-pressed",item.rating==="down");
  mk("Удалить","ghost small","Удалить пример",async()=>{if(confirm("Удалить этот пример? Он больше не попадёт в обучение."))await post("sl-delete",{id:item.id}),await reloadExamples()});
  li.append(row);
  function openFix(){
    if(li.querySelector(".ex-edit"))return;
    const box=document.createElement("div");box.className="ex-edit";
    const label=document.createElement("label");label.className="token-label";label.textContent="Как надо было ответить";
    const ta=document.createElement("textarea");ta.className="field";ta.rows=3;ta.value=item.correction||"";ta.maxLength=2000;label.htmlFor=ta.id="fix-"+item.id;
    const save=document.createElement("button");save.className="primary";save.textContent="Сохранить";
    const skip=document.createElement("button");skip.className="ghost";skip.textContent="Просто 👎 без исправления";
    save.onclick=()=>act(save,async()=>{await post("sl-rate",{id:item.id,rating:"down",correction:ta.value});await reloadExamples()});
    skip.onclick=()=>act(skip,async()=>{await post("sl-rate",{id:item.id,rating:"down"});await reloadExamples()});
    const btns=document.createElement("div");btns.className="button-row";btns.append(save,skip);
    box.append(label,ta,btns);li.append(box);ta.focus();
  }
  return li;
}
async function loadExamples(reset){
  if(reset)shown=0;
  const r=await post("sl-list",{view,offset:shown,limit:20});
  const list=$("examples");if(reset)list.replaceChildren();
  for(const item of r.items)list.append(example(item));
  shown+=r.items.length;
  if(!list.children.length){const li=document.createElement("li");li.className="empty-state";li.textContent=view==="unrated"?"Неоценённых примеров нет. Включите сбор и нажмите «Собрать из чата».":"Здесь пока пусто.";list.append(li)}
  $("more").hidden=shown>=r.matching;renderCounts(r.counts);
}
const reloadExamples=async()=>{const keep=shown;await loadExamples(true);while(shown<keep&&!$("more").hidden)await loadExamples(false)};
function renderProposal(p){
  proposalNow=p;$("proposal").hidden=!p;$("proposal-empty").hidden=!!p;if(!p)return;
  const meta=r=>[`${num(r.steps)} шагов`,r.best_nll!=null?`ошибка ${r.best_nll.toFixed(3)}`:null,r.dataset].filter(Boolean).join(" · ");
  $("prop-new").textContent=when(p.candidate.id);$("prop-new-meta").textContent=meta(p.candidate);
  $("prop-active").textContent=p.active?when(p.active.id):"Cloud.ru";$("prop-active-meta").textContent=p.active?meta(p.active):"своя модель ещё не выбрана";
}
async function refreshSelf(){
  try{
    const s=await api("/api/training/sl-status");
    $("collect-toggle").checked=s.collect;$("collect-now").disabled=!s.collect;
    renderCounts(s.counts);renderProposal(s.proposal);await loadExamples(true);
  }catch(e){showError(e.message)}
}
$("collect-toggle").onchange=e=>{const on=e.target.checked;act(e.target,async()=>{await post("sl-collect-setting",{enabled:on});$("collect-now").disabled=!on}).then(r=>{if(r===null)e.target.checked=!on})};
$("collect-now").onclick=e=>act(e.currentTarget,async()=>{const r=await post("sl-collect");$("exp-result").textContent=r.added?`Добавлено новых примеров: ${num(r.added)}. Оцените их ниже.`:"Новых пар «вопрос → ответ» в чате нет.";view="unrated";document.querySelector("input[name=view][value=unrated]").checked=true;await loadExamples(true)});
$("export-exp").onclick=e=>act(e.currentTarget,async()=>{const r=await post("sl-export");$("exp-result").textContent=`Сохранён файл «${r.name}»: ${num(r.count)} примеров. Он появился в блоке «Данные» на вкладке «Обучение».`+(r.long_ready?"":" Для долгого обучения примеров пока мало.");await refresh()});
for(const r of document.querySelectorAll("input[name=view]"))r.onchange=()=>{view=r.value;act(r,()=>loadExamples(true))};
$("more").onclick=e=>act(e.currentTarget,()=>loadExamples(false));
$("prop-accept").onclick=e=>{if(proposalNow&&confirm("Включить новую версию? Прошлую можно будет вернуть в блоке «Версии модели»."))act(e.currentTarget,async()=>{await post("activate",{id:proposalNow.candidate.id});await refresh();await refreshSelf()})};
$("prop-dismiss").onclick=e=>{if(proposalNow)act(e.currentTarget,async()=>{await post("sl-dismiss",{id:proposalNow.candidate.id});await refreshSelf()})};
$("prop-compare").onclick=()=>{if(!proposalNow)return;openTab("train");$("cmp-a").value=proposalNow.active?proposalNow.active.id:proposalNow.candidate.id;$("cmp-b").value=proposalNow.active?proposalNow.candidate.id:"";$("quality-title").scrollIntoView({behavior:"smooth",block:"start"})};

// ---- 07–19: growth steps ----
const GROW=[
 {group:"Сильнее, но реально на ноутбуке"},
 {n:"07",t:"Инструменты",d:"Калькулятор, поиск по памяти, календарь. Yorika сама решает, когда нужен инструмент, а не угадывает ответ.",m:"Доля задач, решённых с инструментом верно",s:"plan"},
 {n:"08",t:"Самопроверка ответа",d:"Черновик → проверка по памяти и инструментам → исправление. Найденные ошибки идут в обучение.",m:"Сколько ошибок поймано до ответа",s:"plan"},
 {n:"09",t:"Знание своих границ",d:"Говорить «не знаю», а не выдумывать.",m:"Доля выдуманных ответов на вопросы без ответа",s:"plan"},
 {n:"10",t:"Память в навыки",d:"Из сотен разговоров выбираются устойчивые факты и привычки, и на них модель учится.",m:"Точность ответов о ваших фактах",s:"plan"},
 {n:"11",t:"Уроки, которые она составляет сама",d:"Находит, где ошибается чаще всего, и делает упражнения именно на это.",m:"Рост оценки на слабых темах",s:"plan"},
 {group:"Дальше обычного помощника"},
 {n:"12",t:"Команда специалистов",d:"Маленькие модели для речи, памяти, плана и проверки, одна главная распределяет работу. Для вас это одна Yorika.",m:"Качество против одной модели того же размера",s:"research"},
 {n:"13",t:"Модель мира",d:"Виртуальный мир: Yorika действует, предсказывает последствия и учится на ошибках прогноза.",m:"Ошибка прогноза следующего состояния",s:"research"},
 {n:"14",t:"Умение учиться",d:"Измеряется, как быстро она осваивает совсем новую задачу, и улучшается именно эта скорость.",m:"Шагов до освоения новой задачи",s:"research"},
 {n:"15",t:"Изменение собственного устройства",d:"Предлагает изменения своей нейросети, проверяет их отдельно от рабочей версии и показывает цифры.",m:"Выигрыш на тесте при той же цене",s:"research"},
 {n:"16",t:"Гипотезы и эксперименты",d:"Сама ставит небольшие опыты над своим обучением, а выводы проверяете вы.",m:"Доля гипотез, подтверждённых повтором",s:"research"},
 {n:"17",t:"Обучение в облаке",d:"Тяжёлые эксперименты в Cloud.ru, только с лимитом расходов и вашим подтверждением.",m:"Рубли и часы на каждый запуск",s:"plan"},
 {group:"Защита"},
 {n:"18",t:"Уровни свободы и аварийная остановка",d:"Что она делает сама, что после вопроса, а что запрещено. Уже сейчас новая версия включается только вами, а обучение можно остановить одной кнопкой.",m:"Журнал всех решений и остановок",s:"partial",stop:true},
 {n:"19",t:"Независимые экзамены",d:"Задачи, которых модель никогда не видела: видно, что она стала умнее, а не заучила ответы.",m:"Оценка на закрытом тесте и слепая оценка людьми",s:"plan"},
];
const CHIP={partial:["chip chip-ok","Работает частично"],plan:["chip","В планах"],research:["chip chip-research","Исследование"]};
function renderGrow(){
  const box=$("grow-cards");box.replaceChildren();
  for(const g of GROW){
    if(g.group){const h=document.createElement("h3");h.className="grow-group";h.textContent=g.group;box.append(h);continue}
    const card=document.createElement("article");card.className="grow-card";card.dataset.status=g.s;
    const head=document.createElement("header");
    const n=document.createElement("span");n.className="panel-index";n.textContent=g.n;
    const t=document.createElement("h4");t.textContent=g.t;
    const chip=document.createElement("span");[chip.className,chip.textContent]=CHIP[g.s];
    head.append(n,t,chip);
    const d=document.createElement("p");d.textContent=g.d;
    const m=document.createElement("p");m.className="grow-measure";m.textContent="Как измеряем: "+g.m;
    card.append(head,d,m);
    if(g.stop){const b=document.createElement("button");b.className="danger";b.textContent="Аварийная остановка обучения";b.onclick=()=>{if(confirm("Остановить всё обучение сейчас? Сохранённый прогресс останется."))act(b,async()=>{const r=await post("stop-all");alert(r.stopped.length?"Обучение останавливается.":"Сейчас ничего не обучается.");await refresh()})};card.append(b)}
    box.append(card);
  }
}

// ---- powerful self-learning (Развитие) and the 50-year horizon (Будущее) ----
const POWER=[
 {n:"1",i:"teacher",t:"Учитель на Cloud.ru",d:"Большая модель через уже подключённый Cloud.ru пишет тысячи ответов в стиле Yorika, а своя маленькая модель учится на них.",gain:"10 000 примеров за вечер, а не за месяцы",cost:"Токены Cloud.ru: лимит и подтверждение перед запуском",s:"plan"},
 {n:"2",i:"book",t:"Предобучение на открытых текстах",d:"Сначала модель читает много открытых русских текстов и учится просто языку, потом переходит к диалогам.",gain:"Самый большой скачок грамотности для маленькой модели",cost:"Часы на видеокарте, соблюдение лицензий текстов",s:"plan"},
 {n:"3",i:"zap",t:"Ускорение обучения в 5–20 раз",d:"Пачки примеров вместо одного за шаг, половинная точность на RTX 3050 и накопление градиента.",gain:"Те же часы дают в разы больше обучения",cost:"Бесплатно",s:"next"},
 {n:"4",i:"clipboard",t:"Учитель-проверяющий",d:"Учитель оценивает ответы Yorika и предлагает исправления, а вы только подтверждаете.",gain:"Оценивать в разы быстрее",cost:"Оценки учителя помечаются отдельно и не выдаются за проверку человеком",s:"plan"},
 {n:"5",i:"target",t:"Умный порядок оценки",d:"Первыми вы видите примеры, в которых Yorika меньше всего уверена.",gain:"Ваши 10 минут дают в разы больше пользы",cost:"Бесплатно",s:"plan"},
 {n:"6",i:"play",t:"Самоигра",d:"Yorika сама придумывает вопросы по темам, где ошибается, учитель отвечает, пара идёт в обучение.",gain:"Учится без вас, точно в слабых местах",cost:"В пределах месячного лимита денег",s:"plan"},
 {n:"7",i:"moon",t:"Ночной цикл",d:"Собрать опыт → ответы учителя → дообучение → экзамен → утром вопрос «Есть версия лучше, включить?».",gain:"Каждый день немного умнее",cost:"Ноутбук на зарядке ночью, утреннее «да» за вами",s:"plan"},
];
const HORIZON=[
 {when:"Сейчас",sub:"2026",items:[
  {i:"brain",t:"Своя нейросеть",d:"5 млн параметров, обучается на вашем ноутбуке.",s:"ok"},
  {i:"loop",t:"Самообучение с вашей оценкой",d:"Опыт из чата, 👍/👎, решение о версии за вами.",s:"ok"},
  {i:"stop",t:"Аварийная остановка",d:"Любое обучение останавливается одной кнопкой.",s:"ok"}]},
 {when:"5 лет",sub:"учится постоянно",items:[
  {i:"moon",t:"Обучение каждую ночь",d:"Каждый день немного умнее, с экзаменом и вашим утренним «да».",s:"plan"},
  {i:"brain",t:"Своя большая модель",d:"Сотни миллионов параметров на хорошей видеокарте или в облаке, с глубоким знанием именно вас.",s:"plan"},
  {i:"users",t:"Несколько учителей",d:"Учится у разных моделей сразу и сама выбирает, кто лучше в какой теме.",s:"research"},
  {i:"eye",t:"Видит, слышит, говорит",d:"Голос, камера и экран только по разрешению, все чувства в одной модели.",s:"research"}]},
 {when:"15 лет",sub:"улучшает себя",items:[
  {i:"pen",t:"Проектирует следующую версию",d:"Предлагает новую архитектуру, обучает её в песочнице и доказывает цифрами, что она лучше.",s:"research"},
  {i:"flask",t:"Собственная наука",d:"Тысячи экспериментов над своим обучением, выводы вам, перепроверка самой собой.",s:"research"},
  {i:"globe",t:"Модель мира",d:"Понимает причины и следствия, планирует на недели вперёд.",s:"research"},
  {i:"swarm",t:"Рой Yorika",d:"Много копий-специалистов работают параллельно и сводятся в одну личность и одну память.",s:"research"}]},
 {when:"50 лет",sub:"за пределами сегодняшнего",items:[
  {i:"infinity",t:"Учится всю жизнь",d:"Непрерывно, без забывания, из каждого опыта, как человек.",s:"dream"},
  {i:"bulb",t:"Открывает новое",d:"Гипотезы, которых нет в данных, проверенные и подтверждённые людьми.",s:"dream"},
  {i:"archive",t:"Память на десятилетия",d:"Вся история вашей совместной жизни, бережно и под вашим контролем.",s:"dream"},
  {i:"move",t:"Переезжает на любое железо",d:"Новая техника, та же Yorika: та же память, тот же характер.",s:"dream"}]},
];
const GUARD=[
 {i:"exam",t:"Экзамены на невиданном",d:"Каждое улучшение измеряется на задачах, которых модель никогда не видела."},
 {i:"sliders",t:"Больше силы — больше контроля",d:"Уровни свободы, журнал решений и аварийная остановка всегда у вас."},
 {i:"lock",t:"Ваши данные — ваши",d:"Всё видно и всё можно удалить. Без согласия ничего не собирается."},
];
const CHIPS={...CHIP,next:["chip chip-next","Следующий шаг"],ok:["chip chip-ok","Уже есть"],dream:["chip chip-dream","Открытый вопрос науки"]};
const tag=(name,cls,text)=>{const e=document.createElement(name);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e};
function renderPower(){
  const box=$("power-cards");box.replaceChildren();
  for(const p of POWER){
    const card=tag("article","power-card");card.dataset.status=p.s;
    const head=tag("header");const ic=tag("span","card-ic");ic.append(icon(p.i));
    const title=tag("div","card-title");title.append(tag("span","card-num",p.n),tag("h3",null,p.t));
    const chip=tag("span");[chip.className,chip.textContent]=CHIPS[p.s];
    head.append(ic,title,chip);
    const dl=tag("dl","card-facts");
    for(const [k,v] of [["Даёт",p.gain],["Цена",p.cost]]){const row=tag("div");row.append(tag("dt",null,k),tag("dd",null,v));dl.append(row)}
    card.append(head,tag("p",null,p.d),dl);box.append(card);
  }
  // Night cycle: five steps around a ring, the owner's decision highlighted.
  const svg=$("night-cycle"),ns="http://www.w3.org/2000/svg";svg.replaceChildren();
  const el=(t,a,txt)=>{const n=document.createElementNS(ns,t);for(const k in a)n.setAttribute(k,a[k]);if(txt!=null)n.textContent=txt;svg.append(n);return n};
  const steps=[["chat","Опыт"],["teacher","Учитель"],["zap","Дообучение"],["exam","Экзамен"],["check","Ваше «да»"]];
  const cx=160,cy=160,R=112;
  el("circle",{cx,cy,r:R,class:"ring"});
  el("circle",{cx,cy,r:R,class:"ring-glow"});
  steps.forEach(([ic,label],k)=>{
    const a=-Math.PI/2+k*2*Math.PI/steps.length,x=cx+R*Math.cos(a),y=cy+R*Math.sin(a);
    const g=document.createElementNS(ns,"g");g.setAttribute("class","node"+(k===4?" node-you":""));svg.append(g);
    const c=document.createElementNS(ns,"circle");c.setAttribute("cx",x);c.setAttribute("cy",y);c.setAttribute("r",27);g.append(c);
    const i=icon(ic);i.setAttribute("x",x-11);i.setAttribute("y",y-11);i.setAttribute("width",22);i.setAttribute("height",22);g.append(i);
    const t=document.createElementNS(ns,"text");t.setAttribute("x",x);t.setAttribute("y",y+(y>cy+10?45:-36));t.setAttribute("text-anchor","middle");t.setAttribute("class","node-label");t.textContent=label;g.append(t);
  });
  const mid=icon("moon");mid.setAttribute("x",cx-17);mid.setAttribute("y",cy-30);mid.setAttribute("width",34);mid.setAttribute("height",34);mid.classList.add("mid-ic");svg.append(mid);
  el("text",{x:cx,y:cy+22,"text-anchor":"middle",class:"mid-title"},"Каждую ночь");
  el("text",{x:cx,y:cy+40,"text-anchor":"middle",class:"mid-sub"},"утром решаете вы");
}
function renderFuture(){
  const list=$("timeline");list.replaceChildren();
  HORIZON.forEach((h,k)=>{
    const li=tag("li","stage");li.style.setProperty("--k",k);
    const head=tag("div","stage-head");head.append(tag("span","stage-dot"),tag("strong",null,h.when),tag("small",null,h.sub));
    const items=tag("div","stage-items");
    for(const it of h.items){
      const card=tag("article","stage-card");card.dataset.status=it.s;
      const top=tag("header");const ic=tag("span","card-ic");ic.append(icon(it.i));
      const chip=tag("span");[chip.className,chip.textContent]=CHIPS[it.s];
      top.append(ic,tag("h3",null,it.t));card.append(top,tag("p",null,it.d),chip);items.append(card);
    }
    li.append(head,items);list.append(li);
  });
  const g=$("guard-cards");g.replaceChildren();
  for(const it of GUARD){const card=tag("article","guard-card");const ic=tag("span","card-ic");ic.append(icon(it.i));card.append(ic,tag("h3",null,it.t),tag("p",null,it.d));g.append(card)}
}

renderGrow();renderPower();renderFuture();fillIcons();syncMode();refresh();
let startTab="train";try{startTab=location.hash.slice(1)||localStorage.getItem("yorika.training.tab")||"train"}catch{}
openTab(startTab);
if(startTab!=="self")api("/api/training/sl-status").then(r=>renderCounts(r.counts)).catch(()=>{});
addEventListener("hashchange",()=>openTab(location.hash.slice(1)));
