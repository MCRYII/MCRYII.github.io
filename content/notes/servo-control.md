---
title: "控制舵机"
num: 02
date: 2026-07-26T20:00:00+08:00
description: "用 ESP32 的 LEDC 外设输出 PWM 控制舵机，逐行解释"
group: "ESP32"
draft: false
---

## {{< icon "book" >}} 逐行详细解释（原版ledc控制）

```cpp
/*
  该程序作用是使用 LEDC 外设控制舵机
  在线文档：https://docs.geeksman.com/esp32/Arduino/17.esp32-arduino-servo.html
*/
#define FREQ        50
#define CHANNEL     0
#define RESOLUTION  8
#define SERVO       20


int calculatePWM(int degree) {
  
  int min_width = 0.5 / 20 * pow(2, RESOLUTION);
  int max_width = 2.5 / 20 * pow(2, RESOLUTION);
   
  return (max_width - min_width) * degree / 180 + min_width;
}

void setup() {
  ledcAttach(SERVO, FREQ, RESOLUTION);

}


void loop() {
  for (int i = 0;i<=180; i+=10) {
    // 输出 PWM，设置占空比
    ledcWrite(SERVO, calculatePWM(i));  // <-- 这里改成 SERVO（引脚号），不是 CHANNEL
    delay(500);
    }
}
```

---

```cpp
#define FREQ        50
```
定义舵机 PWM 信号的**频率**为 50Hz。舵机要求 20ms 一个周期，50Hz 正好对应 20ms。

```cpp
#define CHANNEL     0
```
定义 LEDC 通道号为 0。**但注意**：在 ESP32 新版库（3.0+）中，`ledcWrite()` 已经不用通道号了，而是直接用引脚号。这个 `CHANNEL` 在这里其实**没有任何作用**，只是留着没删而已。

```cpp
#define RESOLUTION  8
```
定义 PWM 的**分辨率**为 8 位，也就是占空比的数值范围是 **0 ~ 255**（2^8 - 1）。

```cpp
#define SERVO       20
```
定义舵机的**信号引脚**为 GPIO 20。你的舵机信号线（黄色/橙色）要插在这个引脚上。

```cpp
int calculatePWM(int degree) {
```
定义一个函数，输入**角度**（0~180），输出对应的**占空比数值**（0~255）。

```cpp
  int min_width = 0.5 / 20 * pow(2, RESOLUTION);
```
计算 **0°** 对应的占空比数值。
- 舵机 0° 对应 0.5ms 的高电平。
- 占空比 = 0.5ms / 20ms = 0.025。
- 乘以最大值 256（2^8），得到 `6.4`，存为 `int` 变成 **6**。

- **`pow()`** 是 C/C++ 里的**幂函数**，来自 `math.h` 库。`pow(a, b)` 的意思就是计算 **a 的 b 次方**。
- 所以 `pow(2, RESOLUTION)` 就是计算 **2 的 RESOLUTION 次方**。

​      代码里定义了 `#define RESOLUTION 8`，所以：**`pow(2, RESOLUTION)` = `pow(2, 8)` = 2⁸ = 256**

```cpp
  int max_width = 2.5 / 20 * pow(2, RESOLUTION);
```
计算 **180°** 对应的占空比数值。
- 舵机 180° 对应 2.5ms 的高电平。
- 占空比 = 2.5ms / 20ms = 0.125。
- 乘以最大值 256，得到 `32`。

```cpp
  return (max_width - min_width) * degree / 180 + min_width;
```
**线性映射公式**：

- `max_width - min_width` = 32 - 6 = 26（整个 0°~180° 范围对应的数值跨度）
- 比如你要转 90°，就是 `26 * 90 / 180 + 6 = 13 + 6 = 19`。
- 把 0~180 的角度，映射成 6~32 的占空比数值，并返回。

```cpp
void setup() {
```
Arduino 初始化函数，只在开机时运行一次。

```cpp
  ledcAttach(SERVO, FREQ, RESOLUTION);
```
**新版 ESP32 库（3.0+）的核心 API**。
- 这一个函数顶替了旧版的 `ledcSetup()` + `ledcAttachPin()`。
- 它把 **GPIO 20** 引脚设置为 PWM 输出，频率 **50Hz**，分辨率 **8 位**。
- **注意**：它内部会自动分配一个空闲通道，所以你不用手动管 `CHANNEL` 了。

```cpp
void loop() {
```
主循环，会无限重复执行。

```cpp
  for (int i = 0;i<=180; i+=10) {
```
`for` 循环，变量 `i` 从 0 开始，每次加 10，一直加到 180。也就是：0° → 10° → 20° → ... → 180°。

