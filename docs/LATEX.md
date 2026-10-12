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

这些操作只改变语法表示，不补写标题、作者、年份，也不检查文章是否检索正确。代码不调用 AI。

## 原文与修改记录

- `merged.bib`：用于导入 LaTeX 的合并结果。
- `entries/*.bib`、`responses/*.txt`：抓取原文，保持不变，便于查看真实来源。
- `formatting.json`：每处修改的字段、行号、引用键、修改前值与修改后值；兼容处理动作名为 `latex_compatibility`。
- `process.jsonl`：原有真实抓取记录，导出格式处理不会伪造新的网络请求。

URL 和缩写的四种组合都会经过兼容处理。重复导出不会叠加转义。

## 已经下载旧版文件

1. 更新程序并刷新网页，从历史记录打开已完成任务。
2. 直接重新下载“合并 BibTeX”，不必重新检索。
3. 用新文件替换 LaTeX 项目的 `.bib`，保持 `\bibliography{...}` 引用的文件名一致。
4. 从头重新编译，让旧 `.aux`、`.bbl`、`.blg` 重新生成。不要手动修补生成的 `.bbl`。

本地典型编译顺序为 `pdflatex main` → `bibtex main` → `pdflatex main` → `pdflatex main`。

## 模板依赖与回归测试

工具不会猜测未知 Unicode 字符或外部自定义宏的含义；例如中文仍由文档的字体／编译引擎支持，来源中的自定义命令仍需要模板定义。保留 URL 时，模板需要提供其参考文献样式要求的 `url` 或 `hyperref` 支持。格式处理不能替代任意模板的宏包配置。

测试使用明确标注的合成 HTTP 响应，覆盖抓取、GUI API、ZIP、CLI、原文保持和幂等性。装有 TeX 时，还会实际编译 `plain`、`abbrv`、`IEEEtran` 样式及全部 URL／缩写组合；详见[开发文档](DEVELOPMENT.md)。这些编译回归不涉及文献真实性核验。

实现参考：[pylatexenc 2.10 编码与括号保护选项](https://pylatexenc.readthedocs.io/en/v2.10/latexencode/)。
