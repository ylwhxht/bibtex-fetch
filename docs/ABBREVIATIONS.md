# 期刊与会议缩写

[返回首页](../README.md)

导出时勾选 **使用期刊／会议缩写**，或在 CLI 中传入 `--abbreviate`。缩写功能只处理 `journal`、`journaltitle` 和 `booktitle`，不改动下载原文。所有合并导出还会自动执行 [LaTeX 兼容处理](LATEX.md)。

## 匹配方式

先匹配内置键、缩写文本和明确的全称／别名。会议名称还允许列表内的年份、届次、Proceedings 前缀、首尾会议缩写等形式，包括首尾同时重复的缩写。例如 `ICASSP 2025 - 2025 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)` 输出 `ICASSP`；`2022 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS)` 输出 `IROS`。所有映射都是代码中的确定规则，不做模糊相似度匹配。

主会与 Workshop 分别匹配。例如 CVPR 和 CVPRW、ICCV 和 ICCVW 不互换。未知、联合会议或额外包含未列出词语的名称保留原样。

输出使用带花括号的文本：

```bibtex
booktitle = {CVPR},
journal = {IEEE Trans. Pattern Anal. Mach. Intell.},
```

这两行是格式示意，不是抓取结果。合并文件不需要另外加载字符串宏。完整包中的 `abbreviations.bib` 和界面“查看缩写表”提供参考定义。

## 重复定义约定

缩写来自项目最初提供的名称表，拼写按该表保留，不按其他出版样式自动修订。重复键采用最后一个定义：

- `TOG` 最终为 `ACM TOG`，同时识别旧值 `ACM Trans. Graph.`。
- `NIPS` 对应 `NeurIPS`。
- `TVC` 与 `TVCOMP` 是不同键，两者保留。全称 The Visual Computer / Visual Computer 使用靠后的 `TVCOMP = Vis. Comput.`。
- 原始重复键去重后有 70 个定义；2.0.2 增加 IROS、ICRA 后共 72 个。
- `TCSVT`、`SPL` 等保持最初提供的缩写拼写。

## 完整表

此表对应 [abbreviations.py](../bibclean/abbreviations.py) 中的 `VENUES`；增加映射时同步更新文档。

| 键 | 输出文本 |
| --- | --- |
| `TPAMI` | IEEE Trans. Pattern Anal. Mach. Intell. |
| `IJCV` | Int. J. Comput. Vis. |
| `TOG` | ACM TOG |
| `TIP` | IEEE Trans. Image Process. |
| `TVCG` | IEEE Trans. Vis. Comput. Graph. |
| `TMM` | IEEE Trans. Multimedia |
| `ACCV` | ACCV |
| `AAAI` | AAAI |
| `CVPRW` | CVPRW |
| `TCSVT` | IEEE Trans. Circuit Syst. Video Technol. |
| `SPL` | IEEE Sign. Process. Letters |
| `VR` | Vis. Res. |
| `JOV` | J. Vis. |
| `TVC` | The Vis. Comput. |
| `JCST` | J. Comput. Sci. Tech. |
| `CGF` | Comput. Graph. Forum |
| `CVM` | Computational Visual Media |
| `SPM` | IEEE Signal Process. Mag. |
| `CVPR` | CVPR |
| `ICCV` | ICCV |
| `ECCV` | ECCV |
| `NIPS` | NeurIPS |
| `ICPR` | ICPR |
| `BMVC` | BMVC |
| `ACMMM` | ACM MM |
| `ICME` | ICME |
| `ICASSP` | ICASSP |
| `ICIP` | ICIP |
| `ICLR` | ICLR |
| `IROS` | IROS |
| `ICRA` | ICRA |
| `IJCAI` | IJCAI |
| `PR` | Pattern Recognit. |
| `ACCESS` | IEEE Access |
| `RAL` | IEEE RA-L |
| `SENSJ` | IEEE Sensors J. |
| `TII` | IEEE Trans. Ind. Informat. |
| `TIM` | IEEE Trans. Instrum. Meas. |
| `TVT` | IEEE Trans. Veh. Technol. |
| `IF` | Inf. Fusion |
| `JMS` | J. Manuf. Syst. |
| `MEAS` | Measurement |
| `SIGPRO` | Signal Process. |
| `PRL` | Pattern Recognit. Lett. |
| `APOPT` | Appl. Opt. |
| `OE` | Opt. Eng. |
| `TVCOMP` | Vis. Comput. |
| `SENSORS` | Sensors |
| `REMOTES` | Remote Sens. |
| `DISPLAYS` | Displays |
| `ELECTRON` | Electronics |
| `APPSCI` | Appl. Sci. |
| `WACV` | WACV |
| `EDGE` | ACM/IEEE Symp. Edge Comput. |
| `ICCVW` | ICCVW |
| `TITS` | IEEE Trans. Intell. Transp. Syst. |
| `TIV` | IEEE Trans. Intell. Veh. |
| `JIMG` | J. Imaging |
| `JCHEMED` | J. Chem. Educ. |
| `MTA` | Multimedia Tools Appl. |
| `OPTCOMM` | Opt. Commun. |
| `OER` | Opto-Electron. Rev. |
| `PEERJCS` | PeerJ Comput. Sci. |
| `PIMECHD` | Proc. Inst. Mech. Eng., Part D: J. Automob. Eng. |
| `SCIDATA` | Sci. Data |
| `NATCOMM` | Nat. Commun. |
| `IJRR` | Int. J. Robot. Res. |
| `ISPRS` | ISPRS J. Photogramm. Remote Sens. |
| `VTM` | IEEE Veh. Technol. Mag. |
| `IJAT` | Int. J. Automot. Technol. |
| `ARS` | Adv. Radio Sci. |
| `JCD` | J. Control Decis. |

## 添加或修改缩写

编辑 `bibclean/abbreviations.py` 中的 `VENUES`，每条结构为：

```python
("KEY", "Output abbreviation", ["Exact full name", "Another known alias"])
```

新增会议时还需将键加入 `CONFERENCES`。不要重复定义键，也不要用宽泛子串匹配替代明确别名。为容易混淆的主会／Workshop、相近刊名增加正反两类测试，然后运行：

```shell
uv run --frozen pytest tests/test_formatting.py -q
```

通过缩写表生成的字符串定义由 `string_definitions()` 提供，界面和导出使用同一函数。
