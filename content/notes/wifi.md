---
title: "Wi-Fi 连接"
num: 03
date: 2026-07-27T20:00:00+08:00
description: "ESP32 连接 Wi-Fi 的完整流程与代码讲解"
group: "ESP32"
draft: false
---

```c++

#include <WiFi.h>

#define LED   10

const char * ssid = "D213";
const char * password = "DGUT862158";

void setup() {
  Serial.begin(9600);

  WiFi.begin(ssid, password);

  Serial.print("正在连接 Wi-Fi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    }

  Serial.println("连接成功");
  Serial.print("IP 地址：");
  Serial.println(WiFi.localIP());

  pinMode(LED, OUTPUT);

  digitalWrite(LED, HIGH);
  delay(100);
  digitalWrite(LED, LOW);
  delay(100);

  digitalWrite(LED, HIGH);
  delay(100);
  digitalWrite(LED, LOW);
  delay(100);

  digitalWrite(LED, HIGH);
  delay(1500);
  digitalWrite(LED, LOW);
}

void loop() {
}

```

好的，下面是对这段 Arduino/ESP32 代码的**逐行详解**。  
代码功能：连接指定 Wi-Fi 网络，连接成功后用板载 LED 闪烁三次（两次短闪、一次长闪），之后进入空循环。

---

```cpp
#include <WiFi.h>
```
- **作用：引入 ESP32 的 Wi-Fi 库。**  
- **详细：`WiFi.h` 是 ESP32 官方提供的网络库，包含了连接 Wi-Fi、获取网络状态、IP 地址等函数。该库定义了 `WiFi` 类对象（全局实例），后续所有 `WiFi.xxx()` 调用都来自这个库。**

---

```cpp
#define LED   10
```
- **作用**：定义一个宏，将 `LED` 替换为数字 `10`。  
- **详细**：这表示 LED 所连接的 GPIO 引脚号为 10。在编译预处理阶段，代码中所有出现 `LED` 的地方都会被替换成 `10`。这样做可以提高代码的可读性和可维护性。

---

```cpp
const char * ssid = "D213";
```
- **作用：定义一个指向字符常量的指针 `ssid`，并初始化为字符串 `"D213"`。**  
- **详细：`ssid` 存储要连接的 Wi-Fi 网络名称（即热点名）。使用 `const char*` 表示字符串内容不可修改（存储在只读区域），避免意外篡改。**

---

```cpp
const char * password = "DGUT862158";
```
- **作用**：定义 Wi-Fi 密码指针 `password`，初始化为 `"DGUT862158"`。  
- **详细**：这是对应 SSID 的 Wi-Fi 密码，同样使用 `const char*` 保证安全。

---

```cpp
void setup() {
```
- **作用**：`setup()` 函数是 Arduino 程序的入口之一，在复位或上电后执行一次。  
- **详细**：该函数用于初始化硬件、配置网络等一次性任务。执行完毕后，会进入 `loop()` 函数无限循环。

---

```cpp
  Serial.begin(9600);
```
- **作用**：初始化串口通信，波特率设为 9600 bps。  
- **详细**：`Serial` 是 Arduino 内置的串口对象，`begin(9600)` 打开 UART 并设置通信速率。之后可以通过 `Serial.print()` 等函数向串口监视器输出调试信息。

---

```cpp
  WiFi.begin(ssid, password);
```
- **作用：启动 Wi-Fi 连接过程，尝试连接指定的 AP（接入点）。**  
- **详细：调用 `WiFi` 类的 `begin()` 方法，传入 SSID 和密码。该函数是非阻塞的，它会启动连接过程并立即返回，但连接可能尚未完成。后续代码会通过 `WiFi.status()` 检查连接状态。**

---

```cpp
  Serial.print("正在连接 Wi-Fi");
```
- **作用**：在串口监视器输出字符串 "正在连接 Wi-Fi"，**不换行**。  
- **详细**：`print()` 不会附加换行符，后面紧接着会输出点号，形成动态等待效果。

---

```cpp
  while (WiFi.status() != WL_CONNECTED) {
```
- **作用：进入循环，条件为 Wi-Fi 未连接（状态不等于 `WL_CONNECTED`）。**  
- **详细：`WiFi.status()` 返回当前连接状态，`WL_CONNECTED` 是表示已连接成功的常量。只要未连接，循环体就会反复执行。**

