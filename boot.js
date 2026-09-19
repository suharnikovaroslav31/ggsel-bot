const http = require("http");
const https = require("https");
const fs = require("fs");
const { spawn, spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname);
const publicPort = Number(process.env.PORT || 3000);
const pyPort = publicPort === 3001 ? 3002 : 3001;

function has(bin) {
  return spawnSync(bin, ["--version"], { encoding: "utf8" }).status === 0;
}

function run(py, args) {
  return spawnSync(py, args, { cwd: root, env: process.env, stdio: "inherit" });
}

function pipOk(py) {
  return spawnSync(py, ["-m", "pip", "--version"], { encoding: "utf8" }).status === 0;
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, (res) => {
      if (res.statusCode === 301 || res.statusCode === 302) {
        return download(res.headers.location, dest).then(resolve, reject);
      }
      if (res.statusCode !== 200) {
        reject(new Error("download " + url + " -> " + res.statusCode));
        return;
      }
      const file = fs.createWriteStream(dest);
      res.pipe(file);
      file.on("finish", () => file.close(resolve));
      file.on("error", reject);
    });
    req.on("error", reject);
  });
}

async function ensurePip(py) {
  if (pipOk(py)) return;
  console.log("pip missing, trying ensurepip...");
  run(py, ["-m", "ensurepip", "--user", "--upgrade"]);
  if (pipOk(py)) return;
  const getPip = path.join(root, "get-pip.py");
  console.log("Downloading get-pip.py...");
  await download("https://bootstrap.pypa.io/get-pip.py", getPip);
  const pipInstall = run(py, [getPip, "--user"]);
  if (pipInstall.status !== 0) {
    throw new Error("get-pip.py failed");
  }
  if (!pipOk(py)) {
    throw new Error("pip still missing after get-pip.py");
  }
}

function startHttp() {
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
    .listen(publicPort, "0.0.0.0", () => {
      console.log("HTTP proxy on", publicPort);
    });
}

(async function main() {
  const py = has("python3") ? "python3" : has("python") ? "python" : null;
  if (!py) {
    console.error("Python not found in this container.");
    process.exit(1);
  }

  startHttp();
  await ensurePip(py);
  console.log("Installing Python packages...");
  const pip = run(py, [
    "-m",
    "pip",
    "install",
    "--user",
    "-r",
    path.join(root, "requirements.txt"),
  ]);
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
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
