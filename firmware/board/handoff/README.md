# 走线优化题目包（给外部模型用）

这个目录是自包含的：把整个 `handoff/` 文件夹交给对方（或让对方直接在这个目录里干活），
再粘 `PROMPT.md` 的内容就行。

| 文件 | 说明 |
| --- | --- |
| `PROMPT.md` | **要粘贴的提示词** |
| `problem.json` | 题目：55×37 板、禁布区、112 个焊点坐标、33 根线的必经焊点、评分规则 |
| `candidate.json` | 当前方案（基线），对方在这个基础上改 |
| `holecheck.py` | 校验器：`python3 holecheck.py candidate.json --png check.png` |
| `export_problem.py` | 重新从 layout.py 导出 problem.json + candidate.json（改布局时才用） |

基线：15 处跨线、2.26 m。合规标准：holecheck 报 `错误 0 条`。

对方只要产出新的 `candidate.json`，拿回来运行：

```bash
cd firmware/board && ROUTE_JSON=/path/to/new_candidate.json python3 layout.py
```

就会重算 HTML（两个 board.html 一起更新）。注意 `ROUTE_JSON` 的格式是 `{"wires":[{"id":..,"path":[[x,y],...]}]}`，
和 `candidate.json` 完全一样。

## 外部模型的结果（已采纳）

`candidate.json`（Nov 11 21:17）是外部模型交的版本：**0 处跨线 / 1.96 m**（基线是 23 处 / 2.15 m）。
它的走法和本项目布线器不同：线基本沿孔中心走直线，有 504 处从**空孔**上压过（空孔没有接任何东西，不短路），
但经独立复核：没有压到任何别人的焊点、没有进禁布区、没有出界、每条线都按顺序经过全部焊点。

`holecheck.py` 已按这个口径调整：压到「别人的焊点」才是错误，从空孔上压过只记提示。

## 冻结成正式版

`../route_final.json` 是这版的冻结副本（33 根线的 id→path，附焊点坐标用于校验）。
`layout.py` 默认就读它，所以直接 `python3 layout.py` 生成的就是 0 跨线 / 1.96 m 这版；
元件或接线一变，校验不通过就会打印“与当前网络不匹配，改为重新布线”，不会悄悄用旧路线。
