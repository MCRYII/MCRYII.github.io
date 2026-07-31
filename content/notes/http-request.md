---
title: "网络请求"
num: 04
date: 2026-07-28T20:00:00+08:00
description: "ESP32 请求天气 API 并解析返回的 JSON 数据"
group: "ESP32"
draft: false
---

**连接 Wi-Fi，向聚合数据（JUHE）的天气 API 发起 GET 请求，解析返回的 JSON 数据，并提取温度、天气状况和空气质量指数，最后通过串口打印出来。**

---

## 1. 头文件包含

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
```

- **WiFi.h**：ESP32 官方 Wi-Fi 库，提供连接无线网络的功能（`WiFi.begin()`、`WiFi.status()` 等）。
- **HTTPClient.h**：用于发送 HTTP 请求（GET、POST 等），支持 HTTPS（需配置证书或跳过验证）。
- **ArduinoJson.h**：一个流行的 JSON 解析/生成库，用于处理 API 返回的 JSON 数据。这里使用 `DynamicJsonDocument` 来存储解析后的对象。

---

## 2. 全局变量定义

```cpp
const char * ssid = "D213";
const char * password = "DGUT862158";
```

- 定义 Wi-Fi 热点的名称和密码，使用 `const char*` 字符串常量。

```cpp
String url = "https://apis.juhe.cn/simpleWeather/query";
String city = "上海";
String key = "17ce867efa4ae96fc5b19da461f36ff7";
```

- `url`：聚合数据“简单天气”API 的接口地址（HTTPS）。
- `city`：要查询的城市，这里写死为“上海”。
- `key`：个人在聚合数据平台申请的 API 密钥（AppKey），需要有效才能获取数据。  
  > **注意**：密钥是敏感信息，实际项目中应通过安全方式管理，避免硬编码公开。

---

## 3. `setup()` 函数

`setup()` 在 ESP32 复位或上电后执行一次，完成所有初始化工作。

### 3.1 串口初始化

```cpp
Serial.begin(115200);
```

- 设置串口通信波特率为 **115200**，与代码中的 `Serial.printf()` 和 `Serial.println()` 匹配。  
  建议将串口监视器也设为 115200，避免乱码。

### 3.2 连接 Wi-Fi

```cpp
WiFi.begin(ssid, password);
Serial.print("正在连接 WiFi.");
```

- 调用 `WiFi.begin()` 启动连接过程（非阻塞），随后通过循环等待连接成功。

```cpp
while (WiFi.status() != WL_CONNECTED) {
  delay(500);
  Serial.print(".");
}
Serial.println("连接成功");
```

- `WiFi.status()` 返回当前连接状态。当不等于 `WL_CONNECTED` 时，每隔 500ms 打印一个点，形成动态等待提示。  
- 连接成功后，打印“连接成功”。

---

### 3.3 发送 HTTP 请求

```cpp
HTTPClient http;
http.begin(url + "?city=" + city + "&key=" + key);
```

- 创建一个 `HTTPClient` 对象。
- `http.begin()` 设置目标 URL，将城市和密钥拼接为查询参数：  
  实际请求的 URL 为 `https://apis.juhe.cn/simpleWeather/query?city=上海&key=xxx`。

```cpp
int http_code = http.GET();
Serial.printf("HTTP 状态码：%d\n", http_code);
```

- 调用 `http.GET()` 发送 GET 请求，返回值是 HTTP 状态码（如 200 表示成功，404 表示未找到等）。打印出来便于调试。

```cpp
String response = http.getString();
Serial.print("响应数据：");
Serial.println(response);
http.end();
```

- `http.getString()` 获取服务器返回的响应体（JSON 字符串），并打印到串口。  
- `http.end()` 释放连接资源。

---

### 3.4 解析 JSON 数据

```cpp
DynamicJsonDocument doc(1024);
deserializeJson(doc, response);
```

- `DynamicJsonDocument doc(1024)`：创建一个动态 JSON 文档对象，分配 1024 字节内存用于存储解析结果。若响应数据较大，可能需要增大容量（但 1024 对于简单天气接口通常足够）。
- `deserializeJson(doc, response)`：将接收到的 JSON 字符串解析为文档对象。如果解析失败，会返回错误代码，这里未做错误检查（实际项目中建议检查）。

---

### 3.5 提取具体字段

```cpp
unsigned int temp = doc["result"]["realtime"]["temperature"].as<unsigned int>();
String info = doc["result"]["realtime"]["info"].as<String>();
int aqi = doc["result"]["realtime"]["aqi"].as<int>();
```

- 使用嵌套的 `doc["key"]` 访问 JSON 树的节点。假设 API 返回的 JSON 结构为：
  ```json
  {
    "result": {
      "realtime": {
        "temperature": "28",
        "info": "晴",
        "aqi": "65"
      }
    }
  }
  ```
- `.as<unsigned int>()` 将节点值转换为无符号整数（温度通常是整数），`.as<String>()` 转为字符串（天气描述），`.as<int>()` 转为整数（空气质量指数）。
- 注意：若 API 返回的是字符串类型的数字（如 `"28"`），`as<int>()` 仍能正确转换。

---

### 3.6 打印解析结果

```cpp
Serial.printf("温度：%d,天气：%s,空气指数：%d\n", temp, info, aqi);
```

- 使用 `Serial.printf()` 格式化输出提取的数据。  
  这里 `%s` 用于输出 `info` 字符串（`String` 类型可直接作为 `%s` 参数，它会自动转换为 C 风格字符串）。  
  最终串口会显示类似：`温度：28,天气：晴,空气指数：65`

---

## 4. `loop()` 函数

```cpp
void loop() {
  // put your main code here, to run repeatedly:
}
```

- 该函数为空，因此程序在 `setup()` 执行完毕后，会一直处于空闲状态，不会重复执行任何操作。  
  如果希望定期更新天气，可以将上述 HTTP 请求放在 `loop()` 中并加入延时。

---

## 5. 可能的问题与改进建议

1. **API 密钥有效性**：示例中的 `key` 是公开的，可能已失效或被限制，实际使用时请替换为自己申请的密钥。
2. **错误处理**：未检查 Wi-Fi 连接失败、HTTP 状态码非 200、JSON 解析失败等情况，容易导致程序崩溃或显示无效数据。建议增加条件判断。
3. **HTTPS 证书**：`HTTPClient` 默认会验证 HTTPS 证书，如果证书不受信任，可能请求失败。可以通过 `http.setInsecure()` 跳过验证（测试环境），或手动配置证书。
4. **内存管理**：`DynamicJsonDocument` 在栈上分配，若响应过大可能溢出，可改用 `StaticJsonDocument` 或适当增大容量。
5. **串口输出**：`Serial.printf()` 在 ESP32 上可用，但需要确保波特率一致。若使用 `Serial.print(info)` 也可。

---

## 6. 总结

这段代码是一个典型的 ESP32 物联网应用示例：  
1. **联网** → 2. **请求 Web API** → 3. **解析 JSON** → 4. **输出结果**。  

它展示了如何使用 Arduino 框架下的常用库，将硬件与云服务结合，为后续开发智能设备（如环境监测、远程控制等）打下基础。

如果你运行该代码，串口监视器将输出类似：
```
正在连接 WiFi........
连接成功
HTTP 状态码：200
响应数据：{"resultcode":"200","reason":"success",...}
温度：28,天气：晴,空气指数：65
```
若状态码非 200 或响应数据为空，请检查网络和 API 配置。
