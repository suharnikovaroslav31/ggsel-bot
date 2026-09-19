const http = require("http");
const https = require("https");
const fs = require("fs");
const { spawn, spawnSync } = require("child_process");
const path = require("path");

const root = path.resolve(__dirname);
const publicPort = Number(process.env.PORT || 3000);
const pyPort = publicPort === 3001 ? 3002 : 3001;
const venvDir = path.join(root, ".venv");
const venvPy =
  process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
const vendorDir = path.join(root, "pydeps");
const pipPyz = path.join(root, "pip.pyz");
const reqFile = path.join(root, "requirements.txt");

function has(bin) {
  return spawnSync(bin, ["--version"], { encoding: "utf8" }).status === 0;
}

function run(py, args) {
  return spawnSync(py, args, {
    cwd: root,
    env: {
      ...process.env,
      PIP_DISABLE_PIP_VERSION_CHECK: "1",
    },
    stdio: "inherit",
  });
}

function download(url, dest) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location) {
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

async function ensurePipPyz() {
  if (fs.existsSync(pipPyz) && fs.statSync(pipPyz).size > 10000) return;
  console.log("Downloading pip.pyz...");
  await download("https://bootstrap.pypa.io/pip/pip.pyz", pipPyz);
}

function withPythonPath(extra) {
  const parts = [vendorDir];
  if (process.env.PYTHONPATH) parts.push(process.env.PYTHONPATH);
  return { PYTHONPATH: parts.join(path.delimiter), ...extra };
}

async function preparePython(systemPy) {
  await ensurePipPyz();
  run(systemPy, ["-V"]);

  console.log("Creating venv without system pip...");
  run(systemPy, ["-m", "venv", "--without-pip", "--clear", venvDir]);
  if (fs.existsSync(venvPy)) {
    console.log("Installing packages into venv via pip.pyz...");
    const pip = run(venvPy, [pipPyz, "install", "-r", reqFile]);
    if (pip.status === 0) {
      return { py: venvPy, env: {} };
    }
    console.error("venv install failed:", pip.status);
  } else {
    console.error("venv was not created, using --target instead");
  }

  fs.mkdirSync(vendorDir, { recursive: true });
  console.log("Installing packages into", vendorDir, "via pip.pyz --target...");
  const pip = run(systemPy, [pipPyz, "install", "--target", vendorDir, "-r", reqFile]);
  if (pip.status !== 0) {
    throw new Error("pip.pyz install failed: " + pip.status);
  }
  return { py: systemPy, env: withPythonPath() };
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
  const systemPy = has("python3") ? "python3" : has("python") ? "python" : null;
  if (!systemPy) {
    console.error("Python not found in this container.");
    process.exit(1);
  }

  startHttp();
  const ready = await preparePython(systemPy);

  console.log("GGSel boot:", ready.py, "main.py | proxy", publicPort, "->", pyPort);
  const child = spawn(ready.py, [path.join(root, "main.py")], {
    cwd: root,
    env: {
      ...process.env,
      ...ready.env,
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
