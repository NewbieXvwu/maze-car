// car.ino —— 迷宫小车主程序
//
// 开机后：蓝灯 = 就绪，红灯 = 有模块没初始化成功（串口里会说是哪个）。
// 按启动键（或板载 BOOT 键）→ 黄灯：手拿开，校准陀螺仪约 1 秒 → 绿灯：出发。跑的时候再按一下 = 急停。
// 拨码 1：OFF 稳妥档 / ON 快档。拨码 2：OFF 比赛赛道模式 / ON 通用迷宫模式。
// 串口（115200）或 WiFi 发 ? 看全部命令；装车时先用 i d g e m 逐个模块体检。
#include "config.h"
#include "hw.h"
#include "brain.h"
#include <Preferences.h>
#if TELEMETRY
#include <WiFi.h>
#include <WiFiUdp.h>
#endif

static const char* PNAMES[] = {
  "cell_mm", "wall_half_mm", "side_y_mm", "front_x_mm", "vmax_mm_s", "deadband_pwm",
  "cruise_mm_s", "creep_mm_s", "accel_mm_s2", "brake_mm_s2", "open_th_mm", "edge_lag_mm",
  "debounce_mm", "k_lat", "max_corr_deg", "k_head", "k_hd", "k_turn", "k_td",
  "turn_pwm", "turn_min_pwm", "k_align", "single_path", "stop_turns", "exit_run_mm"};
static const int NP = sizeof(PNAMES) / sizeof(PNAMES[0]);
static_assert(sizeof(BrainParams) == NP * sizeof(float), "BrainParams 加了字段：PNAMES 也要同步加");

static BrainParams base;                 // 基础参数：开机从闪存读，没存过就用 brain 的默认值
static float fast_cruise = FAST_CRUISE;
static Preferences prefs;
static String hw_err;

// ---------------------------------------------------------------- 输出：串口 + WiFi 同时发
#if TELEMETRY
static WiFiUDP udp;
static IPAddress bcast;
#endif
class Out : public Print {
  char buf[512]; size_t n = 0;
 public:
  size_t write(uint8_t c) override {
    Serial.write(c);
#if TELEMETRY
    if (n < sizeof(buf)) buf[n++] = (char)c;
    if (c == '\n') flush_line();
#endif
    return 1;
  }
  void flush_line() {
#if TELEMETRY
    if (!n) return;
    udp.beginPacket(bcast, UDP_PORT); udp.write((const uint8_t*)buf, n); udp.endPacket();
    n = 0;
#endif
  }
} out;

static void udp_send(const char* s, int len) {
#if TELEMETRY
  udp.beginPacket(bcast, UDP_PORT); udp.write((const uint8_t*)s, len); udp.endPacket();
#endif
}

// ---------------------------------------------------------------- 一次跑车
static bool running = false;
static uint32_t t0_us, last_tick_us, done_ms = 0;
static float dist[3] = {-1, -1, -1};
static int last_ndec = 0;
static float prev_encL, prev_encR, stall_t;
static bool btn_armed = true;

static void stop_run(const char* why, const Act* a) {
  motors(0, 0);                          // 短路刹车
  running = false;
  float t = (micros() - t0_us) / 1e6f;
  out.printf("停车：%s。用时 %.2f 秒，转弯/直行决策 %d 次\n", why, t, a ? a->ndec : last_ndec);
  led(80, 80, 80); done_ms = millis();
}

