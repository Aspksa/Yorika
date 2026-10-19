// «Обучение» page: talks to /api/training/* served by scripts/yorika-tray.ps1.
import {api} from "./api.js";

const $=id=>document.getElementById(id);
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

async function refresh(){
  try{
    const s=await api("/api/training/status");
    renderGpu(s);renderData(s);renderJob(s.runs);renderVersions(s);
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
const TABS=["train","self","grow"];
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

renderGrow();syncMode();refresh();
let startTab="train";try{startTab=location.hash.slice(1)||localStorage.getItem("yorika.training.tab")||"train"}catch{}
openTab(startTab);
addEventListener("hashchange",()=>openTab(location.hash.slice(1)));
