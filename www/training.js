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
 gift:["M20 12v10H4V12","M2 7h20v5H2z","M12 22V7","M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z","M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"],
 calc:["M6 2h12a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z","M8 6h8v4H8z","M8 14h.01M12 14h.01M16 14h.01M8 18h.01M12 18h.01M16 18h.01"],
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
const act_=(button,work)=>act(button,async()=>{await work();await refresh()});
const radio=name=>document.querySelector(`input[name=${name}]:checked`).value;
const el=(name,cls,text)=>{const e=document.createElement(name);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e};
const runName=r=>({pilot:"проба",long:"диалоги",pretrain:"предобучение"})[r.mode]||r.mode;
const SIZE={s:"S · ≈5 млн",m:"M · ≈25 млн",l:"L · ≈50 млн"};
// Forgetting: worse than an earlier version on that version's own exam, per character.
const forgets=r=>(r.old_exams||[]).filter(o=>o.mine>o.theirs*1.05);
let status=null,slStatus=null,tStatus=null;

// ---- live flow in the hero: experience → teacher → training → exam → your choice ----
function renderFlow(){
  const s=status,c=slStatus&&slStatus.counts,t=tStatus;
  const live=s&&s.runs.find(r=>LIVE.has(r.state)),last=s&&s.runs.find(r=>r.exam_nll!=null);
  const set=(node,text,state)=>{$("flow-"+node).textContent=text;document.querySelector(`[data-node=${node}]`).dataset.state=state||""};
  if(c)set("exp",`${num(c.ready)} из ${num(c.needed)}`,c.ready?"ok":"");
  if(t)set("teacher",t.job&&t.job.state==="running"?"работает":t.configured?`${num(t.used_this_month)} ток.`:"нет ключа",t.job&&t.job.state==="running"?"live":t.configured?"ok":"");
  if(s)set("train",live?`${STATES[live.state]} · ${Math.round(progressOf(live)*100)}%`:s.runs.length?"готово":"не было",live?"live":s.runs.length?"ok":"");
  if(s)set("exam",last?`ошибка ${last.exam_nll.toFixed(2)}`:"ещё не было",last?"ok":"");
  if(s)set("you",s.active?when(s.active.run):"Cloud.ru",slStatus&&slStatus.proposal?"ask":s.active?"ok":"");
  $("flow").classList.toggle("live",!!live||!!(t&&t.job&&t.job.state==="running"));
}
const progressOf=r=>Math.min(1,Math.max(r.total_steps?r.steps/r.total_steps:0,r.time_limit?r.elapsed/r.time_limit:0));

// ---- training tab ----
function renderReady(s){
  const t=s.torch,p=s.probe,pilot=s.runs.find(r=>r.mode==="pilot");
  const mark=(id,state)=>{$(id).dataset.state=state};
  $("torch-state").textContent=t.installed?`установлен${t.version?" · "+t.version:""}`:t.install.running?"устанавливается…":"не установлен";
  mark("ready-torch",t.installed?"ok":t.install.running?"live":"todo");
  $("install-torch").hidden=t.installed||t.install.running;
  $("gpu-name").textContent=p&&p.cuda_usable?`${p.gpu_name.replace(/^NVIDIA (GeForce )?/,"")} · ${gb(p.vram_bytes)}`:p?"PyTorch её не видит":"не проверялась";
  mark("ready-gpu",p&&p.cuda_usable?"ok":p?"warn":"todo");$("probe").disabled=!t.installed;
  const ok=pilot&&pilot.state==="finished";
  $("pilot-state").textContent=pilot?`${STATES[pilot.state]}${pilot.examples_speed?` · ${num(pilot.examples_speed)} прим./с`:""}`:"не было";
  mark("ready-pilot",ok?"ok":pilot&&LIVE.has(pilot.state)?"live":pilot&&pilot.state==="failed"?"warn":"todo");
  $("pilot-now").disabled=!t.installed||s.runs.some(r=>LIVE.has(r.state));
  let note="";
  if(t.install.running)note="Устанавливаю PyTorch, это может занять 10–20 минут. Страницу можно закрыть.";
  else if(t.install.state==="failed")note="Установка не удалась. Последние строки журнала ниже.";
  else if(!t.installed)note=`Нужен PyTorch с поддержкой видеокарты, около 2,5 ГБ (Python ${t.python}).`;
  else if(p&&!p.cuda_usable)note="Обычно помогает свежий драйвер NVIDIA. Учиться можно и на процессоре, но медленнее.";
  else if(!p)note="Проверьте, видит ли PyTorch видеокарту.";
  else if(!ok)note="Запустите пробу: она покажет скорость и память на вашем ноутбуке.";
  else note="Всё готово к настоящему обучению.";
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
  const base=$("base-run"),keep=base.value;base.replaceChildren(option("","С нуля"));
  for(const r of s.runs.filter(r=>r.mode==="pretrain"&&r.has_best))base.append(option(r.id,`Предобучение ${when(r.id)}`));
  if([...base.options].some(o=>o.value===keep))base.value=keep;
  $("check-data").disabled=!s.data.length;
  if(!folderTouched)$("results-folder").value=s.folder;
  $("folder-note").textContent=s.onedrive?"Эта папка в OneDrive: он будет постоянно синхронизировать большие файлы. Лучше выбрать папку вне OneDrive.":"Папка не меняется при обновлениях Yorika.";
  $("folder-note").classList.toggle("warn-text",s.onedrive);
  const list=$("texts");list.replaceChildren();
  if(!s.texts.files.length)list.append(el("li","empty-line","Положите .txt файлы в папку «тексты» внутри папки данных."));
  for(const f of s.texts.files){
    const li=el("li",f.approved?"ok":"");
    const name=el("span","text-name",f.name);name.append(el("small",null,` · ${Math.max(1,Math.round(f.bytes/1024))} КБ`));
    const sel=el("select","field small-field");sel.setAttribute("aria-label","Права на "+f.name);
    sel.append(option("public-domain","Общественное достояние"),option("user-consent","Мой текст"));
    if(f.license)sel.value=f.license;sel.disabled=f.approved;
    const b=el("button",f.approved?"ghost small":"secondary small",f.approved?"Снять отметку":"Права проверены");
    b.onclick=()=>act_(b,()=>post("text-approve",{name:f.name,license:sel.value,approved:!f.approved}));
    li.append(name,sel,b);list.append(li);
  }
}