static void start_run() {
  if (running) return;
  if (!tof_ok(0) || !tof_ok(1) || !tof_ok(2) || !gyro_ok()) {
    out.printf("有模块没初始化成功，不能发车：%s\n", hw_err.c_str()); led(255, 0, 0); return;
  }
  // 这一版 PCB 没接电池分压，检查关掉时也不报电压（报 0.00 V 会误导）
  String bat_note;
#if BAT_CHECK_ENABLED
  float v = battery_v();
  if (v > 1.0f && v < BAT_MIN_V) { out.printf("电池 %.2f V，太低了，充满再跑\n", v); led(255, 0, 0); return; }
  bat_note = String("，电池 ") + String(v, 2) + " V";
#endif
  int sw = dip();
  BrainParams p = base;
  if (sw & 1) p.cruise_mm_s = fast_cruise;
  if (sw & 2) { p.single_path = 0; p.stop_turns = 0; }
  else        { p.single_path = 1; p.stop_turns = RACE_TURNS; }

  led(255, 140, 0);                      // 黄灯：手拿开
  while (button()) delay(5);
  delay(400);
  gyro_calibrate(800);
  enc_reset();
  dist[0] = dist[1] = dist[2] = -1;
  brain_init(&p, MODE_LEFT);

  // 遥测头：把这次用的全部参数发出去，回放时要用
  String h = "H,";
  h += (sw & 1) ? "fast" : "safe"; h += (sw & 2) ? ",generic" : ",race";
  for (int i = 0; i < NP; i++) { h += ","; h += PNAMES[i]; h += "="; h += String(((float*)&p)[i], 7); }
  h += "\n"; udp_send(h.c_str(), h.length());
  out.printf("出发：%s，%s，巡航 %.0f mm/s%s\n", (sw & 1) ? "快档" : "稳妥档",
             (sw & 2) ? "通用迷宫模式" : "比赛赛道模式", p.cruise_mm_s, bat_note.c_str());

  running = true; last_ndec = 0; stall_t = 0; prev_encL = prev_encR = 0;
  gyro_take_angle();
  t0_us = last_tick_us = micros();
  led(0, 255, 0);
}

static void run_tick() {
  uint32_t now = micros();
  float dt = (now - last_tick_us) * 1e-6f;
  last_tick_us = now;

  Sense s;
  s.t_ms = (now - t0_us) / 1000.0f;      // 用 micros 算，和陀螺仪积分用同一个 dt
  s.fresh = tof_poll(dist);
  s.dL = dist[0]; s.dF = dist[1]; s.dR = dist[2];
  s.gyro_z = dt > 0 ? gyro_take_angle() / dt : 0;   // 这 10 ms 里的平均角速度：大脑积出来的角度和 1 kHz 采样的一样准
  enc_read_mm(&s.encL, &s.encR);

  Act a;
  brain_step(&s, &a);
  motors(a.pwmL, a.pwmR);

  char line[200];
  int len = snprintf(line, sizeof(line), "D,%.9g,%.0f,%.0f,%.0f,%d,%.9g,%.9g,%.9g,%.4f,%.4f,%d,%d,%c\n",
                     s.t_ms, s.dL, s.dF, s.dR, s.fresh, s.gyro_z, s.encL, s.encR,
                     a.pwmL, a.pwmR, a.state, a.ndec, a.last_decision ? a.last_decision : '-');
  udp_send(line, len);
  if (a.ndec != last_ndec) { last_ndec = a.ndec; Serial.printf("%6.2f s  %c\n", s.t_ms / 1000, a.last_decision); }

  // 堵转保护：两个轮子都在用力、却都几乎不动，超过 1 秒就停（卡墙了，别烧电机）
  float vL = (s.encL - prev_encL) / dt, vR = (s.encR - prev_encR) / dt;
  prev_encL = s.encL; prev_encR = s.encR;
  bool stuck = fabsf(a.pwmL) > 0.3f && fabsf(a.pwmR) > 0.3f && fabsf(vL) < 15 && fabsf(vR) < 15;
  stall_t = stuck ? stall_t + dt : 0;

  if (a.state == 3) stop_run("到达终点", &a);
  else if (stall_t > 1.0f) stop_run("堵转", &a);
  else if (s.t_ms > RUN_TIMEOUT_MS) stop_run("超时", &a);
}

// ---------------------------------------------------------------- 体检命令
static bool abort_requested() {
  return button() || Serial.available();
}

static void test_tof() {
  out.println("测距（毫米）5 秒：车摆在通道正中时，侧面应约 102，前方离墙一格约 390");
  float d[3] = {-1, -1, -1};
  uint32_t t0 = millis(), tp = 0;
  while (millis() - t0 < 5000 && !abort_requested()) {
    tof_poll(d);
    if (millis() - tp >= 200) {
      tp = millis();
      out.printf("左 %5.0f   前 %5.0f   右 %5.0f%s\n", d[0], d[1], d[2],
                 (!tof_ok(0) || !tof_ok(1) || !tof_ok(2)) ? "   （有一颗没初始化，读数恒为 -1）" : "");
    }
    delay(5);
  }
}

