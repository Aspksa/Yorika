import { YorikaCore } from "./core/app.js";

const status = document.getElementById("status");
const core = new YorikaCore();
try {
  await core.start();
  status.textContent = ""; // Intentionally empty starting interface.
  // Expose a tiny diagnostics handle for development, no AI features implied.
  globalThis.yorika = core;
} catch (error) {
  status.textContent = "Не удалось открыть локальную базу данных";
  console.error("Yorika initialization failed:", error);
}
