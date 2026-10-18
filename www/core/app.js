import { EventBus } from "./events.js";
import { Database } from "./database.js";

/** Application composition root. Models, agents and UI features are not installed yet. */
export class YorikaCore {
  constructor() {
    this.events = new EventBus();
    this.state = "new";
    this.db = null;
  }
  async start() {
    if (this.state !== "new") throw new Error("Yorika has already started");
    this.state = "starting";
    try {
      this.db = await Database.open();
      this.state = "ready";
      this.events.emit("core:ready", { time: Date.now(), dbVersion: 1 });
      return this;
    } catch (error) {
      this.state = "failed";
      this.events.emit("core:error", error);
      throw error;
    }
  }
  stop() {
    this.db?.close();
    this.db = null;
    this.state = "stopped";
    this.events.emit("core:stopped");
    this.events.clear();
  }
}