static void test_gyro() {
  out.println("陀螺仪：车放平别动，校准 1 秒……");
  gyro_calibrate(1000);
  out.println("现在用手把车逆时针（从上往下看向左）转 90°，读数应接近 +90。10 秒：");
  float ang = 0; uint32_t t0 = millis(), tp = 0;
  while (millis() - t0 < 10000 && !abort_requested()) {
    gyro_sample(); ang += gyro_take_angle();
    if (millis() - tp >= 300) { tp = millis(); out.printf("航向 %+7.1f°\n", ang); }
  }
  out.println("读数是负的 → GYRO_SIGN 改成 -1。车静止时读数还在慢慢漂 → 重新校准时别碰车。");
}

static void test_enc() {
  out.println("编码器 10 秒：用手把两个轮子往前滚一圈（约 132 mm），两个读数都应约 +132");
  enc_reset();
  uint32_t t0 = millis(), tp = 0;
  while (millis() - t0 < 10000 && !abort_requested()) {
    if (millis() - tp >= 300) { tp = millis(); float l, r; enc_read_mm(&l, &r); out.printf("左 %+8.1f mm   右 %+8.1f mm\n", l, r); }
    delay(5);
  }
  out.println("往前滚却是负数 → 对应的 ENC_SIGN 改成 -1。");
}

static void test_motors() {
  out.println("电机：先把车架空，轮子离地！3 秒后开始，每个轮子正反各转 0.8 秒。");
  delay(3000);
  const char* name[2] = {"左轮", "右轮"};
  for (int side = 0; side < 2; side++) {
    for (int sgn = 1; sgn >= -1; sgn -= 2) {
      enc_reset();
      float u = 0.3f * sgn;
      motors(side == 0 ? u : 0, side == 1 ? u : 0);
      delay(800);
      motors(0, 0);
      float l, r; enc_read_mm(&l, &r);
      out.printf("%s PWM %+.1f：编码器 %+.0f mm —— 这时轮子应该在%s转\n", name[side], u, side == 0 ? l : r, sgn > 0 ? "往前" : "往后");
      delay(400);
    }
  }
  out.println("轮子方向反了 → 改 MOTOR_SIGN；方向对但编码器正负号反了 → 改 ENC_SIGN。");
  // 估一下 PWM=1 时的车速（架空空载，比落地略快）
  enc_reset(); motors(0.6f, 0.6f); delay(600);
  float l0, r0; enc_read_mm(&l0, &r0); delay(500);
  float l1, r1; enc_read_mm(&l1, &r1); motors(0, 0);
  float vL = (l1 - l0) / 0.5f, vR = (r1 - r0) / 0.5f, db = base.deadband_pwm;
  out.printf("PWM 0.6 空载：左 %.0f mm/s，右 %.0f mm/s → vmax_mm_s 约 %.0f（落地后再用直线跑校准）\n",
             vL, vR, (vL + vR) / 2 / ((0.6f - db) / (1 - db)));
}

static void list_params() {
  for (int i = 0; i < NP; i++) out.printf("  %-14s %g\n", PNAMES[i], ((float*)&base)[i]);
  out.printf("  %-14s %g   （快档巡航速度）\n", "fast_cruise", fast_cruise);
  out.println("（single_path / stop_turns 由拨码 2 在发车时决定，这里的值不起作用）");
}

static void param_cmd(String rest) {
  if (!rest.length()) { list_params(); return; }
  int sp = rest.indexOf(' ');
  if (sp < 0) { out.println("用法：p 名字 数值，例如 p cruise_mm_s 450"); return; }
  String name = rest.substring(0, sp), val = rest.substring(sp + 1);
  float v = val.toFloat();
  if (name == "fast_cruise") { fast_cruise = v; out.printf("fast_cruise = %g\n", v); return; }
  for (int i = 0; i < NP; i++) if (name == PNAMES[i]) { ((float*)&base)[i] = v; out.printf("%s = %g（save 才会存进闪存）\n", PNAMES[i], v); return; }
  out.println("没有这个参数，输入 p 看列表");
}

