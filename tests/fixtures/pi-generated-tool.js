// Isolated live integration fixture. No filesystem, network, or command tools.
import { randomUUID } from "node:crypto";
import { Type } from "typebox";

export default function generatedTool(pi) {
  let calls = 0;
  pi.registerTool({
    name: "fixture_lookup",
    label: "Generated fixture",
    description: "Return a newly generated test value for key alpha.",
    parameters: Type.Object({key: Type.Literal("alpha")}, {additionalProperties:false}),
    async execute(_id, params) {
      if (params.key !== "alpha" || ++calls > 3) throw new Error("Fixture call limit exceeded");
      return {content:[{type:"text",text:JSON.stringify({value:`fixture-${randomUUID()}`})}], details:{}};
    },
  });
  pi.on("session_start", () => { pi.setActiveTools(["fixture_lookup"]); });
  pi.on("before_provider_request", event => {
    const names = (event.payload?.tools || []).map(tool => tool.function?.name);
    if (names.length !== 1 || names[0] !== "fixture_lookup") {
      throw new Error("The live test requires exactly the fixture_lookup tool on the wire");
    }
  });
}
