import fs from "node:fs";
import { OpenAISchemaCompatLayer, wrapSchemaWithNullTransform } from "@mastra/schema-compat";

const fixtures = JSON.parse(fs.readFileSync(new URL("../fixtures/workflows.json", import.meta.url), "utf8"));
const results = [];
for (const f of fixtures) {
  const standard = {"~standard": {
    version: 1, vendor: "argbridge-offline-benchmark",
    validate: value => ({value}),
    jsonSchema: {input: () => structuredClone(f.schema), output: () => structuredClone(f.schema)}
  }};
  try {
    const layer = new OpenAISchemaCompatLayer({
      provider: "openai", modelId: "gpt-4.1", supportsStructuredOutputs: true
    });
    const schema = layer.processToJSONSchema(standard);
    results.push({id: f.id, schema});
  } catch (error) {
    results.push({id: f.id, error: String(error)});
  }
}
const result = {comparator: "@mastra/schema-compat", version: "1.3.17",
  mode: "OpenAISchemaCompatLayer.processToJSONSchema(StandardSchemaWithJSON)",
  note: "Offline schema conversion only. Pass-through Standard Schema validator supplies the JSON schema; Python jsonschema independently validates emitted schemas.",
  results};
// Probe the exported normalizer in isolation, without pretending the pass-through
// inner validator represents Mastra's complete execution/validation pipeline.
result.normalizer_probes = [];
for (const [id, input] of [["patch", {id:"A", name:null}], ["required_null", {x:null}]]) {
  const source = fixtures.find(f=>f.id===id).schema;
  const standard = {"~standard":{
    version:1, vendor:"argbridge-offline-probe", validate:value=>({value}),
    jsonSchema:{input:()=>source, output:()=>source}
  }};
  const wrapped = wrapSchemaWithNullTransform(standard);
  const transformed = await wrapped["~standard"].validate(input);
  result.normalizer_probes.push({
    workflow:id, input, output_after_json_serialization:transformed.value,
    undefined_members:Object.keys(transformed.value).filter(k=>transformed.value[k]===undefined),
    null_members:Object.keys(transformed.value).filter(k=>transformed.value[k]===null)
  });
}
fs.mkdirSync(new URL("../results/", import.meta.url), {recursive:true});
fs.writeFileSync(new URL("../results/mastra.json", import.meta.url), JSON.stringify(result, null, 2)+"\n");
console.log(JSON.stringify({schemas:results.length, normalizer_probes:result.normalizer_probes}, null, 2));