## {{< icon "book" >}} ESP32Servo完整代码解析

```c++
#include <ESP32Servo.h>


#define SERVO_PIN   12
#define MAX_WIDTH   2500
#define MIN_WIDTH   500

// 定义 servo 对象
Servo my_servo;

void setup() {
  // 分配硬件定时器
  ESP32PWM::allocateTimer(0);
  // 设置频率
  my_servo.setPeriodHertz(50);
  // 关联 servo 对象与 GPIO 引脚，设置脉宽范围
  my_servo.attach(SERVO_PIN, MIN_WIDTH, MAX_WIDTH);
}


void loop() {
  
  my_servo.write(180);
  delay(1000);

  my_servo.write(0);
  delay(1000);
}

```



```cpp
#include <ESP32Servo.h>
```
- 引入专门为 ESP32 写的舵机库。**注意**：不是 Arduino 自带的 `Servo.h`，而是 `ESP32Servo.h`，它利用 ESP32 的硬件定时器（LEDC）产生精确 PWM，更适合 ESP32 系列芯片（包括 S3）。

---

```cpp
#define SERVO_PIN   12
#define MAX_WIDTH   2500
#define MIN_WIDTH   500
```
- **`SERVO_PIN`**：舵机信号线连接的 GPIO 引脚号，这里设为 12（你可以改成任意支持 PWM 的引脚）。
- **`MIN_WIDTH`** 和 **`MAX_WIDTH`**：舵机 **0°** 和 **180°** 对应的脉宽（单位：微秒 µs）。  
  标准舵机脉宽范围是 0.5ms ~ 2.5ms，即 **500µs ~ 2500µs**。  
  这两个值定义了舵机行程的边界，库会根据你写的角度（0~180）自动线性映射到这个脉宽范围。

---

```cpp
Servo my_servo;
```
- 创建一个 `Servo` 类对象，命名为 `my_servo`。之后所有舵机操作都通过这个对象进行。

---

### {{< icon "wrench" >}} setup() 函数

```cpp
void setup() {
  // 分配硬件定时器
  ESP32PWM::allocateTimer(0);
```
- **`ESP32PWM::allocateTimer(0)`**：  
  ESP32Servo 库底层使用 LEDC 硬件产生 PWM，需要占用一个硬件定时器。  
  这里明确分配 **定时器 0** 给舵机使用（ESP32 有 4 个定时器，编号 0~3）。  
  如果不分配，库也会自动分配，但**显式分配**能避免与其他库冲突，保证代码稳定性。

```cpp
  // 设置频率
  my_servo.setPeriodHertz(50);
```
- **`setPeriodHertz(50)`**：设置 PWM 频率为 **50Hz**，即周期 20ms，这是标准舵机的工作频率。  
  注意：这里的单位是 Hz（每秒周期数），50Hz 就是每 20ms 一个周期。

```cpp
  // 关联 servo 对象与 GPIO 引脚，设置脉宽范围
  my_servo.attach(SERVO_PIN, MIN_WIDTH, MAX_WIDTH);
```
- **`attach(pin, min, max)`**：将舵机对象绑定到物理引脚，并设定脉宽范围。  
  - 第一个参数 `SERVO_PIN`（12）是 GPIO 号。  
  - 第二个参数 `MIN_WIDTH`（500µs）对应 0° 的脉宽。  
  - 第三个参数 `MAX_WIDTH`（2500µs）对应 180° 的脉宽。  
  绑定成功后，这个引脚就会持续输出 50Hz 的 PWM 信号，初始角度通常是 0°（或上次断电时位置，取决于舵机）。

---

### {{< icon "refresh" >}} loop() 函数

```cpp
void loop() {
  my_servo.write(180);
  delay(1000);
```
- **`my_servo.write(180)`**：让舵机转到 **180°**（最大角度）。  
  库内部会自动将 180° 映射到 `MAX_WIDTH`（2500µs），并更新 PWM 占空比。  
  随后 `delay(1000)` 保持这个位置 **1 秒**（1000 毫秒）。

```cpp
  my_servo.write(0);
  delay(1000);
```
- 舵机转到 **0°**（最小角度），对应 `MIN_WIDTH`（500µs），保持 1 秒。

然后循环往复，舵机就在 0° 和 180° 之间来回摆动，每个位置停留 1 秒。

---

### {{< icon "search" >}} 深入理解关键点

**1. 为什么需要 `allocateTimer(0)`？**

ESP32Servo 库底层用 LEDC 通道生成 PWM，而 LEDC 需要占用一个定时器作为时钟源。多个舵机可以共用一个定时器（只要频率相同），所以通常只需分配一次。如果不调用，库会动态分配，但为了更可控，建议显式分配。