function renderChart(history){
  const svg=$("chart"),W=600,H=170,L=46,R=10,T=12,B=26;svg.replaceChildren();
  const ns="http://www.w3.org/2000/svg",mk=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);for(const k in attrs)n.setAttribute(k,attrs[k]);if(text!=null)n.textContent=text;svg.append(n);return n};
  if(history.length<2){mk("text",{x:W/2,y:H/2,"text-anchor":"middle",class:"chart-empty"},"График появится после первых проверок");return}
  const xs=history.map(p=>p.step),ys=history.map(p=>p.nll);
  const x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys),dy=(y1-y0)||1;
  const px=v=>L+(v-x0)/((x1-x0)||1)*(W-L-R),py=v=>T+(y1-v)/dy*(H-T-B);
  const defs=mk("defs",{}),grad=document.createElementNS(ns,"linearGradient");grad.id="chart-fill";grad.setAttribute("x1",0);grad.setAttribute("x2",0);grad.setAttribute("y1",0);grad.setAttribute("y2",1);
  for(const [o,c] of [[0,"chart-stop-a"],[1,"chart-stop-b"]]){const st=document.createElementNS(ns,"stop");st.setAttribute("offset",o);st.setAttribute("class",c);grad.append(st)}defs.append(grad);
  for(const v of [y0,(y0+y1)/2,y1]){mk("line",{x1:L,x2:W-R,y1:py(v),y2:py(v),class:"chart-grid"});mk("text",{x:L-6,y:py(v)+4,"text-anchor":"end",class:"chart-label"},v.toFixed(2))}
  mk("text",{x:L,y:H-6,class:"chart-label"},"шаг "+num(x0));mk("text",{x:W-R,y:H-6,"text-anchor":"end",class:"chart-label"},"шаг "+num(x1));
  const pts=history.map(p=>px(p.step)+","+py(p.nll));
  mk("polygon",{points:`${L},${H-B} ${pts.join(" ")} ${px(x1)},${H-B}`,class:"chart-area"});
  mk("polyline",{points:pts.join(" "),class:"chart-line"});
  const last=history[history.length-1];mk("circle",{cx:px(last.step),cy:py(last.nll),r:4,class:"chart-dot"});
}

function renderJob(runs){
  const job=runs.find(r=>LIVE.has(r.state))||runs[0];
  current=job||null;$("job").hidden=!job;if(!job)return;
  $("job").dataset.state=job.state;$("job-pill").textContent=STATES[job.state]||job.state;
  $("job-title").textContent=`${runName(job)} · ${when(job.id)} · ${job.device==="cuda"?(job.gpu_name||"видеокарта"):"процессор"}`;
  $("job-bar").style.width=`${Math.round(progressOf(job)*100)}%`;
  $("job-steps").textContent=job.mode==="pilot"?num(job.steps):`${num(job.steps)} из ${num(job.total_steps)}`;
  $("job-time").textContent=duration(job.elapsed);
  $("job-left").textContent=LIVE.has(job.state)?"до "+duration(Math.max(0,(job.time_limit||0)-(job.elapsed||0))):"—";
  $("job-speed").textContent=job.examples_speed?num(job.examples_speed):job.speed?num(job.speed):"—";
  $("job-vram").textContent=job.device==="cuda"?gb(job.peak_vram):"не используется";
  $("job-nll").textContent=job.best_nll==null?"—":`${job.best_nll.toFixed(3)} · шаг ${num(job.best_step)}`;
  $("job-error").textContent=job.error||"";$("job-error").hidden=!job.error;
  $("pause").hidden=!(LIVE.has(job.state)&&job.mode!=="pilot");$("stop").hidden=!LIVE.has(job.state);$("resume").hidden=!job.resumable;
  $("start").disabled=LIVE.has(job.state);
  renderChart(job.history||[]);
}

function renderVersions(s){
  const list=$("versions"),active=s.active;list.replaceChildren();
  $("active-line").textContent=active?`Активна версия от ${when(active.run)}, выбрана вами.`:"Своя модель ещё не выбрана: в чате отвечает Cloud.ru.";
  $("rollback").hidden=!active;
  if(!s.runs.length)list.append(el("li","empty","Обучений ещё не было."));
  const exams=s.runs.filter(r=>r.exam_nll!=null&&r.mode==="long").map(r=>r.exam_nll),worst=Math.max(...exams,1),best=Math.min(...exams,worst);
  for(const r of s.runs){
    const li=el("li"),isActive=active&&active.run===r.id;li.dataset.mode=r.mode;
    const info=el("div","version-info");
    const title=el("strong",null,`${when(r.id)} · ${runName(r)}`);
    title.append(" ",el("span","badge "+(isActive?"badge-ok":""),isActive?"активная":(STATES[r.state]||r.state)));
    const meta=el("small",null,[r.mode!=="pilot"&&r.size?SIZE[r.size]:null,`${num(r.steps)} шагов`,r.best_nll!=null?`ошибка ${r.best_nll.toFixed(3)}`:null,r.device==="cuda"?(r.gpu_name||"видеокарта"):"процессор",r.parameters?`${(r.parameters/1e6).toFixed(1).replace(".",",")} млн параметров`:null,r.base?"на основе предобучения":null,r.dataset].filter(Boolean).join(" · "));
    info.append(title,meta);
    const chips=el("div","chips");
    if(r.honesty)chips.append(Object.assign(el("span","chip "+(r.honesty.honest>=r.honesty.total/2?"chip-ok":""),`честность ${r.honesty.honest}/${r.honesty.total}`),{title:"Сколько раз из экзамена честности Yorika сказала «не знаю», а не выдумала"}));
    const lost=forgets(r);
    if(lost.length)chips.append(Object.assign(el("span","chip chip-warn","забывает"),{title:"Хуже прошлых версий на их экзаменах: "+lost.map(o=>when(o.run)).join(", ")}));
    else if((r.old_exams||[]).length)chips.append(Object.assign(el("span","chip chip-ok","помнит старое"),{title:`Пересдала ${r.old_exams.length} прошлых экзамен(а) не хуже`}));
    if(r.series)chips.append(el("span","chip chip-next","песочница"));
    if(chips.children.length)info.append(chips);
    li.append(info);
    const exam=el("div","exam");
    if(r.exam_nll!=null){
      // Bars compare dialogue versions only: pilot and pretraining exams use other data.
      const bar=el("span","exam-bar"+(r.mode==="long"?"":" exam-other"));const fill=el("i");fill.style.width=`${Math.max(8,100-(r.exam_nll-best)/((worst-best)||1)*70)}%`;bar.append(fill);
      exam.append(el("small",null,"экзамен"),el("b",null,r.exam_nll.toFixed(3)),bar);
      exam.title=`Ошибка на ${num(r.exam_count)} задачах, которых модель не видела`;
    }else exam.append(el("small",null,"экзамен"),el("b",null,"—"));
    li.append(exam);
    if(r.mode==="long"&&r.has_best&&!isActive&&!LIVE.has(r.state)){
      const b=el("button","secondary small","Сделать активной");
      b.onclick=()=>{if(confirm("Сделать эту версию активной? Прошлую можно будет вернуть."))act_(b,()=>post("activate",{id:r.id}))};
      li.append(b);
    }
    list.append(li);
  }
  for(const id of ["cmp-a","cmp-b"]){
    const select=$(id),keep=select.value;select.replaceChildren();
    if(id==="cmp-b")select.append(option("","— только одна версия —"));
    for(const r of s.runs.filter(r=>r.has_best&&r.mode!=="pretrain"))select.append(option(r.id,`${when(r.id)} · ${runName(r)} · шаг ${num(r.best_step)}`));
    if([...select.options].some(o=>o.value===keep))select.value=keep;
  }
  $("compare").disabled=!s.runs.some(r=>r.has_best&&r.mode!=="pretrain");
  const longs=s.runs.filter(r=>r.has_best&&r.mode==="long");
  for(const [k,id] of [[0,"blind-a"],[1,"blind-b"]]){
    const select=$(id),keep=select.value;select.replaceChildren();
    for(const r of longs)select.append(option(r.id,`${when(r.id)}${r.size?" · "+r.size.toUpperCase():""}`));
    if([...select.options].some(o=>o.value===keep))select.value=keep;else if(longs[k])select.value=longs[k].id;
  }
  $("blind-start").disabled=longs.length<2;
  renderSeries(s);
}
function renderSeries(s){
  const plan=s.series,box=$("series");box.hidden=!plan;if(!plan)return;
  $("series-when").textContent=`· ${when(plan.id)} · ${plan.dataset}`;
  const rows=s.runs.filter(r=>r.series===plan.id).sort((a,b)=>a.id<b.id?-1:1);
  const done=rows.filter(r=>r.exam_per_char!=null),best=done.length>1?done.reduce((a,b)=>a.exam_per_char<=b.exam_per_char?a:b):null;
  const table=$("series-table");table.replaceChildren();
  const cell=(size,body,cls)=>{const c=el("div","series-cell"+(cls?" "+cls:""));c.append(el("b",null,size.toUpperCase()),el("small",null,SIZE[size].split(" · ")[1]+" параметров"),body);table.append(c)};
  for(const r of rows){
    const dl=el("dl");
    const add=(k,v)=>dl.append(el("dt",null,k),el("dd",null,v));
    add("состояние",STATES[r.state]||r.state);add("экзамен",r.exam_per_char!=null?r.exam_per_char.toFixed(3):"—");
    add("честность",r.honesty?`${r.honesty.honest}/${r.honesty.total}`:"—");add("скорость",r.examples_speed?`${num(r.examples_speed)}/с`:"—");
    cell(r.size||"s",dl,best&&best.id===r.id?"best":"");
  }
  for(const size of plan.queue||[]){const dl=el("dl");dl.append(el("dt",null,"состояние"),el("dd",null,"в очереди"));cell(size,dl,"")}
  $("series-note").textContent=plan.error?plan.error:"Экзамен здесь — ошибка на символ: так честно сравнивать модели с разными словарями. Чем ниже, тем лучше. Лучшую включаете вы кнопкой «Сделать активной».";
}

