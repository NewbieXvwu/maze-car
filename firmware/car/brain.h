// brain.h —— 小车的"大脑"：只做决策，不碰任何硬件
// 同一份代码既编译进仿真器（sim.py），也直接放进 Arduino 工程上车。
#pragma once
#ifdef __cplusplus
extern "C" {
#endif

// 可调参数。单位：毫米、毫米/秒、度
typedef struct {
  float cell_mm;        // 格子间距 = 通道宽 + 墙厚（宣讲会赛道图为 300；到场实测后改这里）
  float wall_half_mm;   // 墙厚的一半
  float side_y_mm;      // 左右测距传感器到车中线的距离（传感器装在车轮轴正上方）
  float front_x_mm;     // 前测距传感器在车轮轴前方多远
  float vmax_mm_s;      // PWM=1 时的车速
  float deadband_pwm;   // 电机死区：PWM 小于它轮子不转
  float cruise_mm_s;    // 巡航速度
  float creep_mm_s;     // 快到停车点时的蠕行速度
  float accel_mm_s2;    // 加速度上限（太猛会打滑）
  float brake_mm_s2;    // 刹车减速度
  float open_th_mm;     // 侧面读数大于它 = 这边有开口
  float edge_lag_mm;    // 传感器视场角 + 滤波造成的"看见开口"滞后
  float debounce_mm;    // 开口要连续存在这么远才算数（防接缝缝隙）
  float k_lat;          // 横向偏差 → 航向修正（度/毫米）
  float max_corr_deg;   // 航向修正上限
  float k_head;         // 航向误差 → 左右轮差速（PWM/度）
  float k_hd;           // 航向阻尼（PWM/(度/秒)）
  float k_turn;         // 原地转弯 P（PWM/度）
  float k_td;           // 原地转弯阻尼
  float turn_pwm;       // 原地转弯最大 PWM
  float turn_min_pwm;   // 原地转弯最小 PWM（克服死区）
  float k_align;        // 用墙校正陀螺仪零漂的力度（0 = 不校正）
  // —— 已知赛道模式（比赛赛道没有岔路时打开）——
  float single_path;    // 1 = 赛道只有一条路：不检测侧面岔路，只在前墙处转弯；起步直接直行
  float stop_turns;     // 转完第几个弯后准备停车（比赛赛道是 14；0 = 不数弯）
  float exit_run_mm;    // 最后一个弯转完后再走多远停车
} BrainParams;

// 每个控制周期喂给大脑的数据
typedef struct {
  float t_ms;           // 时间（毫秒）
  float dL, dF, dR;     // 三个测距读数（毫米），<0 表示无效/超量程
  float gyro_z;         // 陀螺仪 Z 轴角速度（度/秒，逆时针为正）
  float encL, encR;     // 左右轮累计里程（毫米）
  int   fresh;          // 本周期哪些测距是新数据：bit0=左 bit1=前 bit2=右
} Sense;

// 大脑的输出
typedef struct {
  float pwmL, pwmR;     // -1..1
  int   state;          // 0 起步 1 巡航 2 转弯 3 结束
  int   ndec;           // 已做出的路口决策次数（每次 +1）
  char  last_decision;  // 'L' 'S' 'R' 'B'
} Act;

enum { MODE_LEFT = 0, MODE_RIGHT = 1, MODE_REPLAY = 2 };

void brain_default_params(BrainParams* p);
void brain_init(const BrainParams* p, int mode);  // 每次发车前调用；不会清掉已学到的路线
void brain_step(const Sense* s, Act* a);           // 建议 100 Hz 调用
int  brain_get_path(char* buf, int maxlen);        // 取出学到的路线（左/右手跑完后），用来存进闪存
void brain_set_path(const char* buf);              // 载入路线（回放模式之前）
int  brain_debug(float* out, int n);               // 导出内部状态，调试/遥测用（上车后可以经 WiFi 发到电脑）

#ifdef __cplusplus
}
#endif
