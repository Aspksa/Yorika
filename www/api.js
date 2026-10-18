// Shared client for the local updater API served by scripts/yorika-tray.ps1.
export const api=async(path,options={})=>{
  const r=await fetch(path,{cache:"no-store",...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});
  const text=await r.text();let data;try{data=JSON.parse(text)}catch{throw Error("Неверный ответ сервера")}
  if(!r.ok)throw Error(data.error||"Ошибка сервера");return data;
};
