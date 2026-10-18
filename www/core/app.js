import { EventBus } from "./events.js";
import { Database } from "./database.js";
import { ModuleRegistry } from "./modules.js";

/** Application composition root. Models, agents and UI features are not installed yet. */
export class YorikaCore {
  constructor() {
    this.events = new EventBus();
    this.state = "new";
    this.db = null;
    this.modules = null;
  }
  async start() {
    if (this.state !== "new") throw new Error("Yorika has already started");
    this.state = "starting";
    try {
      this.db = await Database.open();
      this.modules = new ModuleRegistry(this.db, this.events);
      this.state = "ready";
      this.events.emit("core:ready", { time: Date.now(), dbVersion: Database.version });
      return this;
    } catch (error) {
      this.state = "failed";
      this.events.emit("core:error", error);
      throw error;
    }
  }
  async stop() {
    await this.modules?.stopAll();
    this.modules = null;
    this.db?.close();
    this.db = null;
    this.state = "stopped";
    this.events.emit("core:stopped");
    this.events.clear();
  }
}
