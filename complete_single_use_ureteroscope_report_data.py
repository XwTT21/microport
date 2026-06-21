from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "outputs" / "single_use_ureteroscope_screening" / "single_use_ureteroscope_screening_data.json"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def sentence_snippets(text: str, patterns: list[str], limit: int = 3) -> list[str]:
    text = clean(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?。；;])\s+", text)
    out: list[str] = []
    for sent in sentences:
        if any(re.search(p, sent, flags=re.I) for p in patterns):
            if sent not in out:
                out.append(sent[:850])
        if len(out) >= limit:
            break
    return out


def first_match(text: str, patterns: list[str]) -> str:
    for p in patterns:
        m = re.search(p, text or "", flags=re.I)
        if m:
            return m.group(0)
    return ""


def extract_sample_size(text: str) -> str:
    patterns = [
        r"\b(?:included|enrolled|retrospectively analyzed|prospectively enrolled|collected|evaluated)\s+(?:a total of\s+)?(\d{1,5})\s+(?:patients|cases|subjects|procedures|ureteroscopies)",
        r"\b(?:patients|cases|subjects|procedures)\s*\(\s*n\s*=\s*(\d{1,5})\s*\)",
        r"\bn\s*=\s*(\d{1,5})\b",
        r"\b(\d{2,5})\s+(?:patients|cases|subjects|procedures|ureteroscopies)\b",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(1)
    return ""


def extract_design(text: str, study_type: str) -> str:
    patterns = [
        r"randomi[sz]ed controlled trial",
        r"prospective randomi[sz]ed trial",
        r"prospective cohort",
        r"retrospective cohort",
        r"retrospective case[- ]controlled study",
        r"case[- ]control study",
        r"cross[- ]sectional analysis",
        r"systematic review",
        r"meta[- ]analysis",
        r"case report",
        r"in vitro",
        r"ex vivo",
    ]
    found = first_match(text, patterns)
    return found or study_type


def extract_comparator(text: str) -> str:
    patterns = [
        r"reusable (?:digital )?flexible ureteroscope(?:s)?",
        r"reusable ureteroscope(?:s)?",
        r"single[- ]use (?:and|vs\.?|versus) reusable",
        r"reusable (?:and|vs\.?|versus) single[- ]use",
        r"mini[- ]percutaneous nephrolithotomy",
        r"\bmini[- ]?PCNL\b",
        r"conventional ureteroscope(?:s)?",
        r"all other single[- ]use ureteroscope(?:s)?",
        r"7\.5\s*Fr",
        r"6\.3\s*Fr",
    ]
    return first_match(text, patterns)


def extract_percentages(snippets: list[str]) -> str:
    joined = " ".join(snippets)
    values = re.findall(r"\b\d{1,3}(?:\.\d+)?\s*%", joined)
    return " | ".join(dict.fromkeys(values))


def dataset_assignment(record: dict[str, Any], appraisal: dict[str, Any] | None) -> tuple[str, str]:
    cls = record.get("Inclusion_Class", "").lower()
    study = record.get("Study_Type", "").lower()
    overall = (appraisal or {}).get("Overall_Appraisal", "")
    if record.get("Decision") == "待人工确认" or overall == "待确认":
        return "Pending confirmation", "主题权重、证据用途或结局提取需人工复核"
    if "economic" in cls or "economic" in study or re.search(r"cost|workflow|resource|environment", record.get("Title", ""), flags=re.I):
        return "Economic/resource evidence", "评价一次性/可重复使用输尿管镜成本、维修、灭菌、资源利用、流程或环境影响"
    if "secondary" in cls or "review" in study or "guideline" in study or "recommendation" in study:
        return "SOTA dataset", "系统综述/Meta/指南/叙述综述，可用于技术现状和总体安全/性能背景"
    if "technical" in cls or "non-clinical" in study:
        return "Technical supportive data", "体外、工程、成像、弯曲、灌注、可用性或性能测试等非临床数据"
    if "case" in cls or "case report" in study:
        return "Supportive case evidence", "病例或特殊场景证据，作为补充支持"
    return "Similar device clinical dataset", "直接评价一次性输尿管镜或相似一次性软镜的临床安全性/性能"


def main() -> int:
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    source = json.loads(Path(data["source_cache"]).read_text(encoding="utf-8"))
    pdf_by_path = {p["pdf_path"]: p for p in source["pdf_manifest"]}
    appraisal_by_id = {r["Record_ID"]: r for r in data.get("appraisal", [])}

    evidence_rows: list[dict[str, Any]] = []
    dataset_rows: list[dict[str, Any]] = []
    for record in data["records"]:
        if record.get("Decision") not in {"纳入", "待人工确认"}:
            continue
        pdf = pdf_by_path.get(record.get("PDF_Path", ""), {})
        text = clean(" ".join([
            record.get("Title", ""),
            record.get("Evidence_Sentence", ""),
            pdf.get("pdf_text_excerpt", ""),
        ]))
        performance = sentence_snippets(text, [
            r"stone[- ]free", r"\bSFR\b", r"clearance", r"success rate", r"effective", r"efficacy",
            r"scope failure", r"device failure", r"deflection", r"image quality", r"usability",
        ], 4)
        safety = sentence_snippets(text, [
            r"complication", r"safety", r"fever", r"infection", r"sepsis", r"\bSIRS\b", r"bleeding",
            r"hemoglobin", r"ureteral injury", r"perforation", r"mucosal injury", r"adverse",
        ], 4)
        pressure = sentence_snippets(text, [
            r"intrarenal pressure", r"renal pelvic pressure", r"pressure", r"irrigation", r"flow rate",
            r"temperature", r"visuali[sz]ation",
        ], 3)
        efficiency = sentence_snippets(text, [
            r"operative time", r"operation time", r"procedure time", r"surgical time", r"surgery duration",
            r"hospital stay", r"readmission", r"cost", r"repair", r"sterili[sz]ation", r"workflow",
            r"resource", r"environment", r"carbon footprint", r"contamination", r"cross[- ]infection",
        ], 4)
        appraisal = appraisal_by_id.get(record["Record_ID"])
        assignment, reason = dataset_assignment(record, appraisal)
        dataset_rows.append({
            "Record_ID": record["Record_ID"],
            "Dataset_Assignment": assignment,
            "Assignment_Reason": reason,
            "Overall_Appraisal": (appraisal or {}).get("Overall_Appraisal", ""),
            "Title": record.get("Title", ""),
            "Study_Type": record.get("Study_Type", ""),
            "Decision": record.get("Decision", ""),
            "Source_Database": record.get("Source_Database", ""),
            "Search_Batch": record.get("Search_Batch", ""),
            "PDF_Path": record.get("PDF_Path", ""),
        })
        evidence_rows.append({
            "Record_ID": record["Record_ID"],
            "Dataset_Assignment": assignment,
            "Title": record.get("Title", ""),
            "Study_Design": extract_design(text, record.get("Study_Type", "")),
            "Sample_Size_N": extract_sample_size(text),
            "Single_Use_Ureteroscope_Device_or_Technique": record.get("Single_Use_Ureteroscope_Device_or_Technique", ""),
            "Comparator": extract_comparator(text),
            "Clinical_Context": record.get("Clinical_Context", ""),
            "Performance_Outcomes": " | ".join(performance),
            "Safety_Outcomes": " | ".join(safety),
            "Pressure_or_Irrigation_Outcomes": " | ".join(pressure),
            "Efficiency_or_Resource_Outcomes": " | ".join(efficiency),
            "Extracted_Percentages": extract_percentages(performance + safety + pressure + efficiency),
            "Overall_Appraisal": (appraisal or {}).get("Overall_Appraisal", ""),
            "Use_For": (appraisal or {}).get("Use_For", ""),
            "Extraction_Note": "自动抽取，核心证据正式提交前建议全文核对。",
            "PDF_Path": record.get("PDF_Path", ""),
        })

    decision_counts = data["summary"]["decision_counts"]
    source_counts = data["summary"]["source_counts"]
    flow_rows = [
        {"Step": "缓存PDF识别", "Count": data["summary"]["cache_pdf_count"], "Description": "已有缓存中的PDF总数。"},
        {"Step": "产品文献排除", "Count": data["summary"]["product_pdf_excluded_count"], "Description": "路径或检索文件夹含“产品”的PDF，按本轮范围不纳入筛选。"},
        {"Step": "进入筛选PDF", "Count": data["summary"]["pdf_count"], "Description": "Cochrane、Google Scholar、PubMed及二次搜索文件夹内实际筛选PDF数，不含产品文献。"},
        {"Step": "去重后进入筛选", "Count": data["summary"]["screened_unique_count"], "Description": "按题名/DOI/PMID/保守PubMed匹配去重后的记录数。"},
        {"Step": "重复记录", "Count": data["summary"]["duplicate_row_count"], "Description": f"{data['summary']['duplicate_group_count']}个重复组，共{data['summary']['duplicate_row_count']}条重复来源行。"},
        {"Step": "纳入一次性输尿管镜证据", "Count": decision_counts.get("纳入", 0), "Description": "题名或摘要显示一次性/可抛弃输尿管镜为研究对象、干预、对照、器械、技术平台或主要临床问题。"},
        {"Step": "排除", "Count": decision_counts.get("排除", 0), "Description": "无一次性输尿管镜主题、仅背景提及、主要研究对象为其他器械/术式或缺少相关结局。"},
        {"Step": "待人工确认", "Count": decision_counts.get("待人工确认", 0), "Description": "主题权重、研究类型、报告质量或证据用途需人工复核。"},
        {"Step": "PubMed未匹配但潜在一次性输尿管镜题录", "Count": data["summary"].get("potential_single_use_ureteroscope_unmatched_pubmed_count", 0), "Description": "题录提示一次性输尿管镜相关，但未匹配到本地PDF；单独列出，不混入PDF筛选总表。"},
    ]
    for source_name, count in source_counts.items():
        flow_rows.append({"Step": f"来源：{source_name}", "Count": count, "Description": "去重后筛选总表中的主来源计数。"})

    dataset_counts: dict[str, int] = {}
    for row in dataset_rows:
        dataset_counts[row["Dataset_Assignment"]] = dataset_counts.get(row["Dataset_Assignment"], 0) + 1

    report_summary = {
        "title": "Single-use / Disposable Ureteroscope Literature Screening and Evaluation Report",
        "scope": "Cochrane, Google Scholar, PubMed and secondary search folders; 产品文献 excluded.",
        "screening_basis": "筛选.docx and the completed UAS workflow were used as process/templates; topic criteria were adapted to single-use/disposable ureteroscopes.",
        "main_result": f"{data['summary']['screened_unique_count']} unique PDF records were screened after excluding product literature: {decision_counts.get('纳入', 0)} included, {decision_counts.get('排除', 0)} excluded, and {decision_counts.get('待人工确认', 0)} pending manual confirmation.",
        "dataset_counts": dataset_counts,
        "appraisal_counts": data["summary"].get("appraisal_overall_counts", {}),
        "key_message": "The evidence base is organized around direct clinical comparisons or feasibility studies of single-use/disposable ureteroscopes, SOTA reviews/guidance, technical bench evidence, and economic/resource evidence. Automatically extracted outcomes require full-text verification before formal submission.",
    }

    data["flow_rows"] = flow_rows
    data["dataset_assignment"] = dataset_rows
    data["performance_safety_extraction"] = evidence_rows
    data["report_summary"] = report_summary
    DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "flow_rows": len(flow_rows),
        "dataset_assignment": dataset_counts,
        "evidence_rows": len(evidence_rows),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
