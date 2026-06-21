# 代码仅供参考

本目录提供当前项目的参考脚本，目的是让其他大模型或同事理解“筛选、评估、摘录、Excel、Word报告”如何被拆成步骤。它不是固定产品模板，也不是一键运行包。

## 使用前必须先做的事

1. 重新确认本次产品或器械主题。
2. 重写英文关键词、中文关键词、缩写和同义词。
3. 重写纳入标准、排除标准和待人工确认标准。
4. 重写证据分层名称和含义。
5. 重写适应性评估维度解释。
6. 决定产品目录文献是否单独处理。
7. 决定Excel sheet和Word章节是否沿用当前示例。

## 脚本分工参考

- `literature_screening_extract.py`：读取基础文献、题录和PDF文本，形成可复用缓存。
- `uas_screening_from_cache.py`：UAS主题筛选示例。
- `add_uas_appraisal.py`：UAS适应性评估示例。
- `complete_uas_report_data.py`：UAS证据分层和数据摘录示例。
- `build_uas_screening_workbook.mjs`：UAS Excel生成示例。
- `verify_uas_workbook.mjs`：UAS Excel检查示例。
- `build_uas_report_docx.py`：UAS Word报告生成示例。
- `single_use_ureteroscope_screening_from_cache.py`：一次性输尿管镜主题筛选示例。
- `add_single_use_ureteroscope_appraisal.py`：一次性输尿管镜适应性评估示例。
- `complete_single_use_ureteroscope_report_data.py`：一次性输尿管镜证据分层和数据摘录示例。
- `build_single_use_ureteroscope_screening_workbook.mjs`：一次性输尿管镜Excel生成示例。
- `verify_single_use_ureteroscope_workbook.mjs`：一次性输尿管镜Excel检查示例。
- `build_single_use_ureteroscope_report_docx.py`：一次性输尿管镜Word报告生成示例。

## 方案B额外限制

目标电脑没有LibreOffice，因此只能做Word报告结构和内容检查。正式提交前，仍建议把DOCX转到有Word或LibreOffice的电脑上做页面视觉检查。
