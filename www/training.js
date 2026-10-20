// «Обучение» page: talks to /api/training/* served by scripts/yorika-tray.ps1.
import {api} from "./api.js";

const $=id=>document.getElementById(id);
// ---- icons: one stroke style, filled into every [data-icon] ----
const ICONS={
 crown:["M3 7l4 4 5-7 5 7 4-4-2 12H5z","M5 21h14"],
 egg:["M12 2C8 2 5 9 5 14a7 7 0 0 0 14 0c0-5-3-12-7-12z","M9 14l2-2 2 2 2-2"],
 gauge:["M12 14l4-4","M3.3 18a10 10 0 1 1 17.4 0","M12 14a1 1 0 1 0 0 .01"],
 comet:["M14 10 4 20","M10 4l10 10","M14.5 9.5a5 5 0 1 1-1 7"],
 seed:["M12 22V12","M12 12C12 7 8 4 3 4c0 5 4 8 9 8z","M12 14c0-4 3-7 8-7 0 4-3 7-8 7z"],
 bubble:["M21 11.5a8.4 8.4 0 0 1-9 8.4 9 9 0 0 1-3.9-.9L3 21l1.9-5.1A8.4 8.4 0 0 1 12 3a8.4 8.4 0 0 1 9 8.5z","M8 11h.01M12 11h.01M16 11h.01"],
 dna:["M7 2c0 6 10 6 10 12s-10 6-10 8","M17 2c0 6-10 6-10 12s10 6 10 8","M8 6h8M8 18h8M10 10h4M10 14h4"],
 hex:["M12 2l8.7 5v10L12 22l-8.7-5V7z","M12 8l3.5 2v4L12 16l-3.5-2v-4z"],
 stairs:["M3 21h5v-5h5v-5h5V6h3","M3 21V3"],
 flask:["M9 2h6","M10 2v6L4 19a2 2 0 0 0 1.8 3h12.4a2 2 0 0 0 1.8-3L14 8V2","M7 15h10"],
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
 puzzle:["M19.4 15a1.6 1.6 0 0 0 0 3.2H21V22h-4v-1.6a1.6 1.6 0 0 0-3.2 0V22H3V11h1.6a1.6 1.6 0 0 0 0-3.2H3V4h7v1.6a1.6 1.6 0 0 0 3.2 0V4H21v11z"],
 pause:["M8 5v14","M16 5v14"],
 calendar:["M3 5h18v16H3z","M3 10h18","M8 3v4M16 3v4","M7 14h2M11 14h2M15 14h2M7 18h2M11 18h2"],
 branch:["M6 3v12","M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6z","M6 21a3 3 0 1 0 0-6 3 3 0 0 0 0 6z","M18 9a9 9 0 0 1-9 9"],
 hourglass:["M6 2h12","M6 22h12","M7 2v4a5 5 0 0 0 10 0V2","M7 22v-4a5 5 0 0 1 10 0v4"],
 code:["M16 18l6-6-6-6","M8 6l-6 6 6 6","M14 4l-4 16"],
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
const KINDS={quick:"урок",sleep:"сон",evolution:"эволюция",merge:"скрещена"};
const VERDICT={rolled_back:["chip-warn","откат"],waiting:["chip-next","ждёт вас"],activated:["chip-ok","включена сама"]};
const mb=b=>b?(b/1048576).toFixed(1).replace(".",",")+" МБ":"—";
const fx=v=>v==null?"—":Number(v).toFixed(3);
const archBody=()=>{const a={};if($("arch-loops").checked)a.loops=3;if($("arch-experts").checked)a.experts=4;if($("arch-memory").checked)a.memory=256;
  if($("arch-ssm").checked)a.mixer="hybrid";if($("arch-liquid").checked)a.mixer="liquid";if($("arch-dendrites").checked)a.dendrites=4;
  if($("arch-hopfield").checked)a.hopfield=256;if($("arch-fast").checked)a.fast=true;return a};
// Pairs that replace the same part of a block: choosing one clears the other.
for(const [a,b] of [["arch-ssm","arch-liquid"],["arch-dendrites","arch-experts"]]){
  $(a).addEventListener("change",()=>{if($(a).checked)$(b).checked=false});$(b).addEventListener("change",()=>{if($(b).checked)$(a).checked=false})}
const MIXER={ssm:"Mamba",liquid:"жидкие нейроны",hybrid:"Mamba + внимание"};
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
    const a=r.arch||{};
    if(a.loops>1)chips.append(Object.assign(el("span","chip chip-next",`думает ×${a.loops}`),{title:"Слои проходятся несколько раз; на трудном вопросе дольше"}));
    if(a.experts)chips.append(Object.assign(el("span","chip chip-next",`эксперты ×${a.experts}`),{title:"На каждое слово работают 2 эксперта из "+a.experts}));
    if(a.memory)chips.append(Object.assign(el("span","chip chip-next","память "+a.memory),{title:"Ячейки памяти внутри сети"}));
    if(a.mixer)chips.append(Object.assign(el("span","chip chip-next",MIXER[a.mixer]),{title:"Чем слова смешиваются в слоях"}));
    if(a.dendrites)chips.append(Object.assign(el("span","chip chip-next","дендриты"),{title:"Тема разговора включает свои группы нейронов"}));
    if(a.hopfield)chips.append(Object.assign(el("span","chip chip-next","Хопфилд "+a.hopfield),{title:"Ассоциативная память: по части вспоминает целое"}));
    if(a.fast)chips.append(Object.assign(el("span","chip chip-next","быстрые веса"),{title:"Связи из текста в контексте запоминаются на лету"}));
    if(r.forward_forward)chips.append(Object.assign(el("span","chip chip-next","Forward-Forward"),{title:"Разгон: слои различают настоящий ответ и перемешанный в долях "+r.forward_forward.separation.join(", ")}));
    if(KINDS[r.kind])chips.append(el("span","chip",KINDS[r.kind]));
    if(r.grown_from)chips.append(Object.assign(el("span","chip chip-next",`выросла · ${r.layers} слоёв`),{title:"Выросла из версии "+when(r.grown_from)}));
    if(r.logic){const lv=r.logic.levels||{},passed=Object.keys(lv).filter(k=>lv[k]>=.8).length;chips.append(Object.assign(el("span","chip "+(passed?"chip-ok":""),`логика ур. ${passed}`),{title:"Уровни логики, сданные на 80%: "+Object.entries(lv).map(([k,v])=>`${k}: ${Math.round(v*100)}%`).join(", ")}))}
    if(r.verdict&&VERDICT[r.verdict.result])chips.append(Object.assign(el("span","chip "+VERDICT[r.verdict.result][0],VERDICT[r.verdict.result][1]),{title:r.verdict.why||""}));
    if(r.compressed)chips.append(Object.assign(el("span","chip chip-ok","4 бита"),{title:`Сжата: ${mb(r.compressed.bytes)} вместо ${mb(r.compressed.original_bytes)}, экзамен ${fx(r.compressed.exam_before)} → ${fx(r.compressed.exam_after)}`}));
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
    if(r.mode==="long"&&r.has_best&&!LIVE.has(r.state)){
      const more=el("div","version-more");
      if(r.arch&&r.arch.lab){
        const g=el("button","ghost small","Вырастить +2 слоя");g.title="Новая версия глубже на 2 слоя: начинает с того же, что знает эта, и учится дальше";
        g.onclick=()=>{if(confirm(`Вырастить версию на 2 слоя и учить дальше на «${r.dataset}»? Эта версия не изменится.`))act_(g,()=>post("grow",{id:r.id,dataset:r.dataset,device:r.device||radio("device"),steps:parseInt($("steps").value,10),hours:parseFloat($("hours").value)}))};
        more.append(g);
      }
      const c=el("button","ghost small",r.compressed?"Сжать заново":"Сжать в 4 бита");c.title="Копия в 4 раза меньше для ответов; экзамен покажет, чего это стоило";
      c.onclick=()=>act(c,async()=>{c.textContent="Сжимаю…";const x=await post("compress",{id:r.id});alert(`Сжато: ${mb(x.bytes)} вместо ${mb(x.original_bytes)}. Экзамен ${fx(x.exam_before)} → ${fx(x.exam_after)} (ниже — лучше).`);await refresh()});
      more.append(c);li.append(more);
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
    renderReady(s);renderData(s);renderJob(s.runs);renderVersions(s);renderFlow();if(!$("pane-brain").hidden)renderLogic();
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
  if(mode==="sandbox"&&radio("sandbox-kind")==="evolution")$("arch-box").hidden=true;
}
const startRun=(button,mode)=>act_(button,()=>{
  if(mode==="sandbox"){
    const common={dataset:$("long-file").value,device:radio("device"),steps:parseInt($("steps").value,10),hours:parseFloat($("hours").value)};
    if(radio("sandbox-kind")==="evolution")return post("evolve",{...common,population:parseInt($("population").value,10)});
    const sizes=[...document.querySelectorAll("input[name=series-size]:checked")].map(i=>i.value);
    return post("series",{...common,sizes,arch:archBody(),ff:$("arch-ff").checked});
  }
  const body={mode,device:radio("device")};
  if(mode!=="pilot"){body.arch=archBody();body.ff=$("arch-ff").checked}
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
const syncKind=()=>{const evo=radio("sandbox-kind")==="evolution";$("evolution-box").hidden=!evo;$("size-box").hidden=evo;$("arch-box").hidden=evo||!["long","pretrain","sandbox"].includes(radio("mode"))};
for(const r of document.querySelectorAll("input[name=sandbox-kind]"))r.onchange=syncKind;
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
$("merge").onclick=e=>{
  const ids=[$("cmp-a").value,$("cmp-b").value];
  if(!ids[1]||ids[0]===ids[1]){showError("Выберите две разные версии");return}
  if(confirm("Скрестить две версии: усреднить их веса? Получится новая версия, она сдаст экзамены. Родители не изменятся."))act_(e.currentTarget,()=>post("merge",{ids}));
};
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
const TABS=["train","brain","evo","exp","teacher","night","future"];
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
  if(name==="brain")refreshBrain();
  if(name==="evo")refreshEvo();
  if(name==="train")refreshSelfcheck();
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
  const SRC={selfplay:"самоигра",teacher:"от учителя",honesty:"«не знаю»",tools:"инструменты",selfcheck:"самопроверка",memory:"из памяти",logic:"логика ✓"};
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
const EMPTY={unrated:"Неоценённых примеров нет. Включите сбор и нажмите «Собрать из чата» или попросите учителя написать примеры.",uncertain:"Неоценённых примеров нет.",teacher:"Учитель ещё ничего не проверял: вкладка «Учитель» → «Проверить ответы».",surprise:"Удивление считается по активной или последней обученной версии. Пока удивляться нечему."};
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

// ---- schedule: when to study, what each day does, the study cycle ----
const DAY_NAMES=["Пн","Вт","Ср","Чт","Пт","Сб","Вс"],DAY_FULL=["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"];
const PRESET={night:Array(7).fill("0"+"1".repeat(6)+"0".repeat(17)),day:Array(7).fill("0".repeat(10)+"1".repeat(6)+"0".repeat(8)),evening:Array(7).fill("0".repeat(18)+"1".repeat(4)+"00"),weekend:[...Array(5).fill("0".repeat(24)),"1".repeat(24),"1".repeat(24)],always:Array(7).fill("1".repeat(24)),clear:Array(7).fill("0".repeat(24))};
const ACT_ICON={sleep:"moon",distill:"hourglass",search:"branch",swarm:"swarm",evolution:"flask",fresh:"sparkles",rest:"pause"};
let grid=PRESET.night.slice(),nightSettings=null,activities={};
function renderHeat(){
  const box=$("heat");box.replaceChildren();
  const now=new Date(),today=(now.getDay()+6)%7,hour=now.getHours();
  box.append(el("span","heat-corner"));
  for(let h=0;h<24;h++)box.append(el("span","heat-h",h%3===0?String(h).padStart(2,"0"):""));
  for(let d=0;d<7;d++){
    box.append(el("span","heat-d"+(d===today?" today":""),DAY_NAMES[d]));
    for(let h=0;h<24;h++){
      const c=el("button","heat-c"+(grid[d][h]==="1"?" on":"")+(d===today&&h===hour?" now":""));c.type="button";
      c.dataset.d=d;c.dataset.h=h;c.setAttribute("aria-label",`${DAY_FULL[d]}, ${h}:00 — ${grid[d][h]==="1"?"учёба":"отдых"}`);c.setAttribute("aria-pressed",grid[d][h]==="1");
      box.append(c);
    }
  }
  const total=grid.reduce((n,r)=>n+[...r].filter(x=>x==="1").length,0);
  $("heat-sum").textContent=`${total} ч учёбы в неделю`;
  $("heat-now").textContent=grid[today][hour]==="1"?"сейчас: часы учёбы":"сейчас: отдых";
  $("heat-now").classList.toggle("on",grid[today][hour]==="1");
}
// Paint by pressing and dragging; the first cell decides whether the stroke paints or erases.
let painting=null;
const paint=c=>{const d=+c.dataset.d,h=+c.dataset.h,row=grid[d].split("");row[h]=painting;grid[d]=row.join("");c.classList.toggle("on",painting==="1");c.setAttribute("aria-pressed",painting==="1")};
$("heat").addEventListener("pointerdown",e=>{const c=e.target.closest(".heat-c");if(!c)return;e.preventDefault();painting=grid[+c.dataset.d][+c.dataset.h]==="1"?"0":"1";paint(c)});
$("heat").addEventListener("pointerover",e=>{const c=e.target.closest(".heat-c");if(c&&painting)paint(c)});
addEventListener("pointerup",()=>{if(painting){painting=null;renderHeat()}});
$("heat").addEventListener("keydown",e=>{const c=e.target.closest(".heat-c");if(c&&(e.key===" "||e.key==="Enter")){e.preventDefault();painting=grid[+c.dataset.d][+c.dataset.h]==="1"?"0":"1";paint(c);painting=null;renderHeat();$("heat").querySelector(`[data-d="${c.dataset.d}"][data-h="${c.dataset.h}"]`).focus()}});
for(const b of document.querySelectorAll("[data-preset]"))b.onclick=()=>{grid=PRESET[b.dataset.preset].slice();renderHeat()};
$("heat-save").onclick=e=>act(e.currentTarget,async()=>{await post("schedule-set",{grid,enforce:$("heat-enforce").checked});await refreshNight()});
function renderWeek(){
  const box=$("week-plan");box.replaceChildren();const today=(new Date().getDay()+6)%7;
  nightSettings.week.forEach((a,d)=>{
    const card=el("label","day-card"+(d===today?" today":"")),ic=el("span","day-ic");ic.append(icon(ACT_ICON[a]||"sparkles"));
    const sel=el("select","field small-field");sel.dataset.day=d;sel.setAttribute("aria-label","Занятие: "+DAY_FULL[d]);
    for(const [k,v] of Object.entries(activities))sel.append(option(k,v));sel.value=a;
    sel.onchange=()=>{nightSettings.week[d]=sel.value;ic.replaceChildren(icon(ACT_ICON[sel.value]||"sparkles"));card.dataset.act=sel.value;syncNight()};
    card.dataset.act=a;card.append(el("b",null,DAY_NAMES[d]),ic,sel);box.append(card);
  });
}
async function refreshNight(){
  try{
    const n=await api("/api/training/night-status"),s=nightSettings=n.settings;activities=n.activities;
    grid=n.schedule.grid.slice();$("heat-enforce").checked=n.schedule.enforce;renderHeat();renderWeek();
    $("night-on").checked=s.enabled;$("night-tokens").value=s.teacher_tokens;$("night-play").value=s.selfplay;$("night-lives").value=s.lives;
    $("night-curiosity").checked=s.curiosity!==false;$("night-programs").checked=s.programs!==false;$("night-evolve").value=String(s.evolve||0);
    for(const box of document.querySelectorAll("input[name=night-size]"))box.checked=(s.sizes||["s"]).includes(box.value);
    syncNight();$("night-note").textContent=n.note+(n.windows?"":" Ставится в планировщик Windows.");
    const log=$("night-log");log.replaceChildren();
    if(!n.log.length)log.append(el("li","empty-line","Учёбы по расписанию ещё не было."));
    for(const entry of n.log.slice().reverse()){
      const li=el("li");li.append(el("strong",null,new Date(entry.started).toLocaleString("ru-RU",{day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"})));
      const ul=el("ul");for(const st of entry.steps)ul.append(el("li",null,`${{collect:"Сбор",teacher:"Учитель",curiosity:"Любопытство",sim:"Мир задач",programs:"Программы",resume:"Продолжение",export:"Набор",train:"Обучение",compress:"Сжатие",cycle:"Цикл"}[st.step]||st.step}: ${st.result}`));
      li.append(ul);log.append(li);
    }
  }catch(e){showError(e.message)}
}
function syncNight(){
  const tokens=parseInt($("night-tokens").value,10)||0;
  $("nl-teacher").textContent=tokens?`до ${num(tokens)} токенов`:"выключен";
  const lives=parseInt($("night-lives").value,10)||0;$("nl-lives").textContent=lives?`${num(lives)} жизней`:"выключен";
  $("nl-programs").textContent=$("night-programs").checked?"поиск":"выключен";
  if(nightSettings)$("nl-hours").textContent=(activities[nightSettings.week[(new Date().getDay()+6)%7]]||"—").toLowerCase();
  $("night-line").classList.toggle("on",$("night-on").checked);
}
for(const id of ["night-tokens","night-on","night-lives","night-programs"])$(id).addEventListener("input",syncNight);
$("night-save").onclick=e=>act(e.currentTarget,async()=>{
  const tokens=parseInt($("night-tokens").value,10)||0,s=nightSettings||{time:"02:00",hours:4,week:null};
  if($("night-on").checked&&tokens&&!confirm(`Разрешить учителю тратить до ${num(tokens)} токенов Cloud.ru за каждый блок учёбы?`))return;
  await post("night-settings",{enabled:$("night-on").checked,time:s.time,hours:s.hours,teacher_tokens:tokens,selfplay:parseInt($("night-play").value,10),
    sizes:[...document.querySelectorAll("input[name=night-size]:checked")].map(i=>i.value),sleep:true,curiosity:$("night-curiosity").checked,
    evolve:parseInt($("night-evolve").value,10),week:s.week,lives:parseInt($("night-lives").value,10)||0,programs:$("night-programs").checked});
  await refreshNight();
});

// ---- brain: who answers, living learning, logic, memory, curiosity, thinking ----
const LIVE_EVENT={start:"урок начат",rolled_back:"откат",activated:"включена сама",waiting:"ждёт вас"};
let brainTimer=null;
function renderLogic(){
  const runs=status?status.runs.filter(r=>r.mode==="long"&&r.has_best):[];
  const ref=(status&&status.active&&runs.find(r=>r.id===status.active.run))||runs[0];
  const box=$("logic-bars");box.replaceChildren();
  const lv=ref&&ref.logic&&ref.logic.levels;
  for(const k of ["1","2","3","4","5"]){
    const v=lv?lv[k]||0:0,row=el("div","logic-row"+(lv&&v>=.8?" ok":"")),bar=el("span","exam-bar"),fill=el("i");
    fill.style.width=`${Math.round(v*100)}%`;bar.append(fill);
    row.append(el("b",null,`Ур. ${k}`),bar,el("small",null,lv?`${Math.round(v*100)}%`:"—"));box.append(row);
  }
  $("logic-note").textContent=!ref?"Обучите версию: экзамен логики она сдаёт после обучения.":!lv?`У версии от ${when(ref.id)} экзамена логики ещё не было.`:`Версия от ${when(ref.id)}. Сдано, если решено 80%. Следующая цель: уровень ${ref.logic.frontier}.`;
  const sel=$("think-run"),keep=sel.value;sel.replaceChildren();
  if(!runs.length)sel.append(option("","Обученных версий нет"));
  for(const r of runs)sel.append(option(r.id,`${when(r.id)}${status.active&&status.active.run===r.id?" · активная":""}`));
  if([...sel.options].some(o=>o.value===keep))sel.value=keep;
  $("think-go").disabled=!runs.length;
}
async function refreshBrain(){
  try{
    if(!status)status=await api("/api/training/status");
    const b=await api("/api/training/brain-status"),e=b.engine,c=b.continual,s=c.settings,m=c.memory;
    if(!$("pane-brain").contains(document.activeElement)){
      document.querySelector(`input[name=engine][value=${e.engine}]`).checked=true;
      document.querySelector(`input[name=drafts][value="${e.drafts}"]`).checked=true;$("engine-q4").checked=e.compressed;
      $("live-on").checked=s.enabled;$("live-auto").checked=s.auto_activate;$("live-min").value=s.min_new;$("live-min-time").value=s.minutes;
    }
    $("engine-note").textContent=e.engine==="own"?`Сейчас отвечает своя модель: активная версия${status.active?" от "+when(status.active.run):""}.`:"Сейчас отвечает Cloud.ru.";
    $("live-pending").textContent=`Новых одобренных примеров: ${num(c.pending)} из ${num(s.min_new)}`;
    const log=$("live-log");log.replaceChildren();
    for(const x of c.log.slice().reverse().slice(0,6)){
      const li=el("li",x.event==="rolled_back"?"warn":x.event==="activated"?"ok":"");
      li.append(el("b",null,LIVE_EVENT[x.event]||x.event),` · ${new Date(x.at).toLocaleString("ru-RU",{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"})}`,x.why?` · ${x.why}`:x.new!=null?` · новых ${x.new}, повтор ${x.replay}`:"");
      log.append(li);
    }
    if(!c.log.length)log.append(el("li","empty-line","Уроков ещё не было."));
    $("mem-ready").textContent=num(m.ready);$("mem-strong").textContent=num(m.strong);$("mem-faded").textContent=num(m.faded);$("mem-half").textContent=`${m.half_life_days} дней`;
    const w=$("wishes");w.replaceChildren();
    for(const x of b.wishes){
      const li=el("li");li.append(el("span",null,x.what));
      if(x.action)li.append(el("span","chip "+(x.free?"chip-ok":""),x.free?"бесплатно":"нужен учитель"));
      w.append(li);
    }
    const cur=b.curiosity,running=cur&&cur.state==="running";
    $("cur-now").disabled=running;$("cur-now").textContent=running?"Занимается…":"Позаниматься сейчас";
    $("cur-last").textContent=cur?(running?"Решает задачи на краю своих сил…":`Последний раз: ${cur.state==="failed"?"не получилось":""} ${cur.result||""}`):"Ещё не занималась. Ночью это происходит само, если включено.";
    renderLogic();renderAutopilot(b.autopilot);renderMap();renderPlan(b.plans);renderSkills(b.skills);renderWorld(b.sim);
    const planLive=b.plans.plan&&["preparing","running"].includes(b.plans.plan.state),simLive=b.sim.job&&b.sim.job.state==="running";
    clearTimeout(brainTimer);if(running||planLive||simLive)brainTimer=setTimeout(refreshBrain,4000);
  }catch(e){showError(e.message)}
}

// ---- autopilot, a look inside, superpowers, program skills, the game world ----
function renderAutopilot(a){
  $("ap-on").checked=a.on;$("ap-state").textContent=a.on?"Включён":"Выключен";$("autopilot").classList.toggle("on",a.on);
  $("ap-line").textContent=a.on?`Сегодня по плану: ${a.today.toLowerCase()}. Часов учёбы в неделю: ${a.schedule.hours_week}${a.schedule.now?", сейчас учится":""}.`:"Одна кнопка: собирает опыт, учится после разговоров, тренируется и ищет навыки в часы учёбы.";
  const ul=$("ap-parts");ul.replaceChildren();
  for(const p of a.parts){const li=el("li",p.on?"on":"");li.append(el("i"),p.title);if(p.optional)li.title="Это решаете вы отдельно";ul.append(li)}
}
$("ap-on").onchange=e=>{const on=e.target.checked;act(e.target,async()=>{const r=await post("autopilot",{enabled:on});if(r.notes&&r.notes.length)showError(r.notes.join(". "));await refreshBrain()}).then(r=>{if(r===null)e.target.checked=!on})};

function mapRef(){
  const runs=status?status.runs.filter(r=>r.mode==="long"&&r.has_best):[];
  return (status&&status.active&&runs.find(r=>r.id===status.active.run))||runs[0];
}
function renderMap(){
  const svg=$("map-svg"),ref=mapRef(),rep=ref&&ref.introspection,ns="http://www.w3.org/2000/svg";svg.replaceChildren();
  const mk=(tag,attrs,text,parent=svg)=>{const n=document.createElementNS(ns,tag);for(const k in attrs)n.setAttribute(k,attrs[k]);if(text!=null)n.textContent=text;parent.append(n);return n};
  $("map-look").disabled=!ref;
  $("map-sub").textContent=ref?`Версия от ${when(ref.id)}. Каждый слой выключается по очереди: насколько хуже без него экзамен.`:"Обучите версию, и здесь появится её карта.";
  const advice=$("map-advice");advice.replaceChildren();
  if(!rep||rep.error){mk("text",{x:320,y:130,"text-anchor":"middle",class:"chart-empty"},rep&&rep.error?rep.error:ref?"Нажмите «Заглянуть»: замер займёт пару минут":"Карта появится после первого обучения");return}
  const defs=mk("defs",{});const g=mk("linearGradient",{id:"layer-fill",x1:0,x2:1,y1:0,y2:0},null,defs);
  mk("stop",{offset:0,class:"map-stop-a"},null,g);mk("stop",{offset:1,class:"map-stop-b"},null,g);
  const blocks=rep.blocks,n=blocks.length,top=24,h=Math.min(34,(212)/Math.max(1,n)),max=Math.max(...blocks.map(b=>b.contribution||0),0.0001);
  mk("text",{x:24,y:16,class:"map-label"},"слои: вклад в экзамен");
  blocks.slice().reverse().forEach((b,i)=>{
    const y=top+i*h,w=b.contribution==null?30:Math.max(6,(b.contribution/max)*200);
    mk("text",{x:24,y:y+(h-6)/2+4,class:"map-text"},`Слой ${b.layer}`);
    mk("rect",{x:86,y,width:200,height:h-6,rx:6,class:"map-track"});
    const bar=mk("rect",{x:86,y,width:w,height:h-6,rx:6,class:"map-bar"+(b.contribution!=null&&b.contribution<0.002?" weak":"")});
    bar.style.setProperty("--d",`${i*80}ms`);
    mk("text",{x:340,y:y+(h-6)/2+4,"text-anchor":"end",class:"map-text dim"},b.contribution==null?"—":`+${(b.contribution*100).toFixed(1)}%`);
  });
  const cx=480;
  if(rep.experts){
    mk("text",{x:cx,y:16,"text-anchor":"middle",class:"map-label"},"эксперты");
    const k=rep.experts.length;
    rep.experts.forEach((v,i)=>{const a=-Math.PI/2+i*2*Math.PI/k,x=cx+Math.cos(a)*52,y=82+Math.sin(a)*42,r=7+v*k*9;
      const c=mk("circle",{cx:x,cy:y,r,class:"map-orb"+(v<0.25/k?" weak":"")});c.style.setProperty("--d",`${i*120}ms`);
      mk("text",{x,y:y+4,"text-anchor":"middle",class:"map-orb-text"},Math.round(v*100)+"%")});
    mk("circle",{cx,cy:82,r:5,class:"map-core"});
  }
  if(rep.memory){
    const m=rep.memory,dots=64,lit=Math.round(m.used/m.slots*dots),y0=rep.experts?188:40;
    mk("text",{x:cx,y:y0-8,"text-anchor":"middle",class:"map-label"},`память: ${m.used} из ${m.slots} ячеек в деле`);
    for(let i=0;i<dots;i++)mk("circle",{cx:cx-75+(i%16)*10,cy:y0+4+Math.floor(i/16)*10,r:3,class:"map-dot"+(i<lit?" on":"")});
  }
  if(!rep.experts&&!rep.memory)mk("text",{x:cx,y:130,"text-anchor":"middle",class:"map-label"},"без экспертов и памяти");
  for(const a of rep.advice){const li=el("li",a.kind);li.append(el("span",null,a.text));advice.append(li)}
}
$("map-look").onclick=e=>act(e.currentTarget,async()=>{const ref=mapRef();if(!ref)return;await post("introspect",{id:ref.id});$("map-sub").textContent="Заглядываю внутрь: замер идёт в фоне, карта обновится сама.";setTimeout(async()=>{await refresh();renderMap()},15000)});

const PLAN_NAME={swarm:"Копии и слияние",search:"Ветки времени",distill:"Учёба у себя будущей",recipes:"Конкурс рецептов",shrink:"Сжатие после роста",hemispheres:"Два полушария",thoughts:"Язык мыслей",coevolve:"Коэволюция задач",redqueen:"Красная Королева",baldwin:"Эффект Болдуина",es:"Эволюция весов",dataevo:"Эволюция уроков",symbiosis:"Эндосимбиоз"};
const PLAN_STATE={preparing:"готовится",running:"идёт",finished:"готово",failed:"ошибка",stopped:"остановлен"};
function renderPlan(p){
  const plan=p.plan,box=$("plan-box");box.hidden=!plan;
  const live=plan&&["preparing","running"].includes(plan.state);
  for(const b of document.querySelectorAll("[data-plan-go]"))b.disabled=!!live||!(status&&status.active);
  for(const c of document.querySelectorAll(".power"))c.classList.toggle("live",!!live&&plan.kind===c.dataset.plan);
  if(!plan)return;
  $("plan-pill").textContent=PLAN_STATE[plan.state]||plan.state;box.dataset.state=plan.state;
  $("plan-title").textContent=`${PLAN_NAME[plan.kind]} · ${when(plan.id)}${plan.rounds?` · раунд ${plan.round} из ${plan.rounds}`:""}`;
  const ol=$("plan-runs");ol.replaceChildren();
  for(const r of plan.runs||[]){const run=status&&status.runs.find(x=>x.id===r.id),li=el("li",run?run.state:"");li.append(el("b",null,r.label),el("small",null,run?`${STATES[run.state]||run.state}${run.exam_per_char!=null?` · экзамен ${run.exam_per_char.toFixed(3)}`:""}`:"—"));ol.append(li)}
  for(const q of plan.queued||[]){const li=el("li","queued");li.append(el("b",null,q),el("small",null,"в очереди"));ol.append(li)}
  const log=$("plan-log");log.replaceChildren();
  for(const x of (plan.log||[]).slice().reverse().slice(0,6)){const li=el("li");li.append(el("b",null,new Date(x.at).toLocaleTimeString("ru-RU",{hour:"2-digit",minute:"2-digit"})),` · ${x.text}`);log.append(li)}
}
for(const b of document.querySelectorAll("[data-plan-go]"))b.onclick=()=>{
  const kind=b.dataset.planGo,body={kind,minutes:parseFloat($("plan-minutes").value)};
  if(kind==="swarm")body.copies=[...document.querySelectorAll("#swarm-skills input:checked")].map(i=>i.value);
  if(kind==="search")Object.assign(body,{branches:parseInt($("search-branches").value,10),rounds:parseInt($("search-rounds").value,10)});
  if(kind==="distill")Object.assign(body,{rounds:parseInt($("distill-rounds").value,10),prompts:parseInt($("distill-prompts").value,10)});
  if(!confirm(`${PLAN_NAME[kind]}: запустить план из нескольких уроков по ${body.minutes} мин? Активная версия не изменится без вашего решения.`))return;
  act(b,async()=>{await post("plan-start",body);await refresh();await refreshBrain()});
};
function renderSkills(list){
  const ul=$("skills");ul.replaceChildren();let have=0;
  for(const k of list){const li=el("li",k.expr?"on":"");if(k.expr)have++;
    li.append(el("b",null,k.title),el("code",null,k.pretty?`${k.name}(${k.args.join(", ")}) = ${k.pretty}`:"ещё не найдена"));ul.append(li)}
  $("skills-find").textContent=have===list.length?"Все найдены":"Искать";$("skills-find").disabled=have===list.length;
}
$("skills-find").onclick=e=>act(e.currentTarget,async()=>{const r=await post("programs-learn");renderSkills(r.skills);$("skills-note").textContent=r.found.length?`Найдено: ${r.found.length}. Уроков, как ими пользоваться: ${r.lessons}.`:"Новых программ не нашлось."});
function renderWorld(w){
  $("world-lives").textContent=num(w.lives);
  const box=$("world-envs");box.replaceChildren();
  for(const [k,e] of Object.entries(w.envs)){
    const row=el("div","logic-row"),bar=el("span","exam-bar"),fill=el("i");fill.style.width=`${e.lives?Math.round(e.wins/e.lives*100):0}%`;bar.append(fill);
    row.append(el("b",null,e.name),bar,el("small",null,e.lives?`${Math.round(e.wins/e.lives*100)}%`:"—"));box.append(row);
  }
  const job=w.job,running=job&&job.state==="running";
  $("world-now").disabled=running||!(status&&status.runs.some(r=>r.has_best&&r.mode==="long"));$("world-now").textContent=running?"Живёт…":"Прожить 150 жизней";
  $("world-last").textContent=job?(running?"Играет и решает…":`Последний раз: ${job.result||""}`):`Ночей в мире задач: ${num(w.nights)}.`;
}
$("world-now").onclick=e=>act(e.currentTarget,async()=>{await post("sim-now");await refreshBrain()});
$("engine-save").onclick=e=>{
  const engine=radio("engine");
  if(engine==="own"&&!confirm("Отвечать в чате своей моделью? Она маленькая и может отвечать слабо. Cloud.ru подставляться не будет."))return;
  act(e.currentTarget,async()=>{await post("chat-engine",{engine,drafts:parseInt(radio("drafts"),10),compressed:$("engine-q4").checked});await refreshBrain()});
};
$("live-save").onclick=e=>{
  if($("live-auto").checked&&!confirm("Разрешить включать новую версию без вас, если она не хуже на экзаменах? Прошлую всегда можно вернуть."))return;
  act(e.currentTarget,async()=>{await post("continual-settings",{enabled:$("live-on").checked,auto_activate:$("live-auto").checked,min_new:parseInt($("live-min").value,10),minutes:parseFloat($("live-min-time").value)});await refreshBrain()});
};
$("live-now").onclick=e=>act(e.currentTarget,async()=>{const r=await post("continual-now");await refresh();await refreshBrain();if(r.run)$("live-pending").textContent="Урок начат: его видно на вкладке «Обучение»."});
$("cur-now").onclick=e=>act(e.currentTarget,async()=>{await post("curiosity-now");await refreshBrain()});
$("think-go").onclick=e=>act(e.currentTarget,async()=>{
  e.currentTarget.textContent="Думает…";
  const r=await post("think",{id:$("think-run").value,question:$("think-q").value,drafts:parseInt(radio("drafts"),10)});
  const out=$("think-out");out.hidden=false;out.replaceChildren();
  out.append(el("p","think-answer",r.answer||"(пустой ответ)"));
  const facts=[`черновиков ${r.drafts}`,r.passes>1?`думала ×${r.passes}, вопрос трудный`:r.hard?"вопрос трудный":"вопрос лёгкий",r.fixed?"лучшим оказался не первый черновик":"первый черновик оказался лучшим",r.errors?`ошибок в счёте: ${r.errors}`:"ошибок в счёте нет",r.tools&&r.tools.length?`инструменты: ${r.tools.length}`:null].filter(Boolean);
  out.append(el("small",null,facts.join(" · ")));
});

// ---- future: horizon, steps 07–19, safety ----
const GROW=[
 {n:"07",t:"Инструменты",d:"Калькулятор, время и поиск по памяти. Урок есть, модель сама пишет вызов, результат считает программа.",s:"partial"},
 {n:"08",t:"Самопроверка ответа",d:"Черновик Yorika проверяет учитель, ошибки с исправлением идут в опыт.",s:"partial"},
 {n:"09",t:"Знание своих границ",d:"Отдельный экзамен честности у каждой версии и уроки «не знаю».",s:"partial"},
 {n:"10",t:"Память в навыки",d:"Учитель делает примеры из фактов памяти, в обучение они идут после вашей оценки.",s:"partial"},
 {n:"11",t:"Уроки на слабых местах",d:"Самоигра уже даёт новые вопросы там, где Yorika ошиблась.",s:"partial"},
 {n:"12",t:"Команда специалистов",d:"Рой экспертов внутри сети: на каждое слово работают 2 из 4. Отдельные модели для речи и плана пока в исследовании.",s:"partial"},
 {n:"13",t:"Модель мира",d:"Предсказывает последствия действий и учится на ошибках прогноза.",s:"research"},
 {n:"14",t:"Умение учиться",d:"Измеряется и улучшается скорость освоения новой задачи.",s:"research"},
 {n:"15",t:"Изменение своего устройства",d:"Смотрит внутрь себя (вклад каждого слоя, эксперты, память), растёт на слои, эволюция пробует варианты; экзамен выбирает, включаете вы.",s:"partial"},
 {n:"16",t:"Гипотезы и эксперименты",d:"Ветки времени и копии: несколько путей обучения из одной точки, экзамен решает, какой оставить.",s:"partial"},
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
  {i:"brain",t:"Своя большая модель",d:"Уже 5, 25 или 50 млн параметров, рост на слои и сжатие в 4 бита для ответов. Дальше сотни миллионов.",s:"partial"},
  {i:"users",t:"Несколько учителей",d:"До 4 моделей Cloud.ru, по каждой теме зовётся та, кого вы одобряете чаще.",s:"partial"},
  {i:"eye",t:"Видит, слышит, говорит",d:"Голос, камера и экран только по разрешению.",s:"research"}]},
 {when:"15 лет",sub:"улучшает себя",items:[
  {i:"pen",t:"Проектирует следующую версию",d:"Эволюция уже пробует варианты устройства в песочнице, доказательство цифрами экзамена.",s:"partial"},
  {i:"globe",t:"Модель мира",d:"Причины и следствия, планы на недели вперёд.",s:"research"},
  {i:"swarm",t:"Рой Yorika",d:"Копии учат разные навыки и сливаются обратно; дальше — копии на разных компьютерах.",s:"partial"}]},
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


// ---- evolution: the morning report, health, the map of species, the task ladder, study recipes ----
const DAWN_IC={plateau:"comet",train:"play",plan:"swarm",sim:"puzzle",programs:"code",tidy:"archive",health:"shield",run:"layers",archive:"hex",ladder:"stairs"};
const GENE={experience:["разговоры","--gene-a"],logic:["логика","--gene-b"],sim:["мир задач","--gene-c"],programs:["программы","--gene-d"],tools:["инструменты","--gene-e"]};
let evo=null,evoTimer=null,scTimer=null;
async function refreshEvo(){
  try{
    if(!status)status=await api("/api/training/status");
    const b=await api("/api/training/brain-status");evo=b.evolution||{};
    renderDawn(evo.report||{},evo.tonight||{},b.autopilot);renderHealth(evo.health||{},b.autopilot);
    renderSpecies(evo.archive||{});renderLadders(evo.ladder||{},evo.envs||{});renderRecipes(evo.recipes||{});
    renderDiary(evo.diary||[]);renderMind(evo);renderKnow(evo);renderSelection(evo,status);
    const live=b.plans.plan&&["preparing","running"].includes(b.plans.plan.state);
    for(const x of document.querySelectorAll("[data-evo-plan],[data-mind-go]"))x.disabled=!!live||!(status&&status.active)||x.dataset.none==="1";
    $("ex-go").disabled=!!live||!((evo.extinction||{}).count>0);
    const ex=evo.exchange;if(ex&&ex.state==="running"){document.querySelector("[data-mind-go=exchange]").disabled=true;clearTimeout(evoTimer);evoTimer=setTimeout(refreshEvo,5000)}
  }catch(e){showError(e.message)}
}
function renderDawn(r,t,ap){
  $("dawn-since").textContent=r.since?`Утренний отчёт · с ${new Date(r.since).toLocaleString("ru-RU",{day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"})}`:"Утренний отчёт";
  const ul=$("dawn-lines");ul.replaceChildren();
  for(const x of r.lines||[]){const li=el("li");const i=el("span","dawn-ic");i.dataset.icon=DAWN_IC[x.kind]||"sparkles";li.append(i,el("span",null,x.text));ul.append(li)}
  if(!(r.lines||[]).length)ul.append(el("li","empty-line","Ночью ещё ничего не происходило. Отчёт появится после первого часа учёбы."));
  if((r.waiting||[]).length){const li=el("li","dawn-ask");const i=el("span","dawn-ic");i.dataset.icon="check";const a=el("a",null,`Ждут вашего решения: ${r.waiting.length} верс. → «Версии и экзамен»`);a.href="#";a.onclick=e=>{e.preventDefault();openTab("train");$("versions-title").scrollIntoView({behavior:"smooth"})};li.append(i,a);ul.append(li)}
  const box=$("dawn-tonight");box.replaceChildren();
  if(t&&t.activity){
    const on=ap&&ap.parts&&ap.parts.find(p=>p.key==="auto_week");
    box.append(el("span","dawn-moon"),el("b",null,on&&on.on?"Сегодня ночью сама выберу: ":"Если разрешите выбирать самой, сегодня я бы выбрала: "),el("span","chip chip-next",(evo&&evo.activities||{})[t.activity]||ACT_NAME[t.activity]||t.activity),el("span",null,` — ${t.why}.`));
  }
  fillIcons(ul);
}
const ACT_NAME={sleep:"Сон",distill:"Учёба у себя будущей",search:"Ветки времени",swarm:"Копии",evolution:"Эволюция",fresh:"Новая версия",rest:"Отдых",recipes:"Рецепты учёбы",grow:"Рост глубже",experts:"Рост вширь (эксперты)",shrink:"Сжатие после роста",coevolve:"Коэволюция задач",redqueen:"Красная Королева",baldwin:"Эффект Болдуина",es:"Эволюция весов",dataevo:"Эволюция уроков",symbiosis:"Эндосимбиоз"};
function renderHealth(h,ap){
  $("health-dot").dataset.state=h.state||"";
  const ul=$("health-list");ul.replaceChildren();
  for(const x of h.items||[]){const li=el("li",x.level);li.append(el("span",null,x.text));if(x.fix)li.append(el("small",null,x.fix));ul.append(li)}
  if(h.free_gb!=null)ul.append(el("li","ok",`Свободно на диске: ${String(h.free_gb).replace(".",",")} ГБ`));
  const part=k=>((ap&&ap.parts)||[]).find(p=>p.key===k);
  if(!$("pane-evo").contains(document.activeElement)){$("opt-week").checked=!!(evo.options||{}).auto_week;$("opt-tidy").checked=(evo.options||{}).tidy!==false}
  $("opt-week").title=part("auto_week")&&!part("auto_week").on?"Работает, когда включено расписание учёбы":"";
}
function renderSpecies(a){
  const box=$("species");box.replaceChildren();
  const cells=(a.rows||[]).flatMap(r=>r.cells).filter(Boolean),fits=cells.map(c=>c.fitness);
  const lo=Math.min(...fits),hi=Math.max(...fits),active=status&&status.active&&status.active.run;
  const head=el("div","sp-row sp-head");head.append(el("span","sp-size",""));
  for(const f of a.families||[])head.append(el("span","sp-fam",f));box.append(head);
  (a.rows||[]).forEach((row,k)=>{
    const line=el("div","sp-row");line.style.setProperty("--shift",k%2?"1":"0");line.append(el("span","sp-size",row.size));
    row.cells.forEach((c,j)=>{
      const cell=el("div","sp-cell"+(c?" full":"")+(c&&c.run===active?" active":"")+(c&&!c.alive?" lost":""));
      cell.setAttribute("role","cell");
      if(c){const t=hi>lo?(c.fitness-lo)/(hi-lo):1;cell.style.setProperty("--fit",(0.25+0.75*t).toFixed(2));
        cell.append(el("b",null,when(c.run)),el("small",null,c.label||""),el("i",null,`сила ${c.fitness.toFixed(2)}`));
        cell.title=`${a.families[j]}, ${row.size}: ${c.run}${c.replaced?` (сменила ${c.replaced})`:""}`;}
      else{cell.append(el("small",null,"пусто"));cell.title=`${a.families[j]}, ${row.size}: ещё никого`}
      line.append(cell);
    });
    box.append(line);
  });
  $("species-sub").textContent=`Занято ${a.filled||0} из ${a.total||30} клеток. Лучшая версия каждого вида: размер × устройство. Эволюция берёт родителя из любой клетки, поэтому не застревает на одном пути.`;
  const log=$("species-log");log.replaceChildren();
  for(const x of (a.log||[]).slice().reverse().slice(0,5)){const li=el("li",/вошла/.test(x.result||"")?"ok":"warn");li.append(el("b",null,when(x.run)),` · ${x.result||""}`);log.append(li)}
  if(!(a.log||[]).length)log.append(el("li","empty-line","Архив пополнится после первого экзамена новой версии. Перед входом она играет турнир с предком."));
}
function renderLadders(l,names){
  const box=$("ladders");box.replaceChildren();const max=10;
  for(const [env,level] of Object.entries(l.levels||{})){
    const row=el("div","ladder");row.append(el("span","ladder-name",names[env]||env));
    const steps=el("div","steps");steps.setAttribute("aria-label",`${names[env]||env}: уровень ${level} из ${max}`);
    for(let k=1;k<=max;k++){const s=el("span","step"+(k<level?" done":k===level?" here":""));s.style.setProperty("--h",(k/max).toFixed(2));steps.append(s)}
    row.append(steps,el("b","ladder-level",`${level}`));box.append(row);
  }
  const moves=(l.history||[]).slice(-3).reverse();
  if(moves.length){const p=el("p","hint");p.textContent="Недавно: "+moves.map(m=>`${names[m.env]||m.env} ${m.from}→${m.to}`).join(", ");box.append(p)}
}
function renderRecipes(r){
  const g=$("genome");g.replaceChildren();const best=r.best;
  if(best){const total=Object.values(best.mix).reduce((a,b)=>a+b,0)||1;
    for(const [k,v] of Object.entries(best.mix)){if(!v)continue;const seg=el("span","gene");seg.style.flex=String(v);seg.style.background=`var(${GENE[k][1]})`;seg.title=`${GENE[k][0]} ${Math.round(100*v/total)}%`;seg.append(el("small",null,`${GENE[k][0]} ${Math.round(100*v/total)}%`));g.append(seg)}}
  $("genome-line").textContent=best?`Шаг обучения ${best.lr} · время ×${best.time}${best.level?" · логика на ступень выше":""} · поколений рецептов: ${r.generations||0}${r.default?" · пока обычный рецепт":""}`:"";
  const ol=$("recipe-board");ol.replaceChildren();const tried=r.tried||[];const top=Math.max(1e-9,...tried.map(t=>Math.abs(t.gain_per_hour)));
  for(const t of tried.slice(0,5)){const li=el("li",t.gain_per_hour>0?"up":"down");const bar=el("span","rb-bar");bar.style.setProperty("--w",(Math.abs(t.gain_per_hour)/top).toFixed(2));
    li.append(el("span","rb-label",t.label),bar,el("b",null,(t.gain_per_hour>0?"+":"")+t.gain_per_hour.toFixed(3)+"/ч"));ol.append(li)}
  if(!tried.length)ol.append(el("li","empty-line","Рецепты ещё не соревновались."));
}
$("opt-week").onchange=e=>act(e.target,async()=>{await post("autopilot-options",{auto_week:e.target.checked});await refreshEvo()});
$("opt-tidy").onchange=e=>act(e.target,async()=>{await post("autopilot-options",{tidy:e.target.checked});await refreshEvo()});
$("tidy-now").onclick=e=>{if(!confirm("Удалить рабочие копии уроков, закончившихся больше суток назад? Сами версии, активная и архив не трогаются."))return;
  act(e.currentTarget,async()=>{const r=await post("tidy");showError("");$("tidy-now").textContent=r.removed.length?`Освобождено ${r.freed_mb} МБ`:"Убирать нечего";await refreshEvo()})};
for(const b of document.querySelectorAll("[data-evo-plan]"))b.onclick=()=>{
  const kind=b.dataset.evoPlan,body={kind,minutes:parseFloat($("plan-minutes").value)||20,branches:3,rounds:1};
  if(!confirm(`${PLAN_NAME[kind]}: запустить? Уроки по ${body.minutes} мин. Активная версия не изменится без вашего решения.`))return;
  act(b,async()=>{await post("plan-start",body);await refresh();await refreshEvo()});
};

// ---- the diary, the mind lab, the self-check, more data, screen help ----
function renderDiary(list){
  const box=$("diary-pages");box.replaceChildren();
  const pages=list.slice().reverse().slice(0,3);
  for(const [k,e] of pages.entries()){
    const page=el("article","diary-page"+(k===0?" today":""));
    page.append(el("time",null,new Date(e.at).toLocaleDateString("ru-RU",{weekday:"long",day:"numeric",month:"long"})));
    for(const line of e.lines)page.append(el("p",null,line));
    const n=e.numbers||{},chips=el("div","diary-nums");
    for(const [label,v] of [["логика",n.logic],["мир",n.sim],["честность",n.honesty]])if(v!=null)chips.append(el("span","chip",`${label} ${Math.round(v*100)}%`));
    if(n.ladder)chips.append(el("span","chip",`ступеней ${n.ladder}`));
    page.append(chips);box.append(page);
  }
  if(!pages.length)box.append(el("p","empty-line","Первая запись появится после первой ночи учёбы. Можно записать и сейчас."));
}
function renderMind(e){
  const t=e.trust||{},box=$("trust");box.replaceChildren();
  const NAMES={logic:"логика",sim:"мир задач",inverse:"обратные"};
  for(const [kind,row] of Object.entries(t)){
    const line=el("div","trust-row"),a=row.left/Math.max(1,row.asked),b=row.right/Math.max(1,row.asked);
    const bar=el("span","trust-bar");bar.style.setProperty("--l",a.toFixed(2));bar.style.setProperty("--r",b.toFixed(2));
    line.append(el("small",null,NAMES[kind]||kind),bar,el("small",null,`${Math.round(a*100)} : ${Math.round(b*100)}`));box.append(line);
  }
  if(!Object.keys(t).length)box.append(el("small","mind-stat","Споров ещё не было: левая — активная, правая — сильнейшая из архива."));
  const best=(e.recipes||{}).best;$("mind-rule").textContent=best&&best.rule?`Сейчас: распад ${best.rule.wd}, срез ${best.rule.clip}, разгон ${best.rule.warmup}, пластичность ×${best.rule.plasticity}`:"Закон пока обычный; меняется в конкурсе рецептов";
  const ex=e.exchange;$("mind-exchange").textContent=ex?(ex.state==="running"?"Меняются блоками…":ex.result||""):"";
}
for(const b of document.querySelectorAll("[data-mind-go]"))b.onclick=()=>{
  const kind=b.dataset.mindGo,mins=parseFloat($("plan-minutes").value)||20;
  const say={rebirth:"Молчащие нейроны активной версии родятся заново, потом короткий урок.",hemispheres:`Две версии решат задачи, урок из их споров по ${mins} мин.`,thoughts:`Урок языка мыслей по ${mins} мин.`,exchange:"Активная версия попробует взять блоки у версий своей линии; берётся только то, что улучшает экзамен."}[kind];
  if(!confirm(say+" Активная версия не изменится без вашего решения."))return;
  act(b,async()=>{
    if(kind==="rebirth")await post("rebirth",{hours:Math.max(0.1,mins/60)});
    else if(kind==="exchange")await post("exchange");
    else await post("plan-start",{kind,minutes:mins,prompts:90});
    await refresh();await refreshEvo();
  });
};
// ---- selection of weights, lessons and genes ----
function fillList(id,rows,empty){const ul=$(id);ul.replaceChildren();
  for(const [a,b] of rows){const li=el("li","sel-row");li.append(el("span",null,a),el("b",null,b));ul.append(li)}
  if(!rows.length)ul.append(el("li","co-foot",empty))}
const millions=n=>n?`${(n/1e6).toFixed(1).replace(".",",")} млн`:"—";
const ES_VERDICT={rolled_back:"хуже активной",waiting:"ждёт решения",activated:"включена"};
function renderSelection(e,status){
  const es=(e.es||{}).last;
  fillList("es-list",es?[["поколений",String(es.generations)],["потеря на уроках",`${es.loss_before} → ${es.loss_after}`],
    ["итог",es.run?(ES_VERDICT[es.verdict]||"на экзамене"):"лучше не нашла"]]:[],"Ещё не запускалась.");
  const pa=e.pareto||{};
  fillList("pareto-list",(pa.front||[]).slice(0,4).map(p=>[`${millions(p.parameters)} · логика ${Math.round(p.logic*100)}%`,String(p.exam).replace(".",",")]),"Фронт появится после экзаменов.");
  if((pa.front||[]).length)$("pareto-list").append(el("li","co-foot",`На фронте ${pa.front.length} из ${pa.count}; справа экзамен (меньше — лучше)`));
  const de=(e.dataevo||{}).last;
  fillList("dataevo-list",de?[["поколение",String(de.generation)],["выжило / выбыло",`${de.kept} / ${de.died}`],["новых из лучших источников",String(de.fresh)]]:[],"Уроки ещё не отбирались.");
  const cur=(status&&status.active)||null,item=cur&&(status.runs||[]).find(r=>r.id===cur.run);
  const blocks=((item&&item.introspection)||{}).blocks||[],expr=blocks.filter(b=>b.expression!=null);
  fillList("epi-list",expr.slice(0,4).map(b=>[`слой ${b.layer}`,`×${String(b.expression).replace(".",",")}`]),
    item&&(item.arch||{}).epigenetic?"Сила слоёв появится после взгляда внутрь.":"У активной версии гена нет; эволюция может его включить.");
  const guest=(e.symbiosis||{}).guest;
  fillList("sym-list",guest?[["кандидат",guest]]:[],"Нет меньшей версии с тем же словарём.");
  $("sym-go").dataset.none=guest?"":"1";
  const tb=e.tabu||{};
  fillList("tabu-list",(tb.active||[]).slice(0,4).map(t=>[t.change,`ещё ${t.left}`]),"Запретов нет.");
  if(tb.count>4)$("tabu-list").append(el("li","co-foot",`Всего под запретом ${tb.count}`));
}
// ---- evolutionary know-how: coevolution, the Red Queen, Baldwin, mutation strength, species, extinction ----
function renderKnow(e){
  const co=e.coevolution||{},ul=$("co-list");ul.replaceChildren();
  for(const t of (co.top||[]).slice(0,4)){const li=el("li"),bar=el("span","co-bar");bar.style.setProperty("--f",String(t.fail??0));
    li.append(el("span",null,t.label),bar,el("b",null,t.fail==null?"—":`${Math.round(t.fail*100)}%`));li.title=`${t.label}: проваливает ${t.fail==null?"—":Math.round(t.fail*100)+"%"}`;ul.append(li)}
  if(!(co.top||[]).length)ul.append(el("li","co-foot","Поколений задач ещё не было: первое найдёт, где она ошибается чаще всего."));
  else ul.append(el("li","co-foot",`Поколение задач ${co.generation} · в популяции ${co.size}`));
  const rq=(co.redqueen||{}),box=$("rq");box.replaceChildren();const m=rq.last;
  if(m){const side=(name,score,rating,win)=>{const d=el("div","rq-side"+(win?" win":""));d.append(el("small",null,name),el("strong",null,String(score)),el("small",null,`рейтинг ${Math.round(rating)}`));return d};
    box.append(side("активная",m.score[0],m.ratings[0],m.score[0]>m.score[1]),el("span","rq-vs","VS"),side("соперница",m.score[1],m.ratings[1],m.score[1]>m.score[0]),
      el("small","rq-note",`Верных вопросов задано: ${m.asked[0]} и ${m.asked[1]} · матчей ${rq.matches}`))}
  else box.append(el("small","rq-note","Матчей ещё не было. Соперница — сильнейшая другая версия из архива."));
  const bw=e.baldwin||{},chart=$("bw");chart.replaceChildren();const curve=(bw.curve||[]).slice(-8);
  const vals=curve.flatMap(c=>[c.inherited,c.control]).filter(v=>v!=null),hi=Math.max(...vals,0),lo=Math.min(...vals,hi);
  const h=v=>v==null?0:hi>lo?0.15+0.85*(hi-v)/(hi-lo):0.6;
  for(const c of curve){const g=el("div","bw-gen");const a=el("i","inh"),b=el("i");a.style.setProperty("--h",h(c.inherited).toFixed(2));b.style.setProperty("--h",h(c.control).toFixed(2));
    a.title=`поколение ${c.g}: врождённая ${c.inherited??"—"}`;b.title=`поколение ${c.g}: случайная ${c.control??"—"}`;g.append(a,b);chart.append(g)}
  if(!curve.length)chart.append(el("span","bw-empty","Выше столбик — быстрее училась. Цветной — врождённая точка, серый — случайная."));
  $("bw-stat").textContent=bw.generation?`Поколений ${bw.generation} · врождённая быстрее случайной в ${bw.inherited_wins} из ${bw.duels}`:"Ни одного поколения стартов ещё не было";
  const mu=e.mutation||{},gauge=$("mu");const frac=mu.strength?(mu.strength-(mu.low||1))/((mu.high||4)-(mu.low||1)):0;
  gauge.style.setProperty("--s",(mu.boost?1:frac).toFixed(3));gauge.classList.toggle("boost",!!mu.boost);
  $("mu-stat").textContent=mu.tries?`Сила ${String(mu.strength).replace(".",",")} гена · удачных ${mu.wins} из ${mu.tries}${mu.plateau?" · плато":""}${mu.boost?` · смелые мутанты ещё ${mu.boost} пок.`:""}`:"Сила 1,5 гена · поколений ещё не было";
  const sp=e.species||{},dots=$("sp-dots");dots.replaceChildren();const list=sp.species||[];
  for(const x of list.slice(-14)){const d=el("span","sp-dot"+(x.protected?" young":""),String(x.id));d.style.setProperty("--n",String(Math.min(6,x.size)));d.style.setProperty("--k",(x.solved/(sp.probes||24)).toFixed(2));
    d.title=`Вид №${x.id}: версий ${x.size}, решает ${x.solved} из ${sp.probes||24} проб${x.protected?`, под защитой ещё ${x.left}`:""}`;dots.append(d)}
  if(!list.length)dots.append(el("small","mind-stat","Виды появятся после экзаменов новых версий."));
  $("sp-stat").textContent=list.length?`Видов ${list.length} · под защитой ${list.filter(x=>x.protected).length} · версий изучено ${sp.versions}`:"";
  const ex=e.extinction||{},exb=$("ex");exb.replaceChildren();
  exb.append(el("span","ex-state"+(ex.plateau?" stuck":""),ex.plateau?"Плато":"Эволюция идёт"),el("small",null,ex.why||""),
    el("small",null,ex.count?`Слабых версий, которых можно удалить: ${ex.count} (${String(ex.mb).replace(".",",")} МБ)`:"Удалять некого: все версии нужны"));
  const last=(ex.history||[]).slice(-1)[0];if(last)exb.append(el("small",null,`Последнее: ${new Date(last.at).toLocaleDateString("ru-RU")}, удалено ${last.removed.length}`));
}
$("ex-go").onclick=e=>act(e.currentTarget,async()=>{
  const p=await post("extinction-preview");
  if(!p.count){showError("Удалять некого: все версии нужны");return}
  const list=p.candidates.slice(0,12).map(c=>`• ${c.run} — сила ${c.fitness.toFixed(2)}, ${c.mb} МБ`).join("\n");
  if(!confirm(`${p.plateau?"Эволюция на плато: "+p.why+".":"Плато сейчас нет."}\n\nБудут удалены с диска ${p.count} слабых версий (${p.mb} МБ):\n${list}${p.count>12?"\n…":""}\n\nАктивная, её предки, лучшие в архиве и молодые виды не трогаются. Вернуть удалённое нельзя.`))return;
  const word=prompt("Чтобы подтвердить, напишите слово: вымирание");
  if((word||"").trim().toLowerCase()!=="вымирание")return;
  const r=await post("extinction",{confirm:true,expect:p.count});
  showError("");$("ex-go").textContent=`Удалено ${r.removed.length}, освобождено ${r.freed_mb} МБ`;await refreshEvo();
});
$("diary-now").onclick=e=>act(e.currentTarget,async()=>{await post("diary-write");await refreshEvo()});

const SC_STEPS=["PyTorch и видеокарта","Папка обучения и диск","Урок на минуту","Экзамены","Мир задач","Поиск программы","Расписание и планировщик","Уборка за собой"];
async function refreshSelfcheck(){
  try{const b=await api("/api/training/brain-status");renderSelfcheck((b.evolution||{}).selfcheck)}catch{}
}
function renderSelfcheck(r){
  const ol=$("sc-steps");ol.replaceChildren();const running=r&&r.state==="running";
  $("sc-go").disabled=running;$("sc-go").textContent=running?"Проверяю…":r?"Проверить ещё раз":"Проверить всё";
  $("selfcheck").dataset.state=r?(running?"live":r.ok?"ok":"bad"):"";
  if(!r){$("sc-copy-row").hidden=true;return}
  const done=r.steps||[];
  for(const title of SC_STEPS){
    const s=done.find(x=>x.title===title),li=el("li",s?(s.ok?"ok":"bad"):running?"wait":"skip");
    li.append(el("b",null,title),el("small",null,s?`${s.detail} · ${s.seconds} с`:running?"ждёт":"пропущено"));ol.append(li);
  }
  const passed=done.filter(x=>x.ok).length;$("sc-ring").style.setProperty("--p",(passed/SC_STEPS.length).toFixed(2));
  $("sc-line").textContent=running?"Идёт проверка, около двух минут.":r.state==="failed"?`Проверка остановилась: ${r.error||""}`:r.ok?`Всё работает: ${passed} из ${done.length} шагов.`:`Прошло ${passed} из ${done.length}; что упало — видно ниже.`;
  $("sc-copy-row").hidden=!r.text;
  clearTimeout(scTimer);if(running)scTimer=setTimeout(refreshSelfcheck,3000);
}
$("sc-go").onclick=e=>act(e.currentTarget,async()=>{renderSelfcheck(await post("selfcheck"));setTimeout(refreshSelfcheck,2000)});
$("sc-copy").onclick=async()=>{const b=await api("/api/training/brain-status");const t=((b.evolution||{}).selfcheck||{}).text||"";
  try{await navigator.clipboard.writeText(t);$("sc-copy").textContent="Скопировано"}catch{prompt("Скопируйте отчёт:",t)}};

$("harvest-go").onclick=e=>{
  if(!confirm("Собрать файл из ваших одобренных разговоров и проверенных уроков до 10 000 записей? Ничего не тратится, файл появится в папке данных."))return;
  act(e.currentTarget,async()=>{const r=await post("harvest");const bar=$("harvest-bar");bar.replaceChildren();bar.hidden=false;
    const COL={experience:"--gene-a",logic:"--gene-b",sim:"--gene-c",programs:"--gene-d",tools:"--gene-e",dream:"--brand-hi"};
    for(const [k,v] of Object.entries(r.mix)){if(!v)continue;const seg=el("span","gene");seg.style.flex=String(v);seg.style.background=`var(${COL[k]})`;seg.title=`${r.names[k]}: ${v}`;seg.append(el("small",null,`${r.names[k]} ${v}`));bar.append(seg)}
    $("harvest-note").textContent=`Готов файл ${r.name}: ${num(r.count)} записей, из них ваших разговоров ${Math.round(r.conversation_share*100)}%. ${r.long_ready?"Можно запускать долгое обучение.":""}${r.conversation_share<0.2?" Разговоров мало: она будет хорошо решать задачи, но говорить пока бедно.":""}`;
    await refresh()})};

$("screen-go").onclick=e=>act(e.currentTarget,async()=>{
  const r=await post("screen-help",{question:$("screen-q").value});$("screen-out").hidden=false;
  $("screen-text").textContent=r.text||"(текста нет)";$("screen-answer").textContent=r.answer||"—";$("screen-note").textContent=r.note||"";
});

renderFuture();fillIcons();syncMode();refresh();
let startTab="train";try{startTab=location.hash.slice(1)||localStorage.getItem("yorika.training.tab")||"train"}catch{}
openTab(startTab);
if(!["exp"].includes(startTab))api("/api/training/sl-status").then(r=>{slStatus=r;renderCounts(r.counts);renderFlow()}).catch(()=>{});
if(startTab!=="teacher")api("/api/training/teacher-status").then(r=>{tStatus=r;renderFlow()}).catch(()=>{});
addEventListener("hashchange",()=>openTab(location.hash.slice(1)));
