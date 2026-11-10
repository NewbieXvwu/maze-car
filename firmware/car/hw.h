// hw.h —— 硬件层：电机、编码器、激光测距、陀螺仪、开关、电池、灯
#pragma once
#include <Arduino.h>

bool  hw_begin(String& err);          // 初始化全部硬件；失败的模块名写进 err，其余照常工作

void  motors(float l, float r);        // -1..1，正 = 往前；0 = 刹车
void  motors_off();                    // 断开驱动（STBY 拉低）

void  enc_reset();
void  enc_read_mm(float* l, float* r); // 从上次 enc_reset 起的累计里程（毫米），往前为正

int   tof_poll(float d[3]);            // 取新到的测距（左/前/右，毫米，无效 = -1），返回哪几个是新的（bit0 左 bit1 前 bit2 右）
bool  tof_ok(int i);

void  gyro_calibrate(int ms);          // 车静止时调用：测零漂
void  gyro_sample();                   // 尽量常调用：读一次角速度并累加角度
float gyro_take_angle();               // 取出上次以来累加的角度（度，逆时针为正）并清零
float gyro_rate();                     // 最近一次的角速度（度/秒）
bool  gyro_ok();

float battery_v();                     // 没接分压电阻时返回接近 0
int   dip();                           // bit0 = 拨码 1，bit1 = 拨码 2（ON = 1）
bool  button();                        // 外接按键或 BOOT 键按下
void  led(uint8_t r, uint8_t g, uint8_t b);
void  i2c_scan(Print& out);
