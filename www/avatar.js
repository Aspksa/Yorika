// Yorika's floating avatar and chat panel, shared by every page. History lives per browser in localStorage.
// A real responder can be plugged in with YorikaChat.setResponder(async (text, history, onChunk, signal) => "reply").
// Uploaded pictures, the chosen one and the size are managed on settings.html through YorikaAvatar.
(function(){
 var KEY="yorika.chat",POS="yorika.avatar",LOOK="yorika.avatars",SIZE={min:70,max:240,def:140},LIMIT=200,IMG="./assets/yorika-avatar.webp",MARGIN=12,GAP=12;
 var THREAD_KEY="yorika.cloud.thread";
 function newThread(){
  var bytes=new Uint8Array(16);crypto.getRandomValues(bytes);
  return "c"+Array.from(bytes,function(b){return b.toString(16).padStart(2,"0")}).join("");
 }
 function threadId(){
  var id;try{id=localStorage.getItem(THREAD_KEY)}catch(e){}
  if(id&&/^c[0-9a-f]{32}$/.test(id))return id;
  id=newThread();try{localStorage.setItem(THREAD_KEY,id)}catch(e){}
  return id;
 }
 // Each step remembers why it failed, so the chat can say what to fix instead of a generic line.
 async function serverError(response){try{var v=await response.json();if(v&&typeof v.error==="string"&&v.error.length<200)return v.error}catch(e){}return "ошибка сервера ("+response.status+")"}
 var SETTINGS_HINT="Откройте Настройки → «Языковая модель», вставьте API-ключ Cloud.ru и нажмите «Сохранить ключ и модель».";
 var responder=async function(text,history,onChunk,signal){
  var receivedAny=false,modelError="";
  try{
   var stream=await fetch('/api/chat/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:text,conversation_id:threadId()}),cache:'no-store',signal:signal});
   if(stream.ok&&stream.body){
    var reader=stream.body.getReader(),decoder=new TextDecoder(),buffer='',full='',finished=false;
    while(true){
     var part=await reader.read();if(part.done)break;
     buffer+=decoder.decode(part.value,{stream:true});
     if(buffer.length>20000)throw Error('Слишком длинное событие');
     var lines=buffer.split('\n');buffer=lines.pop();
     for(var line of lines){if(!line.trim())continue;
      var evt=JSON.parse(line);
      if(evt.type==='delta'){receivedAny=true;full+=evt.text;if(full.length>8000)throw Error('Ответ слишком длинный');if(onChunk)onChunk(full)}
      else if(evt.type==='done'){finished=true;full=evt.answer||full}
      else if(evt.type==='error')throw Error(evt.message||'Cloud.ru не завершил поток');
     }
    }
    if(finished&&full.trim())return full;
    if(full)throw Error('Поток оборвался до завершения ответа');
   }else if(!stream.ok)modelError=await serverError(stream);
  }catch(e){if(receivedAny||e&&e.name==="AbortError")throw e;modelError=e&&e.message||String(e)}
  // A classified Cloud.ru error (no key, 401, 403, 404) would only repeat on a second paid request.
  if(!/^Cloud\.ru: (сначала|неверный|нет доступа|проверьте|модель вернула)/.test(modelError)){
   try{
    var generated=await fetch("/api/chat/respond",{
     method:"POST",headers:{"Content-Type":"application/json"},
     body:JSON.stringify({query:text,conversation_id:threadId()}),cache:"no-store",signal:signal
    });
    if(generated.ok){
     var completed=await generated.json();
     if(typeof completed.answer==="string"&&completed.answer.trim())return completed.answer;
    }else modelError=await serverError(generated);
   }catch(e){if(e&&e.name==="AbortError")throw e;if(!modelError)modelError="нет связи с локальным сервером Yorika"}
  }
  var because;
  if(/сначала сохраните/.test(modelError))because="Языковая модель ещё не подключена. "+SETTINGS_HINT;
  else{
   because="Языковая модель не ответила: "+(modelError||"причина неизвестна").replace(/\.$/,"")+". ";
   if(/Python/.test(modelError))because+="После установки Python перезапустите Yorika.bat.";
   else if(/^Cloud\.ru(: (неверный|нет доступа|проверьте)| HTTP 40[134])/.test(modelError))because+="Проверьте ключ и ID модели в Настройках → «Языковая модель».";
  }

  try{
   var response=await fetch("/api/memory/recall",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({query:text}),cache:"no-store"
   });
   if(!response.ok)throw Error(await serverError(response));
   var result=await response.json();
   if(Array.isArray(result.memories)&&result.memories.length){
    return because+"\n\nНашла в сохранённой памяти (это поиск, а не ответ модели):\n"+
     result.memories.map(function(m){
      return "• "+m.text+" [источник: "+m.source+
       (m.source_id?", "+m.source_id:"")+"]";
     }).join("\n");
   }
   return because+"\n\nВ сохранённой памяти подходящих записей нет.";
  }catch(e){
   return because+"\n\nПоиск по долговременной памяти тоже недоступен: "+(e&&e.message||e)+".";
  }
 };
 function readLook(){
  var v={};try{v=JSON.parse(localStorage.getItem(LOOK))||{}}catch(e){}
  var items=Array.isArray(v.items)?v.items.filter(function(i){return i&&typeof i.id==="string"&&/^data:image\//.test(i.src)}):[];
  var size=Math.round(Number(v.size));if(!(size>=SIZE.min&&size<=SIZE.max))size=SIZE.def;
  var selected=items.some(function(i){return i.id===v.selected})?v.selected:"default";
  return{items:items,selected:selected,size:size};
 }
 // Throws when the browser storage is full, so the Settings page can say so.
 function writeLook(v){localStorage.setItem(LOOK,JSON.stringify(v));window.dispatchEvent(new Event("yorika-avatar"))}
 function srcOf(v){for(var i=0;i<v.items.length;i++)if(v.items[i].id===v.selected)return v.items[i].src;return IMG}
 window.YorikaAvatar={read:readLook,write:writeLook,size:SIZE,defaultSrc:IMG};
 function load(){try{var v=JSON.parse(localStorage.getItem(KEY));return Array.isArray(v)?v:[]}catch(e){return[]}}
 function store(list){try{localStorage.setItem(KEY,JSON.stringify(list.slice(-LIMIT)))}catch(e){}}
 function make(tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n}
 function time(ts){try{return new Date(ts).toLocaleTimeString("ru-RU",{hour:"2-digit",minute:"2-digit"})}catch(e){return""}}

 function build(){
  var history=load(),serverReady=false,serverBusy=false,dirty=false,needsSync=false;
  var revision=0,changeSerial=0,clearPending=false,UNSYNCED="yorika.chat.unsynced";
  function markPending(flag){try{if(flag)localStorage.setItem(UNSYNCED,"1");else localStorage.removeItem(UNSYNCED)}catch(e){}}
  function sameMessage(a,b){return a.from===b.from&&a.text===b.text&&a.ts===b.ts}
  function mergeHistories(remote,local){
   var out=Array.isArray(remote)?remote.slice():[];
   local.forEach(function(m){if(!out.some(function(old){return sameMessage(old,m)}))out.push(m)});
   out.sort(function(a,b){return a.ts-b.ts});
   return out;
  }
  function changed(){
   dirty=true;changeSerial++;markPending(true);
   store(history);
   syncHistory();
  }
  async function syncHistory(){
   if(!serverReady)return;
   if(serverBusy){needsSync=true;return}
   serverBusy=true;
   try{
    for(var attempt=0;attempt<3;attempt++){
     var serial=changeSerial, snapshot=history.slice(),base=revision;
     var response=await fetch("/api/chat/history",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({history:snapshot,revision:base})});
     if(!response.ok)throw Error("SQLite unavailable");
     var result=await response.json();
     if(result.conflict===true){
      revision=result.revision;
      if(clearPending){
       clearPending=false;
       history=mergeHistories(result.history||[],history);
       store(history);markPending(false);render();
       api.label("Конфликт очистки — сообщения сохранены");
       return;
      }
      history=mergeHistories(result.history||[],history);
      store(history);
      if(!panel.hidden)render();
      continue;
     }
     if(result.ok!==true||!Number.isInteger(result.revision))throw Error("Invalid SQLite response");
     revision=result.revision;
     clearPending=false;
     if(serial===changeSerial)markPending(false);
     api.label("Память SQLite");
     if(serial===changeSerial){dirty=false;return}
     // A new user message arrived while this snapshot was being written.
    }
    throw Error("Too many concurrent chat edits");
   }catch(e){serverReady=false;api.label("Память браузера — SQLite недоступна");}
   finally{
    serverBusy=false;
    if(needsSync&&serverReady){needsSync=false;syncHistory()}
   }
  }
  async function initHistory(){
   try{
    var response=await fetch("/api/chat/history",{cache:"no-store"});
    if(!response.ok)throw Error("SQLite unavailable");
    var value=await response.json();
    if(!Number.isInteger(value.revision)||value.revision<0||!(value.history===null||Array.isArray(value.history)))throw Error("Invalid SQLite history");
    revision=value.revision;
    var saved=Array.isArray(value.history)?value.history:[];
    var pending=false;try{pending=localStorage.getItem(UNSYNCED)==="1"}catch(e){}
    var combined=(value.history===null||pending||dirty)?mergeHistories(saved,history):saved;
    // Never silently replace browser-only messages from the current origin.
    var needImport=value.history===null||combined.length!==saved.length;
    history=combined;store(history);
    serverReady=true;api.label("Память SQLite");
    if(!panel.hidden)render();
    if(needImport||dirty){markPending(true);syncHistory()}else markPending(false);
   }catch(e){serverReady=false;api.label("Память браузера — SQLite недоступна");}
  }
  var VIEW="yorika.chat.view";
  var ICON={
   search:'<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
   wide:'<path d="M4 9V4h5M20 15v5h-5M4 4l6 6M20 20l-6-6"/>',
   narrow:'<path d="M10 4v6H4M14 20v-6h6M10 10L4 4M14 14l6 6"/>',
   more:'<circle cx="5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="19" cy="12" r="1.3"/>',
   close:'<path d="M6 6l12 12M18 6L6 18"/>',
   send:'<path d="M5 12h13"/><path d="M13 6l6 6-6 6"/>',
   stop:'<rect x="7" y="7" width="10" height="10" rx="2"/>',
   copy:'<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/>',
   up:'<path d="M7 10v10H4V10zM7 10l4-7a2 2 0 0 1 3 2l-1 5h6a2 2 0 0 1 2 2l-2 7a2 2 0 0 1-2 1H7"/>',
   down:'<path d="M7 14V4H4v10zM7 14l4 7a2 2 0 0 0 3-2l-1-5h6a2 2 0 0 0 2-2l-2-7a2 2 0 0 0-2-1H7"/>',
   again:'<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 5v6h-6"/>',
   edit:'<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
   arrow:'<path d="M12 5v14M6 13l6 6 6-6"/>'
  };
  function icon(name){var span=make("span","yc-ic");span.setAttribute("aria-hidden","true");span.innerHTML='<svg viewBox="0 0 24 24" focusable="false">'+ICON[name]+'</svg>';return span}
  function tool(name,title,cls){var b=make("button","yc-tool"+(cls?" "+cls:""));b.type="button";b.title=title;b.setAttribute("aria-label",title);b.appendChild(icon(name));return b}
  function readView(){try{return localStorage.getItem(VIEW)==="wide"?"wide":"compact"}catch(e){return"compact"}}
  var view=readView();

  var root=make("div","yc");
  var fab=make("button","yc-fab");
  fab.type="button";fab.title="Чат с Yorika (Alt+Y). Перетащите, чтобы переместить";fab.setAttribute("aria-label","Открыть чат с Yorika");
  fab.setAttribute("aria-expanded","false");fab.setAttribute("aria-controls","yc-panel");
  var face=make("img","yc-face");face.src=IMG;face.alt="";face.width=140;face.height=140;face.decoding="async";face.draggable=false;
  fab.appendChild(face);

  var panel=make("section","yc-panel");panel.id="yc-panel";panel.hidden=true;
  panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Чат с Yorika");
  var head=make("header","yc-head");
  var hface=make("img","yc-head-face");hface.src=IMG;hface.alt="";hface.width=46;hface.height=46;
  var who=make("div","yc-who");who.appendChild(make("strong",null,"Yorika"));
  var sub=make("span","yc-sub","Локальный чат");who.appendChild(sub);
  var findBtn=tool("search","Поиск по разговору");
  var sizeBtn=tool(view==="wide"?"narrow":"wide",view==="wide"?"Компактное окно":"Широкое окно","yc-size");
  var moreBtn=tool("more","Ещё");moreBtn.setAttribute("aria-haspopup","menu");moreBtn.setAttribute("aria-expanded","false");
  var close=tool("close","Закрыть чат","yc-close");
  head.append(hface,who,findBtn,sizeBtn,moreBtn,close);

  var menu=make("div","yc-menu");menu.hidden=true;menu.setAttribute("role","menu");
  function menuItem(text,fn){var b=make("button","yc-menu-item",text);b.type="button";b.setAttribute("role","menuitem");b.addEventListener("click",function(){showMenu(false);fn()});menu.appendChild(b);return b}
  var findBar=make("div","yc-find");findBar.hidden=true;
  var findInput=make("input","yc-find-input");findInput.type="search";findInput.placeholder="Найти в разговоре…";findInput.setAttribute("aria-label","Найти в разговоре");
  var findCount=make("span","yc-find-count");
  findBar.append(icon("search"),findInput,findCount);

  var log=make("div","yc-log");log.setAttribute("role","log");log.setAttribute("aria-live","polite");
  var toBottom=make("button","yc-down");toBottom.type="button";toBottom.title="К последнему сообщению";toBottom.setAttribute("aria-label","К последнему сообщению");toBottom.appendChild(icon("arrow"));toBottom.hidden=true;
  var form=make("form","yc-form");
  var box=make("div","yc-box");
  var input=make("textarea","yc-input");input.rows=1;input.placeholder="Напишите сообщение…";input.setAttribute("aria-label","Сообщение для Yorika");input.maxLength=4000;
  var send=make("button","yc-send");send.type="submit";send.setAttribute("aria-label","Отправить");send.title="Отправить (Enter)";send.appendChild(icon("send"));
  box.append(input,send);
  var hint=make("div","yc-hint");
  var hintText=make("span",null,"Enter — отправить · Shift+Enter — новая строка · ↑ — изменить последнее");var counter=make("span","yc-count");
  hint.append(hintText,counter);
  form.append(box,hint);
  var toast=make("div","yc-toast");toast.setAttribute("role","status");toast.hidden=true;
  panel.append(head,menu,findBar,log,toBottom,form,toast);
  root.append(panel,fab);
  document.body.appendChild(root);

  // ---- a small, safe formatter: code blocks, `code`, **bold**, lists and links, built as DOM nodes ----
  function inline(parent,text){
   var re=/(`[^`\n]+`|\*\*[^*\n]+\*\*|https?:\/\/[^\s<>"«»]+[^\s<>"«».,;:!?)\]])/g,at=0,m;
   while((m=re.exec(text))){
    if(m.index>at)parent.appendChild(document.createTextNode(text.slice(at,m.index)));
    var t=m[0];
    if(t[0]==="`")parent.appendChild(make("code",null,t.slice(1,-1)));
    else if(t[0]==="*")parent.appendChild(make("strong",null,t.slice(2,-2)));
    else{var a=make("a",null,t);a.href=t;a.target="_blank";a.rel="noopener noreferrer";parent.appendChild(a)}
    at=m.index+t.length;
   }
   if(at<text.length)parent.appendChild(document.createTextNode(text.slice(at)));
  }
  function rich(text){
   var out=make("div","yc-text"),parts=String(text).split(/```/);
   parts.forEach(function(part,k){
    if(k%2){var pre=make("pre","yc-code"),body=part.replace(/^[\w+-]*\n/,"").replace(/\n$/,"");pre.appendChild(make("code",null,body));out.appendChild(pre);return}
    var list=null,para=null;
    part.split("\n").forEach(function(line){
     var item=/^\s*(?:[-•*]|\d+[.)])\s+(.*)$/.exec(line);
     if(item){
      var ordered=/^\s*\d/.test(line);
      if(!list||list.tagName!==(ordered?"OL":"UL")){list=make(ordered?"ol":"ul");out.appendChild(list)}
      var li=make("li");inline(li,item[1]);list.appendChild(li);para=null;return;
     }
     list=null;
     if(!line.trim()){para=null;return}
     if(!para){para=make("p");out.appendChild(para)}else para.appendChild(document.createElement("br"));
     inline(para,line);
    });
   });
   if(!out.childNodes.length)out.appendChild(make("p",null,String(text)));
   return out;
  }

  function dayOf(ts){var d=new Date(ts);return d.getFullYear()+"-"+d.getMonth()+"-"+d.getDate()}
  function dayLabel(ts){
   var d=new Date(ts),today=new Date(),yesterday=new Date(Date.now()-864e5);
   if(dayOf(ts)===dayOf(today))return"Сегодня";
   if(dayOf(ts)===dayOf(yesterday))return"Вчера";
   try{return d.toLocaleDateString("ru-RU",{day:"numeric",month:"long",year:d.getFullYear()===today.getFullYear()?undefined:"numeric"})}catch(e){return""}
  }
  function flash(text){toast.textContent=text;toast.hidden=false;clearTimeout(flash.t);flash.t=setTimeout(function(){toast.hidden=true},2200)}
  async function copy(text){
   try{await navigator.clipboard.writeText(text);flash("Скопировано")}
   catch(e){var ta=make("textarea");ta.value=text;document.body.appendChild(ta);ta.select();try{document.execCommand("copy");flash("Скопировано")}catch(x){flash("Не удалось скопировать")}ta.remove()}
  }
  // A rating goes straight into «Опыт»: 👍 keeps the answer as an example, 👎 with a fix teaches the better one.
  async function rate(index,rating,correction){
   var m=history[index],ask=history[index-1];
   if(!m||!ask||ask.from!=="me")return;
   try{
    var r=await fetch("/api/training/sl-chat-rate",{method:"POST",headers:{"Content-Type":"application/json"},
     body:JSON.stringify({prompt:ask.text,ts:ask.ts,answer:m.text,rating:rating,correction:correction||null})});
    if(!r.ok)throw Error(await serverError(r));
    m.rating=rating;changed();render(true);
    flash(rating==="up"?"Сохранила как хороший пример":correction?"Запомню, как надо было ответить":"Отметила как неудачный ответ");
   }catch(e){flash("Оценка не сохранилась: "+(e&&e.message||e))}
  }
  function fixForm(row,index){
   if(row.querySelector(".yc-fix"))return;
   var f=make("div","yc-fix"),ta=make("textarea","yc-fix-input");ta.rows=2;ta.placeholder="Как надо было ответить? Можно оставить пустым";ta.maxLength=2000;
   var ok=make("button","yc-chip yc-chip-on","Сохранить");ok.type="button";
   var no=make("button","yc-chip","Отмена");no.type="button";
   ok.addEventListener("click",function(){rate(index,"down",ta.value.trim())});
   no.addEventListener("click",function(){f.remove()});
   f.append(ta,make("div","yc-fix-actions"));f.lastChild.append(ok,no);row.appendChild(f);ta.focus();
  }
  function actions(row,m,index,isLast){
   var bar=make("div","yc-actions"),b;
   b=tool("copy","Копировать");b.addEventListener("click",function(){copy(m.text)});bar.appendChild(b);
   if(m.from==="bot"&&index>0&&history[index-1].from==="me"){
    b=tool("up","Хороший ответ: в примеры для учёбы","yc-rate"+(m.rating==="up"?" on":""));b.setAttribute("aria-pressed",String(m.rating==="up"));
    b.addEventListener("click",function(){rate(index,"up")});bar.appendChild(b);
    b=tool("down","Плохой ответ: показать, как надо","yc-rate"+(m.rating==="down"?" on":""));b.setAttribute("aria-pressed",String(m.rating==="down"));
    b.addEventListener("click",function(){fixForm(row,index)});bar.appendChild(b);
    if(isLast){b=tool("again","Ответить ещё раз");b.addEventListener("click",regenerate);bar.appendChild(b)}
   }
   if(m.from==="me"){b=tool("edit","Изменить и отправить заново");b.addEventListener("click",function(){editFrom(index)});bar.appendChild(b)}
   bar.appendChild(make("span","yc-time",time(m.ts)));
   return bar;
  }
  var query="";
  function bubble(m,index,prev,isLast){
   if(!prev||dayOf(prev.ts)!==dayOf(m.ts))log.appendChild(make("div","yc-day",dayLabel(m.ts)));
   var first=!prev||prev.from!==m.from||m.ts-prev.ts>5*60e3||dayOf(prev.ts)!==dayOf(m.ts);
   var row=make("div","yc-msg yc-"+m.from+(first?" yc-first":""));
   if(m.from==="bot"){var mini=make("img","yc-mini");mini.alt="";mini.src=face.src;mini.width=28;mini.height=28;if(!first)mini.style.visibility="hidden";row.appendChild(mini)}
   var col=make("div","yc-col");
   var text=rich(m.text);
   if(query&&m.text.toLowerCase().indexOf(query)>=0)row.classList.add("yc-hit");
   col.appendChild(text);
   if(index>=0)col.appendChild(actions(col,m,index,isLast));
   row.appendChild(col);log.appendChild(row);
   return row;
  }
  var SUGGEST=["Что ты умеешь?","Придумай, чем заняться вечером","Помоги составить план на день","Объясни простыми словами, что такое нейросеть"];
  function render(keepScroll){
   var top=log.scrollTop,atEnd=log.scrollHeight-log.scrollTop-log.clientHeight<40;
   log.textContent="";
   var shown=history;
   if(query)shown=history.filter(function(m){return m.text.toLowerCase().indexOf(query)>=0});
   if(!history.length){
    var empty=make("div","yc-empty"),big=make("img","yc-empty-face");big.src=face.src;big.alt="";
    empty.append(big,make("strong",null,"Привет! Я Yorika."),make("p",null,"Спроси меня о чём угодно. Я помню наш разговор и буду рядом на любой странице. Меня можно перетащить в любое место экрана."));
    var chips=make("div","yc-chips");
    SUGGEST.forEach(function(t){var c=make("button","yc-chip",t);c.type="button";c.addEventListener("click",function(){input.value=t;grow();submit()});chips.appendChild(c)});
    empty.appendChild(chips);log.appendChild(empty);
   }
   var prev=null;
   history.forEach(function(m,i){if(shown.indexOf(m)<0)return;bubble(m,i,prev,i===history.length-1);prev=m});
   findCount.textContent=query?(shown.length?shown.length+" найдено":"ничего"):"";
   if(keepScroll&&!atEnd)log.scrollTop=top;else log.scrollTop=log.scrollHeight;
   updateDown();
  }
  function updateDown(){toBottom.hidden=log.scrollHeight-log.scrollTop-log.clientHeight<80}
  function grow(){input.style.height="auto";input.style.height=Math.min(input.scrollHeight,view==="wide"?240:160)+"px";
   var n=input.value.length;counter.textContent=n>3500?n+" / 4000":"";}
  // Positions are kept as a share of the free space, so the avatar stays in the same corner after a resize.
  // Coordinates from the browser are visual pixels; styles are divided by the page zoom from the size setting.
  function zoom(){return parseFloat(getComputedStyle(document.documentElement).zoom)||1}
  function clamp(v,lo,hi){return Math.max(lo,Math.min(v,hi))}
  function readPos(){try{var p=JSON.parse(localStorage.getItem(POS));if(p&&isFinite(p.x)&&isFinite(p.y))return{x:clamp(p.x,0,1),y:clamp(p.y,0,1)}}catch(e){}return null}
  var pos=readPos();
  function place(left,top){
   var z=zoom(),r=fab.getBoundingClientRect();
   left=clamp(left,MARGIN,Math.max(MARGIN,innerWidth-r.width-MARGIN));top=clamp(top,MARGIN,Math.max(MARGIN,innerHeight-r.height-MARGIN));
   root.style.left=left/z+"px";root.style.top=top/z+"px";root.style.right="auto";root.style.bottom="auto";
   return{left:left,top:top,w:r.width,h:r.height};
  }
  function applyPos(){
   if(!pos){root.style.left=root.style.top=root.style.right=root.style.bottom="";layout();return}
   var r=fab.getBoundingClientRect();
   place(pos.x*Math.max(0,innerWidth-r.width-2*MARGIN)+MARGIN,pos.y*Math.max(0,innerHeight-r.height-2*MARGIN)+MARGIN);layout();
  }
  function savePos(p){
   pos={x:(p.left-MARGIN)/Math.max(1,innerWidth-p.w-2*MARGIN),y:(p.top-MARGIN)/Math.max(1,innerHeight-p.h-2*MARGIN)};
   try{localStorage.setItem(POS,JSON.stringify(pos))}catch(e){}
  }
  // Compact: next to the avatar, on whichever side has more room. Wide: a tall panel along the side
  // the avatar is on. On a phone the chat takes the whole screen.
  function layout(){
   if(panel.hidden)return;
   var z=zoom(),r=fab.getBoundingClientRect(),vw=innerWidth,vh=innerHeight,w,h,left,top;
   var phone=vw<600;
   panel.classList.toggle("yc-full",phone);panel.classList.toggle("yc-wide",!phone&&view==="wide");
   if(phone){w=vw;h=vh;left=0;top=0}
   else if(view==="wide"){
    w=Math.min(760*z,vw-2*MARGIN);h=vh-2*MARGIN;top=MARGIN;
    left=r.left+r.width/2>vw/2?vw-w-MARGIN:MARGIN;
   }else{
    w=Math.min(460*z,vw-2*MARGIN);var max=680*z;
    left=r.left+r.width/2>vw/2?r.right-w:r.left;left=clamp(left,MARGIN,vw-w-MARGIN);
    var above=r.top-GAP-MARGIN,below=vh-r.bottom-GAP-MARGIN;
    if(Math.max(above,below)<300*z){h=Math.min(max,vh-2*MARGIN);top=MARGIN}
    else if(above>=below){h=Math.min(max,above);top=r.top-GAP-h}
    else{h=Math.min(max,below);top=r.bottom+GAP}
   }
   panel.style.left=left/z+"px";panel.style.top=top/z+"px";panel.style.width=w/z+"px";panel.style.height=h/z+"px";
  }
  function setView(v){
   view=v;try{localStorage.setItem(VIEW,v)}catch(e){}
   sizeBtn.replaceChildren(icon(v==="wide"?"narrow":"wide"));
   sizeBtn.title=v==="wide"?"Компактное окно":"Широкое окно";sizeBtn.setAttribute("aria-label",sizeBtn.title);
   layout();grow();log.scrollTop=log.scrollHeight;
  }
  function setOpen(open){
   panel.hidden=!open;fab.setAttribute("aria-expanded",String(open));root.classList.toggle("yc-open",open);
   if(open){layout();render();input.focus()}else{showMenu(false);fab.focus()}
  }
  function showMenu(open){menu.hidden=!open;moreBtn.setAttribute("aria-expanded",String(open));if(open&&menu.firstChild)menu.firstChild.focus()}
  function showFind(open){
   findBar.hidden=!open;findBtn.classList.toggle("on",open);
   if(open)findInput.focus();else{findInput.value="";if(query){query="";render()}}
  }

  var busy=false,controller=null;
  function setBusy(flag){
   busy=flag;send.replaceChildren(icon(flag?"stop":"send"));
   send.title=flag?"Остановить ответ":"Отправить (Enter)";send.setAttribute("aria-label",flag?"Остановить ответ":"Отправить");
   send.classList.toggle("yc-stop",flag);
  }
  async function ask(text){
   setBusy(true);
   var typing=make("div","yc-msg yc-bot yc-first yc-typing"),mini=make("img","yc-mini");mini.src=face.src;mini.alt="";mini.width=28;mini.height=28;
   var col=make("div","yc-col"),bubbleText=make("div","yc-text");bubbleText.appendChild(make("span","yc-dots"));
   col.appendChild(bubbleText);typing.append(mini,col);log.appendChild(typing);log.scrollTop=log.scrollHeight;
   var partial="",stopped=false,reply;
   controller=typeof AbortController==="function"?new AbortController():null;
   var signal=controller&&controller.signal;
   try{
    reply=await responder(text,history.slice(),function(part){
     if(stopped)return;partial=part;var near=log.scrollHeight-log.scrollTop-log.clientHeight<80;
     col.replaceChild(rich(part),col.firstChild);if(near)log.scrollTop=log.scrollHeight;
    },signal);
   }catch(e){
    if(e&&e.name==="AbortError")stopped=true;
    else reply="Не удалось получить ответ: "+(e&&e.message||e);
   }
   if(signal&&signal.aborted)stopped=true;
   if(stopped)reply=(partial?partial+"\n\n":"")+"(ответ остановлен)";
   controller=null;typing.remove();
   history.push({from:"bot",text:String(reply||"…").slice(0,4000),ts:Date.now()});changed();render();
   setBusy(false);input.focus();
  }
  function stop(){if(controller)controller.abort()}
  async function submit(){
   if(busy){stop();return}
   var text=input.value.trim();if(!text)return;
   if(query)showFind(false);
   input.value="";grow();
   history.push({from:"me",text:text,ts:Date.now()});changed();render();
   await ask(text);
  }
  function regenerate(){
   if(busy)return;
   var last=history[history.length-1],prev=history[history.length-2];
   if(!last||last.from!=="bot"||!prev||prev.from!=="me")return;
   history.pop();changed();render();ask(prev.text);
  }
  // Editing an earlier message drops it and everything after it, then puts the text back in the box.
  function editFrom(index){
   if(busy)return;
   var m=history[index];if(!m||m.from!=="me")return;
   if(index<history.length-2&&!confirm("Изменить это сообщение? Разговор после него будет удалён."))return;
   history=history.slice(0,index);changed();render();
   input.value=m.text;grow();input.focus();input.setSelectionRange(input.value.length,input.value.length);
  }
  function exportText(){
   var lines=history.map(function(m){return"["+new Date(m.ts).toLocaleString("ru-RU")+"] "+(m.from==="me"?"Вы":"Yorika")+":\n"+m.text});
   var blob=new Blob([lines.join("\n\n")+"\n"],{type:"text/plain;charset=utf-8"}),a=make("a");
   a.href=URL.createObjectURL(blob);a.download="yorika-chat-"+new Date().toISOString().slice(0,10)+".txt";
   document.body.appendChild(a);a.click();a.remove();setTimeout(function(){URL.revokeObjectURL(a.href)},1000);
  }
  menuItem("Новый разговор",function(){
   if(history.length&&!confirm("Начать новый разговор? Текущий будет очищен."))return;
   clearPending=true;history=[];try{localStorage.setItem(THREAD_KEY,newThread())}catch(e){}changed();render();input.focus();
  });
  menuItem("Сохранить разговор в файл",exportText);
  menuItem("Копировать весь разговор",function(){copy(history.map(function(m){return(m.from==="me"?"Вы: ":"Yorika: ")+m.text}).join("\n\n"))});

  // Dragging moves the avatar; a press without movement still opens the chat.
  var drag=null,moved=false;
  fab.addEventListener("pointerdown",function(e){
   if(e.button!==0)return;
   var r=fab.getBoundingClientRect();
   drag={id:e.pointerId,dx:e.clientX-r.left,dy:e.clientY-r.top,sx:e.clientX,sy:e.clientY,last:null};moved=false;
   fab.setPointerCapture(e.pointerId);
  });
  fab.addEventListener("pointermove",function(e){
   if(!drag||e.pointerId!==drag.id)return;
   if(!moved&&Math.hypot(e.clientX-drag.sx,e.clientY-drag.sy)<6)return;
   if(!moved){moved=true;root.classList.add("yc-dragging")}
   drag.last=place(e.clientX-drag.dx,e.clientY-drag.dy);layout();
  });
  function endDrag(e){
   if(!drag||e.pointerId!==drag.id)return;
   if(moved&&drag.last)savePos(drag.last);
   root.classList.remove("yc-dragging");drag=null;
  }
  fab.addEventListener("pointerup",endDrag);
  fab.addEventListener("pointercancel",endDrag);
  fab.addEventListener("click",function(e){if(moved){moved=false;e.preventDefault();return}setOpen(panel.hidden)});
  // Arrow keys move the avatar for keyboard users; Home puts it back in the corner.
  fab.addEventListener("keydown",function(e){
   var step=e.shiftKey?60:20,d={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]}[e.key];
   if(e.key==="Home"){e.preventDefault();pos=null;try{localStorage.removeItem(POS)}catch(x){}applyPos();return}
   if(!d)return;
   e.preventDefault();var r=fab.getBoundingClientRect();savePos(place(r.left+d[0],r.top+d[1]));layout();
  });
  window.addEventListener("resize",applyPos);
  close.addEventListener("click",function(){setOpen(false)});
  sizeBtn.addEventListener("click",function(){setView(view==="wide"?"compact":"wide")});
  moreBtn.addEventListener("click",function(){showMenu(menu.hidden)});
  findBtn.addEventListener("click",function(){showFind(findBar.hidden)});
  findInput.addEventListener("input",function(){query=findInput.value.trim().toLowerCase();render()});
  document.addEventListener("pointerdown",function(e){if(!menu.hidden&&!menu.contains(e.target)&&!moreBtn.contains(e.target))showMenu(false)});
  log.addEventListener("scroll",updateDown);
  toBottom.addEventListener("click",function(){log.scrollTo({top:log.scrollHeight,behavior:"smooth"})});
  form.addEventListener("submit",function(e){e.preventDefault();submit()});
  input.addEventListener("input",grow);
  input.addEventListener("keydown",function(e){
   if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();if(!busy)submit();return}
   if(e.key==="ArrowUp"&&!input.value&&!busy){
    for(var i=history.length-1;i>=0;i--)if(history[i].from==="me"){e.preventDefault();editFrom(i);break}
   }
  });
  panel.addEventListener("keydown",function(e){
   if(e.key!=="Escape")return;
   if(!menu.hidden){showMenu(false);moreBtn.focus();return}
   if(!findBar.hidden){showFind(false);input.focus();return}
   if(busy){stop();return}
   setOpen(false);
  });
  // Alt+Y opens and closes the chat from anywhere; Ctrl+F inside it searches the conversation.
  document.addEventListener("keydown",function(e){
   if(e.altKey&&!e.ctrlKey&&!e.metaKey&&(e.code==="KeyY")){e.preventDefault();setOpen(panel.hidden);return}
   if(!panel.hidden&&(e.ctrlKey||e.metaKey)&&e.code==="KeyF"&&panel.contains(document.activeElement)){e.preventDefault();showFind(true)}
  });
  // Keep the same conversation in other open Yorika tabs.
  window.addEventListener("storage",function(e){if(e.key===KEY){var other=load();history=other.length?mergeHistories(history,other):[];if(!panel.hidden)render(true)}if(e.key===POS){pos=readPos();applyPos()}if(e.key===VIEW){view=readView();setView(view)}});
  function applyLook(){
   var v=readLook(),src=srcOf(v);
   if(face.getAttribute("src")!==src){face.src=src;hface.src=src;if(!panel.hidden)render(true)}
   root.style.setProperty("--yc-size",v.size+"px");
   applyPos();
  }
  window.addEventListener("yorika-avatar",applyLook);
  window.addEventListener("storage",function(e){if(e.key===LOOK)applyLook()});
  applyLook();
  initHistory();

  api.open=function(){setOpen(true)};api.close=function(){setOpen(false)};
  api.label=function(text){sub.textContent=text};if(label)sub.textContent=label;
 }
 var label="",api=window.YorikaChat={
  open:function(){},close:function(){},label:function(text){label=text},
  setResponder:function(fn,text){if(typeof fn==="function"){responder=fn;if(text)api.label(text)}}
 };
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build);else build();
})();
