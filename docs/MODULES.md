# Yorika modules — foundation v1

First-party modules may be statically imported and registered with `core.modules.register({ id, version, permissions, activate })`.

- IDs: lowercase letters, digits, hyphens (2–64 characters; must start with a letter).
- Versions: `major.minor.patch`.
- Permissions: `storage:read`, `storage:write`, `events:emit`.
- Settings and granted permissions are stored under `settings/module:<id>` in IndexedDB.
- Records are namespaced by module ID. No module receives direct Database access from its context.
- Grants default to empty and are applied only when configuring a stopped module.
- `activate(context)` may return an asynchronous cleanup function; `deactivate` calls it.

Example (for future trusted module code, not enabled now):

```js
core.modules.register({
  id: "example-module",
  version: "1.0.0",
  permissions: ["storage:read"],
  async activate(context) {
    const value = await context.storage.get("counter");
    console.log(value);
    return () => {};
  }
});
await core.modules.configure("example-module", { values: {}, permissions: ["storage:read"] });
await core.modules.activate("example-module");
```

## Security and persistence limits

This design offers **API-level separation only**. JavaScript modules in the same browser realm can still access global objects such as `indexedDB`, `fetch`, and the DOM, bypassing the registry. Do **not** execute third-party/untrusted modules this way. True permission enforcement requires isolation using Workers or separate processes, plus a mediated host API.

IndexedDB is scoped to the origin. Because Yorika currently chooses a different port at launch, stored configuration may not be accessible on the next launch. Permanent portable storage and database migrations must be implemented before using this for valuable data.

No modules are installed or activated by default. The webpage remains intentionally empty.
