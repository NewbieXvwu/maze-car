// brain.cpp —— 沿墙走 + 路口决策 + 学习/回放
//
// 整体思路（假设迷宫墙横平竖直、通道宽度大致一致）：
//   巡航：陀螺仪锁住"目标航向"（永远是 90° 的整数倍），再用侧墙距离微调航向，让车走在通道中间。
//   路口：侧面读数突然变大 = 看见开口。由开口边缘的位置推算出路口中心，开到中心再做决定。
//   前墙：前方读数到"停车距离" = 车轴正好在格子中心，就地决定往哪转。
//   决定：左手/右手法则；或者按学到的路线回放。
//   学习：只在"真路口"（≥2 个可选方向）和死胡同记录，并按 Pololu 的 xBx 规则随走随化简。
#include "brain.h"
#include <math.h>
#include <string.h>

static float clampf(float x, float lo, float hi) { return x < lo ? lo : (x > hi ? hi : x); }
static float minf(float a, float b) { return a < b ? a : b; }
static float maxf(float a, float b) { return a > b ? a : b; }

enum { ST_START = 0, ST_CRUISE = 1, ST_TURN = 2, ST_DONE = 3 };

static BrainParams P;
static int g_mode;
static int st;

static float last_t;
static float heading, head_tgt;   // 积分出来的航向 / 目标航向（度）
static float s_now;               // 里程（两轮平均，毫米）
static float v_cur;               // 当前前进速度指令（毫米/秒）
static float settle;              // 转弯到位后的稳定计时
static float far_timer;           // 三面都空旷多久了（判断出了迷宫）

// 测距中值滤波（取最近 3 次新数据的中位数，干掉锡箔胶带之类的离谱读数）
static float hist[3][3];
static int   hcnt[3];
static float dLf, dFf, dRf;

// 路口追踪
static float open_since[2];       // 侧面从哪个里程开始变"空"，-1 表示目前有墙
static int   pend;                // 是否有待处理的路口
static float pend_s;              // 待处理路口中心的里程
static float ignore_until;        // 刚过完路口，在离开这一格之前忽略侧面变化
static float check_at;            // 离开这一格时检查一次：下一格侧面是否也空
static float last_center;         // 上一个决策点的里程

// 用墙校正陀螺仪
static int   wl_ok[2];
static float wl_s[2], wl_d[2];

// 派生常量
static float SIDE_TGT, FRONT_STOP;
static float DEC_TH;      // 在格子中心判断"有没有开口"的阈值（比巡航时的低，因为中心处墙和开口的读数差得很开）
static float WALL_OK;     // 侧面读数小于它才拿来做居中控制

// 记忆
static char learn_buf[256]; static int learn_n;
static char learn_hand = 'l';
static char replay_buf[256]; static int replay_n, replay_i;
static char replay_hand = 'l';
static int  lost;
static int  ndec;
static char last_dec = '-';

// 已知赛道模式
static int   n_turns;             // 已经开始的转弯数（不含直行）
static float exit_mark;           // 最后一个弯转完时的里程，-1 = 还没到
static float hold_t;              // 前墙处两侧都像有墙时，等测距再看一眼的计时

// 防死循环：航位推算出"现在在第几格、朝哪"，同一状态出现第二次 = 绕圈了
typedef struct { short x, y; char dir; short ln; } Visit;
static Visit visits[256]; static int nvis;
static int cx, cy, n_loops;
static const int DX[4] = {1, 0, -1, 0}, DY[4] = {0, 1, 0, -1};
static int dir_now(void) { int k = (int)lroundf(head_tgt / 90.0f); return ((k % 4) + 4) % 4; }

void brain_default_params(BrainParams* p) {
  p->cell_mm = 300; p->wall_half_mm = 3; p->side_y_mm = 45; p->front_x_mm = 55;
  p->vmax_mm_s = 750; p->deadband_pwm = 0.06f;
  p->cruise_mm_s = 380; p->creep_mm_s = 50;
  p->accel_mm_s2 = 1800; p->brake_mm_s2 = 1000;
  p->open_th_mm = 250; p->edge_lag_mm = 45; p->debounce_mm = 40;
  p->k_lat = 0.25f; p->max_corr_deg = 8;
  p->k_head = 0.02f; p->k_hd = 0.0006f;
  p->k_turn = 0.010f; p->k_td = 0.0004f; p->turn_pwm = 0.45f; p->turn_min_pwm = 0.12f;
  p->k_align = 0.15f;
  p->single_path = 0; p->stop_turns = 0; p->exit_run_mm = 350;   // 默认是通用迷宫；比赛固件里打开
}

