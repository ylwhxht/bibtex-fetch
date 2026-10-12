# 期刊与会议缩写

[返回首页](../README.md)

导出时勾选 **使用期刊／会议缩写**，或在 CLI 中传入 `--abbreviate`。处理 `journal`、`journaltitle` 和 `booktitle`，并只对下表中会议名匹配的 `inproceedings`／`conference` 删除重复 `publisher`。书籍、章节、技术报告、未知会议及 `SAE Technical Paper Series` 保留出版社。作者、题名、年份、月份和页码保留，不改动下载原文。所有合并导出自动执行 [LaTeX 兼容处理](LATEX.md)。

## 匹配方式

先匹配内置键、缩写文本和明确的全称／别名。会议名称允许列表内的年份、届次、Proceedings 前缀、首尾会议缩写等形式，包括首尾重复的缩写。例如长 ICASSP 名称输出 `Proc. IEEE Int. Conf. Acoust., Speech Signal Process. (ICASSP)`；IROS 输出 `Proc. IEEE/RSJ Int. Conf. Intell. Robots Syst. (IROS)`。所有映射都是确定规则，不做模糊相似度匹配。

主会与 Workshop 分别匹配。例如 CVPR 和 CVPRW、ICCV 和 ICCVW 不互换。未知、联合会议或额外包含未列出词语的名称保留原样。

会议采用规范词语缩写并保留会议简称，见下表。`VTC2022-Spring` 等形式保留年份及春秋季标识；ECCV Workshops 单独匹配。少数明确列出的来源拼写变体（如 `Procedings` 和 ICCVW 的单数 `Workshop`）也可匹配。

输出使用带花括号的文本：

```bibtex
booktitle = {Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. (CVPR)},
journal = {IEEE Trans. Pattern Anal. Mach. Intell.},
```

这两行是格式示意，不是抓取结果。合并文件不需要另外加载字符串宏。完整包中的 `abbreviations.bib` 和界面“查看缩写表”提供参考定义。

## 重复定义约定

缩写来自明确的名称表；2.1.2 根据用户指定标准更新会议写法及两种期刊拼写，旧的简称仍作为别名识别。重复键采用唯一有效定义：

