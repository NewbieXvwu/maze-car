# 原理图生成脚本（maze-car）

原理图不是手工拖出来的，而是按 `firmware/board/netlist.md` 由脚本生成，改网表后重跑即可。

## 文件

| 文件 | 作用 |
|---|---|
| `gen_symbols.py` | 12 个模块的左/右列引脚与网络定义 → 生成 `specs/<NAME>.json` 与 `specs/manifest.json` |
| `build_lib.py` | 单模块：在工程库建符号 → 灌几何 → 建设备，结果写回 `lib_built.json` |
| `rebuild_all.py` | 批量：删旧符号/器件后重建 12 套，输出 `lib_built.json`（name→uuid） |
| `place.py` | 按 LAYOUT 坐标放 12 个器件并逐脚 `sch connect` 打网络名标签，输出 `placed.json` |
| `netverify.json` | 期望 vs 实际 的引脚→网络全量对照（核对用） |

## 重跑顺序

```bash
python3 gen_symbols.py      # 改过 netlist.md 就先跑这个
python3 rebuild_all.py      # 重建工程库里的符号与器件
easyeda sch clear --doc P1 --project maze-car
python3 place.py            # 放置 + 79 根桩线 + 网络标签
easyeda sch read --doc P1 --project maze-car   # 逐脚核对
```

## 注意

- 工程库令牌：`lib symbol build` / `lib_Device.create` 要传**工程 UUID**
  （`0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e`），
  而 `lib symbol create --scope project` 和各类 `search` 用字符串 `"project"`。
- `lib device create` 报 `[object Object]` 失败时器件通常已建好，先 `lib_Device.search` 复核，别重试。
- 12 个模块目前**只有符号、没有封装**，`sch drc` 会对每个器件报一条 `MISSFOOTPRINT`——
  这是预期的中间态；做 PCB 前要按实测排针顺序建 footprint。
- 引脚编号用信号名（`IO4`、`1'`、`IN+`），不是 1..N：实物排针顺序未实测时不假装知道位置。

---

# PCB 生成脚本

板子同样按 `迷宫小车主板布线.html`（手焊布线图，35×34 格，1 格 = 2.54mm）生成，
1 格 = 100 mil，板框 3600×3500 mil ≈ 91.4×88.9mm，2 层，R120 圆角。

## 文件

| 文件 | 作用 |
|---|---|
| `gen_footprints.py` | 解析 HTML 的 `const D`，按模块物理针脚 1..N 建封装 + 器件（`pcb_plan.json`） |
| `route_via.py` | **当前方案**：清空 → 每个针脚打一个 via（1.0mm 孔 / 1.66mm 环）→ 按 44 根线走 134 段铜 |
| `mask_open.py` | 给每个孔在阻焊层（5/6）画实心多边形开窗 —— 不开窗的话孔环被绿油盖住，排针焊不上 |
| `silk_pcb.py` | 每个模块上方写中文名 + 位号，板边写标题 |
| `outline_devices.py` | 建 12 个"纯丝印封装"（只有框线、无焊盘）+ 器件 |
| `place_outline.py` | 把 12 个丝印器件放到模块框位置 |
| `pcb_plan.json` | 每个针脚的全局坐标、网络、所属模块 |
| `outline_devices.json` | 12 个丝印器件的 uuid 与锚点 |

## 重跑顺序

```bash
python3 gen_footprints.py   # 改过布线图才需要
easyeda pcb clear --doc PCB1 --project maze-car
python3 route_via.py        # 112 个孔 + 134 段线
python3 mask_open.py        # 224 个阻焊开窗（正反各 112）
python3 silk_pcb.py         # 丝印文字
python3 outline_devices.py  # 只在工程库还没有丝印器件时跑
python3 place_outline.py    # 12 个模块框
easyeda pcb save --doc PCB1 --project maze-car
```

## 关键坑（都是实测）

- **工程库封装的焊盘写不进钻孔**。`lib footprint build` 的 `pads[].hole` 只接受
  `null` 或 tuple，试过 `["ROUND",1.0]` / `["CIRCLE",1.0]` / `["SLOT",1,1]` 全部让
  build 挂死（`connector did not respond`）并回滚；`layer:1` 落成
  `"layerId":1,"hole":null`，也就是 SMD 焊盘 —— 底层走线永远连不上。
  所以针脚孔全部用 **via** 打（原生镀通孔，双面铜环 + 钻孔）。
- **Gerber 导出要求板上有"可读器件"**：`pcb.export.gerber` 在 0 器件时直接
  `INVALID_STATE: PCB has no readable components`。12 个纯丝印封装就是为此加的。
- 丝印封装里的线要用 `startX/startY/endX/endY`（不是 `x1/y1`），`layer:3` = 顶层丝印。
- 2.54mm 栅格下走线宽度：信号 12 mil、电源 20 mil。25 mil 会让线到相邻孔只剩
  4.9 mil 净空（DRC 要求 ≥6 mil）。
- **过孔默认盖油**。`pcb via` 没有开窗参数；`eda.pcb_PrimitiveVia.modify(...,{solderMaskExpansion:{top,bottom}})`
  改了能回读，但导出的 GTS/GBS 里依然是 0 个开窗（4.1.97 的生成器不认）。
  可行的开窗办法：在阻焊层（5=顶层 6=底层）用 `pcb fill create --points` 画实心多边形，
  它会被当作开窗写进 GTS/GBS（实测 112+112 个）。
- `pcb export-gerber` 的 `--out` **必须是新文件**（已存在会直接报 `--out must be new`，
  不覆盖、也不删旧的），重导出要换名再替换。
- 两个钻孔文件 `Drill_PTH_Through.DRL` 与 `Drill_PTH_Through_Via.DRL` 内容相同（各 112 孔），
  是 4.1.97 把 via 同时写进两份。上传嘉立创若提示重复钻孔，删掉后者再传即可。
- 焊盘号不能重复（`Duplicate pad number`），所以 PCB 侧按物理针脚 1..N 编号；
  `lib device create` 允许符号引脚名与焊盘号不一致（会报 `[object Object]` 但建成了）。

## 当前状态（2026-11-10）

- DRC：clearance / spacing / outline **0 条**；剩 9 条 `No Connection` —— 都是模块的
  **重复电源脚**（ESP 的第二个 3V3、各模块多出来的 GND），模块内部本来就通，不用走线；
  另有 1 条 `Netlist Error`（PCB 按针脚号 1..N、原理图按信号名，且 12 个器件是纯丝印无焊盘）。
- 网表自检：84 个带网络的针脚，全部落在同网络铜皮的端点或线段上（`netverify` 式逐点校验）。
- 阻焊：112 个孔正反各一个开窗（直径 72 mil），排针可以直接插焊。
- 钻孔：112 个 1.0mm 孔。EasyEDA 4.1.97 会把 via 同时写进
  `Drill_PTH_Through.DRL` 和 `Drill_PTH_Through_Via.DRL`，两个文件内容相同（各 112 孔）。
- 导出：`out/gerber/maze-car-gerber.zip`（GTL/GBL/GTO/GBO/GTS/GBS/GKO + 钻孔 + 飞针）。
