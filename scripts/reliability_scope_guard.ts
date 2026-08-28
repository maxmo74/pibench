import { appendFileSync } from "node:fs";
import { isAbsolute, resolve } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const WORKSPACE = "/tmp/pibench-reliability-cwd-v2";
const MARKER_PATH = "/output/scope-guard-active.txt";
const FORBIDDEN_ROOTS = ["/agent", "/sessions", "/output", "/proc", "/etc", "/root", "/home"];

function readIsInScope(input: Record<string, unknown>): boolean {
  if (typeof input.path !== "string") return false;
  const candidate = isAbsolute(input.path) ? resolve(input.path) : resolve(WORKSPACE, input.path);
  return candidate === WORKSPACE || candidate.startsWith(`${WORKSPACE}/`);
}

function bashIsInScope(input: Record<string, unknown>): boolean {
  if (typeof input.command !== "string") return false;
  const command = input.command;
  if (/(^|[;&|]\s*)(env|printenv)(\s|$)/.test(command)) return false;
  if (/\b(curl|wget|nc|ncat|ssh|socat|telnet|ftp|openssl|python\d*|node|perl|ruby|php)\b/.test(command)) return false;
  if (/\/dev\/(tcp|udp)\b/.test(command)) return false;
  if (FORBIDDEN_ROOTS.some((root) => command.includes(root))) return false;
  if (/(^|[\s;&|])\.\.\//.test(command)) return false;
  const absolutePaths = command.match(/(?<![\w:.*?{}-])(\/[A-Za-z0-9_./*?{}-]+)/g) ?? [];
  return absolutePaths.every((candidate) =>
    candidate.startsWith(WORKSPACE) || candidate.startsWith("/dev/null")
  );
}

export default function reliabilityScopeGuard(pi: ExtensionAPI) {
  pi.on("before_agent_start", () => {
    appendFileSync(MARKER_PATH, "active\n", { mode: 0o600 });
  });

  pi.on("tool_call", (event) => {
    const input = event.input as Record<string, unknown>;
    const allowed = event.toolName === "read"
      ? readIsInScope(input)
      : event.toolName === "bash" && bashIsInScope(input);
    if (allowed) return;
    return {
      block: true,
      reason: "Reliability gate blocked a tool call outside the read-only fixture scope.",
      terminate: true,
    };
  });
}
