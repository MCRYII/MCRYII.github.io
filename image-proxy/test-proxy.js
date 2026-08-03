const assert = require("assert");
const { transformBody } = require("./proxy");

async function main() {
  const input = {
    input: [
      {
        type: "message",
        content: [
          { type: "input_text", text: "看这张图" },
          { type: "input_image", image_url: { url: "data:image/png;base64,abc" } },
          { type: "image_url", image_url: "data:image/png;base64,def" },
        ],
      },
    ],
  };

  const output = await transformBody(input, async (url) => `DESC:${url.slice(0, 12)}`);
  const json = JSON.stringify(output);
  assert.strictEqual(json.includes("image_url"), false);
  assert.strictEqual(json.includes("input_image"), false);
  assert.ok(output.input[0].content.some((part) => part.type === "input_text" && part.text.includes("DESC:data:image/p")));
  assert.ok(output.input[0].content.some((part) => part.type === "text" && part.text.includes("DESC:data:image/p")));
  console.log("image-proxy transform test ok");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
