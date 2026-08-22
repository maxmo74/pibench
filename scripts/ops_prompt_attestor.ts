import { createHash } from "node:crypto";
import { appendFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

/** Record only the effective system-prompt hash for the versioned pi-ops-v1 profile. */
export default function opsPromptAttestor(pi: ExtensionAPI) {
  pi.on("before_agent_start", (event) => {
    const output = process.env.PIBENCH_OPS_PROMPT_ATTESTATION;
    if (!output) throw new Error("PIBENCH_OPS_PROMPT_ATTESTATION is required");
    const hash = createHash("sha256").update(event.systemPrompt, "utf8").digest("hex");
    appendFileSync(output, `${hash}\n`, { encoding: "utf8", mode: 0o600 });
  });
}