- `TOG` 最终为 `ACM TOG`，同时识别旧值 `ACM Trans. Graph.`。
- `NIPS` 对应 `Adv. Neural Inf. Process. Syst. (NeurIPS)`。
- `TVC` 与 `TVCOMP` 是不同键，两者保留。全称 The Visual Computer / Visual Computer 使用靠后的 `TVCOMP = Vis. Comput.`。
- 原始重复键去重后有 70 个定义；2.0.2 共 72 个，2.0.3 增至 107 个。新增名称使用代码中明确列出的固定输出，不自动推测任意缩写。
- `RAL` 输出 `IEEE Robot. Autom. Lett.`；`TCSVT` 输出 `IEEE Trans. Circuits Syst. Video Technol.`。旧 `IEEE RA-L` 与单数 `Circuit` 拼写仍可识别并修正。

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
| `ACCV` | Proc. Asian Conf. Comput. Vis. (ACCV) |
| `AAAI` | Proc. AAAI Conf. Artif. Intell. (AAAI) |
| `CVPRW` | Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. Workshops (CVPRW) |
| `TCSVT` | IEEE Trans. Circuits Syst. Video Technol. |
| `SPL` | IEEE Sign. Process. Letters |
| `VR` | Vis. Res. |
| `JOV` | J. Vis. |
| `TVC` | The Vis. Comput. |
| `JCST` | J. Comput. Sci. Tech. |
| `CGF` | Comput. Graph. Forum |
| `CVM` | Computational Visual Media |
| `SPM` | IEEE Signal Process. Mag. |
| `CVPR` | Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. (CVPR) |
| `ICCV` | Proc. IEEE/CVF Int. Conf. Comput. Vis. (ICCV) |
| `ECCV` | Proc. Eur. Conf. Comput. Vis. (ECCV) |
| `NIPS` | Adv. Neural Inf. Process. Syst. (NeurIPS) |
| `ICPR` | Proc. Int. Conf. Pattern Recognit. (ICPR) |
| `BMVC` | Proc. Brit. Mach. Vis. Conf. (BMVC) |
| `ACMMM` | Proc. ACM Int. Conf. Multimedia (ACM MM) |
| `ICME` | Proc. IEEE Int. Conf. Multimedia Expo (ICME) |
| `ICASSP` | Proc. IEEE Int. Conf. Acoust., Speech Signal Process. (ICASSP) |
| `ICIP` | Proc. IEEE Int. Conf. Image Process. (ICIP) |
| `ICLR` | Int. Conf. Learn. Represent. (ICLR) |
| `IV` | Proc. IEEE Intell. Veh. Symp. (IV) |
| `ITSC` | Proc. IEEE Int. Conf. Intell. Transp. Syst. (ITSC) |
| `ICPRS` | Proc. Int. Conf. Pattern Recognit. Syst. (ICPRS) |
| `ICVES` | Proc. IEEE Int. Conf. Veh. Electron. Saf. (ICVES) |
| `ICDL` | Proc. IEEE Int. Conf. Develop. Learn. (ICDL) |
| `ICTC` | Proc. Int. Conf. Inf. Commun. Technol. Converg. (ICTC) |
| `ICECET` | Proc. Int. Conf. Electr., Comput. Energy Technol. (ICECET) |
| `NNICE` | Proc. Int. Conf. Neural Netw., Inf. Commun. Eng. (NNICE) |
| `INDIN` | Proc. IEEE Int. Conf. Ind. Informat. (INDIN) |
| `SECON` | Proc. IEEE Int. Conf. Sens., Commun. Netw. (SECON) |
| `ISAS` | Proc. Int. Symp. Auton. Syst. (ISAS) |
| `CCC` | Proc. Chin. Control Conf. (CCC) |
| `RadarConf` | Proc. IEEE Radar Conf. (RadarConf) |
| `VTCSpring` | Proc. IEEE Veh. Technol. Conf. (VTC-Spring) |
| `VTCFall` | Proc. IEEE Veh. Technol. Conf. (VTC-Fall) |
| `ICONIP` | Proc. Int. Conf. Neural Inf. Process. (ICONIP) |
| `ECCVW` | Proc. Eur. Conf. Comput. Vis. Workshops (ECCVW) |
| `GeMiC` | Proc. German Microw. Conf. (GeMiC) |
| `CRV` | Proc. Conf. Comput. Robot Vis. (CRV) |
| `MCSoC` | Proc. IEEE Int. Symp. Embedded Multicore/Many-core Syst.-on-Chip (MCSoC) |
| `ICCRI` | Proc. Int. Conf. Control, Robot. Informat. (ICCRI) |
| `ROBIO` | Proc. IEEE Int. Conf. Robot. Biomimetics (ROBIO) |
| `VCIP` | Proc. IEEE Int. Conf. Vis. Commun. Image Process. (VCIP) |
| `CSCWD` | Proc. Int. Conf. Comput. Supported Cooperative Work Design (CSCWD) |
| `IECON` | Proc. Annu. Conf. IEEE Ind. Electron. Soc. (IECON) |
| `ICAUS` | Proc. Int. Conf. Auton. Unmanned Syst. (ICAUS) |
| `ECSA` | Proc. Int. Electron. Conf. Sensors Appl. (ECSA) |
| `CoRL` | Proc. Conf. Robot Learn. (CoRL) |
| `EuRAD` | Proc. Eur. Radar Conf. (EuRAD) |
| `IROS` | Proc. IEEE/RSJ Int. Conf. Intell. Robots Syst. (IROS) |
| `ICRA` | Proc. IEEE Int. Conf. Robot. Autom. (ICRA) |
| `IJCAI` | Proc. Int. Joint Conf. Artif. Intell. (IJCAI) |
| `PR` | Pattern Recognit. |
| `ACCESS` | IEEE Access |
| `RAL` | IEEE Robot. Autom. Lett. |
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
| `WACV` | Proc. IEEE/CVF Winter Conf. Appl. Comput. Vis. (WACV) |
| `EDGE` | Proc. ACM/IEEE Symp. Edge Comput. (EDGE) |
| `ICCVW` | Proc. IEEE/CVF Int. Conf. Comput. Vis. Workshops (ICCVW) |
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
| `TNNLS` | IEEE Trans. Neural Netw. Learn. Syst. |
| `ESWA` | Expert Syst. Appl. |
| `NN` | Neural Netw. |
| `ISPRSARCH` | ISPRS Archives |
| `AIReview` | Artif. Intell. Rev. |
| `IJPEM` | Int. J. Precis. Eng. Manuf. |

## 添加或修改缩写

编辑 `bibclean/abbreviations.py` 中的 `VENUES`，每条结构为：

```python
("KEY", "Output abbreviation", ["Exact full name", "Another known alias"])
```

新增会议时还需在 `CONFERENCE_TITLES` 明确写出规范会议名，该表同时限定可删除出版社的会议范围。不要重复定义键，也不要用宽泛子串匹配替代明确别名。为容易混淆的主会／Workshop、相近刊名增加正反两类测试，然后运行：

```shell
uv run --frozen pytest tests/test_formatting.py -q
```

通过缩写表生成的字符串定义由 `string_definitions()` 提供，界面和导出使用同一函数。
