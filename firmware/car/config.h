// config.h —— 接线和需要实测后修改的常数都在这里
#pragma once

// ============ 遥测 ============
// 1 = 开 WiFi：车自己开热点，把每个控制周期的数据用 UDP 发给电脑，也能从电脑发命令。
// 比赛前改成 0 再烧一次：WiFi 彻底不启动。
#define TELEMETRY 1
#define AP_SSID   "maze-car"
#if __has_include("secrets.h")
#include "secrets.h"               // 自己在本目录建这个文件，只写一行 #define AP_PASS "你的密码"（至少 8 位）；它不进仓库
#endif
#ifndef AP_PASS
#define AP_PASS   "mazecar123"     // 仓库是公开的，这个默认密码谁都看得到：去试车场地前建好 secrets.h 换掉
#endif
#define UDP_PORT  4210

// ============ 引脚（YD-ESP32-S3，排针和 DevKitC-1 相同）============
// 按洞洞板布局排的（board/layout.py 会核对这里和布局是否一致）：TB6612、陀螺仪、编码器和 ESP32 的脚都在同一行，直线就能连。
// 避开了：0/3/45/46（启动配置）、19/20（USB）、43/44（串口）、48（板载 RGB 灯）
#define PIN_SDA     41
#define PIN_SCL     42
#define PIN_XSHUT_L 40             // 三个 VL53L0X 的 XSHUT
#define PIN_XSHUT_F 39
#define PIN_XSHUT_R 38

#define PIN_PWMA     4             // TB6612 A 路 = 左电机
#define PIN_AIN2     5
#define PIN_AIN1     6
#define PIN_STBY     7
#define PIN_BIN1    15             // TB6612 B 路 = 右电机
#define PIN_BIN2    16
#define PIN_PWMB    17

#define PIN_ENC_LA  10             // 左编码器 C1
#define PIN_ENC_LB   9             // 左编码器 C2
#define PIN_ENC_RA  14             // 右编码器 C1
#define PIN_ENC_RB  13             // 右编码器 C2

#define PIN_DIP1    47             // 拨码 1：OFF = 稳妥档，ON = 快档
#define PIN_DIP2    21             // 拨码 2：OFF = 比赛赛道模式，ON = 通用迷宫模式（布局和图不一样时用）
#define PIN_BTN      2             // 启动/停止按键（另一脚接 GND）；板载 BOOT 键也能用
#define PIN_BAT      1             // 电池电压：100k + 33k 分压后接这里（可选；必须是 ADC1 的脚）

// ============ 方向和比例（用串口命令 m / e / g 实测后改）============
#define MOTOR_SIGN_L  1            // 给正 PWM 时轮子往前转就是 1，往后转改成 -1
#define MOTOR_SIGN_R  1
#define ENC_SIGN_L    1            // 轮子往前转时编码器读数增加就是 1，减少改成 -1
#define ENC_SIGN_R    1
#define GYRO_SIGN     1            // 从上往下看，车逆时针转（左转）时读数为正就是 1
#define WHEEL_D_MM   42.0f
#define COUNTS_PER_REV 1400.0f     // 7 PPR × 50 减速比 × 4 倍频
#define BAT_DIVIDER  (133.0f / 33.0f)
#define BAT_MIN_V     7.0f         // 低于这个电压不让发车（没接分压电阻时读数接近 0，自动跳过检查）

// ============ 比赛 ============
#define RACE_TURNS   14            // 比赛赛道一共 14 个弯，转完最后一个再走一段就停车
#define FAST_CRUISE  550.0f        // 快档巡航速度（毫米/秒），可以用 p fast_cruise 500 在线改
#define RUN_TIMEOUT_MS 120000      // 跑超过 2 分钟自动停
