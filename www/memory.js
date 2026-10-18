import {Database} from "./core/database.js";
const list=document.getElementById("memory-list");
const status=document.getElementById("memory-status");
const query=document.getElementById("memory-query");
let db,records=[];
function visibleText(value){
 const parts=[],stack=[value];let visited=0;
 while(stack.length&&visited++<10000){
  const item=stack.pop();
  if(typeof item==="string")parts.push(item);
  else if(Array.isArray(item))stack.push(...item);
  else if(item&&typeof item==="object")stack.push(...Object.values(item));
 }
 return parts.join(" ").toLocaleLowerCase();
}
function render(){
 const term=query.value.trim().toLocaleLowerCase();
 const matches=records.filter(item=>!term||visibleText(item).includes(term)).slice(0,200);
 list.replaceChildren();
 for(const item of matches){
  const li=document.createElement("li");
  const heading=document.createElement("strong");heading.textContent=String(item.id);
  const text=document.createElement("pre");text.textContent=JSON.stringify(item,null,2);
  const remove=document.createElement("button");remove.className="ghost danger";
  remove.type="button";remove.textContent="Удалить воспоминание";
  remove.onclick=async()=>{
   if(!confirm('Удалить воспоминание «'+item.id+'» из текущего браузера?'))return;
   remove.disabled=true;
   try{
    // Refuse stale UI deletes: only delete the record that was displayed.
    const now=await db.get("memories",item.id);
    if(JSON.stringify(now)!==JSON.stringify(item))throw Error("Запись изменилась. Обновите список.");
    await db.delete("memories",item.id);
    await refresh();
   }catch(error){status.textContent="Ошибка удаления: "+error.message;remove.disabled=false}
  };
  li.append(heading,text,remove);list.append(li);
 }
 status.textContent="Найдено "+matches.length+" из "+records.length+
  (records.length>200?"; показываются первые 200 совпадений":"");
}
async function refresh(){
 records=await db.all("memories");render();
}
query.addEventListener("input",render);
(async()=>{
 try{db=await Database.open();await refresh()}
 catch(error){status.textContent="Память недоступна: "+error.message}
})();
