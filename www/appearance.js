// Applies the look chosen on settings.html before the page paints. Stored per browser in localStorage.
(function(){
 var KEY="yorika.appearance";
 var defaults={theme:"dark",accent:"gold",radius:"normal",size:"normal"};
 var allowed={theme:["dark","light","system"],accent:["gold","jade"],radius:["sharp","normal","round"],size:["compact","normal","large"]};
 var media=window.matchMedia?window.matchMedia("(prefers-color-scheme: light)"):null;
 function read(){
  var stored={},out={};
  try{stored=JSON.parse(localStorage.getItem(KEY))||{}}catch(e){}
  for(var k in defaults)out[k]=allowed[k].indexOf(stored[k])>=0?stored[k]:defaults[k];
  return out;
 }
 function apply(s){
  var root=document.documentElement,theme=s.theme==="system"?(media&&media.matches?"light":"dark"):s.theme;
  root.dataset.theme=theme;root.dataset.accent=s.accent;root.dataset.radius=s.radius;root.dataset.size=s.size;
  var meta=document.querySelector('meta[name="theme-color"]');
  if(meta)meta.content=theme==="light"?"#f5f1ea":"#1c1a17";
 }
 function save(s){try{localStorage.setItem(KEY,JSON.stringify(s))}catch(e){}apply(s)}
 apply(read());
 if(media&&media.addEventListener)media.addEventListener("change",function(){var s=read();if(s.theme==="system")apply(s)});
 // Keep other open Yorika tabs in step with a change made on the Settings page.
 window.addEventListener("storage",function(e){if(e.key===KEY)apply(read())});
 window.YorikaAppearance={read:read,save:save,defaults:defaults};
})();
