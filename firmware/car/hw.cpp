// hw.cpp —— 硬件层实现（Arduino-ESP32 3.x）
#include "hw.h"
#include "config.h"
#include <Wire.h>
#include <VL53L0X.h>               // Pololu 的 VL53L0X 库（库管理器里搜 "VL53L0X"，作者 Pololu）
#include "driver/pulse_cnt.h"

// ---------------------------------------------------------------- 电机（TB6612）
static const uint32_t PWM_FREQ = 20000, PWM_BITS = 10, PWM_MAX = (1 << PWM_BITS) - 1;

static void motor_one(int pwm_pin, int in1, int in2, float u) {
  if (u > 1) u = 1;
  if (u < -1) u = -1;
  if (u >= 0) { digitalWrite(in1, HIGH); digitalWrite(in2, LOW); }
  else        { digitalWrite(in1, LOW);  digitalWrite(in2, HIGH); u = -u; }
  ledcWrite(pwm_pin, (uint32_t)(u * PWM_MAX + 0.5f));   // 占空比为 0 时 TB6612 是短路刹车
}

void motors(float l, float r) {
  digitalWrite(PIN_STBY, HIGH);
  motor_one(PIN_PWMA, PIN_AIN1, PIN_AIN2, l * MOTOR_SIGN_L);
  motor_one(PIN_PWMB, PIN_BIN1, PIN_BIN2, r * MOTOR_SIGN_R);
}

void motors_off() {
  ledcWrite(PIN_PWMA, 0); ledcWrite(PIN_PWMB, 0);
  digitalWrite(PIN_STBY, LOW);
}

static bool motors_begin() {
  int outs[] = {PIN_AIN1, PIN_AIN2, PIN_BIN1, PIN_BIN2, PIN_STBY};
  for (int p : outs) { pinMode(p, OUTPUT); digitalWrite(p, LOW); }
  bool ok = ledcAttach(PIN_PWMA, PWM_FREQ, PWM_BITS) && ledcAttach(PIN_PWMB, PWM_FREQ, PWM_BITS);
  motors_off();
  return ok;
}

// ---------------------------------------------------------------- 编码器（PCNT 硬件计数，四倍频）
static pcnt_unit_handle_t enc_unit[2] = {nullptr, nullptr};
static const int ENC_LIMIT = 30000;

static bool enc_one(int i, int pin_a, int pin_b) {
  pcnt_unit_config_t uc = {};
  uc.low_limit = -ENC_LIMIT; uc.high_limit = ENC_LIMIT;
  uc.flags.accum_count = 1;                       // 到上下限自动清零时把溢出部分累加起来
  if (pcnt_new_unit(&uc, &enc_unit[i]) != ESP_OK) return false;
  pcnt_glitch_filter_config_t fc = {};
  fc.max_glitch_ns = 1000;
  pcnt_unit_set_glitch_filter(enc_unit[i], &fc);
  pcnt_chan_config_t ca = {}; ca.edge_gpio_num = pin_a; ca.level_gpio_num = pin_b;
  pcnt_chan_config_t cb = {}; cb.edge_gpio_num = pin_b; cb.level_gpio_num = pin_a;
  pcnt_channel_handle_t ha = nullptr, hb = nullptr;
  if (pcnt_new_channel(enc_unit[i], &ca, &ha) != ESP_OK) return false;
  if (pcnt_new_channel(enc_unit[i], &cb, &hb) != ESP_OK) return false;
  pcnt_channel_set_edge_action(ha, PCNT_CHANNEL_EDGE_ACTION_DECREASE, PCNT_CHANNEL_EDGE_ACTION_INCREASE);
  pcnt_channel_set_level_action(ha, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE);
  pcnt_channel_set_edge_action(hb, PCNT_CHANNEL_EDGE_ACTION_INCREASE, PCNT_CHANNEL_EDGE_ACTION_DECREASE);
  pcnt_channel_set_level_action(hb, PCNT_CHANNEL_LEVEL_ACTION_KEEP, PCNT_CHANNEL_LEVEL_ACTION_INVERSE);
  pcnt_unit_add_watch_point(enc_unit[i], -ENC_LIMIT);
  pcnt_unit_add_watch_point(enc_unit[i], ENC_LIMIT);
  if (pcnt_unit_enable(enc_unit[i]) != ESP_OK) return false;
  pcnt_unit_clear_count(enc_unit[i]);
  return pcnt_unit_start(enc_unit[i]) == ESP_OK;
}

