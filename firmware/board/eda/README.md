# maze-car 原理图 / PCB 生成脚本

原理图和 PCB 都不是手拖出来的，全部由脚本按源数据生成，改源数据重跑即可。

- 原理图源数据：`firmware/board/netlist.md`（27 网络 / 79 引脚 / 12 模块）
- PCB 源数据：`firmware/board/eda/wiring_plan.json`（从用户手焊布线图导出的冻结数据，35×34 格，1 格 = 2.54mm）。
  原始 `迷宫小车主板布线.html`（仓库根，未入库）用 `gen_footprints.load_html()` 也能解析，但以冻结副本为准

## 文件

| 文件 | 作用 |
|---|---|
| `gen_symbols.py` | 12 个模块的左/右列引脚与网络 → `specs/<NAME>.json` + `specs/manifest.json` |
| `build_lib.py` | 单模块：工程库建符号 → 灌几何 → 建设备 |
| `rebuild_all.py` | 批量重建 12 套符号+器件，输出 `lib_built.json`（name→uuid） |
| `place.py` | 按 LAYOUT 放 12 个器件，逐脚 `sch connect` 打网络名标签，输出 `placed.json` |
| `netverify.json` | 期望 vs 实际 的引脚→网络全量对照 |
| `gen_footprints.py` | 解析 HTML，按模块物理针脚 1..N 建封装+器件（`pcb_plan.json`） |
| `board_setup.py` | 板框 3600×3500 R120 + 四角 4 个 M3 安装孔（3.2mm 孔 / 4mm 环）；幂等，已有的不重复加 |
| `route_via.py` | 清空 → 每针脚一个 via（1.0mm 孔 / 1.66mm 环）→ 按 44 根线走 134 段铜 |
| `bridge_nets.py` | 顶层 A* 补 5 根桥接线，把 GND 的 5 块 / 3V3 的 2 块孤岛连成一整片 |
| `mask_open.py` | 每孔在阻焊层（5/6）画实心多边形开窗，否则孔环被绿油盖住焊不上 |
| `silk_pcb.py` | 模块英文名（跟在位号右边）+ 板边标题；改位置只改 `NAMES`/`TITLES` |
| `pin1_label.py` | 每个模块外侧标一个丝印 `1`（BT1 标 `+`/`-`），装配时认方向；字高 60 mil（墨迹约 1.08mm）、笔画 8 mil |
| `outline_devices.py` / `place_outline.py` | 12 个"纯丝印封装"器件（Gerber 导出要求板上有可读器件） |
| `verify_board.py` | **出厂自检**：连通性、间距、几何，只看真实铜 |
| `audit_gerber.py` | **对最终压缩包做独立审计**：不看编辑器，只读 Gerber/钻孔文件 |
| `verify_silk.py` | 丝印自检：40 条文字在板内、无压字、13 个标记都指向各自 1 脚（BT1 的 `-` 指 2 脚） |
| `verify_gerber_nets.py` | **从 Gerber 重建铜层连通性**核对网表（断路/短路都能抓到，做过反向验证）|
| `wiring_plan.json` | 布线图冻结数据（13 个元件、44 根线、35×34 格栅） |
| `pcb_plan.json` | 每针脚的全局坐标、网络、所属模块 |
| `outline_devices.json` | 12 个丝印器件的 uuid 与锚点 |

## 重跑顺序

```bash
# 原理图
python3 gen_symbols.py && python3 rebuild_all.py
easyeda sch clear --doc P1 --project maze-car
python3 place.py
easyeda sch read --doc P1 --project maze-car        # 逐脚核对

# PCB
easyeda pcb clear --doc PCB1 --project maze-car
python3 route_via.py        # 112 孔 + 134 段线
python3 board_setup.py      # 板框 + 四角安装孔（放在 route_via 之后，clear 会清孔）
python3 bridge_nets.py      # 5 根顶层桥接线（先 --dry-run 看路径）
python3 mask_open.py        # 224 个阻焊开窗（正反各 112）
python3 silk_pcb.py         # 丝印文字（模块名 + 位号 + 板边标题）
python3 pin1_label.py       # 12 个模块各标一个「1」（1 脚位置）
python3 place_outline.py    # 12 个模块框
easyeda pcb save --doc PCB1 --project maze-car

# 出厂验证
python3 verify_board.py                                   # 板级连通性/间距
easyeda pcb drc --doc PCB1 --project maze-car              # 官方 DRC
easyeda pcb export-gerber --window <id> --project maze-car \
        --doc fda2ba1555e9ca0d --out <新zip> --unit mm
python3 audit_gerber.py ../../../out/gerber/<新zip>.zip     # 文件级审计
python3 verify_silk.py                                     # 丝印位置 + 标记指向
python3 verify_gerber_nets.py ../../../out/gerber/<新zip>.zip  # 从制造文件反推网表
```

## 关键坑（都是实测）

- **工程库封装的焊盘写不进钻孔**。`lib footprint build` 的 `pads[].hole` 只接受 `null` 或 tuple，
  `["ROUND",1.0]`/`["CIRCLE",1.0]`/`["SLOT",1,1]` 全部让 build 挂死（`connector did not respond`）
  并回滚；`layer:1` 落成 `"layerId":1,"hole":null` = SMD 焊盘，底层走线永远连不上。
  → 针脚孔全部用 **via** 打（原生镀通孔，双面铜环 + 进钻孔表）。
- **过孔默认盖油**。`pcb via` 没有开窗参数；`eda.pcb_PrimitiveVia.modify(...,{solderMaskExpansion})`
  能回读但导出结果不变（4.1.97 的生成器不认）。
  → 在阻焊层用 `pcb fill create --points` 画实心多边形当开窗，实测写进 GTS/GBS。