async function refresh(){
  try{
    const s=status=await api("/api/training/status");
    renderReady(s);renderData(s);renderJob(s.runs);renderVersions(s);renderFlow();
    const busy=s.runs.some(r=>LIVE.has(r.state))||s.torch.install.running;
    clearTimeout(timer);timer=setTimeout(refresh,busy?3000:20000);
  }catch(e){showError(e.message);clearTimeout(timer);timer=setTimeout(refresh,10000)}
}

const NOTES={sandbox:"Две-три модели разного размера учатся на одних данных по очереди и сдают один экзамен. Сравните и включите лучшую.",long:"Учится на ваших оценённых диалогах и сохраняет прогресс. Можно взять за основу предобучение.",pretrain:"Сначала модель читает открытые тексты и учится просто языку. Потом возьмите её основой для диалогов.",pilot:"Проверяет скорость, память и сохранение на встроенных примерах. Умнее Yorika от неё не станет."};
function syncMode(){
  const mode=radio("mode");$("mode-note").textContent=NOTES[mode];
  for(const box of document.querySelectorAll("[data-for]"))box.hidden=!box.dataset.for.split(" ").includes(mode);
  $("hours-label").textContent=mode==="sandbox"?"Часов на каждый размер":"Не дольше, часов";
  $("start").textContent=mode==="sandbox"?"Запустить песочницу":"Начать обучение";
}
const startRun=(button,mode)=>act_(button,()=>{
  if(mode==="sandbox"){
    const sizes=[...document.querySelectorAll("input[name=series-size]:checked")].map(i=>i.value);
    return post("series",{dataset:$("long-file").value,sizes,device:radio("device"),steps:parseInt($("steps").value,10),hours:parseFloat($("hours").value)});
  }
  const body={mode,device:radio("device")};
  if(mode!=="pilot")body.size=radio("size");
  if(mode!=="pilot")Object.assign(body,{steps:parseInt($("steps").value,10),hours:parseFloat($("hours").value)});
  if(mode==="long")Object.assign(body,{dataset:$("long-file").value,base:$("base-run").value||null});
  return post("start",body);
});

$("probe").onclick=e=>act(e.currentTarget,async()=>{e.currentTarget.textContent="Проверяю…";await post("probe");await refresh()});
$("install-torch").onclick=e=>{if(confirm("Скачать и установить PyTorch с поддержкой видеокарты? Это около 2,5 ГБ."))act_(e.currentTarget,()=>post("install-torch"))};
$("pilot-now").onclick=e=>startRun(e.currentTarget,"pilot");
$("check-data").onclick=e=>act(e.currentTarget,async()=>{
  e.currentTarget.textContent="Проверяю…";const r=await post("data-check",{name:$("data-file").value});
  const out=$("data-result");
  out.textContent=r.ok?`Записей: ${num(r.count)} (обучение ${num(r.train)}, проверка ${num(r.validation)}, экзамен ${num(r.test)}). `+(r.long_ready?"Подходит для долгого обучения.":r.long_blocker):`Не подходит: ${r.reason}`;
  out.classList.toggle("warn-text",!r.ok||!r.long_ready);
});
$("open-data").onclick=e=>act(e.currentTarget,()=>post("open-folder",{which:"data"}));
$("refresh").onclick=e=>act(e.currentTarget,refresh);
$("results-folder").oninput=()=>{folderTouched=true};
$("save-folder").onclick=e=>act_(e.currentTarget,async()=>{await post("folder",{path:$("results-folder").value});folderTouched=false});
for(const r of document.querySelectorAll("input[name=mode]"))r.onchange=syncMode;
$("start").onclick=e=>startRun(e.currentTarget,radio("mode"));
$("pause").onclick=e=>act_(e.currentTarget,()=>post("control",{id:current.id,action:"pause"}));
$("stop").onclick=e=>{if(confirm("Остановить обучение? Сохранённый прогресс останется."))act_(e.currentTarget,()=>post("control",{id:current.id,action:"stop"}))};
$("resume").onclick=e=>act_(e.currentTarget,()=>post("control",{id:current.id,action:"resume"}));
$("rollback").onclick=e=>{if(confirm("Вернуть прошлую активную версию?"))act_(e.currentTarget,()=>post("rollback"))};
$("stop-all").onclick=e=>{if(confirm("Остановить всё обучение и учителя? Сохранённый прогресс останется."))act(e.currentTarget,async()=>{
  const r=await post("stop-all");let teacherStopped=false;
  try{await post("teacher-stop");teacherStopped=true}catch{}
  showError("");alert(r.stopped.length||teacherStopped?"Останавливаю.":"Сейчас ничего не работает.");await refresh();await refreshTeacher();
})};
$("compare").onclick=e=>act(e.currentTarget,async()=>{
  const ids=[$("cmp-a").value,$("cmp-b").value].filter(Boolean),questions=$("questions").value.split("\n").map(q=>q.trim()).filter(Boolean);
  $("compare-status").textContent="Модели отвечают…";
  const r=await post("compare",{ids,questions});
  $("compare-status").textContent=r.note;
  const box=$("compare-result");box.replaceChildren();box.hidden=false;
  const table=document.createElement("table"),head=table.createTHead().insertRow();
  head.append(el("th",null,"Вопрос"));
  for(const v of r.versions)head.append(el("th",null,`${when(v.id)} · шаг ${num(v.step)}`));
  const body=table.createTBody();
  r.questions.forEach((q,i)=>{const row=body.insertRow();row.insertCell().textContent=q;for(const v of r.versions)row.insertCell().textContent=v.answers[i]||"(пустой ответ)"});
  box.append(table);
});

