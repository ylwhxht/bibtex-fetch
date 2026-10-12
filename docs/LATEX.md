# LaTeX 兼容导出

从 2.0.1 起，抓取 → 合并 → 导出的默认流程自动处理 BibTeX／LaTeX 语法兼容。网页预览、合并 `.bib` 下载、ZIP 中的 `merged.bib` 和 CLI 导出共用实现。无需勾选新选项、重新抓取或手动修复字段。

## 自动处理规则

| 来源写法 | 合并导出写法 | 作用 |
| --- | --- | --- |
| `month = June` / `July` / `Sept` | `month = {June}` / `{July}` / `{September}` | 消除未定义的月份宏 |
| `author = {Example, Álvaro}` | `author = {Example, {\'A}lvaro}` | 保护重音首字母，避免传统 BibTeX 生成无效 UTF-8 字节 |
| `title = {File_supp1.pdf}` | `title = {File\_supp1.pdf}` | 避免普通文本下划线触发数学模式 |
| 文本中的 `&`、`%`、`#` | `\&`、`\%`、`\#` | 避免对齐符、注释符或参数符干扰排版 |
| `pages = {1–9}` | `pages = {1--9}` | 使用 TeX 的页码连接号 |

标准 `jan`／`jun` 等月份宏保持原样；来源内显式定义的同名 `@String` 优先保留。文本字段中的已知 Unicode 字母与符号按固定映射转成 TeX，重音命令带保护括号。Unicode 引号、短横线和不换行空格转为相应 TeX 写法。未配对的 `$` 按字面量转义，普通文本的 `^` 转为文本符号。

已有转义、分组括号、成对的 `$...$`／`$$...$$`／`\(...\)`／`\[...\]`、`\ensuremath{...}` 和 URL 命令中的地址参数保留。BibTeX 的 `#` 字符串拼接结构保留，字符串内的普通 `#` 才转义。URL、DOI、eprint 和交叉引用等标识字段保持字面值，URL 勾选项仍只决定是否删除整个 `url` 字段。

这些语法操作不补写标题、作者、年份，也不检查文章是否检索正确。下述三个指定发表版本采用用户明确给出的字段，不由语法规则推断。代码不调用 AI。

## 来源条目类型兼容

导出对可由现有字段确定的类型问题应用固定规则：

- 从 2.1.2 起，`inbook`／`incollection` 保留章节类型及出版社，不再仅凭会议名称自动改为会议论文。
- `article` 缺少 `journal`、`journaltitle`、`booktitle`、`crossref` 和 `xdata`，且已有明确的 TechRxiv DOI、SSRN DOI 或 arXiv DOI／编号／链接时，改为 `misc`。不添加虚构的期刊字段。

其他缺字段的记录保留原样，需由使用者决定如何补充。工具不截断作者，也不删除月份、卷期、页码和年份。开启缩写时，只有 `inproceedings`／`conference` 且会议名匹配[清单](ABBREVIATIONS.md)的条目删除重复 `publisher`。书籍、章节、技术报告、未知会议及 `SAE Technical Paper Series` 保留出版社。来源差异、作者显示数量以及模板控制的页数需要手动决定。

## 三个明确指定的正式会议版本

仅当**原始引用键与完整题名同时匹配**时应用下表；不会据题名相似度自动升级其他预印本。保留引用键、题名、作者、eprint 和其他未列出的字段，类型设为 `inproceedings`。字段来自用户明确提供的发表信息；导出过程不发起新的核验请求。