static float pwm_from_v(float v) {
  if (v <= 1) return 0;
  return P.deadband_pwm + (v / P.vmax_mm_s) * (1 - P.deadband_pwm);
}

static float med_of(int i) {
  int n = hcnt[i] < 3 ? hcnt[i] : 3;
  if (n == 0) return 2000;
  if (n == 1) return hist[i][0];
  if (n == 2) return (hist[i][0] + hist[i][1]) / 2;
  float a = hist[i][0], b = hist[i][1], c = hist[i][2];
  return maxf(minf(a, b), minf(maxf(a, b), c));
}
static void push(int i, float d) {
  if (d < 0) d = 2000;                       // 无效/超量程 = 很远
  hist[i][hcnt[i] % 3] = d; hcnt[i]++;
}
static void reset_filters(void) { hcnt[0] = hcnt[1] = hcnt[2] = 0; }

// ---------- 决策 ----------
static char hand_rule(int L, int S, int R, char hand) {
  if (hand == 'l') return L ? 'L' : S ? 'S' : R ? 'R' : 'B';
  return R ? 'R' : S ? 'S' : L ? 'L' : 'B';
}
static char decide(int L, int S, int R, int consume) {
  if (g_mode == MODE_REPLAY) {
    if (!lost && replay_i < replay_n) {
      char d = replay_buf[replay_i];
      int ok = (d == 'L' && L) || (d == 'S' && S) || (d == 'R' && R);
      if (ok) { if (consume) replay_i++; return d; }
    }
    if (consume) lost = 1;                   // 路线对不上：退回沿墙法兜底
    return hand_rule(L, S, R, replay_hand);
  }
  return hand_rule(L, S, R, g_mode == MODE_RIGHT ? 'r' : 'l');
}
static int ang(char c) { return c == 'R' ? 90 : c == 'B' ? 180 : c == 'L' ? 270 : 0; }
static void record(char d) {
  if (g_mode == MODE_REPLAY) return;
  if (learn_n < 255) learn_buf[learn_n++] = d;
  // Pololu 化简：x B y → 总转角对应的一个动作（剪掉走进死胡同又退出来的那段）
  while (learn_n >= 3 && learn_buf[learn_n - 2] == 'B') {
    int a = (ang(learn_buf[learn_n - 3]) + ang(learn_buf[learn_n - 2]) + ang(learn_buf[learn_n - 1])) % 360;
    learn_n -= 2;
    learn_buf[learn_n - 1] = a == 0 ? 'S' : a == 90 ? 'R' : a == 180 ? 'B' : 'L';
  }
}

// 路口中心只可能在"上一个决策点 + 整数个格距"处。估算值离网格点不远就吸附过去，
// 消掉开口检测的滞后（25° 视场角的光锥会扫到路口处横着的墙，让开口看起来"开得晚"）
static float snap_center(float est) {
  float k = roundf((est - last_center) / P.cell_mm);
  if (k < 1) k = 1;
  float g = last_center + k * P.cell_mm;
  return fabsf(g - est) < 0.35f * P.cell_mm ? g : est;
}

static void enter_post_zone(void) {
  ignore_until = last_center + P.cell_mm / 2 + 30;
  check_at = last_center + P.cell_mm / 2 + 80;
  open_since[0] = open_since[1] = -1;
  wl_ok[0] = wl_ok[1] = 0;
  pend = 0;
}

static void start_turn(char d) {
  head_tgt += (d == 'L') ? 90 : (d == 'R') ? -90 : 180;
  st = ST_TURN; settle = 0; v_cur = 0;
}

