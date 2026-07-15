#!/usr/bin/env node
/** Start the Python API and Vite dev server without third-party Node packages. */

import { spawn } from "node:child_process";
import http from "node:http";
import process from "node:process";

const isWindows = process.platform === "win32";
const host = process.env.GLIMT_DEV_HOST || "127.0.0.1";
const apiPort = Number.parseInt(process.env.GLIMT_API_PORT || "4173", 10);
const webPort = Number.parseInt(process.env.GLIMT_WEB_PORT || "5173", 10);
const pythonCommand = process.env.PYTHON || (isWindows ? "python" : "python3");
const children = new Set();
let stopping = false;

function validPort(value, name) {
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    throw new Error(`${name} must be a port between 1 and 65535.`);
  }
}

function apiAlreadyRunning() {
  return new Promise((resolve) => {
    const request = http.get({ host, port: apiPort, path: "/api/health", timeout: 800 }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => { body += chunk; });
      response.on("end", () => {
        try {
          const value = JSON.parse(body);
          resolve(response.statusCode === 200 && value.ok === true && value.service === "ljusglimt");
        } catch {
          resolve(false);
        }
      });
    });
    request.on("timeout", () => request.destroy());
    request.on("error", () => resolve(false));
  });
}

function start(label, command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: process.cwd(),
    stdio: "inherit",
    windowsHide: false,
    ...options,
  });
  children.add(child);
  child.once("error", (error) => {
    console.error(`[${label}] kunde inte starta: ${error.message}`);
    stop(1);
  });
  child.once("exit", (code, signal) => {
    children.delete(child);
    if (!stopping) {
      const reason = signal ? `signal ${signal}` : `kod ${code ?? 1}`;
      console.error(`[${label}] avslutades (${reason}).`);
      stop(code || 1);
    }
  });
  return child;
}

function terminate(child) {
  if (!child.pid || child.exitCode !== null) return;
  if (isWindows) {
    spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
      stdio: "ignore",
      windowsHide: true,
    });
  } else {
    child.kill("SIGTERM");
  }
}

function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) terminate(child);
  setTimeout(() => process.exit(code), 250);
}

process.once("SIGINT", () => stop(0));
process.once("SIGTERM", () => stop(0));

async function main() {
  validPort(apiPort, "GLIMT_API_PORT");
  validPort(webPort, "GLIMT_WEB_PORT");
  const existingApi = await apiAlreadyRunning();
  if (existingApi) {
    console.log(`[api] återanvänder Ljusglimt på http://${host}:${apiPort}`);
  } else {
    start("api", pythonCommand, ["server.py"], {
      env: { ...process.env, GLIMT_HOST: host, PORT: String(apiPort) },
    });
  }

  const npmCommand = isWindows ? (process.env.ComSpec || "cmd.exe") : "npm";
  const npmArgs = isWindows
    ? ["/d", "/s", "/c", "npm", "run", "dev:web", "--", "--host", host, "--port", String(webPort)]
    : ["run", "dev:web", "--", "--host", host, "--port", String(webPort)];
  start("vite", npmCommand, npmArgs);
  console.log(`[webb] Vite startar på http://${host}:${webPort}`);
  console.log("Tryck Ctrl+C för att stoppa båda processerna.");
}

main().catch((error) => {
  console.error(error.message);
  stop(1);
});