2. **`setPeriodHertz(50)` 和 `attach` 的顺序？**

必须先设置频率，再 `attach`，因为 `attach` 时会根据当前频率计算占空比。顺序颠倒可能导致脉宽错误。

3. **为什么用 500~2500 而不是 544~2400？**

不同的舵机对脉宽的响应略有差异。标准范围是 500~2500µs，但有些舵机（如 SG90）实际范围可能是 544~2400。如果你的舵机在 0° 或 180° 时达不到期望位置，可以微调这两个值（比如改成 600 和 2400）。

4. **`my_servo.write()` 和 `my_servo.writeMicroseconds()` 的区别？**

- `write(angle)`：传入 0~180 的角度，库自动映射到脉宽范围。
- `writeMicroseconds(us)`：直接传入微秒值（如 1500），更精确，适合需要微调的场景。

---

### {{< icon "gear" >}} 硬件连接要点

| 舵机线缆颜色 | 连接目标                                            |
| :----------- | :-------------------------------------------------- |
| 棕色/黑色    | **GND**（ESP32 的 GND）                             |
| 红色         | **外部 5V 电源正极**（**不能**用 ESP32 的 5V 引脚） |
| 黄色/橙色    | **GPIO 12**（或你定义的引脚）                       |

- **必须共地**：外部电源的 GND、ESP32 的 GND 必须连在一起。
- **供电**：舵机启动电流较大，建议用 5V 2A 以上的独立电源。

---

### {{< icon "lightbulb" >}} 如果你想控制多个舵机

```cpp
Servo servo1, servo2;
void setup() {
  ESP32PWM::allocateTimer(0);  // 只需分配一次
  servo1.setPeriodHertz(50);
  servo1.attach(12, 500, 2500);
  servo2.setPeriodHertz(50);
  servo2.attach(13, 500, 2500);  // 共用同一个定时器
}
void loop() {
  servo1.write(90);
  servo2.write(45);
  delay(1000);
  // ...
}
```

---

### {{< icon "flask" >}} 调试技巧

- 如果舵机不动，检查供电和共地。
- 如果舵机抖得厉害，可以尝试在舵机电源引脚并联一个 100~470µF 的电解电容，滤除电源噪声。
- 如果行程不对，调整 `MIN_WIDTH` 和 `MAX_WIDTH`，每次增减 50µs 试。

---

### {{< icon "pen" >}} 总结

这段代码的核心操作：
1. 分配硬件定时器，保证 PWM 信号稳定。
2. 设置 50Hz 频率，匹配舵机标准。
3. 绑定引脚并定义脉宽范围，完成初始化。
4. 在 `loop` 中通过 `write(角度)` 控制舵机转动，并用 `delay` 控制停留时间。



## {{< icon "book" >}} 完整代码解析（PCA9685）

```c++
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
Adafruit_PWMServoDriver pwm(0x40);
#define SERVOMIN 150
#define SERVOMAX 600

void setup() {
  Wire.begin(8,9); 
  pwm.begin();
  pwm.setPWMFreq(50); 
  Serial.begin(115200);
}

void loop() {
  pwm.setPWM(0,0,map(90,0,180,SERVOMIN,SERVOMAX));
  delay(1000);
  pwm.setPWM(0,0,map(0,0,180,SERVOMIN,SERVOMAX));
  delay(1000);
}

```

```cpp
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
```
- **Wire.h**：Arduino 标准 I2C 通信库，用于与 PCA9685 进行 I2C 数据交换。
- **Adafruit_PWMServoDriver.h**：Adafruit 专为 PCA9685 写的驱动库，封装了设置频率、输出 PWM 等操作，让舵机控制变得很简单。

```cpp
Adafruit_PWMServoDriver pwm(0x40);
```
- 创建一个对象 `pwm`，并传入 I2C 地址 **`0x40`**。  
  PCA9685 的默认地址是 `0x40`（可通过硬件引脚改变），绝大多数模块都使用这个地址。

```cpp
#define SERVOMIN 150
#define SERVOMAX 600
```
- 定义舵机 0° 和 180° 对应的 **PWM 计数值**。  
  PCA9685 内部是 12 位分辨率（0~4095），50Hz 频率下周期 20ms，脉宽 0.5ms~2.5ms 对应计数值约为 102~512。  
  这里的 `150` 和 `600` 是经过实践调整的值，使舵机能覆盖完整的 0~180° 行程。  
  **注意**：不同舵机可能略有差异，如果舵机行程不够，可以微调这两个值（比如改成 120 和 580）。

