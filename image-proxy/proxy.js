#!/usr/bin/env node
const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.IMAGE_PROXY_PORT || 15722);
const UPSTREAM_BASE = process.env.UPSTREAM_BASE_URL || "http://127.0.0.1:15721/v1";
const VISION_SCRIPT =
  process.env.VISION_SCRIPT ||
  path.join(
    process.env.USERPROFILE || "C:\\Users\\MCRYII",
    ".codex",
    "skills",
    "claude-vision-skill",
    "vision.js",
  );
const DASHSCOPE_BASE_URL =
  process.env.DASHSCOPE_BASE_URL || "https://dashscope.aliyuncs.com/compatible-mode/v1";
const VISION_MODEL = process.env.VISION_MODEL || "qwen3.5-omni-plus";

function getApiKey() {
  if (process.env.DASHSCOPE_API_KEY) return process.env.DASHSCOPE_API_KEY;
  try {
    const source = fs.readFileSync(VISION_SCRIPT, "utf8");
    const match = source.match(/const API_KEY = process\.env\.DASHSCOPE_API_KEY \|\| "([^"]+)"/);
    if (match) return match[1];
  } catch {}
  return "";
}

const API_KEY = getApiKey();

function toDashScopeImageUrl(value) {
  if (typeof value !== "string") return value;
  if (value.startsWith("data:") || /^https?:\/\//i.test(value)) return value;
  const localPath = value.replace(/^file:\/\/\//, "").replace(/^file:\/\//, "");
  if (fs.existsSync(localPath)) {
    const ext = path.extname(localPath).toLowerCase().replace(".", "");
    const mime = { jpg: "jpeg", jpeg: "jpeg", png: "png", gif: "gif", webp: "webp", bmp: "bmp" }[ext] || "jpeg";
    return `data:image/${mime};base64,${fs.readFileSync(localPath).toString("base64")}`;
  }
  return value;
}

function getImageUrl(part) {
  const value = part.image_url ?? part.url;
  if (typeof value === "string") return toDashScopeImageUrl(value);
  if (value && typeof value === "object") {
    if (typeof value.url === "string") return toDashScopeImageUrl(value.url);
    if (typeof value.file_path === "string") return toDashScopeImageUrl(value.file_path);
  }
  throw new Error("不支持的图片内容格式");
}

function isImagePart(value) {
  return (
    value &&
    typeof value === "object" &&
    (value.type === "image_url" || value.type === "input_image") &&
    (value.image_url != null || value.url != null)
  );
}

async function transformBody(value, describe) {
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      value[i] = await transformBody(value[i], describe);
    }
    return value;
  }
  if (!value || typeof value !== "object") return value;
  if (isImagePart(value)) {
    const description = await describe(getImageUrl(value));
    const type = value.type === "input_image" ? "input_text" : "text";
    return { type, text: `[图片已由 Qwen 视觉模型识别]\n${description}` };
  }
  for (const key of Object.keys(value)) {
    value[key] = await transformBody(value[key], describe);
  }
  return value;
}

async function describeImage(imageUrl) {
  if (!API_KEY) throw new Error("DASHSCOPE_API_KEY 未找到，请检查 vision.js");
  imageUrl = toDashScopeImageUrl(imageUrl);
  const response = await fetch(`${DASHSCOPE_BASE_URL.replace(/\/?$/, "/")}chat/completions`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: VISION_MODEL,
      messages: [
        {
          role: "user",
          content: [
            { type: "image_url", image_url: { url: imageUrl } },
            {
              type: "text",
              text: "请用中文详细描述这张图片的全部内容，包括文字、布局、人物、物体、颜色和界面细节。不要猜测不确定的信息。",
            },
          ],
        },
      ],
      stream: false,
      max_tokens: 2048,
    }),
  });
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 500);
    throw new Error(`DashScope ${response.status}: ${detail}`);
  }
  const data = await response.json();
  return data?.choices?.[0]?.message?.content || "";
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

function sendJson(res, status, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(status, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  res.end(body);
}

function forward(req, res, body) {
  const baseUrl = new URL(UPSTREAM_BASE);
  let target;
  if (req.url.startsWith(baseUrl.pathname)) {
    target = new URL(req.url, UPSTREAM_BASE);
  } else {
    target = new URL(baseUrl.pathname.replace(/\/$/, "") + req.url, UPSTREAM_BASE);
  }

  const headers = { ...req.headers };
  delete headers.host;
  delete headers["content-length"];
  headers.host = target.host;
  if (body && body.length) headers["content-length"] = body.length;

  const transport = target.protocol === "https:" ? https : http;
  const upstreamReq = transport.request(
    target,
    { method: req.method, headers },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode, upstreamRes.headers);
      upstreamRes.pipe(res);
    },
  );
  upstreamReq.on("error", (err) => {
    if (!res.headersSent) {
      sendJson(res, 502, { error: { message: `上游请求失败: ${err.message}` } });
    } else {
      res.destroy();
    }
  });
  if (body && body.length) upstreamReq.write(body);
  upstreamReq.end();
}

async function handle(req, res) {
  if (req.method === "GET" && req.url === "/health") {
    sendJson(res, 200, { ok: true });
    return;
  }

  const rawBody = await readBody(req);
  let outBody = rawBody;
  let parsed = null;
  try {
    parsed = JSON.parse(rawBody.toString("utf8"));
  } catch (err) {
    parsed = null;
  }
  if (parsed) {
    try {
      let changed = false;
      await transformBody(parsed, async (imageUrl) => {
        changed = true;
        return describeImage(imageUrl);
      });
      if (changed) outBody = Buffer.from(JSON.stringify(parsed));
    } catch (err) {
      sendJson(res, 502, { error: { message: `图片转文字失败: ${err.message}` } });
      return;
    }
  }
  forward(req, res, outBody);
}

function start() {
  const server = http.createServer((req, res) => {
    handle(req, res).catch((err) => {
      if (!res.headersSent) sendJson(res, 500, { error: { message: err.message } });
      else res.destroy();
    });
  });
  server.listen(PORT, "127.0.0.1", () => {
    console.log(`Codex image proxy listening on http://127.0.0.1:${PORT}`);
  });
}

if (require.main === module) {
  if (process.argv.includes("--check-vision")) {
    const tinyPng =
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
    const imageArg = process.argv.slice(2).find((arg) => !arg.startsWith("--"));
    describeImage(imageArg || tinyPng)
      .then((text) => {
        console.log("vision ok:", text.slice(0, 120));
      })
      .catch((err) => {
        console.error("vision check failed:", err.message);
        process.exitCode = 1;
      });
  } else {
    start();
  }
}

module.exports = { describeImage, getApiKey, start, transformBody };