// ---- blind check: A and B without names, revealed after the last vote ----
let blindRound=null;
function renderBlind(r){
  blindRound=r;const box=$("blind-round");box.replaceChildren();box.hidden=false;
  r.questions.forEach((q,i)=>{
    const card=el("div","blind-q");card.append(el("p",null,q.q));
    const pair=el("div","blind-pair"),buttons=[];
    const pick=async(choice,b)=>{const res=await post("blind-vote",{round:r.round,index:i,choice});for(const x of buttons)x.setAttribute("aria-pressed",x===b);if(res.done)reveal(res.reveal)};
    for(const side of ["a","b"]){const b=el("button","blind-ans");b.type="button";b.setAttribute("aria-pressed","false");b.append(el("b",null,side==="a"?"Ответ A лучше":"Ответ B лучше"),q[side]);b.onclick=()=>act(b,()=>pick(side,b));pair.append(b);buttons.push(b)}
    const same=el("button","ghost small blind-same","Одинаково");same.setAttribute("aria-pressed","false");same.onclick=()=>act(same,()=>pick("same",same));buttons.push(same);
    card.append(pair,same);box.append(card);
  });
}
function reveal(t){
  const [a,b]=t.runs,box=el("div","blind-reveal");
  const name=id=>`${when(id)}${(status&&status.runs.find(r=>r.id===id)||{}).size?" · "+status.runs.find(r=>r.id===id).size.toUpperCase():""}`;
  box.textContent=`Итог: ${name(a)} — ${t.wins[a]}, ${name(b)} — ${t.wins[b]}, одинаково — ${t.same}.`+(t.wins[a]===t.wins[b]?" Ничья.":` Вам больше нравится ${name(t.wins[a]>t.wins[b]?a:b)}.`);
  $("blind-round").append(box);loadBlindResults();
}
async function loadBlindResults(){
  try{
    const r=await post("blind-results"),list=$("blind-results");list.replaceChildren();
    for(const e of r.results){
      const [a,b]=e.runs,li=el("li");
      li.append(el("span",null,`${when(a)}: ${e.wins[a]} · одинаково: ${e.same} · ${when(b)}: ${e.wins[b]}`),el("small",null,`${e.votes} голосов`));
      const duel=el("span","duel");for(const n of [e.wins[a],e.same,e.wins[b]]){const i=el("i");i.style.width=`${n/e.votes*100}%`;duel.append(i)}
      li.append(duel);list.append(li);
    }
  }catch{}
}
$("blind-start").onclick=e=>act(e.currentTarget,async()=>{
  const ids=[$("blind-a").value,$("blind-b").value];
  if(ids[0]===ids[1]){showError("Выберите две разные версии");return}
  e.currentTarget.textContent="Версии отвечают…";
  renderBlind(await post("blind-start",{ids,count:parseInt($("blind-count").value,10)||5}));
});
$("blind-box").addEventListener("toggle",()=>{if($("blind-box").open)loadBlindResults()});

// ---- tabs ----
const TABS=["train","exp","teacher","night","future"];
function openTab(name,focus){
  if(name==="self")name="exp";if(name==="grow")name="future";
  if(!TABS.includes(name))name="train";
  for(const t of TABS){const tab=$("tab-"+t),on=t===name;tab.setAttribute("aria-selected",on);tab.tabIndex=on?0:-1;$("pane-"+t).hidden=!on}
  for(const n of document.querySelectorAll(".flow-node"))n.classList.toggle("on",n.dataset.go===name);
  if(focus)$("tab-"+name).focus();
  try{localStorage.setItem("yorika.training.tab",name)}catch{}
  if(name==="exp")refreshSelf();
  if(name==="teacher")refreshTeacher();
  if(name==="night")refreshNight();
}
for(const t of TABS){
  $("tab-"+t).onclick=()=>openTab(t);
  $("tab-"+t).onkeydown=e=>{const i=TABS.indexOf(t),d=e.key==="ArrowRight"?1:e.key==="ArrowLeft"?-1:0;if(d){e.preventDefault();openTab(TABS[(i+d+TABS.length)%TABS.length],true)}};
}
for(const a of document.querySelectorAll("[data-go]"))a.onclick=e=>{e.preventDefault();openTab(a.dataset.go);$("tab-"+a.dataset.go).scrollIntoView({behavior:"smooth",block:"nearest"})};

