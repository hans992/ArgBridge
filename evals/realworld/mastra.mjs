import fs from "node:fs";
import {OpenAISchemaCompatLayer, wrapSchemaWithNullTransform} from "../../bench/node/node_modules/@mastra/schema-compat/dist/index.js";
const data = JSON.parse(fs.readFileSync(0,"utf8"));
function standard(schema) {
  return {"~standard":{version:1,vendor:"argbridge-evaluation",validate:value=>({value}),
    jsonSchema:{input:()=>structuredClone(schema),output:()=>structuredClone(schema)}}};
}
if (data.action==="schemas") {
  const out={};
  for (const [name, workflow] of Object.entries(data.workflows)) {
    try {
      const layer=new OpenAISchemaCompatLayer({provider:"openai",modelId:data.model,supportsStructuredOutputs:true});
      out[name]={schema:layer.processToJSONSchema(standard(workflow.schema))};
    } catch(e) {out[name]={error:String(e)};}
  }
  process.stdout.write(JSON.stringify(out));
} else if (data.action==="normalize") {
  const s=wrapSchemaWithNullTransform(standard(data.schema));
  const result=await s["~standard"].validate(data.value);
  // JSON serialization is the observable JSON handler boundary; undefined drops.
  process.stdout.write(JSON.stringify(result.value));
} else throw new Error("Unknown action");
