// Yorika's floating avatar and chat panel, shared by every page. History lives per browser in localStorage.
// A real responder can be plugged in with YorikaChat.setResponder(async (text, history) => "reply").
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
 var responder=async function(text,history,onChunk){
  var receivedAny=false;
  try{
   var stream=await fetch('/api/chat/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:text,conversation_id:threadId()}),cache:'no-store'});
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
      else if(evt.type==='error')throw Error('Не удалось завершить поток');
     }
    }
    if(finished&&full.trim())return full;
    if(full)throw Error('Поток оборвался');
   }
  }catch(e){if(receivedAny)throw e;/* Streaming unavailable before first delta. */}

  try{
   var generated=await fetch("/api/chat/respond",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({query:text,conversation_id:threadId()}),cache:"no-store"
   });
   if(generated.ok){
    var completed=await generated.json();
    if(typeof completed.answer==="string"&&completed.answer.trim())return completed.answer;
   }
  }catch(e){/* Local model is optional; fall back to source-labeled memory search. */}

  try{
   var response=await fetch("/api/memory/recall",{
    method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({query:text}),cache:"no-store"
   });
   if(!response.ok)throw Error("Поиск SQLite недоступен");
   var result=await response.json();
   if(Array.isArray(result.memories)&&result.memories.length){
    return "Нашла в сохранённой памяти (это поиск, а не ответ языковой модели):\\n"+
     result.memories.map(function(m){
      return "• "+m.text+" [источник: "+m.source+
       (m.source_id?", "+m.source_id:"")+"]";
     }).join("\\n");
   }
   return "В сохранённой памяти пока не нашла подходящих записей. Языковая модель ещё не подключена.";
  }catch(e){
   return "Поиск долговременной памяти сейчас недоступен. Языковая модель ещё не подключена.";
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
  var root=make("div","yc");
  var fab=make("button","yc-fab");
  fab.type="button";fab.title="Чат с Yorika. Перетащите, чтобы переместить";fab.setAttribute("aria-label","Открыть чат с Yorika");
  fab.setAttribute("aria-expanded","false");fab.setAttribute("aria-controls","yc-panel");
  var face=make("img","yc-face");face.src=IMG;face.alt="";face.width=140;face.height=140;face.decoding="async";face.draggable=false;
  fab.appendChild(face);

  var panel=make("section","yc-panel");panel.id="yc-panel";panel.hidden=true;
  panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Чат с Yorika");
  var head=make("header","yc-head");
  var hface=make("img","yc-head-face");hface.src=IMG;hface.alt="";hface.width=46;hface.height=46;
  var who=make("div","yc-who");who.appendChild(make("strong",null,"Yorika"));
  var sub=make("span","yc-sub","Локальный чат");who.appendChild(sub);
  var clear=make("button","yc-icon","Очистить");clear.type="button";clear.title="Очистить историю чата";
  var close=make("button","yc-icon yc-close","×");close.type="button";close.title="Закрыть";close.setAttribute("aria-label","Закрыть чат");
  head.append(hface,who,clear,close);

  var log=make("div","yc-log");log.setAttribute("role","log");log.setAttribute("aria-live","polite");
  var form=make("form","yc-form");
  var input=make("textarea","yc-input");input.rows=1;input.placeholder="Напишите сообщение…";input.setAttribute("aria-label","Сообщение для Yorika");input.maxLength=4000;
  var send=make("button","yc-send");send.type="submit";send.setAttribute("aria-label","Отправить");send.title="Отправить";
  send.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 12h13"/><path d="M13 6l6 6-6 6"/></svg>';
  form.append(input,send);
  panel.append(head,log,form);
  root.append(panel,fab);
  document.body.appendChild(root);

  function bubble(m){
   var row=make("div","yc-msg yc-"+m.from);
   row.appendChild(make("p","yc-text",m.text));
   row.appendChild(make("span","yc-time",time(m.ts)));
   log.appendChild(row);
  }
  function render(){
   log.textContent="";
   if(!history.length)bubble({from:"bot",text:"Привет! Я Yorika. Я буду рядом на любой странице. Меня можно перетащить в любое место экрана.",ts:Date.now()});
   history.forEach(bubble);
   log.scrollTop=log.scrollHeight;
  }
  function grow(){input.style.height="auto";input.style.height=Math.min(input.scrollHeight,120)+"px"}
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
  // The panel opens on whichever side of the avatar has more room.
  function layout(){
   if(panel.hidden)return;
   var z=zoom(),r=fab.getBoundingClientRect(),vw=innerWidth,vh=innerHeight;
   var w=Math.min(380*z,vw-2*MARGIN),max=560*z;
   var left=r.left+r.width/2>vw/2?r.right-w:r.left;left=clamp(left,MARGIN,vw-w-MARGIN);
   var above=r.top-GAP-MARGIN,below=vh-r.bottom-GAP-MARGIN,h,top;
   if(Math.max(above,below)<260*z){h=Math.min(max,vh-2*MARGIN);top=MARGIN}
   else if(above>=below){h=Math.min(max,above);top=r.top-GAP-h}
   else{h=Math.min(max,below);top=r.bottom+GAP}
   panel.style.left=left/z+"px";panel.style.top=top/z+"px";panel.style.width=w/z+"px";panel.style.height=h/z+"px";
  }
  function setOpen(open){
   panel.hidden=!open;fab.setAttribute("aria-expanded",String(open));root.classList.toggle("yc-open",open);
   if(open){layout();render();input.focus()}else fab.focus();
  }
  var busy=false;
  async function submit(){
   var text=input.value.trim();if(!text||busy)return;
   busy=true;send.disabled=true;input.value="";grow();
   history.push({from:"me",text:text,ts:Date.now()});changed();bubble(history[history.length-1]);
   var typing=make("div","yc-msg yc-bot yc-typing");typing.appendChild(make("p","yc-text","…"));log.appendChild(typing);log.scrollTop=log.scrollHeight;
   var reply;
   try{reply=await responder(text,history.slice(),function(part){typing.firstChild.textContent=part;log.scrollTop=log.scrollHeight})}catch(e){reply="Не удалось получить ответ: "+(e&&e.message||e)}
   typing.remove();
   history.push({from:"bot",text:String(reply||"…"),ts:Date.now()});changed();bubble(history[history.length-1]);
   log.scrollTop=log.scrollHeight;busy=false;send.disabled=false;input.focus();
  }

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
  clear.addEventListener("click",function(){clearPending=true;history=[];try{localStorage.setItem(THREAD_KEY,newThread())}catch(e){}changed();render();input.focus()});
  form.addEventListener("submit",function(e){e.preventDefault();submit()});
  input.addEventListener("input",grow);
  input.addEventListener("keydown",function(e){if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit()}});
  panel.addEventListener("keydown",function(e){if(e.key==="Escape")setOpen(false)});
  // Keep the same conversation in other open Yorika tabs.
  window.addEventListener("storage",function(e){if(e.key===KEY){var other=load();history=other.length?mergeHistories(history,other):[];if(!panel.hidden)render()}if(e.key===POS){pos=readPos();applyPos()}});
  function applyLook(){
   var v=readLook(),src=srcOf(v);
   if(face.getAttribute("src")!==src){face.src=src;hface.src=src}
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
