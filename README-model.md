# 迷宫小车 · 1:1 数字模型

按 `ref/` 里 10 张实车照片重建的可交互三维模型，附在线查看网页与可直接导入建模软件的模型文件。

## 交付物

| 文件 | 说明 |
| --- | --- |
| `out/model/maze-car.glb` | glTF 2.0 二进制，**米制、Y 轴向上**（标准 glTF 朝向），含 18 张内嵌贴图，Blender / C4D / Maya / Unity / Unreal / three.js 直接拖入 |
| `out/model/maze-car.obj` | Wavefront OBJ，**毫米制、Z 轴向上**（CAD 习惯），逆向/打印软件用 |
| `out/model/maze-car.stl` | 二进制 STL，**毫米制、Z 轴向上**，3D 打印切片用 |
| `viewer/index.html` | 在线查看页（three.js r180），支持轨道旋转、八个预设视角、部件聚焦、线框、参考照片对照、一键导出 |

模型规模：1005 个图元 / 5.35 万三角面 / 157 种材质 / 19 张内嵌贴图（含洞洞板凹凸贴图）。文件：GLB 51.3 MB、OBJ 135 MB、STL 14.4 MB。

## 打开网页

```bash
cd maze-car
python3 -m http.server 8123
# 浏览器打开 http://localhost:8123/viewer/
```

> 必须用 http 打开（ES module + 贴图需要同源），直接双击 html 不行。

页面功能：左侧尺寸卡、右侧视角与部件列表、底部导出与参考照片。
测试钩子（控制台可用）：`__setView('hero'|'front'|'left'|'right'|'top'|'rear'|'bottom'|'pcb'|'pcbzoom'|'iso'|'p03'|'p02'|'p10')`、`__focus('pcb')`、`__export('glb')`、`__ortho(az,el,size)`。

## 尺寸与坐标系

模型单位毫米，Z 向上，**+X 为车头**（前墙 / 前向激光测距方向），+Y 为车左，地面 z=0。

| 部件 | 尺寸 / 位置 |
| --- | --- |
| 底盘洞洞板 | 140 × 94 × 2.5，顶面 z=13 |
| 前墙洞洞板 | 94 宽 × 52 高，x 49–51.5，z 9.5–61.5（比主控板顶高约 21 mm），顶端 6 针 VL53L0X 朝前 |
| 主控 PCB | 91.44 × 88.9 × 1.6，顶面 z=40，前缘 x=49（4 根尼龙柱架在底板上） |
| 驱动轮 | Ø42 × 22，中心 x=22、y=±58.5、z=21，白色 3D 打印轮毂 + 黄铜轴套 |
| 万向球轮 | 2 个，x=+38 与 x=−58，y=0 |
| 18650 电池组 | 77 × 42 × 20，x=+2，z=13–33，两条白胶带 |
| 整车 | 140 × 144 mm，板件高约 78 mm，含拱起排线约 120 mm |

## 还原清单（对照照片逐项建模）

- **底盘**：绿色洞洞板，2.54 mm 孔阵 + 金色焊环、底面焊点/跳线/长排针、A–Z 行号印字、白胶带、四角螺丝。
- **前墙**：整块洞洞板，顶沿外侧焊 6 针 VL53L0X（XSHUT/GPIO1/SDA/SCL/GND/VIN，黑窗朝前），背面 6 针母座 + 彩虹排线插头 + 白胶带，底部两个白色 3D 打印支脚与螺丝。
- **主控 PCB**：满板 2.54 孔阵、白色丝印（U1 ESP32-S3 / U2 TB6612 / U3 MPU6050 / SW1 DIP / SW2 START / BT1 / J1-J2 MOTOR / TOF L-R / 5V REG / IDC1-2，板角 "maze-car PCB 2L 1.0mm hole 2026-11"）。
- **元件**：ESP32-S3-WROOM-1（N8R2）双 USB-C 开发板 + 金属屏蔽罩 + 2×22 黄色排针；红色 TB6612 模块 2×8 排针；MPU6050 蓝板竖立在右后边缘；0.96″ OLED；Mini-360 降压；蓝色拨码开关；两个黑色 IDC 座；BT1/J1/J2 JST 插头；左右两侧 4 针/6 针 VL53L0X 探出板边。
- **行走机构**：N20 减速电机 + 白色编码器端盖/插座 + 白色 L 形打印支架（跨在底板侧边）、Ø3 轴；轮胎两排错位大块花纹、白色轮毂偏置孔。
- **线束**：两条彩虹排线从车尾 IDC 沿左右两侧拱起（峰值 z≈120，实车最显眼的轮廓）再落到前墙顶，另有传感器 4 线束、两侧电机 4 线、电池红黑线、2 个黑色扎带。

## 已知简化

- 丝印文字按照片可辨内容重排，个别位号间距做了压缩以保证可读。
- 洞洞板底面焊点为程序化分布，非逐孔复刻。
- 排线按实车走向手工布线（3 条主环 + 若干支线），不保证每根线序一致。
- 元件丝印/封装细节按常见模块外形近似。

## 重新生成

```bash
python3 tools/shots.py shots/check --views hero,front,top,pcb,p03   # 多视角截图
python3 tools/export_model.py                                      # 重新导出 glb/obj/stl
python3 tools/verify_glb.py glbcheck                               # 回读 GLB 校验并渲染
```

截图脚本用 Playwright + Chromium(SwiftShader) 无头渲染，`shots/compare_sheet.png` 是照片与模型的四视角对照图。

## 路径追踪渲染（3A 画质尝试）

除了网页实时预览，仓库里还用 Blender Cycles（GPU + OpenImageDenoise）对同一个 GLB 做了物理正确的光追渲染：

```bash
/Applications/Blender.app/Contents/MacOS/Blender -b -P tools/cycles_render.py -- \
  --glb out/model/maze-car.glb --out out/renders --views hero,p03,pcb --samples 180 --res 1600x1200
```

- `out/renders/{hero,p03,pcb}.png`：1600×1200，AgX 色调映射，三点柔光 + 渐变背景 + 无限地面。
- `shots/compare_aaa.png`：实拍 vs 渲染 三联对照（前左 3/4、顶板俯视、顶部斜视）。
- `shots/contact_sheet_aaa.png`：三视角渲染总览。

**关于"3A 超写实"的诚实说明**：模型是参数化几何（盒体/圆柱/车削体）精确到毫米级装配关系与元件位置，材质与纹理是程序化生成的 PBR；它能正确表达结构、尺寸和配色，但细部（螺钉、端子、线芯、焊点）是示意级，达不到影视/3A 资产那种手工雕刻 + 扫描贴图的密度。真实感的瓶颈在几何细节与贴图扫描，而不是渲染器。
