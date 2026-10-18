"use strict";
(function () {
  const STORES = ["settings", "projects", "memories", "conversations", "messages", "tasks"];
  const KEYS = ["yorika.chat", "yorika.avatar", "yorika.avatars"];
  const status = document.getElementById("status");
  const button = document.getElementById("export");
  document.getElementById("origin").textContent = "Текущий адрес: " + location.origin;

  function requestValue(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || Error("IndexedDB read failed"));
    });
  }
  async function browserDb() {
    if (!("indexedDB" in window)) return {stores: {}, warning: "IndexedDB недоступна"};
    // indexedDB.open can create an empty v1 database when none existed. Never upgrade
    // or delete existing databases as part of an export.
    if (typeof indexedDB.databases === "function") {
      const names = await indexedDB.databases();
      if (!names.some(x => x.name === "yorika")) return {stores: {}, warning: "База yorika отсутствует на этом адресе"};
    }
    const request = indexedDB.open("yorika");
    const db = await requestValue(request);
    try {
      const stores = {};
      for (const name of STORES) {
        if (!db.objectStoreNames.contains(name)) continue;
        const tx = db.transaction(name, "readonly");
        stores[name] = await requestValue(tx.objectStore(name).getAll());
      }
      return {stores};
    } finally { db.close(); }
  }
  async function perform() {
    button.disabled = true;
    status.textContent = "Чтение данных...";
    try {
      if (!["127.0.0.1", "localhost"].includes(location.hostname)) throw Error("Экспорт разрешён только на локальном адресе");
      const storage = {};
      for (const key of KEYS) {
        const value = localStorage.getItem(key);
        if (value !== null) storage[key] = value;
      }
      const database = await browserDb();
      const payload = {
        format: "yorika-browser-export",
        schema_version: 1,
        exported_at: new Date().toISOString(),
        origin: location.origin,
        indexeddb: database.stores,
        localstorage: storage,
        warning: database.warning || null
      };
      const blob = new Blob([JSON.stringify(payload, null, 2)], {type: "application/json"});
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "yorika-browser-export-" + location.port + "-" + Date.now() + ".json";
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 30000);
      status.textContent = "Экспорт выполнен для " + location.origin + ". Записей IndexedDB: " +
        Object.values(database.stores).reduce((n, list) => n + list.length, 0) +
        ". Полей localStorage: " + Object.keys(storage).length +
        ". " + (database.warning || "Не удаляйте исходные данные до проверки импорта.");
    } catch (error) {
      status.textContent = "Ошибка экспорта: " + (error && error.message || error);
    } finally { button.disabled = false; }
  }
  button.addEventListener("click", perform);
})();