// 软件再兜一层溢出：计数器到 ±30000（约 2.8 m）会清零，一圈赛道约 11 m 会碰到好几次。
// accum_count 生效时读数本身是连续的，下面的修正不会触发；万一没生效，靠"相邻两次读数不可能差半个量程"补回来。
// 前提是至少每秒读一次（跑车时每 10 ms 读一次）。
static int last_raw[2] = {0, 0};
static long long acc[2] = {0, 0};

void enc_reset() {
  for (int i = 0; i < 2; i++) {
    if (enc_unit[i]) pcnt_unit_clear_count(enc_unit[i]);
    last_raw[i] = 0; acc[i] = 0;
  }
}

void enc_read_mm(float* l, float* r) {
  for (int i = 0; i < 2; i++) {
    int raw = 0;
    if (!enc_unit[i] || pcnt_unit_get_count(enc_unit[i], &raw) != ESP_OK) continue;
    int d = raw - last_raw[i];
    if (d > ENC_LIMIT / 2) d -= ENC_LIMIT;
    else if (d < -ENC_LIMIT / 2) d += ENC_LIMIT;
    acc[i] += d; last_raw[i] = raw;
  }
  const float k = 3.14159265f * WHEEL_D_MM / COUNTS_PER_REV;
  *l = acc[0] * k * ENC_SIGN_L;
  *r = acc[1] * k * ENC_SIGN_R;
}

// ---------------------------------------------------------------- 激光测距（3 × VL53L0X）
static VL53L0X tof[3];
static bool tof_good[3];
static const uint8_t XSHUT[3] = {PIN_XSHUT_L, PIN_XSHUT_F, PIN_XSHUT_R};
static const char* TOF_NAME[3] = {"左测距", "前测距", "右测距"};

static void tof_begin(String& err) {
  // 三颗默认地址都是 0x29：先全部复位，再逐个唤醒、逐个改地址
  for (int i = 0; i < 3; i++) { pinMode(XSHUT[i], OUTPUT); digitalWrite(XSHUT[i], LOW); }
  delay(20);
  for (int i = 0; i < 3; i++) {
    digitalWrite(XSHUT[i], HIGH);
    delay(20);
    tof[i].setBus(&Wire);
    tof[i].setTimeout(60);
    tof_good[i] = tof[i].init();
    if (tof_good[i]) {
      tof[i].setAddress(0x30 + i);
      tof[i].startContinuous(0);                  // 连续测量，默认约 33 ms 一次
    } else {
      digitalWrite(XSHUT[i], LOW);                // 坏的那颗留在复位状态，别占着 0x29 干扰下一颗
      err += TOF_NAME[i]; err += " ";
    }
  }
}

bool tof_ok(int i) { return tof_good[i]; }

int tof_poll(float d[3]) {
  int fresh = 0;
  for (int i = 0; i < 3; i++) {
    if (!tof_good[i]) continue;
    if ((tof[i].readReg(VL53L0X::RESULT_INTERRUPT_STATUS) & 0x07) == 0) continue;   // 新数据还没好，不等
    uint16_t mm = tof[i].readRangeContinuousMillimeters();
    d[i] = (tof[i].timeoutOccurred() || mm == 0 || mm >= 2000) ? -1.0f : (float)mm;    // 超量程时库返回 8190 左右
    fresh |= 1 << i;
  }
  return fresh;
}

// ---------------------------------------------------------------- 陀螺仪（MPU6050，只用 Z 轴）
static const uint8_t MPU = 0x68;
static const float GYRO_LSB = 32.8f;              // ±1000 °/s 量程
static bool  mpu_good = false;
static float g_bias = 0, g_angle = 0, g_rate = 0;
static uint32_t g_last_us = 0;

