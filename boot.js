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

function has(bin) {
  return spawnSync(bin, ["--version"], { encoding: "utf8" }).status === 0;
}

function run(py, args) {
  return spawnSync(py, args, {
    cwd: root,
    env: {
      ...process.env,
      PIP_BREAK_SYSTEM_PACKAGES: "1",
      PIP_DISABLE_PIP_VERSION_CHECK: "1",
    },
    stdio: "inherit",
  });
}

function pipOk(py) {
  return spawnSync(py, ["-m", "pip", "--version"], { encoding: "utf8" }).status === 0;
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

async function fetchGetPip() {
  const dest = path.join(root, "get-pip.py");
  if (!fs.existsSync(dest)) {
    console.log("Downloading get-pip.py...");
    await download("https://bootstrap.pypa.io/get-pip.py", dest);
  }
  return dest;
}

async function ensurePip(py, extraArgs) {
  if (pipOk(py)) return true;
  console.log("Trying ensurepip for", py);
  run(py, ["-m", "ensurepip", "--upgrade"]);
  if (pipOk(py)) return true;
  const getPip = await fetchGetPip();
  console.log("Running get-pip.py", extraArgs.join(" "));
  run(py, [getPip, ...extraArgs]);
  return pipOk(py);
}

function installReqs(py, systemWide) {
  const args = ["-m", "pip", "install"];
  if (systemWide) {
    args.push("--user", "--break-system-packages");
  }
  args.push("-r", path.join(root, "requirements.txt"));
  return run(py, args);
}

async function preparePython(systemPy) {
  console.log("Creating virtualenv at", venvDir);
  run(systemPy, ["-m", "venv", venvDir]);
  if (!fs.existsSync(venvPy)) {
    console.log("venv failed, retrying without bundled pip...");
    run(systemPy, ["-m", "venv", "--without-pip", "--clear", venvDir]);
  }

  if (fs.existsSync(venvPy)) {
    const ok = await ensurePip(venvPy, []);
    if (ok) {
      console.log("Installing packages into venv...");
      const pip = installReqs(venvPy, false);
      if (pip.status === 0) return venvPy;
      console.error("venv pip install failed:", pip.status);
    } else {
      console.error("pip missing inside venv");
    }
  } else {
    console.error("virtualenv was not created");
  }

  console.log("Falling back to system Python with --break-system-packages");
  const ok = await ensurePip(systemPy, ["--user", "--break-system-packages"]);
  if (!ok) {
    throw new Error("could not install pip");
  }
  const pip = installReqs(systemPy, true);
  if (pip.status !== 0) {
    throw new Error("pip install failed: " + pip.status);
  }
  return systemPy;
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
  const py = await preparePython(systemPy);

  console.log("GGSel boot:", py, "main.py | proxy", publicPort, "->", pyPort);
  const child = spawn(py, [path.join(root, "main.py")], {
    cwd: root,
    env: {
      ...process.env,
      PORT: String(pyPort),
      WEB_PORT: String(pyPort),
      PYTHONUNBUFFERED: "1",
      PIP_BREAK_SYSTEM_PACKAGES: "1",
    },
    stdio: "inherit",
  });
  child.on("exit", (code) => process.exit(code == null ? 1 : code));
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