---

### {{< icon "wrench" >}} setup() 函数

```cpp
void setup() {
  Wire.begin(8, 9);
```
- **`Wire.begin(8, 9)`**：  
  启动 I2C 总线，并指定 **SDA = GPIO 8**，**SCL = GPIO 9**。  
  这意味着你的开发板必须将 PCA9685 的 SDA/SCL 物理连接到这两个引脚。  
  {{< icon "alert" >}} **务必核对你的板子丝印**：如果 PCA9685 的连接引脚不是 8 和 9，请改成正确的引脚号（例如常见的是 SDA=21, SCL=22）。

```cpp
  pwm.begin();
```
- 初始化 PCA9685 芯片，它会检测芯片是否存在并复位内部寄存器。

```cpp
  pwm.setPWMFreq(50);
```
- 设置 PWM 频率为 **50Hz**（周期 20ms），这是标准舵机的工作频率。

```cpp
  Serial.begin(115200);
```
- 启动串口通信，波特率 115200，用于后续调试（虽然代码里未打印，但可方便添加调试信息）。

---

### {{< icon "refresh" >}} loop() 函数

```cpp
void loop() {
  pwm.setPWM(0, 0, map(90, 0, 180, SERVOMIN, SERVOMAX));
  delay(1000);
```
- **`pwm.setPWM(0, 0, value)`**：  
  在 **通道 0** 输出一个 PWM 信号。三个参数分别为：  
  1. **通道号**（0~15）—— 对应 PCA9685 的 `PWM0` ~ `PWM15` 接口。  
  2. **`on` 时刻**（这里为 0）—— 脉冲开始的时间（通常固定为 0）。  
  3. **`off` 时刻**（计数值）—— 脉冲结束的时间。  
  PCA9685 在周期内，从 `on` 到 `off` 保持高电平，其余时间低电平。`off` 值就是决定了脉宽。

- **`map(90, 0, 180, SERVOMIN, SERVOMAX)`**：  
  将角度 90°（范围 0~180）映射到 `SERVOMIN` ~ `SERVOMAX` 之间，得到对应的计数值。  
  所以这条语句让通道 0 的舵机转到 90° 位置，持续 1 秒。

```cpp
  pwm.setPWM(0, 0, map(0, 0, 180, SERVOMIN, SERVOMAX));
  delay(1000);
```
- 接着让同一个通道转到 0°，持续 1 秒。  
  如此循环，舵机就在 90° 和 0° 之间来回摆动。
  
  ### pwm.setPWM(0, 0, value)详解
  
  第一个工具：`map()` —— “翻译官”
  
  舵机听不懂“90度”、“180度”，它只听得懂“你给我持续通电多少微秒”（也就是脉宽）。`map()` 就是专门帮你做**单位换算**的。
  
  - **格式**：`map(要换算的值, 原范围下限, 原范围上限, 目标范围下限, 目标范围上限)`
  
  - **实战**：`map(90, 0, 180, SERVOMIN, SERVOMAX)`
    - 意思就是：“我这里有 **90**（度），它原本在 **0 到 180** 的范围内，请你把它换算到 **150 到 600** 这个新范围内。”
    - 芯片一算：180度对应600，0度对应150，那么90度正好在中间，换算出来就是 **375**。
    - 所以，**`map()` 帮你算出了一个数字（比如 375）**，这个数字就是舵机转 90° 时需要的“电量”参数。
  
  ---
  
  ### 2. 第二个工具：`pwm.setPWM()` —— “发号施令的传令兵”
  
  现在“翻译官”把数字算出来了，但要把这个数字送到舵机那里去。`pwm.setPWM()` 就是干这个活的。
  
  - **格式**：`pwm.setPWM(通道, 开启时刻, 关闭时刻)`
  
  - **三个参数大白话解释**：
    1. **第一个参数（通道）**：就是“门牌号”。告诉芯片你是要把信号发给 **0号口** 的舵机，还是 **5号口** 的舵机。
    2. **第二个参数（开启时刻）**：你可以理解为“闹钟响铃的时间”。在舵机控制里，我们**永远让它一开机就响**，所以这里**永远写 `0`**，你完全不用纠结它。
    3. **第三个参数（关闭时刻）**：这才是**真正核心的数值**！它就是刚才 `map()` 帮你算出来的那个数字（比如 375）。芯片会这样理解：“从一开机（0）开始，我就给舵机通电，直到时间走到 **375** 的时候，我断电。”
  
  ---
  
   ### {{< icon "lightbulb" >}} 把这两行连起来看（合体技）
  
  ```cpp
  pwm.setPWM(0, 0, map(90, 0, 180, SERVOMIN, SERVOMAX));
  ```
  
  我们把括号里的东西拆开，其实芯片收到的终极指令就是：
  
  > **“传令兵（setPWM），请去 0 号门（第一个0），从 0 时刻起（第二个0），把这个翻译好的 375 数值（map算出来的）发出去！”**
  
  ---
  
   ### {{< icon "wrench" >}} 结论：你想改动舵机，只需要动两个地方
  
  明白了原理，你以后改代码就只用盯着这两处：
  
  1. **改角度**：只改 `map(` 后面的**第一个数字**。
     - 想要 45°？写 `map(45, 0, 180, ...)`
     - 想要 180°？写 `map(180, 0, 180, ...)`
  2. **改舵机插口**：只改 `setPWM(` 后面的**第一个数字**。
     - 舵机插在 `PWM5` 口，就写 `pwm.setPWM(5, 0, ...)`
  
  至于第二个参数（`0`），记住：**永远别碰它，永远写 0 就行！** 它只会把你绕晕，但对控制舵机毫无帮助。
  
  这样解释，是不是瞬间清爽多了？现在你就可以把 `90` 改成任意数字，随心所欲地指挥舵机转动啦！ 😄