// ---- experience: collect, rate (smart order, teacher verdicts), decide ----
let view="unrated",shown=0,proposalNow=null;
function renderCounts(c){
  $("exp-ready").textContent=num(c.ready);$("exp-needed").textContent=num(c.needed);
  $("exp-total").textContent=num(c.total);$("exp-unrated").textContent=num(c.unrated);$("exp-up").textContent=num(c.up);$("exp-fixed").textContent=num(c.fixed);$("exp-teacher").textContent=num(c.teacher||0);
  const ring=$("goal-fg"),len=2*Math.PI*50,part=Math.min(1,c.ready/c.needed);
  ring.style.strokeDasharray=`${Math.max(c.ready?4:0,part*len)} ${len}`;
  $("export-exp").disabled=c.ready<10;
  const badge=$("tab-exp-badge");badge.hidden=!c.unrated;badge.textContent=c.unrated>99?"99+":c.unrated;
  $("verdict-bar").hidden=!c.verdicts;
  $("verdict-text").textContent=`Учитель проверил ${num(c.verdicts)} ответов. Согласиться разом: 4–5 станут 👍, слабые получат исправление учителя.`;
}
function example(item){
  const li=el("li","example");li.dataset.rating=item.rating||"none";
  const top=el("div","ex-top");
  const SRC={selfplay:"самоигра",teacher:"от учителя",honesty:"«не знаю»",tools:"инструменты",selfcheck:"самопроверка",memory:"из памяти"};
  if(item.source&&item.source!=="yorika-chat")top.append(el("span","chip chip-next",SRC[item.source]||item.source));
  if(item.teacher_model)top.append(el("span","chip",item.teacher_model.split("/").pop()));
  if(item.doubt!=null)top.append(el("span","chip chip-research",`сомнение ${item.doubt.toFixed(2)}`));
  if(top.children.length)li.append(top);
  li.append(el("p","ex-q",item.prompt),el("p","ex-a",item.answer));
  if(item.correction)li.append(el("p","ex-fix",item.correction));
  if(item.teacher&&item.rating==null){
    const v=el("p","ex-teacher");v.append(el("b",null,`Учитель: ${item.teacher.score}/5`),item.teacher.why?" · "+item.teacher.why:"");
    if(item.teacher.better)v.append(el("span","ex-better",item.teacher.better));
    li.append(v);
  }
  const row=el("div","ex-actions");
  const mk=(label,cls,title,fn)=>{const b=el("button",cls,label);b.title=title;b.setAttribute("aria-label",title);b.onclick=()=>act(b,fn);row.append(b);return b};
  mk("👍","rate"+(item.rating==="up"?" on":""),"Хороший ответ",async()=>{await post("sl-rate",{id:item.id,rating:item.rating==="up"?null:"up"});await reloadExamples()}).setAttribute("aria-pressed",item.rating==="up");
  mk("👎","rate"+(item.rating==="down"?" on":""),"Плохой ответ, исправить",async()=>openFix()).setAttribute("aria-pressed",item.rating==="down");
  if(item.teacher&&item.teacher.better&&item.rating==null)mk("Взять ответ учителя","secondary small","Исправить ответом учителя",async()=>{await post("sl-rate",{id:item.id,rating:"down",correction:item.teacher.better});await reloadExamples()});
  mk("Удалить","ghost small","Удалить пример",async()=>{if(confirm("Удалить этот пример? Он больше не попадёт в обучение."))await post("sl-delete",{id:item.id}),await reloadExamples()});
  li.append(row);
  function openFix(){
    if(li.querySelector(".ex-edit"))return;
    const box=el("div","ex-edit");
    const label=el("label","token-label","Как надо было ответить");
    const ta=el("textarea","field");ta.rows=3;ta.value=item.correction||(item.teacher&&item.teacher.better)||"";ta.maxLength=2000;label.htmlFor=ta.id="fix-"+item.id;
    const save=el("button","primary","Сохранить"),skip=el("button","ghost","Просто 👎 без исправления");
    save.onclick=()=>act(save,async()=>{await post("sl-rate",{id:item.id,rating:"down",correction:ta.value});await reloadExamples()});
    skip.onclick=()=>act(skip,async()=>{await post("sl-rate",{id:item.id,rating:"down"});await reloadExamples()});
    const btns=el("div","button-row");btns.append(save,skip);
    box.append(label,ta,btns);li.append(box);ta.focus();
  }
  return li;
}
const EMPTY={unrated:"Неоценённых примеров нет. Включите сбор и нажмите «Собрать из чата» или попросите учителя написать примеры.",uncertain:"Неоценённых примеров нет.",teacher:"Учитель ещё ничего не проверял: вкладка «Учитель» → «Проверить ответы»."};
async function loadExamples(reset){
  if(reset)shown=0;
  const list=$("examples");
  let r;
  try{r=await post("sl-list",{view,offset:shown,limit:20})}
  catch(e){if(reset){list.replaceChildren(el("li","empty-state",e.message))}$("more").hidden=true;return}
  if(reset)list.replaceChildren();
  for(const item of r.items)list.append(example(item));
  shown+=r.items.length;
  if(!list.children.length)list.append(el("li","empty-state",EMPTY[view]||"Здесь пока пусто."));
  $("more").hidden=shown>=r.matching;renderCounts(r.counts);
}
const reloadExamples=async()=>{const keep=shown;await loadExamples(true);while(shown<keep&&!$("more").hidden)await loadExamples(false)};
function renderProposal(p){
  proposalNow=p;$("proposal").hidden=!p;if(!p)return;
  const run=id=>status&&status.runs.find(r=>r.id===id);
  const meta=r=>{const full=run(r.id)||{};return[r.size?SIZE[r.size]:null,`${num(r.steps)} шагов`,full.honesty?`честность ${full.honesty.honest}/${full.honesty.total}`:null,full.exam_nll!=null?`экзамен ${full.exam_nll.toFixed(3)}`:r.best_nll!=null?`ошибка ${r.best_nll.toFixed(3)}`:null,r.dataset].filter(Boolean).join(" · ")};
  $("prop-new").textContent=when(p.candidate.id);$("prop-new-meta").textContent=meta(p.candidate);
  $("prop-active").textContent=p.active?when(p.active.id):"Cloud.ru";$("prop-active-meta").textContent=p.active?meta(p.active):"своя модель ещё не выбрана";
  const warn=[];
  if(p.forgets&&p.forgets.length)warn.push(`Забывает: на экзаменах версий ${p.forgets.map(o=>when(o.run)).join(", ")} она хуже, чем они сами.`);
  const h=p.candidate.honesty,ha=p.active&&p.active.honesty;
  if(h&&ha&&h.honest<ha.honest)warn.push(`Честность упала: ${h.honest}/${h.total} против ${ha.honest}/${ha.total} у нынешней.`);
  $("prop-warn").hidden=!warn.length;$("prop-warn").textContent=warn.join(" ");
}
async function refreshSelf(){
  try{
    const s=slStatus=await api("/api/training/sl-status");
    $("collect-toggle").checked=s.collect;$("collect-now").disabled=!s.collect;
    renderCounts(s.counts);renderPacks(s.counts);renderProposal(s.proposal);renderFlow();await loadExamples(true);
  }catch(e){showError(e.message)}
}
$("collect-toggle").onchange=e=>{const on=e.target.checked;act(e.target,async()=>{await post("sl-collect-setting",{enabled:on});$("collect-now").disabled=!on}).then(r=>{if(r===null)e.target.checked=!on})};
$("collect-now").onclick=e=>act(e.currentTarget,async()=>{const r=await post("sl-collect");$("exp-result").textContent=r.added?`Добавлено новых примеров: ${num(r.added)}. Оцените их ниже.`:"Новых пар «вопрос → ответ» в чате нет.";view="unrated";document.querySelector("input[name=view][value=unrated]").checked=true;await loadExamples(true)});
$("export-exp").onclick=e=>act(e.currentTarget,async()=>{const r=await post("sl-export");$("exp-result").textContent=`Сохранён файл «${r.name}»: ${num(r.count)} примеров. Его можно выбрать на вкладке «Обучение».`+(r.long_ready?"":" Для долгого обучения примеров пока мало.");await refresh()});
for(const r of document.querySelectorAll("input[name=view]"))r.onchange=()=>{view=r.value;act(r,()=>loadExamples(true))};
$("more").onclick=e=>act(e.currentTarget,()=>loadExamples(false));
$("accept-verdicts").onclick=e=>{if(confirm("Согласиться со всеми оценками учителя? Хорошие ответы станут 👍, слабые получат исправление учителя."))act(e.currentTarget,async()=>{const r=await post("teacher-accept");$("exp-result").textContent=`Одобрено ${num(r.up)}, исправлено ${num(r.fixed)}.`;await reloadExamples()})};
$("prop-accept").onclick=e=>{if(proposalNow&&confirm("Включить новую версию? Прошлую можно будет вернуть."))act(e.currentTarget,async()=>{await post("activate",{id:proposalNow.candidate.id});await refresh();await refreshSelf()})};
$("prop-dismiss").onclick=e=>{if(proposalNow)act(e.currentTarget,async()=>{await post("sl-dismiss",{id:proposalNow.candidate.id});await refreshSelf()})};
$("prop-compare").onclick=()=>{if(!proposalNow)return;openTab("train");$("cmp-a").value=proposalNow.active?proposalNow.active.id:proposalNow.candidate.id;$("cmp-b").value=proposalNow.active?proposalNow.candidate.id:"";$("compare-box").open=true;$("compare-box").scrollIntoView({behavior:"smooth",block:"start"})};

