const DB_NAME = "yorika";
const DB_VERSION = 1;
const STORES = ["settings", "projects", "memories", "conversations", "messages", "tasks"];

function requestResult(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error("IndexedDB request failed"));
  });
}

export class Database {
  #db;
  static async open() {
    if (!("indexedDB" in globalThis)) throw new Error("IndexedDB is unavailable");
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      for (const store of STORES) {
        if (!db.objectStoreNames.contains(store)) db.createObjectStore(store, { keyPath: "id" });
      }
    };
    const db = await requestResult(request);
    const instance = new Database();
    instance.#db = db;
    db.onversionchange = () => db.close();
    return instance;
  }
  #store(name, mode = "readonly") {
    if (!STORES.includes(name)) throw new Error("Unknown Yorika store: " + name);
    return this.#db.transaction(name, mode).objectStore(name);
  }
  async get(name, id) { return requestResult(this.#store(name).get(id)); }
  async all(name) { return requestResult(this.#store(name).getAll()); }
  async put(name, record) {
    if (!record || typeof record !== "object" || typeof record.id !== "string" || !record.id.trim()) {
      throw new TypeError("record must have a nonempty string id");
    }
    return requestResult(this.#store(name, "readwrite").put(record));
  }
  async delete(name, id) { return requestResult(this.#store(name, "readwrite").delete(id)); }
  async clear(name) { return requestResult(this.#store(name, "readwrite").clear()); }
  close() { this.#db?.close(); }
  static get stores() { return [...STORES]; }
}
