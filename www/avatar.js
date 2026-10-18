// Yorika's floating avatar and chat panel, shared by every page. History lives per browser in localStorage.
// A real responder can be plugged in with YorikaChat.setResponder(async (text, history) => "reply").
(function(){
 var KEY="yorika.chat",LIMIT=200,IMG="./assets/yorika-avatar.webp";
 var responder=function(){
  return "Я пока не подключена к языковой модели, поэтому отвечать по-настоящему не умею. Но я всё запоминаю: история чата сохраняется в этом браузере.";
 };
 function load(){try{var v=JSON.parse(localStorage.getItem(KEY));return Array.isArray(v)?v:[]}catch(e){return[]}}
 function store(list){try{localStorage.setItem(KEY,JSON.stringify(list.slice(-LIMIT)))}catch(e){}}
 function make(tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!=null)n.textContent=text;return n}
 function time(ts){try{return new Date(ts).toLocaleTimeString("ru-RU",{hour:"2-digit",minute:"2-digit"})}catch(e){return""}}

 function build(){
  var history=load();
  var root=make("div","yc");
  var fab=make("button","yc-fab");
  fab.type="button";fab.title="Чат с Yorika";fab.setAttribute("aria-label","Открыть чат с Yorika");
  fab.setAttribute("aria-expanded","false");fab.setAttribute("aria-controls","yc-panel");
  var face=make("img","yc-face");face.src=IMG;face.alt="";face.width=64;face.height=64;face.decoding="async";
  fab.appendChild(face);

  var panel=make("section","yc-panel");panel.id="yc-panel";panel.hidden=true;
  panel.setAttribute("role","dialog");panel.setAttribute("aria-label","Чат с Yorika");
  var head=make("header","yc-head");
  var hface=make("img","yc-head-face");hface.src=IMG;hface.alt="";hface.width=40;hface.height=40;
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
   if(!history.length)bubble({from:"bot",text:"Привет! Я Yorika. Нажми на меня на любой странице, и я буду рядом.",ts:Date.now()});
   history.forEach(bubble);
   log.scrollTop=log.scrollHeight;
  }
  function grow(){input.style.height="auto";input.style.height=Math.min(input.scrollHeight,120)+"px"}
  function setOpen(open){
   panel.hidden=!open;fab.setAttribute("aria-expanded",String(open));root.classList.toggle("yc-open",open);
   if(open){render();input.focus()}else fab.focus();
  }
  var busy=false;
  async function submit(){
   var text=input.value.trim();if(!text||busy)return;
   busy=true;send.disabled=true;input.value="";grow();
   history.push({from:"me",text:text,ts:Date.now()});store(history);bubble(history[history.length-1]);
   var typing=make("div","yc-msg yc-bot yc-typing");typing.appendChild(make("p","yc-text","…"));log.appendChild(typing);log.scrollTop=log.scrollHeight;
   var reply;
   try{reply=await responder(text,history.slice())}catch(e){reply="Не удалось получить ответ: "+(e&&e.message||e)}
   typing.remove();
   history.push({from:"bot",text:String(reply||"…"),ts:Date.now()});store(history);bubble(history[history.length-1]);
   log.scrollTop=log.scrollHeight;busy=false;send.disabled=false;input.focus();
  }

  fab.addEventListener("click",function(){setOpen(panel.hidden)});
  close.addEventListener("click",function(){setOpen(false)});
  clear.addEventListener("click",function(){history=[];store(history);render();input.focus()});
  form.addEventListener("submit",function(e){e.preventDefault();submit()});
  input.addEventListener("input",grow);
  input.addEventListener("keydown",function(e){if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit()}});
  panel.addEventListener("keydown",function(e){if(e.key==="Escape")setOpen(false)});
  // Keep the same conversation in other open Yorika tabs.
  window.addEventListener("storage",function(e){if(e.key===KEY){history=load();if(!panel.hidden)render()}});

  api.open=function(){setOpen(true)};api.close=function(){setOpen(false)};
  api.label=function(text){sub.textContent=text};if(label)sub.textContent=label;
 }
 var label="",api=window.YorikaChat={
  open:function(){},close:function(){},label:function(text){label=text},
  setResponder:function(fn,text){if(typeof fn==="function"){responder=fn;if(text)api.label(text)}}
 };
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build);else build();
})();