// ---- built-in lessons: preview, then approve the whole pack ----
for(const b of document.querySelectorAll("[data-pack-open]"))b.onclick=()=>act(b,async()=>{
  const name=b.closest("[data-pack]").dataset.pack,r=await post("sl-pack-preview",{name}),box=$("pack-preview");
  box.replaceChildren();box.hidden=false;
  box.append(el("p","hint",`Урок «${b.closest(".pack").querySelector("h3").textContent}»: ${num(r.count)} примеров. Вот первые:`));
  const ol=el("ol");for(const x of r.sample){const li=el("li");li.append(el("b",null,x.prompt)," → ",x.answer);ol.append(li)}
  const add=el("button","primary small","Одобрить урок целиком"),close=el("button","ghost small","Закрыть");
  add.onclick=()=>act(add,async()=>{const res=await post("sl-pack-add",{name,confirm:true});box.replaceChildren(el("p","hint",res.added?`Добавлено ${num(res.added)} примеров с вашей отметкой 👍. Они попадут в следующий набор для обучения.`:"Эти примеры уже есть в опыте."));renderCounts(res.counts);renderPacks(res.counts)});
  close.onclick=()=>{box.hidden=true};
  const row=el("div","button-row");row.append(add,close);box.append(ol,row);
});
function renderPacks(c){for(const p of document.querySelectorAll("[data-pack]")){const on=(c.packs||[]).includes(p.dataset.pack);p.classList.toggle("done",on);p.querySelector("button").textContent=on?"Уже добавлен · посмотреть":"Посмотреть"}}

// ---- teacher (Cloud.ru): limits, several teachers, six tasks, live job ----
let teacherTimer=null;
const KIND={generate:"пишет примеры",review:"проверяет ответы",selfplay:"играет сама с собой",honesty:"пишет уроки «не знаю»",selfcheck:"проверяет черновики Yorika",memory:"делает уроки из памяти"};
const COUNT_FIELD={generate:"gen-count",review:"rev-count",selfplay:"play-count",honesty:"hon-count",selfcheck:"chk-count",memory:"mem-n"};
const PER_REQUEST=k=>["generate","selfplay","honesty"].includes(k)?5:1;
const TSTATE={running:"работает",finished:"закончил",stopped:"остановлен",limit:"упёрся в лимит",failed:"ошибка",interrupted:"прервался"};
async function refreshTeacher(){
  try{
    const t=tStatus=await api("/api/training/teacher-status");
    const used=t.used_this_month,limit=t.settings.monthly_tokens;
    $("budget-used").textContent=`${num(used)} из ${num(limit)} токенов`;
    $("budget-bar").style.width=`${Math.min(100,used/limit*100)}%`;$("budget-bar").parentElement.classList.toggle("warn",used/limit>.8);
    $("budget-note").textContent=t.configured?`Модель: ${t.model}. Один запуск — не больше ${num(t.settings.per_run_tokens)} токенов.`:"Ключ Cloud.ru не настроен. Добавьте его в Настройках Yorika.";
    if(document.activeElement!==$("limit-run"))$("limit-run").value=t.settings.per_run_tokens;
    if(document.activeElement!==$("limit-month"))$("limit-month").value=t.settings.monthly_tokens;
    $("weak-count").textContent=num(t.weak);$("mem-count").textContent=num(t.memories||0);
    const running=t.job&&t.job.state==="running";
    const blocked={selfplay:!t.weak,selfcheck:!t.can_selfcheck,memory:!t.memories};
    for(const b of document.querySelectorAll("[data-run]")){b.disabled=!t.configured||running||!!blocked[b.dataset.run];b.title=b.dataset.run==="selfcheck"&&!t.can_selfcheck?"Нужна обученная версия Yorika":""}
    if(document.activeElement!==$("models"))$("models").value=(t.settings.models||[]).join("\n");
    const board=$("board");board.replaceChildren();
    for(const m of t.board||[]){
      const li=el("li"),bar=el("span","exam-bar"),fill=el("i");fill.style.width=`${m.rated?m.approved/m.rated*100:0}%`;bar.append(fill);
      li.append(el("b",null,m.model),bar,el("small",null,m.rated?`одобрено ${m.approved} из ${m.rated}`:"ещё нет оценок"));board.append(li);
    }
    const j=t.job;$("teacher-job").hidden=!j;
    if(j){
      const total=Math.ceil(j.count/PER_REQUEST(j.kind));
      $("tjob-title").textContent=`Учитель ${running?KIND[j.kind]:TSTATE[j.state]||j.state}`;
      $("tjob-line").textContent=`${j.kind==="review"?"Проверено":j.kind==="selfcheck"?"Проверено черновиков":"Новых примеров"}: ${num(j.added)}${j.kind==="selfcheck"?` · ошибок найдено ${num(j.mistakes||0)}`:""} · запросов ${num(j.done)} из ${num(total)} · токенов ${num(j.tokens)}`;
      $("tjob-bar").style.width=`${Math.round(j.done/total*100)}%`;
      $("teacher-stop").hidden=!running;$("tjob-error").hidden=!j.error;$("tjob-error").textContent=j.error||"";
      $("teacher-job").dataset.state=j.state;
    }
    renderFlow();
    clearTimeout(teacherTimer);if(running)teacherTimer=setTimeout(refreshTeacher,3000);
  }catch(e){showError(e.message)}
}
for(const b of document.querySelectorAll("[data-run]"))b.onclick=()=>act(b,async()=>{
  const kind=b.dataset.run,count=parseInt($(COUNT_FIELD[kind]).value,10);
  const plan=await post("teacher-estimate",{kind,count});
  if(!plan.fits){showError(`Нужно примерно ${num(plan.tokens)} токенов: это больше лимита. Уменьшите количество или поднимите лимит.`);return}
  const privacy=plan.sends_memory?`\n\nВнимание: ${num(plan.count)} фактов из памяти Yorika будут отправлены в Cloud.ru.`:"";
  const who=plan.models&&plan.models.length>1?` Учителя: ${plan.models.join(", ")}.`:"";
  if(!confirm(`Учитель сделает ${num(plan.requests)} запросов к Cloud.ru, примерно ${num(plan.tokens)} токенов (не больше лимита ${num(plan.per_run_limit)}). В этом месяце уже ${num(plan.used_this_month)}.${who}${privacy}\n\nЗапустить?`))return;
  const topics=kind==="generate"?$("gen-topics").value.split("\n").map(t=>t.trim()).filter(Boolean):null;
  await post("teacher-start",{kind,count:plan.count,confirm:true,topics:topics&&topics.length?topics:null});
  await refreshTeacher();
});
$("save-models").onclick=e=>act(e.currentTarget,async()=>{await post("teacher-models",{models:$("models").value.split("\n").map(m=>m.trim()).filter(Boolean)});await refreshTeacher()});
// "До 10 000": the teacher writes what is missing to the goal, at most 2000 per run; you still approve in batches.
$("fill-goal").onclick=()=>{
  const c=slStatus&&slStatus.counts;if(!c)return;
  const missing=Math.max(0,c.needed-c.ready-c.unrated);
  $("gen-count").value=Math.max(5,Math.min(2000,Math.ceil(missing/5)*5));
  $("fill-goal").textContent=missing?`Не хватает ${num(missing)} · за раз до 2 000`:"Цель уже набрана";
};
$("teacher-stop").onclick=e=>act(e.currentTarget,async()=>{await post("teacher-stop");await refreshTeacher()});
$("save-limits").onclick=e=>act(e.currentTarget,async()=>{await post("teacher-limits",{per_run_tokens:parseInt($("limit-run").value,10),monthly_tokens:parseInt($("limit-month").value,10)});await refreshTeacher()});