static void help() {
  out.println("命令：");
  out.println("  i          扫描 I2C（应看到 0x30 0x31 0x32 0x68）");
  out.println("  d          测距读数 5 秒");
  out.println("  g          陀螺仪：手动转车看角度");
  out.println("  e          编码器：手动滚轮子看里程");
  out.println("  m          电机方向和编码器方向（要先把车架空）");
  out.println("  b          电池电压      s  拨码和按键状态");
  out.println("  go         发车（同按键）  x  急停");
  out.println("  p          列出参数      p 名字 数值  在线改参数");
  out.println("  save       参数存进闪存  defaults  恢复默认参数");
}

static void command(String line) {
  line.trim();
  if (!line.length()) return;
  int sp = line.indexOf(' ');
  String cmd = sp < 0 ? line : line.substring(0, sp);
  String rest = sp < 0 ? "" : line.substring(sp + 1); rest.trim();
  if (running) { if (cmd == "x") stop_run("手动停止", nullptr); return; }   // 跑的时候只认急停
  if (cmd == "?" || cmd == "help") help();
  else if (cmd == "i") i2c_scan(out);
  else if (cmd == "d") test_tof();
  else if (cmd == "g") test_gyro();
  else if (cmd == "e") test_enc();
  else if (cmd == "m") test_motors();
  else if (cmd == "b") out.printf("电池 %.2f V\n", battery_v());
  else if (cmd == "s") { int d = dip(); out.printf("拨码 1 %s（%s），拨码 2 %s（%s），按键 %s\n", d & 1 ? "ON" : "OFF", d & 1 ? "快档" : "稳妥档",
                                                 d & 2 ? "ON" : "OFF", d & 2 ? "通用迷宫" : "比赛赛道", button() ? "按下" : "松开"); }
  else if (cmd == "go") start_run();
  else if (cmd == "x") out.println("没在跑");
  else if (cmd == "p") param_cmd(rest);
  else if (cmd == "save") { prefs.putBytes("bp", &base, sizeof(base)); prefs.putFloat("fast", fast_cruise); out.println("已存进闪存"); }
  else if (cmd == "defaults") { brain_default_params(&base); fast_cruise = FAST_CRUISE; prefs.clear(); out.println("已恢复默认参数"); }
  else out.println("不认识的命令，输入 ? 看列表");
}

// ---------------------------------------------------------------- 主程序
void setup() {
  Serial.begin(115200);
  delay(300);
  led(0, 0, 40);
  hw_begin(hw_err);
  prefs.begin("car", false);
  brain_default_params(&base);
  if (prefs.getBytesLength("bp") == sizeof(base)) prefs.getBytes("bp", &base, sizeof(base));
  fast_cruise = prefs.getFloat("fast", FAST_CRUISE);
#if TELEMETRY
  WiFi.softAP(AP_SSID, AP_PASS);
  bcast = WiFi.softAPBroadcastIP();
  udp.begin(UDP_PORT + 1);               // 车在 4211 收命令，往 4210 广播数据
#endif                                   // TELEMETRY 为 0 时根本不碰 WiFi，射频默认就是关的
  String status = "全部模块正常。";
  if (hw_err.length()) { status = "初始化失败："; status += hw_err; status += "。"; }
  out.printf("\n迷宫小车就绪。%s电池 %.2f V。输入 ? 看命令。\n", status.c_str(), battery_v());
  led(hw_err.length() ? 255 : 0, 0, hw_err.length() ? 0 : 60);
}

void loop() {
  gyro_sample();                         // 每圈都采：1 kHz 积分陀螺仪

  if (running) {
    if (micros() - last_tick_us >= 10000) run_tick();
  } else if (done_ms && millis() - done_ms > 3000) {
    done_ms = 0; led(hw_err.length() ? 255 : 0, 0, hw_err.length() ? 0 : 60);
  }

  // 按键：没在跑 = 发车，在跑 = 急停；按住不放只算一次
  if (button()) {
    if (btn_armed) {
      btn_armed = false;
      if (running) stop_run("按键停止", nullptr);
      else start_run();
    }
  } else btn_armed = true;

  static String sline;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') { if (sline.length()) command(sline); sline = ""; }
    else sline += c;
  }
#if TELEMETRY
  int n = udp.parsePacket();
  if (n > 0) {
    char buf[128]; int k = udp.read(buf, sizeof(buf) - 1);
    if (k > 0) { buf[k] = 0; command(String(buf)); }
  }
#endif
}
