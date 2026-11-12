# 建模进度

## 2026-11-11 夜

- [x] 选定 dsh-cad 插件（自带 OCCT 内核），改进并提 PR #13（选边倒角/圆角 + `cad_edges`）
- [x] 建 `cad/params.json`：唯一尺寸源（nominal / measured / source）
- [x] 文档 `maze-car-assembly`：底板、4 立柱、电机 ×2、轮 ×2、万向轮、电池、主板、板上 10 类元件、测距龙门 + 3 颗测距
- [x] 底板 1:1 孔位图（DXF/SVG）
- [x] 尺寸链 + 重心自检 `cad/check.py`（10 项全 PASS）
- [x] 装配说明 `ASSEMBLY.md`、核对清单 `CHECKLIST.md`
- [x] GB 第一角总装图（A3，主/俯/左+轴测，1:1）：`out/maze-car-drawing.svg` / `.png`
- [ ] 待实测数据回来后重建（`params.json` 的 measured）
- [x] 整车三视图 + 轴测图：`out/render-views.png`（TOP/FRONT/LEFT/ISO）、`out/render-iso.png`（白底带影）
- [x] 把 CAD 工具切成独立 dsh 模式（goal ⑧）：配置已改好（`dsh.profile.bundles` 移除 + `cordis.patch.yml` 加 `cad` 变体），`--dump-config` 校验通过，**待重启验证**
- [x] STEP / STL 导出：`out/maze-car.step`、`out/maze-car.stl`（61 实例）
- [x] 万向轮改到车头（重心 x=+12.7，在后轴后方，若不前移会前栽）

## 2026-11-12 凌晨：改四轮 + 2×18650

- [x] 四轮布局：左右驱动轮 + 车头 x=+58、车尾 x=−58 各 1 只万向轮（后万向轮由前轮镜像）
- [x] 电池改 2×18650 电池盒 77×40×20（含电池 105 g）：底板面层前后只剩 38 mm 放不下，改为骑在两电机顶面（z 26–46），重心正好压在驱动轮轴
- [x] 主板 45→48（电池顶 46，留 2 mm），铜柱 29→32（M3×32）
- [x] `params.json` / `check.py` 同步；17 项全 PASS，重心 x≈+4.0，整备 ≈409 g
- [x] 重出 `out/maze-car.step` / `.stl`（65 体 6186 面）、`out/parts/` 逐件 STL
- [x] 重出 `out/render-views.png` / `out/render-iso.png`、`out/maze-car-drawing.svg/.png`（图号 MC-ASM-02）
- [x] `ASSEMBLY.md` / `CHECKLIST.md` / `MEASURE.md` / `docs/硬件笔记.md` / `docs/赛情与决策.md` 同步
- 备注：`cad_export target=assembly` 导 STL 会漏面（报 6186 面实际写 4162），改用逐体导出再合并；见 `cad/render.py` 与 `out/parts/`

## CAD 模式（goal ⑧）

- `~/.dsh/profiles/web/package.json` 的 `dsh.profile.bundles` 已移除 `dsh-cad`（依赖保留，不卸载）
- `~/.dsh/profiles/web/cordis.patch.yml` 的 `preset-derive` 末尾加了 `cad` 变体（order 7，仅 `dsh-cad` 一个插件）
- 启动日志：`[preset-derive] cad: ok (22 base + 1 extra)`，roster = standard[default], ptc, minimal, cordis, devtools, easyeda, cad
- **默认（standard）模式已确认没有 `cad_*` 工具与右侧面板**；要用建模工具，新开会话选 `CAD` 模式

## 当前模型状态

- 65 个实体、6186 三角面；装配实例 a72–a124、a140–a147、a174–a182
- 底板 140×82×3，四角 M3 孔 (±39.37, ±38.10)
- 四轮：驱动轮 ×2（轮距 90、Ø42、轴心高 21）+ 万向轮 ×2（x=±58，球 Ø12，总高 13）
- 电池盒 77×40×20，z 26–46，骑在两电机顶面
- 主板 z=48（铜柱 M3×32），龙门顶 69，测距镜头 60.5
- 重心 x ≈ +4.0，整备 ≈ 409 g（占位）

## 下一步（等数据）

1. 把 `MEASURE.md` 的六项填进 `params.json`
2. `python3 cad/check.py`
3. 我按新数字重建 + 出图 + 重导 STEP/STL