// 沿墙法是确定性的：同一个格子、同一个朝向第二次来，就会永远绕下去（比如绕着一个孤岛）。
// 发现后换另一只手，并把学到的路线剪回第一次到这里之前。
static void loop_check(void) {
  int dn = dir_now();
  if (g_mode != MODE_REPLAY || lost) {
    for (int i = 0; i < nvis; i++) {
      if (visits[i].x == cx && visits[i].y == cy && visits[i].dir == dn) {
        if (g_mode == MODE_REPLAY) replay_hand = (replay_hand == 'l') ? 'r' : 'l';
        else {
          g_mode = (g_mode == MODE_LEFT) ? MODE_RIGHT : MODE_LEFT;
          learn_hand = (g_mode == MODE_RIGHT) ? 'r' : 'l';
          if (visits[i].ln < learn_n) learn_n = visits[i].ln;
        }
        nvis = 0; n_loops++;
        break;
      }
    }
  }
  if (nvis < 256) { visits[nvis].x = (short)cx; visits[nvis].y = (short)cy; visits[nvis].dir = (char)dn; visits[nvis].ln = (short)learn_n; nvis++; }
}

// 在决策点（路口中心 / 前墙停车点 / 起点）调用
static void decision_point(int L, int S, int R, float center_s) {
  int k = (int)lroundf((center_s - last_center) / P.cell_mm);   // 从上个决策点走了几格
  cx += DX[dir_now()] * k; cy += DY[dir_now()] * k;
  loop_check();
  int cnt = L + S + R;
  char d;
  if (cnt >= 2) { d = decide(L, S, R, 1); record(d); }
  else if (cnt == 1) d = L ? 'L' : S ? 'S' : 'R';     // 只有一条路的弯，不算决策
  else { d = 'B'; record('B'); }                      // 死胡同
  last_dec = d; ndec++;
  if (d != 'S') n_turns++;
  last_center = (d == 'S') ? center_s : s_now;     // 直行：以网格中心为基准，偏差不往下传
  if (d == 'S') { st = ST_CRUISE; enter_post_zone(); }
  else start_turn(d);
}

// 看见侧面开口后：推算路口中心，判断是不是"真路口"（前方也能走）
static void maybe_schedule(float center) {
  float ahead = center - s_now;
  if (ahead < 0) ahead = 0;
  float front_if_closed = ahead + FRONT_STOP;          // 如果这一格前方有墙，前测距应该读到这个数
  if (dFf > front_if_closed + 0.6f * P.cell_mm) {      // 前方明显更远 → 直行也可以 → 是真路口
    pend = 1; pend_s = s_now + ahead;
  }
  // 否则前墙就在这一格，交给"前墙停车"统一处理
}

void brain_init(const BrainParams* p, int mode) {
  P = *p; g_mode = mode; st = ST_START;
  last_t = -1; heading = head_tgt = 0; s_now = 0; v_cur = 0; settle = 0; far_timer = 0;
  reset_filters(); dLf = dFf = dRf = 2000;
  open_since[0] = open_since[1] = -1; wl_ok[0] = wl_ok[1] = 0; pend = 0; ignore_until = 0; check_at = -1; last_center = 0;
  SIDE_TGT = P.cell_mm / 2 - P.wall_half_mm - P.side_y_mm;
  FRONT_STOP = P.cell_mm / 2 - P.wall_half_mm - P.front_x_mm;
  DEC_TH = 0.55f * P.cell_mm;
  WALL_OK = 1.5f * SIDE_TGT;
  ndec = 0; last_dec = '-'; lost = 0; replay_i = 0;
  nvis = 0; cx = cy = 0; n_loops = 0;
  n_turns = 0; exit_mark = -1; hold_t = 0;
  if (mode != MODE_REPLAY) { learn_n = 0; learn_hand = (mode == MODE_RIGHT) ? 'r' : 'l'; }
}

int brain_get_path(char* buf, int maxlen) {
  if (maxlen < learn_n + 2) return -1;
  buf[0] = learn_hand;
  memcpy(buf + 1, learn_buf, learn_n);
  buf[learn_n + 1] = 0;
  return learn_n + 1;
}
void brain_set_path(const char* buf) {
  int n = (int)strlen(buf);
  if (n < 1) { replay_n = 0; return; }
  replay_hand = buf[0] == 'r' ? 'r' : 'l';
  replay_n = n - 1 > 255 ? 255 : n - 1;
  memcpy(replay_buf, buf + 1, replay_n);
}