| 引用键 | booktitle | 指定字段 | 来源 |
| --- | --- | --- | --- |
| `segment_anything` | Proc. IEEE/CVF Int. Conf. Comput. Vis. (ICCV) | year=2023, month=October, pages=4015--4026 | [SAM](https://openaccess.thecvf.com/content/ICCV2023/html/Kirillov_Segment_Anything_ICCV_2023_paper.html) |
| `li2023logonet` | Proc. IEEE/CVF Conf. Comput. Vis. Pattern Recognit. (CVPR) | year=2023, month=June, pages=17524--17534 | [LoGoNet](https://openaccess.thecvf.com/content/CVPR2023/html/Li_LoGoNet_Towards_Accurate_3D_Object_Detection_With_Local-to-Global_Cross-Modal_Fusion_CVPR_2023_paper.html) |
| `tent` | Int. Conf. Learn. Represent. (ICLR) | year=2021；不添加页码 | [TENT](https://openreview.net/pdf?id=uXl3bZLkr3c) |

这些条目不再额外增加 arXiv `note`，旧导出中仅含 arXiv 编号的 `note`／`howpublished` 会移除，其他实质备注保留。修改及来源链接记录在 `formatting.json` 的 `published_version` 中。键相同但题名不同则保持现有字段，并列入 `formatting-review.md`。规则见 [publication_versions.py](../bibclean/publication_versions.py)。

## arXiv 标识与编号显示

从 2.1.2 起，已有明确 arXiv 编号的条目自动兼容传统 BibTeX 样式。IEEEtran、IEEEtranN、plain 和 abbrv 不读取 `eprint`／`archivePrefix`，所以仅保留这些字段不能保证参考文献中显示编号。

程序从明确的 `archivePrefix=arXiv`／`eprinttype=arxiv` 与 `eprint`、arXiv DOI、arxiv.org 链接或带 `arXiv:` 标签的字段中提取已有编号，添加 `note = {{arXiv}:2401.00001}`。已有备注通过 BibTeX 字符串拼接保留。如果可显示字段已含同一标识与编号，不重复添加。版本号和旧式编号同样保留。原 `eprint` 不删除；双层花括号用于保护 arXiv 大小写。

此处理与 URL／缩写开关无关：**关闭 URL、开启缩写，仍会显示 `arXiv:编号`**。已有期刊名和条目类型不会被 arXiv 链接覆盖；原 `eprint`、`archivePrefix`、DOI 等字段继续保留。这里复制的是来源已有的编号，不生成新的文献信息。

裸 `eprint` 数字而没有 arXiv 来源标识时不猜测仓库；声明为 arXiv 但编号缺失、编号互相冲突时不选择编号，完整包附 `formatting-review.md` 供手动处理。最终排版仍由文档的 `.bst` 决定；上述自动显示面向传统 BibTeX，使用其他样式时应检查其字段显示规则。

## 原文与修改记录

- `merged.bib`：用于导入 LaTeX 的合并结果。
- `entries/*.bib`、`responses/*.txt`：抓取原文，保持不变，便于查看真实来源。
- `formatting.json`：每处修改的字段、行号、引用键、修改前值与修改后值；语法兼容为 `latex_compatibility`，类型修正为 `entry_type`，arXiv 显示为 `arxiv_display`；后两者另含触发原因。`manual_review` 表示编号需手动处理。
- `process.jsonl`：原有真实抓取记录，导出格式处理不会伪造新的网络请求。

URL 和缩写的四种组合都会经过兼容处理。重复导出不会叠加转义。

## 已经下载旧版文件

1. 更新程序、重启服务并刷新网页，从历史记录打开已完成任务。仅刷新页面不会让运行中的 Python 服务加载新代码。
2. 直接重新下载“合并 BibTeX”，不必重新检索。
3. 用新文件替换 LaTeX 项目的 `.bib`，保持 `\bibliography{...}` 引用的文件名一致。
4. 从头重新编译，让旧 `.aux`、`.bbl`、`.blg` 重新生成。不要手动修补生成的 `.bbl`。

本地典型编译顺序为 `pdflatex main` → `bibtex main` → `pdflatex main` → `pdflatex main`。

## 模板依赖与回归测试

工具不会猜测未知 Unicode 字符或外部自定义宏的含义；例如中文仍由文档的字体／编译引擎支持，来源中的自定义命令仍需要模板定义。保留 URL 时，模板需要提供其参考文献样式要求的 `url` 或 `hyperref` 支持。格式处理不能替代任意模板的宏包配置。

测试使用明确标注的合成 HTTP 响应，覆盖抓取、GUI API、ZIP、CLI、原文保持和幂等性。装有 TeX 时，还会实际编译 `plain`、`abbrv`、`IEEEtran`、`IEEEtranN`，检查 `.blg` 无 BibTeX 警告、`.bbl` 中存在 arXiv 标识和编号；另覆盖预印本类型、三个指定会议版本与出版社保留边界。编译顺序为 LaTeX → BibTeX → LaTeX → LaTeX。详见[开发文档](DEVELOPMENT.md)。这些编译回归不涉及文献真实性核验。

实现参考：[pylatexenc 2.10 编码与括号保护选项](https://pylatexenc.readthedocs.io/en/v2.10/latexencode/)。

样式字段参考：[IEEEtran BibTeX 官方说明](https://tug.ctan.org/macros/latex/contrib/IEEEtran/bibtex/IEEEtran_bst_HOWTO.pdf)。