---

```cpp
    delay(500);
```
- **作用**：延时 500 毫秒（0.5 秒）。  
- **详细**：避免过快地检查状态，也起到间隔输出点号的作用，让用户看到连接进度。

---

```cpp
    Serial.print(".");
```
- **作用**：在串口输出一个点号，**不换行**。  
- **详细**：每 500ms 输出一个点，表示正在尝试连接，给用户直观反馈。

---

```cpp
    }
```
- **作用**：`while` 循环体结束括号。  
- **详细**：当 Wi-Fi 连接成功后，条件不成立，跳出循环，继续执行后续代码。

---

```cpp
  Serial.println("连接成功");
```
- **作用**：输出 "连接成功" 并换行。  
- **详细：`println()` 会在字符串末尾添加换行符，使下一串输出从新行开始。**

---

```cpp
  Serial.print("IP 地址：");
```
- **作用**：输出 "IP 地址："，不换行。  
- **详细**：与下一行配合，将 IP 地址打印在同一行。

---

```cpp
  Serial.println(WiFi.localIP());
```
- **作用：获取本机分配到的 IP 地址，并输出，然后换行。**  
- **详细：`WiFi.localIP()` 返回一个 `IPAddress` 对象，`Serial.println()` 会将其转换为点分十进制格式（如 192.168.1.100）并打印。**

---

```cpp
  pinMode(LED, OUTPUT);
```
- **作用**：将引脚 `LED`（即 GPIO 10）设置为输出模式。  
- **详细**：`pinMode(pin, mode)` 配置引脚方向，`OUTPUT` 表示该引脚可输出高低电平，用于控制 LED 的亮灭。

---

```cpp
  digitalWrite(LED, HIGH);
```
- **作用**：将 LED 引脚电平拉高（3.3V），LED 亮起。  
- **详细**：对于共阴 LED（阳极接 GPIO），高电平点亮。具体极性取决于硬件连接。

---

```cpp
  delay(100);
```
- **作用**：延时 100 毫秒。  
- **详细**：让 LED 保持亮态 100ms，形成短暂的亮闪。

---

```cpp
  digitalWrite(LED, LOW);
```
- **作用**：将 LED 引脚电平拉低（0V），LED 熄灭。  
- **详细**：低电平关闭 LED。

---

```cpp
  delay(100);
```
- **作用**：延时 100 毫秒。  
- **详细**：保持熄灭 100ms，完成第一次短闪。

---

```cpp
  digitalWrite(LED, HIGH);
  delay(100);
  digitalWrite(LED, LOW);
  delay(100);
```
- **作用**：完全重复上述三段代码，实现第二次短闪。  
- **详细**：第二次闪烁与第一次完全相同，依然是亮 100ms、灭 100ms。

---

```cpp
  digitalWrite(LED, HIGH);
  delay(1500);
  digitalWrite(LED, LOW);
```
- **作用**：第三次闪烁，亮 1500ms（1.5 秒），然后熄灭，**没有后续灭的延时**。  
- **详细**：这次亮的时间更长，用来区别前两次短闪，通常作为“连接成功”的提示信号。熄灭后不再延时，直接进入 `loop()`。

---

```cpp
}
```
- **作用**：`setup()` 函数结束。

---

```cpp
void loop() {
```
- **作用**：`loop()` 函数是 Arduino 程序的主循环，在 `setup()` 执行完后反复运行。  
- **详细**：该函数内部为空，因此程序将无限空转，不做任何事。LED 保持最后熄灭状态。

---

```cpp
}
```
- **作用**：`loop()` 函数结束。

---

**整体执行流程总结**：  
1. 初始化串口。  
2. 发起 Wi-Fi 连接。  
3. 串口不断打印点号直到连接成功。  
4. 打印“连接成功”和 IP 地址。  
5. 设置 LED 引脚为输出。  
6. LED 闪烁：两次短闪（100ms 亮/100ms 灭）和一次长闪（1500ms 亮）。  
7. 进入空循环，程序停止做其他事情。