int brain_debug(float* o, int n) {
  float v[] = {s_now, (float)pend, pend_s, last_center, ignore_until, check_at,
               open_since[0], open_since[1], dLf, dFf, dRf, heading, head_tgt, v_cur,
               (float)cx, (float)cy, (float)n_loops};
  int k = (int)(sizeof(v) / sizeof(v[0]));
  if (n < k) k = n;
  for (int i = 0; i < k; i++) o[i] = v[i];
  return k;
}

void brain_step(const Sense* s, Act* a) {
  float dt = (last_t < 0) ? 0 : (s->t_ms - last_t) / 1000.0f;
  last_t = s->t_ms;
  heading += s->gyro_z * dt;
  s_now = (s->encL + s->encR) / 2;

  if (s->fresh & 1) push(0, s->dL);
  if (s->fresh & 2) push(1, s->dF);
  if (s->fresh & 4) push(2, s->dR);
  dLf = med_of(0); dFf = med_of(1); dRf = med_of(2);

  a->pwmL = a->pwmR = 0;

  if (st == ST_START) {
    if (s->t_ms >= 150 && hcnt[0] && hcnt[1] && hcnt[2]) {   // 等三个传感器都有数据
      int S = dFf > FRONT_STOP + 0.6f * P.cell_mm;
      if (P.single_path >= 0.5f && S) decision_point(0, 1, 0, s_now);   // 车可能摆在入口线外，两侧看着是空的，别当成路口
      else decision_point(dLf > DEC_TH, S, dRf > DEC_TH, s_now);
    }
  } else if (st == ST_TURN) {
    float err = head_tgt - heading;
    float w = clampf(P.k_turn * err - P.k_td * s->gyro_z, -P.turn_pwm, P.turn_pwm);
    if (fabsf(err) > 1.5f && fabsf(w) < P.turn_min_pwm) w = err > 0 ? P.turn_min_pwm : -P.turn_min_pwm;
    a->pwmL = -w; a->pwmR = w;
    if (fabsf(err) < 1.5f && fabsf(s->gyro_z) < 20) {
      settle += dt;
      if (settle > 0.05f) {
        st = ST_CRUISE; last_center = s_now; enter_post_zone(); reset_filters();
        if (P.stop_turns >= 0.5f && n_turns >= (int)lroundf(P.stop_turns) && exit_mark < 0) exit_mark = s_now;
      }
    } else settle = 0;
  } else if (st == ST_CRUISE) {
    // 1) 侧面开口追踪
    if (hcnt[0] >= 2 && hcnt[2] >= 2) {
      float d2[2] = {dLf, dRf};
      for (int i = 0; i < 2; i++) {
        if (d2[i] > P.open_th_mm) { if (open_since[i] < 0) open_since[i] = s_now; }
        else open_since[i] = -1;
      }
      if (!pend && s_now >= ignore_until && P.single_path < 0.5f) {   // 已知没有岔路就不找岔路：少一类误判
        for (int i = 0; i < 2 && !pend; i++) {
          if (open_since[i] >= ignore_until && s_now - open_since[i] >= P.debounce_mm) {
            float edge = open_since[i] - P.edge_lag_mm;
            maybe_schedule(snap_center(edge + P.cell_mm / 2 - P.wall_half_mm));
          }
        }
      }
      if (check_at >= 0 && s_now >= check_at) {             // 刚离开路口格：下一格侧面也空吗？
        check_at = -1;
        if (!pend && P.single_path < 0.5f && (dLf > P.open_th_mm || dRf > P.open_th_mm)) maybe_schedule(last_center + P.cell_mm);
      }
    }

    // 2) 前墙到停车距离 → 就地决策
    if (hcnt[1] >= 1 && dFf <= FRONT_STOP + 3) {
      int L = dLf > DEC_TH, R = dRf > DEC_TH;
      if (P.single_path >= 0.5f && !L && !R && hold_t < 0.5f) {
        hold_t += dt;                                        // 赛道上没有死胡同：多半是读数抖了，停着再看半秒
      } else {
        hold_t = 0; pend = 0;
        decision_point(L, 0, R, s_now);
      }
    } else if (pend && s_now >= pend_s - 2) {                // 3) 到达路口中心
      decision_point(dLf > DEC_TH, dFf > FRONT_STOP + 0.6f * P.cell_mm, dRf > DEC_TH, pend_s);
    }

    if (st == ST_CRUISE) {
      // 速度规划：要转弯的路口和前墙都提前按刹车曲线减速
      float v_lim = P.cruise_mm_s;
      float dfront = dFf - FRONT_STOP;
      v_lim = minf(v_lim, sqrtf(2 * P.brake_mm_s2 * maxf(dfront, 0)) + (dfront > 3 ? P.creep_mm_s : 0));
      if (pend) {
        char prov = decide(dLf > P.open_th_mm, 1, dRf > P.open_th_mm, 0);
        if (prov != 'S') {
          float dc = pend_s - s_now;
          v_lim = minf(v_lim, sqrtf(2 * P.brake_mm_s2 * maxf(dc, 0)) + (dc > 2 ? P.creep_mm_s : 0));
        }
      }
      if (v_lim > v_cur) v_cur = minf(v_lim, v_cur + P.accel_mm_s2 * dt);
      else v_cur = v_lim;
      float base = pwm_from_v(v_cur);

      // 航向 + 横向：两边都有墙就居中，只有一边就和那边保持距离
      int haveL = dLf < WALL_OK && open_since[0] < 0;   // 介于 WALL_OK 和 open_th 之间的读数说不清，不拿来居中
      int haveR = dRf < WALL_OK && open_since[1] < 0;
      float lat = 0; int use = 1;
      if (haveL && haveR) lat = (dLf - dRf) / 2;
      else if (haveL) lat = dLf - SIDE_TGT;
      else if (haveR) lat = SIDE_TGT - dRf;
      else use = 0;

      // 用墙校正陀螺仪：沿墙走 60 mm，侧面读数变了多少 → 车身相对墙的真实角度。
      // 拿它慢慢修正积分出来的航向，陀螺仪零漂就不会越积越大。
      int have[2] = {haveL, haveR};
      float dd2[2] = {dLf, dRf};
      for (int i = 0; i < 2; i++) {
        if (have[i] && v_cur > 100) {
          if (!wl_ok[i]) { wl_ok[i] = 1; wl_s[i] = s_now; wl_d[i] = dd2[i]; }
          else if (s_now - wl_s[i] >= 60) {
            float ang = atan2f(dd2[i] - wl_d[i], s_now - wl_s[i]) * 57.2958f;
            float meas = (i == 0) ? -ang : ang;          // 车身相对通道的角度，逆时针为正
            float rel = heading - head_tgt;              // 陀螺仪以为的角度
            heading -= P.k_align * (rel - meas);
            wl_s[i] = s_now; wl_d[i] = dd2[i];
          }
        } else wl_ok[i] = 0;
      }
      float corr = (use && v_cur > 60) ? clampf(P.k_lat * lat, -P.max_corr_deg, P.max_corr_deg) : 0;
      float herr = head_tgt + corr - heading;
      float diff = P.k_head * herr - P.k_hd * s->gyro_z;
      a->pwmL = clampf(base - diff, -1, 1);
      a->pwmR = clampf(base + diff, -1, 1);

      // 4) 三面都空旷超过 1 秒 → 已经出了迷宫，停车
      if (dLf > 1500 && dFf > 1500 && dRf > 1500) { far_timer += dt; if (far_timer > 1.0f) st = ST_DONE; }
      else far_timer = 0;
      // 5) 已知赛道：最后一个弯转完、又走够 exit_run_mm → 车已出线，停车（不然左手法则会绕回入口）
      if (exit_mark >= 0 && s_now - exit_mark >= P.exit_run_mm) st = ST_DONE;
      if (st == ST_DONE) { a->pwmL = a->pwmR = 0; }
    }
  }
  a->state = st; a->ndec = ndec; a->last_decision = last_dec;
}
