const http = require("http");
const { spawn, spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname);
const publicPort = Number(process.env.PORT || 3000);
const pyPort = publicPort === 3001 ? 3002 : 3001;

function has(bin) {
  return spawnSync(bin, ["--version"], { encoding: "utf8" }).status === 0;
}

const py = has("python3") ? "python3" : has("python") ? "python" : null;
if (!py) {
  console.error("Python not found in this container.");
  process.exit(1);
}

console.log("Installing Python packages...");
const pip = spawnSync(
  py,
  ["-m", "pip", "install", "--user", "-r", path.join(root, "requirements.txt")],
  { cwd: root, env: process.env, stdio: "inherit" }
);
if (pip.status !== 0) {
  console.error("pip install failed:", pip.status);
  process.exit(pip.status || 1);
}

console.log("GGSel boot:", py, "main.py | proxy", publicPort, "->", pyPort);
const child = spawn(py, [path.join(root, "main.py")], {
  cwd: root,
  env: {
    ...process.env,
    PORT: String(pyPort),
    WEB_PORT: String(pyPort),
    PYTHONUNBUFFERED: "1",
  },
  stdio: "inherit",
});
child.on("exit", (code) => process.exit(code == null ? 1 : code));

http
  .createServer((req, res) => {
    const proxy = http.request(
      {
        hostname: "127.0.0.1",
        port: pyPort,
        path: req.url,
        method: req.method,
        headers: { ...req.headers, host: `127.0.0.1:${pyPort}` },
      },
      (incoming) => {
        res.writeHead(incoming.statusCode || 502, incoming.headers);
        incoming.pipe(res);
      }
    );
    proxy.on("error", () => {
      res.writeHead(200, { "content-type": "text/plain; charset=utf-8" });
      res.end("GGSel starting...");
    });
    req.pipe(proxy);
  })
  .listen(publicPort, "0.0.0.0");
