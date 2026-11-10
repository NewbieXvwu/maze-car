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
