# Bothost sometimes auto-starts this file with Node.
# It is not the Mini App — it only launches the Python bot.
const { spawn, spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname, "..");
const env = { ...process.env, PYTHONUNBUFFERED: "1" };

function has(bin) {
  return spawnSync(bin, ["--version"], { encoding: "utf8" }).status === 0;
}

const py = has("python3") ? "python3" : has("python") ? "python" : null;
if (!py) {
  console.error("Python not found. In Bothost set start command: python main.py");
  process.exit(1);
}

console.log("Starting", py, "main.py from", root);
const child = spawn(py, ["main.py"], { cwd: root, env, stdio: "inherit" });
child.on("exit", (code) => process.exit(code == null ? 1 : code));