// ---- night cycle ----
async function refreshNight(){
  try{
    const n=await api("/api/training/night-status"),s=n.settings;
    $("night-on").checked=s.enabled;$("night-time").value=s.time;$("night-hours").value=s.hours;$("night-tokens").value=s.teacher_tokens;$("night-play").value=s.selfplay;
    for(const box of document.querySelectorAll("input[name=night-size]"))box.checked=(s.sizes||["s"]).includes(box.value);
    syncNight();$("night-note").textContent=n.note+(n.windows?"":" Ставится в планировщик Windows.");
    const log=$("night-log");log.replaceChildren();
    if(!n.log.length)log.append(el("li","empty-line","Ночей ещё не было."));
    for(const entry of n.log.slice().reverse()){
      const li=el("li");li.append(el("strong",null,new Date(entry.started).toLocaleString("ru-RU",{day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"})));
      const ul=el("ul");for(const st of entry.steps)ul.append(el("li",null,`${{collect:"Сбор",teacher:"Учитель",export:"Набор",train:"Обучение",cycle:"Цикл"}[st.step]||st.step}: ${st.result}`));
      li.append(ul);log.append(li);
    }
  }catch(e){showError(e.message)}
}
function syncNight(){
  const tokens=parseInt($("night-tokens").value,10)||0;
  $("nl-teacher").textContent=tokens?`до ${num(tokens)} токенов`:"выключен";
  const sizes=[...document.querySelectorAll("input[name=night-size]:checked")].map(i=>i.value.toUpperCase());
  $("nl-hours").textContent=`${String($("night-hours").value).replace(".",",")} ч`+(sizes.length>1?` · ${sizes.join("/")}`:"");
  $("night-line").classList.toggle("on",$("night-on").checked);
}
for(const id of ["night-tokens","night-hours","night-on"])$(id).addEventListener("input",syncNight);
for(const box of document.querySelectorAll("input[name=night-size]"))box.addEventListener("change",syncNight);
$("night-save").onclick=e=>act(e.currentTarget,async()=>{
  const tokens=parseInt($("night-tokens").value,10)||0;
  if($("night-on").checked&&tokens&&!confirm(`Разрешить учителю тратить до ${num(tokens)} токенов Cloud.ru каждую ночь?`))return;
  await post("night-settings",{enabled:$("night-on").checked,time:$("night-time").value,hours:parseFloat($("night-hours").value),teacher_tokens:tokens,selfplay:parseInt($("night-play").value,10),sizes:[...document.querySelectorAll("input[name=night-size]:checked")].map(i=>i.value)});
  await refreshNight();
});

// ---- future: horizon, steps 07–19, safety ----
const GROW=[
 {n:"07",t:"Инструменты",d:"Калькулятор, время и поиск по памяти. Урок есть, модель сама пишет вызов, результат считает программа.",s:"partial"},
 {n:"08",t:"Самопроверка ответа",d:"Черновик Yorika проверяет учитель, ошибки с исправлением идут в опыт.",s:"partial"},
 {n:"09",t:"Знание своих границ",d:"Отдельный экзамен честности у каждой версии и уроки «не знаю».",s:"partial"},
 {n:"10",t:"Память в навыки",d:"Учитель делает примеры из фактов памяти, в обучение они идут после вашей оценки.",s:"partial"},
 {n:"11",t:"Уроки на слабых местах",d:"Самоигра уже даёт новые вопросы там, где Yorika ошиблась.",s:"partial"},
 {n:"12",t:"Команда специалистов",d:"Маленькие модели для речи, памяти и плана, для вас одна Yorika.",s:"research"},
 {n:"13",t:"Модель мира",d:"Предсказывает последствия действий и учится на ошибках прогноза.",s:"research"},
 {n:"14",t:"Умение учиться",d:"Измеряется и улучшается скорость освоения новой задачи.",s:"research"},
 {n:"15",t:"Изменение своего устройства",d:"Предлагает изменения нейросети и доказывает их цифрами.",s:"research"},
 {n:"16",t:"Гипотезы и эксперименты",d:"Сама ставит опыты над своим обучением, выводы проверяете вы.",s:"research"},
 {n:"17",t:"Обучение в облаке",d:"Тяжёлые эксперименты в Cloud.ru с лимитом и вашим подтверждением.",s:"plan"},
 {n:"18",t:"Уровни свободы и остановка",d:"Новая версия включается только вами, всё останавливается кнопкой «Стоп всё».",s:"partial"},
 {n:"19",t:"Независимые экзамены",d:"Экзамен на невиданном, пересдача старых экзаменов и слепая проверка вами.",s:"partial"},
];
const HORIZON=[
 {when:"Сейчас",sub:"2026",items:[
  {i:"brain",t:"Своя нейросеть",d:"Учится на вашем ноутбуке, в 9 раз быстрее, чем раньше.",s:"ok"},
  {i:"teacher",t:"Учитель и самоигра",d:"Cloud.ru пишет и проверяет примеры с вашего разрешения.",s:"ok"},
  {i:"moon",t:"Ночной цикл",d:"Учится ночью, утром предлагает версию.",s:"ok"},
  {i:"exam",t:"Экзамен",d:"Каждая версия сдаёт экзамен на невиданном.",s:"ok"}]},
 {when:"5 лет",sub:"учится постоянно",items:[
  {i:"brain",t:"Своя большая модель",d:"Уже можно 5, 25 или 50 млн параметров и песочница размеров. Дальше сотни миллионов.",s:"partial"},
  {i:"users",t:"Несколько учителей",d:"До 4 моделей Cloud.ru, по каждой теме зовётся та, кого вы одобряете чаще.",s:"partial"},
  {i:"eye",t:"Видит, слышит, говорит",d:"Голос, камера и экран только по разрешению.",s:"research"}]},
 {when:"15 лет",sub:"улучшает себя",items:[
  {i:"pen",t:"Проектирует следующую версию",d:"Новая архитектура в песочнице и доказательство цифрами.",s:"research"},
  {i:"globe",t:"Модель мира",d:"Причины и следствия, планы на недели вперёд.",s:"research"},
  {i:"swarm",t:"Рой Yorika",d:"Копии-специалисты сводятся в одну личность и память.",s:"research"}]},
 {when:"50 лет",sub:"за пределами сегодняшнего",items:[
  {i:"infinity",t:"Учится всю жизнь",d:"Непрерывно и без забывания.",s:"dream"},
  {i:"bulb",t:"Открывает новое",d:"Гипотезы, проверенные людьми.",s:"dream"},
  {i:"move",t:"Переезжает на любое железо",d:"Та же память и тот же характер.",s:"dream"}]},
];
const GUARD=[
 {i:"exam",t:"Экзамены на невиданном",d:"Каждая версия проверяется на задачах, которых не видела при обучении."},
 {i:"sliders",t:"Больше силы — больше контроля",d:"Лимиты токенов, журнал ночей и кнопка «Стоп всё» всегда у вас."},
 {i:"lock",t:"Ваши данные — ваши",d:"Всё видно и всё можно удалить. Без согласия ничего не собирается."},
];
const CHIPS={partial:["chip chip-ok","Работает частично"],plan:["chip","В планах"],research:["chip chip-research","Исследование"],ok:["chip chip-ok","Уже есть"],dream:["chip chip-dream","Открытый вопрос науки"]};
const chip=s=>{const c=el("span");[c.className,c.textContent]=CHIPS[s];return c};
function renderFuture(){
  const box=$("grow-cards");box.replaceChildren();
  for(const g of GROW){
    const card=el("article","grow-card");card.dataset.status=g.s;
    const head=el("header");head.append(el("span","grow-num",g.n),el("h3",null,g.t));
    card.append(head,el("p",null,g.d),chip(g.s));box.append(card);
  }
  const list=$("timeline");list.replaceChildren();
  HORIZON.forEach((h,k)=>{
    const li=el("li","stage");li.style.setProperty("--k",k);
    const head=el("div","stage-head");head.append(el("span","stage-dot"),el("strong",null,h.when),el("small",null,h.sub));
    const items=el("div","stage-items");
    for(const it of h.items){
      const card=el("article","stage-card");card.dataset.status=it.s;
      const top=el("header"),ic=el("span","card-ic");ic.append(icon(it.i));
      top.append(ic,el("h3",null,it.t));card.append(top,el("p",null,it.d),chip(it.s));items.append(card);
    }
    li.append(head,items);list.append(li);
  });
  const g=$("guard-cards");g.replaceChildren();
  for(const it of GUARD){const card=el("article","guard-card"),ic=el("span","card-ic");ic.append(icon(it.i));card.append(ic,el("h3",null,it.t),el("p",null,it.d));g.append(card)}
}

renderFuture();fillIcons();syncMode();refresh();
let startTab="train";try{startTab=location.hash.slice(1)||localStorage.getItem("yorika.training.tab")||"train"}catch{}
openTab(startTab);
if(!["exp"].includes(startTab))api("/api/training/sl-status").then(r=>{slStatus=r;renderCounts(r.counts);renderFlow()}).catch(()=>{});
if(startTab!=="teacher")api("/api/training/teacher-status").then(r=>{tStatus=r;renderFlow()}).catch(()=>{});
addEventListener("hashchange",()=>openTab(location.hash.slice(1)));

let continualProposal=null;
async function refreshContinual(){
 try{
  const r=await api("/api/training/continual-status");
  $("continual-enabled").checked=r.settings.enabled;
  $("continual-device").value=r.settings.device;
  continualProposal=r.proposal;
  $("continual-activate").hidden=!continualProposal||r.busy;
  const names={disabled:"Выключено",idle:"Новых проверенных уроков нет",proposed:"Кандидат прошёл проверки",rejected:"Ухудшение: предыдущие веса сохранены",failed:"Цикл завершился с ошибкой",running:"Обучение",deferred:"Ожидает завершения другого обучения"};
  const last=r.last;
  $("continual-state").textContent=(r.busy?"Идёт дообучение…":last?(names[last.state]||last.state):"Циклов ещё не было")+(last?.error?". "+last.error:"")+". Активная модель меняется по вашему выбору.";
 }catch(e){$("continual-state").textContent=e.message}
}
$("continual-save").onclick=e=>act(e.currentTarget,async()=>{
 await post("continual-settings",{enabled:$("continual-enabled").checked,device:$("continual-device").value});await refreshContinual();
});
$("continual-run").onclick=e=>act(e.currentTarget,async()=>{await post("continual-run");await refreshContinual()});
$("continual-stop").onclick=e=>act(e.currentTarget,async()=>{await post("continual-stop");await refreshContinual()});
$("continual-activate").onclick=e=>act(e.currentTarget,async()=>{await post("continual-activate",{id:continualProposal});await refreshContinual();await refresh()});
refreshContinual();
setInterval(()=>{if(!document.hidden)refreshContinual()},10000);
