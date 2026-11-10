# 迷宫小车

An ESP32-S3 wall-following car for a campus maze race: firmware, a 2D simulator that runs the same control code, and a perfboard wiring generator.

第九届长安大学迷宫智能小车大赛（迷宫组）参赛车：ESP32-S3（YD 板）+ TB6612 + N20 编码器电机 + 3 × VL53L0X + MPU6050。

```
firmware/car/       Arduino 固件。大脑 brain.cpp 也在这里，整个仓库只有这一份
firmware/board/     洞洞板布线：layout.py 自检并生成 board.html（浏览器直接打开）；netlist.md 是画原理图用的对照表
firmware/telemetry.py  电脑端 WiFi 遥测
maze-sim/           仿真器（直接编译 firmware/car/brain.cpp）和真车数据回放
docs/               赛情与决策、硬件笔记、物料清单
```

各部分怎么用，见 `firmware/README.md` 和 `maze-sim/README.md`。

## 协作约定

三方在改这个仓库：写代码的、焊车的，还有 Claude。

- **开工前 `git pull`，改完马上 `git commit` + `git push`。**别攒一大堆改动，冲突就很少。
- **改了大脑**（`firmware/car/brain.*`）：先跑一遍比赛赛道，还能完赛再提交：
  `cd maze-sim && python3 sim.py --maze track_2026.txt --race --no-anim`
- **改了布线**（`firmware/board/layout.py`）：运行一次 `python3 layout.py`，它会自检并重新生成 `board.html`，两个文件一起提交。
- **调参数**：先用串口或 WiFi 的 `p 名字 数值` 试，定下来的值写回 `brain.cpp` 的默认参数或 `config.h` 再提交。`save` 存的参数只在那块板子的闪存里，不跟着仓库走，换板子也不会带过去。
- **遥测记录**：`runs/` 不进仓库。哪一次值得分析，就复制到 `logs/` 再提交，Claude 拉下来就能用 `replay_log.py` 重放。
- **比赛前**：`config.h` 里 `TELEMETRY` 改成 0，再烧一次。

## 许可

MIT，见 `LICENSE`。代码大部分是和 Claude（Anthropic 的 AI）一起写的，提交记录里的 Co-Authored-By 标明了这一点。
