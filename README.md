# 迷宫小车

An ESP32-S3 wall-following car for a campus maze race: firmware, a 2D simulator that runs the same control code, a custom 55×37 mm carrier PCB, and the mechanical CAD.

第九届长安大学迷宫智能小车大赛（迷宫组）参赛车：ESP32-S3（YD 板）+ TB6612 + N20 编码器电机 + VL53L0X 激光测距 + MPU6050 兼容陀螺仪（实装芯片是 MPU6500），自制 55×37 mm 转接主板。

```
platformio.ini         PlatformIO 构建配置：pio run -e car 编译、-t upload 烧录（详见 firmware/README.md）
firmware/car/          Arduino 固件。大脑 brain.cpp 也在这里，整个仓库只有这一份
firmware/board/        主板布线：layout.py 自检并生成 board.html；netlist.md 是网络表；eda/ 是生成 EDA 工程的脚本
firmware/telemetry.py  电脑端 WiFi 遥测
maze-sim/              仿真器（直接编译 firmware/car/brain.cpp）和真车数据回放
eda/                   主板的嘉立创 EDA 专业版工程：原理图、PCB、拼板（打开 maze-car.eprj3）
out/gerber/            主板的 Gerber 下单包（就是送去打样的那一份）
cad/、out/*.step/.stl  整车结构：参数、尺寸链自检、装配说明；整车 STEP/STL 和各零件 STL
迷宫小车主板布线.html   交互式布线图（浏览器直接打开）：逐根焊线、万用表测量模式
docs/                  赛情与决策、硬件笔记（含装车调试记录）、采购进度、PCB 下单与装配
examples/              最小示例（PSRAM 手动初始化）
```

各部分怎么用，见 `firmware/README.md` 和 `maze-sim/README.md`。

## 比赛版本说明

比赛用的是装车调试阶段（2026-11-15）定下的配置，比赛赛道模式（拨码 2 OFF）的逻辑之后没有再改过：

- **左测距停用**（`config.h`：`LEFT_TOF_ENABLED 0`）。左侧 VL53L0X 换过模块、重焊过，始终时通时断，最终决定不用。
  比赛赛道只有一条路，到前墙时"右边通就右转，否则左转"，用右测距推出左侧；仿真里比赛赛道 20/20 完赛。
  通用迷宫模式（拨码 2 ON）：比赛时这一版会拒绝发车；**赛后**补上了缺左测距时的退路——改用右手法则贴右墙走，
  左边一律当"可能通"去试，仍然用"三面空旷 1 秒"判断出了迷宫（仿真：6×6 随机迷宫无环路 40/40，有环路 38/40，失败的都是超时停车）。
- **陀螺仪**：实装芯片是 MPU6500（WHO_AM_I = 0x70），寄存器用法与 MPU6050 相同，固件两种都认。
  插座接触不良会让它中途掉线，所以固件会持续检查；一旦掉线，自动改用左右编码器的里程差推算航向，车不会因此打转。
- **离开迷宫停车**：比赛赛道共 14 个弯，转完第 14 个弯再走 350 mm 停车（`brain.cpp` 里的 `stop_turns` / `exit_run_mm`）。
- 装车时遇到的硬件问题、诊断过程和结论，记录在 `docs/硬件笔记.md` 的"装车调试记录"一节。

复现检查（不需要硬件）：

```bash
# 都在仓库根目录运行
pio run -e car                                                                         # 固件编译
(cd maze-sim && python3 sim.py --maze track_2026.txt --race --no-anim --png race.png)  # 比赛赛道仿真，应打印"完赛"
(cd firmware/board && python3 layout.py)                                               # 布线自检，异网交叉应为 0
python3 cad/check.py                                                                   # 整车尺寸链自检，应全部 PASS
```

仿真器需要 `numpy` 和 `matplotlib`；不加 `--png` 会弹出动画窗口。

## 协作约定

三方在改这个仓库：写代码的、焊车的，还有 Claude。

- **开工前 `git pull`，改完马上 `git commit` + `git push`。**别攒一大堆改动，冲突就很少。
- **改了大脑**（`firmware/car/brain.*`）：先跑一遍比赛赛道，还能完赛再提交：
  `cd maze-sim && python3 sim.py --maze track_2026.txt --race --no-anim`
- **改了布线**（`firmware/board/layout.py`）：运行一次 `python3 layout.py`，它会自检并重新生成 `board.html`，两个文件一起提交。
  默认走线锁定在 `firmware/board/route_final.json`（55×37、0 跨线、1.96 m）；只要元件或焊点没变，每次生成结果都一样。
  挪了元件/改了接线后，旧路线会自动失效并重新随机搜索（打印“与当前网络不匹配，改为重新布线”），此时把新结果另存为 route_final.json 即可。
  想换一份路线：`ROUTE_JSON=xxx.json python3 layout.py`（只要 id→path 就能用）。
- **调参数**：先用串口或 WiFi 的 `p 名字 数值` 试，定下来的值写回 `brain.cpp` 的默认参数或 `config.h` 再提交。`save` 存的参数只在那块板子的闪存里，不跟着仓库走，换板子也不会带过去。
- **遥测记录**：`runs/` 不进仓库。哪一次值得分析，就复制到 `logs/` 再提交，Claude 拉下来就能用 `replay_log.py` 重放。
- **比赛前**：`config.h` 里 `TELEMETRY` 改成 0，再烧一次。

## 许可

MIT，见 `LICENSE`。代码大部分是和 Claude（Anthropic 的 AI）一起写的，提交记录里的 Co-Authored-By 标明了这一点。
