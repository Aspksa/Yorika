/** Small scoped event bus. */
export class EventBus {
  #listeners = new Map();
  on(type, handler) {
    if (typeof handler !== "function") throw new TypeError("handler must be a function");
    const group = this.#listeners.get(type) ?? new Set();
    group.add(handler); this.#listeners.set(type, group);
    return () => { group.delete(handler); if (!group.size) this.#listeners.delete(type); };
  }
  emit(type, payload) {
    for (const handler of [...(this.#listeners.get(type) ?? [])]) {
      try { handler(payload); } catch (error) { console.error("Yorika event error", error); }
    }
  }
  clear() { this.#listeners.clear(); }
}