- Gerber 导出要求板上有"可读器件"，0 器件时直接 `INVALID_STATE: PCB has no readable components`；
  12 个纯丝印封装就是为此加的。丝印封装的线用 `startX/startY/endX/endY`（不是 x1/y1）。
- `pcb export-gerber --out` **必须是新文件**，已存在直接报 `--out must be new`。
- 两个钻孔文件 `Drill_PTH_Through.DRL` / `Drill_PTH_Through_Via.DRL` 内容完全相同（4.1.97 把 via 写进两份）；
  嘉立创只承诺插件孔公差、"过孔盖油"也只管过孔，所以**交付包（`out/gerber/maze-car-gerber.zip`）
  已经删掉 `_Via` 那份**，只留 `Drill_PTH_Through.DRL`。导出脚本重跑后要再删一次。
- 焊盘号不能重复（`Duplicate pad number`），所以 PCB 侧按物理针脚 1..N；`lib device create`
  允许符号引脚名与焊盘号不一致（报 `[object Object]` 但实际建成，用 `lib search` 复核）。
- **丝印会跑到板外**：字符串的 x/y 是左上角锚点，`silk-add` 不校验边界。跑完必须查一遍，
  `pcb.silk.set` 挪回来；重复叠印的字符串用 `eda.pcb_PrimitiveString.delete([ids])` 删。
- `easyeda doc reload` 在本机一直报 `close state identity is unverified`，`pcb save` 之后
  直接以落盘文件和重新导出的 Gerber 为准（`doc reload` 不是必需步骤）。
- `pcb check` 的 `floating-track-island` / `single-layer-via` 告警是**结构性预期**：本板没有元件焊盘，
  所有连接点都是 via，工具按"有没有焊盘锚住"判断，所以每段铜都被报一次。

## 当前状态（2026-11-10，已交付）

- 板框 3600×3500 mil（91.44×88.90mm），2 层，R120 圆角。
  走线离板边最近 90 mil（2.29mm），孔环离板边最近 167 mil。
- 116 个孔：112 个 1.0mm（模块排针，100 mil 栅格）+ 4 个 3.2mm M3 安装孔（四角，离边 250 mil）。
- 150 段铜：底层 130 段、顶层 20 段（原 9 段跨线 + 11 段桥接）；信号 12 mil、电源 20 mil。
- 阻焊：112 个孔正反各一个开窗（12 边形，半径 36 mil → 开窗 1.83mm，比 1.66mm 焊盘大 0.17mm）。
- 丝印：12 个模块英文名（`ESP32-S3`/`TB6612`/`MPU6050`/`DIST L,F,R`/`MOTOR L,R`/`DIP SW`/`START`/`BAT`/`5V REG`）+ 位号 + 13 个方向标记（12 个 `1`，BT1 换成 `+`/`-`）+ 板边标题；
  **不要用中文**：中文字形是 G36 填充多边形，实测笔画 0.074mm，低于嘉立创 0.1mm 下限，成品会糊；英文走 0.1524/0.2032mm 光圈线条字；
  方向标记字高 60 mil（墨迹约 1.08mm）、名称 45 mil、笔画 8/6 mil（0.2032/0.1524mm，嘉立创下限 0.1mm）；全部落在板框内、不压焊盘、不压别家文字。
- DRC：**clearance / spacing / outline / No Connection 全部 0**；只剩 1 条 `Netlist Error`
  （PCB 用裸孔+实铜，原理图按信号名建符号，两套表示必然不等——结构性差异，不影响制板）。
- 独立验证（三道，互不相信）：
  1. `verify_board.py`（读编辑器数据）→ 27 个网络各一整片（无孤岛）、0 短路、最紧间距 7.3 mil、0 孔出界。
  2. `audit_gerber.py`（只读文件）→ GKO 闭合 91.44×88.90、GTL/GBL 各 116 个孔环、GTS/GBS 各 112 个开窗、
     钻孔 112×1.0008mm + 4×3.2004mm、丝印全部落在板内。
  3. `verify_silk.py`（读编辑器丝印）→ 40 条文字全在板内、0 压字、13 个标记（12 个 `1` + BT1 的 `+`/`-`）到各自 1 脚
     98~130 mil、名称都跟位号同一行。
  4. `verify_gerber_nets.py`（从 Gerber + 钻带重建连通图）→ 跨层连接必须钻带里真有孔（116 个全对上，
     缺钻孔的焊盘 0）；27 个网络各自一整片、0 短路、0 个空脚被铜皮碰到。
     反向验证过：人为在某一层断开 2mm，脚本立刻报 `AO1` 被切成两片并给出 FAIL。

- 交付包 `out/gerber/maze-car-gerber.zip`：11 个文件（已删重复的 `_Via` 钻带），
  36876 B，sha256 `925212d7f6a63fb86a888d0986162d7ad329364482d51fea8925a08cce0ea910`。

## 数据与可重跑性

- 所有几何都由脚本按 `wiring_plan.json` + `netlist.md` 生成，仓库里没有手拖出来的图元。
- 重跑顺序见上；`board_setup.py` 幂等，`route_via.py` 会先 `pcb clear`（保板框、清孔和铜）。
- 丝印 `1`/`+`/`-` 由 `pin1_label.py` 自己管理：重跑会先删掉旧的同类标记再加，不会叠印。
- 出厂验证三道互不依赖：编辑器数据（verify_board）、导出文件（audit_gerber）、
  从铜层重建连通图（verify_gerber_nets，带反向验证）。