---

### {{< icon "search" >}} 重点：setPWM 三个参数的真正含义

很多初学者对 `setPWM(channel, on, off)` 感到困惑，我们用图示解释：

- 一个 PWM 周期（比如 20ms）被分成 4096 个时间片（12位分辨率）。
- `on` 和 `off` 是其中的两个时间点。
- 输出高电平的时间段是 **从 `on` 时刻开始，到 `off` 时刻结束**。
- 通常情况下，我们只需要让 `on = 0`，然后调整 `off` 来控制脉宽。  
  例如 `off = 300` 表示高电平持续 `300/4096 * 20ms ≈ 1.46ms`。
- 所以你的代码中 `on` 始终为 0，只改变 `off`，完全正确。

---

### {{< icon "alert" >}} 硬件检查要点

1. **I2C 引脚**：  
   - 确保 PCA9685 的 SDA 接到 ESP32 的 **GPIO 8**，SCL 接到 **GPIO 9**。  
   - 如果板子丝印不同，必须修改 `Wire.begin()` 中的参数。

2. **供电**：  
   - PCA9685 芯片本身需要 **3.3V~5V 电源**（由 ESP32 的 3.3V 提供即可）。  
   - **舵机必须独立供电**：将外部 5V 电源（例如 5V 2A 适配器）接到 PCA9685 的 **V+** 和 **GND** 端子。  
   - **共地**：外部电源的 GND、ESP32 的 GND、PCA9685 的 GND 必须全部连在一起。

3. **舵机接线**：  
   - 舵机的信号线（黄/橙）插到 `PWM0` 接口（对应通道 0）。  
   - 红线接 `V+`，棕/黑线接 `GND`。

---

### {{< icon "wrench" >}} 如果舵机不动或抖动，可以调整的地方

- **微调 SERVOMIN 和 SERVOMAX**：  
  增大 `SERVOMIN` 会使 0° 位向 180° 方向偏移；减小 `SERVOMAX` 会使 180° 向 0° 靠拢。  
  先试着让舵机在 0° 和 180° 都能到达即可。

- **检查频率**：有些舵机支持更高频率，但 50Hz 是标准，不要轻易更改。

- **增加延迟**：如果舵机反应慢，可适当加长 `delay()` 让舵机有足够时间转到目标位置。

---

### {{< icon "lightbulb" >}} 扩展：如何控制多个舵机

如果你想同时控制多个舵机，非常简单：

```cpp
pwm.setPWM(0, 0, map(angle1, 0, 180, SERVOMIN, SERVOMAX));
pwm.setPWM(1, 0, map(angle2, 0, 180, SERVOMIN, SERVOMAX));
pwm.setPWM(2, 0, map(angle3, 0, 180, SERVOMIN, SERVOMAX));
// ... 最多 16 个通道
```

只需把第一个参数改为对应的通道号（0~15），就可以独立控制每个接口上的舵机。

---

### {{< icon "pen" >}} 总结

这段代码的核心作用：
1. 通过 I2C（GPIO 8/9）与板载 PCA9685 通信。
2. 初始化 PCA9685，设置 50Hz 频率。
3. 在通道 0 上循环输出 90° 和 0° 的 PWM 信号，驱动舵机来回摆动。

你已经成功让舵机动起来了，恭喜！🎉 如果还有任何疑问（比如如何修改角度、如何平滑运动等），随时可以问我。