static bool mpu_write(uint8_t reg, uint8_t v) {
  Wire.beginTransmission(MPU); Wire.write(reg); Wire.write(v);
  return Wire.endTransmission() == 0;
}
static bool mpu_read_gz(int16_t* v) {
  Wire.beginTransmission(MPU); Wire.write(0x47);  // GYRO_ZOUT_H
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(MPU, (size_t)2) != 2) return false;
  uint8_t hi = Wire.read(), lo = Wire.read();
  *v = (int16_t)((hi << 8) | lo);
  return true;
}
static bool mpu_begin() {
  if (!mpu_write(0x6B, 0x01)) return false;       // 唤醒，时钟用 X 轴陀螺仪的 PLL
  delay(50);
  mpu_write(0x1A, 0x03);                          // 数字低通约 44 Hz
  mpu_write(0x1B, 0x10);                          // ±1000 °/s（原地转弯约 400 °/s，留够余量）
  mpu_write(0x19, 0x00);                          // 1 kHz 采样
  int16_t v;
  return mpu_read_gz(&v);
}

bool gyro_ok() { return mpu_good; }

void gyro_calibrate(int ms) {
  if (!mpu_good) return;
  double sum = 0; int n = 0;
  uint32_t t0 = millis();
  while (millis() - t0 < (uint32_t)ms) {
    int16_t v;
    if (mpu_read_gz(&v)) { sum += v; n++; }
    delayMicroseconds(1000);
  }
  if (n) g_bias = sum / n;
  g_angle = 0; g_last_us = micros();
}

void gyro_sample() {
  if (!mpu_good) return;
  uint32_t now = micros();
  if (now - g_last_us < 1000) return;             // 最多 1 kHz，别把 I2C 总线占满
  int16_t v;
  if (!mpu_read_gz(&v)) return;
  float dt = (now - g_last_us) * 1e-6f;
  g_last_us = now;
  g_rate = (v - g_bias) / GYRO_LSB * GYRO_SIGN;
  g_angle += g_rate * dt;
}

float gyro_take_angle() { float a = g_angle; g_angle = 0; return a; }
float gyro_rate() { return g_rate; }

// ---------------------------------------------------------------- 其他
float battery_v() {
  uint32_t mv = 0;
  for (int i = 0; i < 8; i++) mv += analogReadMilliVolts(PIN_BAT);
  return mv / 8.0f / 1000.0f * BAT_DIVIDER;
}

int dip() { return (digitalRead(PIN_DIP1) == LOW ? 1 : 0) | (digitalRead(PIN_DIP2) == LOW ? 2 : 0); }
bool button() { return digitalRead(PIN_BTN) == LOW || digitalRead(0) == LOW; }

void led(uint8_t r, uint8_t g, uint8_t b) {
#ifdef RGB_BUILTIN
  rgbLedWrite(RGB_BUILTIN, r, g, b);
#endif
}

void i2c_scan(Print& out) {
  out.print("I2C 设备：");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) { out.print(" 0x"); out.print(a, HEX); }
  }
  out.println("   （应有 0x30 0x31 0x32 三颗测距 + 0x68 陀螺仪）");
}

bool hw_begin(String& err) {
  pinMode(PIN_DIP1, INPUT_PULLUP); pinMode(PIN_DIP2, INPUT_PULLUP);
  pinMode(PIN_BTN, INPUT_PULLUP);  pinMode(0, INPUT_PULLUP);       // ADC 默认衰减就能量到约 3.1 V，分压后 8.4 V 对应约 2.1 V
  if (!motors_begin()) err += "电机PWM ";
  if (!enc_one(0, PIN_ENC_LA, PIN_ENC_LB)) err += "左编码器 ";
  if (!enc_one(1, PIN_ENC_RA, PIN_ENC_RB)) err += "右编码器 ";
  Wire.begin(PIN_SDA, PIN_SCL, 400000);
  Wire.setTimeOut(10);
  mpu_good = mpu_begin();
  if (!mpu_good) err += "陀螺仪 ";
  tof_begin(err);
  return err.length() == 0;
}
