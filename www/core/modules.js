/**
 * Yorika module registry.
 * Modules must be trusted, statically imported first-party code.
 * This is logical storage isolation, NOT a JavaScript security sandbox.
 */
const ID_RE = /^[a-z][a-z0-9-]{1,63}$/;
const VERSION_RE = /^\d+\.\d+\.\d+$/;
const RIGHTS = new Set(["storage:read", "storage:write", "events:emit"]);
const clone = value => structuredClone(value);

export class ModuleRegistry {
  #db;
  #events;
  #registered = new Map();
  #active = new Map();
  constructor(db, events) {
    this.#db = db;
    this.#events = events;
  }
  register(definition) {
    if (!definition || !ID_RE.test(definition.id) || !VERSION_RE.test(definition.version)) {
      throw new TypeError("Invalid module ID or semantic version");
    }
    if (this.#registered.has(definition.id)) throw new Error("Module already registered");
    if (typeof definition.activate !== "function") throw new TypeError("Module requires activate(context)");
    const permissions = [...new Set(definition.permissions ?? [])];
    if (permissions.some(p => !RIGHTS.has(p))) throw new Error("Unknown module permission");
    const meta = Object.freeze({ id: definition.id, version: definition.version, permissions: Object.freeze(permissions) });
    this.#registered.set(meta.id, { meta, activate: definition.activate });
    return meta;
  }
  list() { return [...this.#registered.values()].map(({meta}) => ({ ...meta, permissions: [...meta.permissions], active: this.#active.has(meta.id) })); }
  async activate(id) {
    const definition = this.#registered.get(id);
    if (!definition) throw new Error("Unknown module");
    if (this.#active.has(id)) throw new Error("Module already active");
    const { meta } = definition;
    const settingsKey = "module:" + id;
    const record = await this.#db.get("settings", settingsKey);
    // No default grants. The permissions recorded by the owner may only narrow those declared in code.
    const granted = (record?.permissions ?? []).filter(p => meta.permissions.includes(p));
    const allowed = new Set(granted);
    const requireRight = right => { if (!allowed.has(right)) throw new Error("Permission denied: " + right); };
    const key = name => {
      if (typeof name !== "string" || !name || name.length > 256) throw new TypeError("Invalid module record key");
      return "module:" + id + ":" + name;
    };
    const context = Object.freeze({
      id: meta.id, version: meta.version,
      permissions: Object.freeze([...allowed]),
      settings: Object.freeze(clone(record?.values ?? {})),
      storage: Object.freeze({
        get: async name => { requireRight("storage:read"); return clone(await this.#db.get("settings", key(name))); },
        put: async (name, value) => { requireRight("storage:write"); await this.#db.put("settings", { id: key(name), value: clone(value) }); },
        delete: async name => { requireRight("storage:write"); await this.#db.delete("settings", key(name)); }
      }),
      emit: (name, value) => { requireRight("events:emit"); this.#events.emit("module:" + id + ":" + name, clone(value)); }
    });
    const dispose = await definition.activate(context);
    if (dispose !== undefined && typeof dispose !== "function") throw new TypeError("activate must return an optional cleanup function");
    this.#active.set(id, dispose ?? (() => {}));
    return meta;
  }
  async configure(id, { values = {}, permissions = [] } = {}) {
    if (!this.#registered.has(id)) throw new Error("Unknown module");
    if (this.#active.has(id)) throw new Error("Stop module before changing configuration");
    if (!values || typeof values !== "object" || Array.isArray(values)) throw new TypeError("Invalid settings");
    const permitted = this.#registered.get(id).meta.permissions;
    if (!Array.isArray(permissions) || permissions.some(p => !permitted.includes(p))) throw new Error("Invalid permission grant");
    await this.#db.put("settings", { id: "module:" + id, values: clone(values), permissions: [...new Set(permissions)] });
  }
  async deactivate(id) {
    const cleanup = this.#active.get(id);
    if (!cleanup) return false;
    await cleanup();
    this.#active.delete(id);
    return true;
  }
  async stopAll() {
    for (const id of [...this.#active.keys()].reverse()) await this.deactivate(id);
  }
}
