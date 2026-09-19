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

let pyReady = false;

function has(bin) {
  return spawnSync(bin, ["--version"], { encoding: "utf8" }).status === 0;
}

function runAsync(py, args) {
  return new Promise((resolve) => {
    const child = spawn(py, args, {
      cwd: root,
      env: {
        ...process.env,
        PIP_DISABLE_PIP_VERSION_CHECK: "1",
      },
      stdio: "inherit",
    });
    child.on("error", (err) => {
      console.error("spawn error", err);
      resolve(1);
    });
    child.on("exit", (code) => resolve(code == null ? 1 : code));
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

function withPythonPath() {
  const parts = [vendorDir];
  if (process.env.PYTHONPATH) parts.push(process.env.PYTHONPATH);
  return { PYTHONPATH: parts.join(path.delimiter) };
}

async function pythonImportsOk(py, env) {
  const child = spawn(py, ["-c", "import aiogram, aiohttp, aiosqlite"], {
    cwd: root,
    env: { ...process.env, ...env },
    stdio: "ignore",
  });
  return new Promise((resolve) => {
    child.on("error", () => resolve(false));
    child.on("exit", (code) => resolve(code === 0));
  });
}

async function preparePython(systemPy) {
  if (fs.existsSync(venvPy) && (await pythonImportsOk(venvPy, {}))) {
    console.log("Using existing venv");
    return { py: venvPy, env: {} };
  }
  if (await pythonImportsOk(systemPy, withPythonPath())) {
    console.log("Using system python + pydeps");
    return { py: systemPy, env: withPythonPath() };
  }

  await ensurePipPyz();
  await runAsync(systemPy, ["-V"]);

  if (!fs.existsSync(venvPy)) {
    console.log("Creating venv without system pip...");
    await runAsync(systemPy, ["-m", "venv", "--without-pip", venvDir]);
  }
  if (fs.existsSync(venvPy)) {
    console.log("Installing packages into venv via pip.pyz...");
    const pip = await runAsync(venvPy, [pipPyz, "install", "-r", reqFile]);
    if (pip === 0 && (await pythonImportsOk(venvPy, {}))) {
      return { py: venvPy, env: {} };
    }
    console.error("venv install failed:", pip);
  } else {
    console.error("venv was not created, using --target instead");
  }

  fs.mkdirSync(vendorDir, { recursive: true });
  console.log("Installing packages into", vendorDir, "via pip.pyz --target...");
  const pip = await runAsync(systemPy, [pipPyz, "install", "--target", vendorDir, "-r", reqFile]);
  if (pip !== 0) {
    throw new Error("pip.pyz install failed: " + pip);
  }
  return { py: systemPy, env: withPythonPath() };
}

function startingPayload() {
  return Buffer.from(JSON.stringify({ ok: true, service: "ggsel-miniapp", starting: !pyReady }));
}

function startHttp() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = String(req.url || "/").split("?")[0];
      if (url === "/health" || !pyReady) {
        res.writeHead(200, {
          "content-type": "application/json; charset=utf-8",
          "cache-control": "no-store",
        });
        res.end(startingPayload());
        return;
      }
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
      proxy.setTimeout(4000);
      proxy.on("timeout", () => {
        proxy.destroy();
        if (!res.headersSent) {
          res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
          res.end(startingPayload());
        }
      });
      proxy.on("error", () => {
        if (!res.headersSent) {
          res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
          res.end(startingPayload());
        }
      });
      req.pipe(proxy);
    });
    server.listen(publicPort, "0.0.0.0", () => {
      console.log("HTTP proxy on", publicPort);
      resolve(server);
    });
  });
}

(async function main() {
  const systemPy = has("python3") ? "python3" : has("python") ? "python" : null;
  if (!systemPy) {
    console.error("Python not found in this container.");
    process.exit(1);
  }

  await startHttp();
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
  child.on("error", (err) => {
    console.error("python spawn failed", err);
    process.exit(1);
  });
  const ping = () => {
    const req = http.get(
      { hostname: "127.0.0.1", port: pyPort, path: "/health", timeout: 800 },
      (res) => {
        res.resume();
        pyReady = true;
        console.log("Python backend is up");
      }
    );
    req.on("timeout", () => {
      req.destroy();
      setTimeout(ping, 400);
    });
    req.on("error", () => setTimeout(ping, 400));
  };
  child.on("spawn", ping);
  child.on("exit", (code) => process.exit(code == null ? 1 : code));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
