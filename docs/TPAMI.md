# TPAMI 精简格式

在导出选项勾选 **TPAMI 精简格式**，即可对当前任务重新预览或导出，无需再次抓取。默认关闭；关闭后恢复普通 URL、缩写选项的原选择。此预设优先于这两个选项，不改变保留未抓取条目和引用键的设置。

这是依据 IEEE 参考文献写法制作的确定性格式预设，适用于配合 TPAMI 提供的 IEEE 模板使用。它不核验论文真实性、不补造缺失字段，也不承诺仅靠 `.bib` 就能满足整篇稿件的投稿要求。作者姓名首字母、标点、斜体和最终布局由所用 `.bst`／模板决定；建议沿用期刊模板中的参考文献样式。

## 精简规则

| 内容 | 开启后的处理 |
| --- | --- |
| 期刊／会议名称 | 使用固定词语缩写表，如 `IEEE Trans. Pattern Anal. Mach. Intell.`、`Proc. IEEE/CVF Int. Conf. Comput. Vis.`；不采用单独 `ICCV` 作为规范模式的会议名 |
| 会议名称中的重复信息 | 不重复年份或括号内简称；保留 `year` 字段及会议／Workshop、VTC 春秋季的区别 |
| IEEE/CVF 等前缀 | CVPR、ICCV 等只保留来源明确提供的 IEEE/CVF 或 IEEE 前缀；纯简称不用于猜测当届主办方 |
| 作者 | 1–6 位全部保留；超过 6 位写为首位作者 `and others`，由 BibTeX 排版为 “et al.”；不拆开花括号中的机构名 |
| 普通会议出版信息 | 省略可选地点 `address`；没有书系、卷号、版本或继承字段时省略 `publisher`、`organization`；书系、卷号、编辑等字段继续保留 |
| 月份 | 仅会议论文已有 DOI 和年份时按带 DOI 的会议格式省略月份；期刊月份、没有 DOI 的会议月份及其他类型日期保留 |
| URL | 已有年份、页码／文章号及出版载体信息的正式期刊／会议记录省略 URL；在线资源、预印本、early access 和不完整出版记录继续保留 URL |
| 其他信息 | 标题、年份、卷期、页码、文章号、DOI、eprint、注释和未列入精简规则的字段继续保留 |
| 未识别名称／缺失信息 | 原样保留，列入完整包的 `manual-review.md`，由用户自行调整 |

例如，来源提供 `2021 IEEE/CVF International Conference on Computer Vision (ICCV)` 时，规范模式使用 `Proc. IEEE/CVF Int. Conf. Comput. Vis.`。与普通缩写模式的 `{ICCV}` 相互独立；普通模式仍沿用用户原有缩写表。这里通过去掉重复信息、精简作者和可省略字段减少篇幅，不以删除必要信息来保证特定页数。

所有处理仍经过 LaTeX 兼容流程。规范模式只改 `merged.bib`、`downloaded.bib` 和预览副本，`original.bib`、`entries/`、HTTP 响应和抓取日志保留原文。每个字段的修改记入 `formatting.json`；其中 `manual_review` 表示未修改、需要人工处理的项目。关闭模式后可重新导出完整字段。

## 命令行与 API

```shell
uv run --frozen --no-dev bibtex-fetch-cli references.bib -o output/tpami --tpami-minimal
```

已有任务可以直接调用：

```text
GET /api/jobs/{job_id}/export?format=bib&tpami_minimal=true
GET /api/jobs/{job_id}/export?format=zip&tpami_minimal=true
```

`tpami_minimal=true` 优先于 `include_url`、`abbreviate`；即使同时设置 `include_url=false`，需要保留的在线链接也不会被删除。设为 `false` 恢复普通选项，省略参数则使用任务设置，旧任务默认 `false`。完整包的 `manual-review.md` 可用于人工精修，程序不会改写用户的参考文献文件。

## 规则依据与边界

依据 [IEEE Reference Guide](https://journals.ieeeauthorcenter.ieee.org/wp-content/uploads/sites/7/IEEE_Reference_Guide.pdf)（于 2026-10-13 读取官方入口指向的现行文档）的以下章节：

- “General Guidelines”：至多 6 位作者全部列出，超过 6 位列首位加 et al.；姓名使用首字母；保留实际存在的期刊卷期／月份信息。
- “Conferences and Conference Proceedings”：会议名使用词语缩写；地点可选；普通会议与带 DOI 的会议基本格式分别决定日期处理。
- “Periodicals” 及在线资源章节：期刊保留卷期、页码／文章号和出版日期；在线资源保留定位信息。
- “Useful Abbreviations in References”：常用词语的缩写原则。项目采用可审查的固定映射，不用语言模型生成名称或元数据。

来源缺失卷期、作者已被上游截断、模板不显示 DOI／eprint、名称未匹配等情况仍需人工处理。程序不会为了消除提示而填造数据。`manual-review.md` 仅列当前规则能识别的格式缺口，并非完整投稿核验报告。
