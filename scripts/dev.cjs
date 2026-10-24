const { spawn, spawnSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const python = path.join(
  root,
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const angular = path.join(root, "apps/web/node_modules/@angular/cli/bin/ng.js");
if (!existsSync(python) || !existsSync(angular)) {
  console.error(
    'Run "uv sync" and "npm --prefix apps/web ci" before starting PaperLab.',
  );
  process.exit(1);
}
const migration = spawnSync(python, ["-m", "alembic", "upgrade", "head"], {
  cwd: root,
  stdio: "inherit",
  windowsHide: true,
});
if (migration.error || migration.status !== 0) {
  console.error(
    "The database migration failed.",
    migration.error?.message || "",
  );
  process.exit(1);
}
const apiPort = process.env.PAPERLAB_API_PORT || "8000";
const webPort = process.env.PAPERLAB_WEB_PORT || "4200";
const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null || !child.pid) continue;
    if (process.platform === "win32") {
      spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      child.kill("SIGTERM");
    }
  }
  process.exit(code);
}
function launch(command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    stdio: "inherit",
    windowsHide: true,
  });
  children.push(child);
  child.on("error", (error) => {
    console.error(error.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) stop(code ?? 1);
  });
}
launch(
  python,
  [
    "-m",
    "uvicorn",
    "paperlab_api.main:create_app",
    "--factory",
    "--host",
    "127.0.0.1",
    "--port",
    apiPort,
  ],
  root,
);
launch(
  process.execPath,
  [angular, "serve", "--host", "127.0.0.1", "--port", webPort],
  path.join(root, "apps/web"),
);
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
console.log(
  `PaperLab: http://127.0.0.1:${webPort} | API: http://127.0.0.1:${apiPort}/docs`,
);
