from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "outputs" / "uas_screening" / "uas_screening_data.json"


def clean(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sentence_snippets(text: str, patterns: list[str], limit: int = 3) -> list[str]:
    text = clean(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?。；;])\s+", text)
    hits: list[str] = []
    for sent in sentences:
        if any(re.search(p, sent, flags=re.I) for p in patterns):
            sent = sent.strip()
            if sent and sent not in hits:
                hits.append(sent[:700])
            if len(hits) >= limit:
                break
    return hits


def first_match(text: str, patterns: list[str]) -> str:
    for p in patterns:
        m = re.search(p, text or "", flags=re.I)
        if m:
            return clean(m.group(0))
    return ""


def extract_sample_size(text: str) -> str:
    patterns = [
        r"\b(?:included|enrolled|retrospectively analyzed|prospectively enrolled|collected)\s+(?:a total of\s+)?(\d{2,5})\s+(?:patients|cases|subjects)",
        r"\b(?:patients|cases|subjects)\s*\(\s*n\s*=\s*(\d{1,5})\s*\)",
        r"\bn\s*=\s*(\d{1,5})\b",
        r"\b(\d{2,5})\s+(?:patients|cases|subjects)\b",
    ]
    for p in patterns:
        m = re.search(p, text or "", flags=re.I)
        if m:
            return m.group(1)
    return ""


def extract_design(text: str, study_type: str) -> str:
    patterns = [
        r"prospective randomized controlled trial",
        r"prospective randomi[sz]ed trial",
        r"randomi[sz]ed controlled trial",
        r"retrospective cohort study",
        r"retrospective analysis",
        r"multicenter retrospective feasibility study",
        r"prospective multicenter study",
        r"case control study",
        r"case-control study",
        r"systematic review and meta-analysis",
        r"meta-analysis and systematic review",
        r"systematic review",
        r"case report",
        r"in vitro",
        r"CFD analyses",
    ]
    hit = first_match(text, patterns)
    return hit or study_type


def extract_comparator(text: str) -> str:
    patterns = [
        r"(?:versus|vs\.?|compared with|comparison of|compared to)\s+([^.;]{5,160})",
        r"(?:control group|traditional group|conventional group)\s+([^.;]{0,120})",
        r"(?:without ureteral access sheath|without UAS)",
        r"(?:conventional ureteral access sheath|standard ureteral access sheath|traditional ureteral access sheath)",
        r"(?:tubeless[- ]mini percutaneous nephrolithotomy|mini[- ]PCNL|mPNL|PCNL)",
    ]
    hit = first_match(text, patterns)
    return hit


def extract_percentages(snippets: list[str]) -> str:
    values: list[str] = []
    for snippet in snippets:
        for value in re.findall(r"\b\d{1,3}(?:\.\d+)?\s*%", snippet):
            if value not in values:
                values.append(value)
    return "; ".join(values[:8])


def dataset_assignment(record: dict[str, Any], appraisal: dict[str, Any] | None) -> tuple[str, str]:
    decision = record.get("Decision", "")
    incl = record.get("Inclusion_Class", "")
    study_type = record.get("Study_Type", "")
    overall = (appraisal or {}).get("Overall_Appraisal", "")
    if decision == "待人工确认":
        return "Pending confirmation", "UAS相关但主题权重、证据用途或研究类型需人工复核"
    if "secondary" in incl or "Systematic review" in study_type:
        return "SOTA dataset", "UAS系统综述/Meta等二级证据，可用于技术现状和总体安全/性能背景"
    if "case" in incl:
        return "Supportive case evidence", "个案或特殊病例证据，仅作补充支持"
    if "Non-clinical" in study_type:
        return "Technical supportive data", "体外/工程/模型研究，可支持机制或技术性能，不作为核心临床证据"
    if "高/核心" in overall or "core clinical" in incl:
        return "Similar device clinical dataset", "直接评价UAS或相似UAS临床安全性/性能，可作为核心临床证据"
    return "Supportive clinical evidence", "UAS相关临床证据，但适用性或报告质量需降权"


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
            r"stone[- ]free", r"\bSFR\b", r"clearance", r"evacuation", r"success rate", r"effective", r"efficacy",
        ], 4)
        safety = sentence_snippets(text, [
            r"complication", r"safety", r"fever", r"infection", r"sepsis", r"\bSIRS\b", r"bleeding",
            r"hemoglobin", r"ureteral injury", r"perforation", r"mucosal injury", r"adverse",
        ], 4)
        pressure = sentence_snippets(text, [
            r"intrarenal pressure", r"renal pelvic pressure", r"pressure", r"irrigation", r"flow rate",
        ], 3)
        efficiency = sentence_snippets(text, [
            r"operative time", r"operation time", r"surgical time", r"surgery duration", r"hospital stay",
            r"length of postoperative hospital stay", r"cost",
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
            "UAS_Device_or_Technique": record.get("UAS_Device_or_Technique", ""),
            "Comparator": extract_comparator(text),
            "Clinical_Context": record.get("Clinical_Context", ""),
            "Performance_Outcomes": " | ".join(performance),
            "Safety_Outcomes": " | ".join(safety),
            "Pressure_or_Irrigation_Outcomes": " | ".join(pressure),
            "Efficiency_or_Resource_Outcomes": " | ".join(efficiency),
            "Extracted_Percentages": extract_percentages(performance + safety + pressure + efficiency),
            "Overall_Appraisal": (appraisal or {}).get("Overall_Appraisal", ""),
            "Use_For": (appraisal or {}).get("Use_For", ""),
            "Extraction_Note": "自动从题名/摘要/PDF前12页文本抽取，正式报告前建议对核心证据逐篇全文核对。",
            "PDF_Path": record.get("PDF_Path", ""),
        })

    decision_counts = data["summary"]["decision_counts"]
    source_counts = data["summary"]["source_counts"]
    flow_rows = [
        {"Step": "数据库和本地文件识别", "Count": data["summary"]["pdf_count"], "Description": "三大数据库及二次搜索文件夹内PDF总数，不含产品文献。"},
        {"Step": "去重后进入筛选", "Count": data["summary"]["screened_unique_count"], "Description": "按题名/DOI/PMID/保守PubMed匹配去重后的记录数。"},
        {"Step": "重复记录", "Count": data["summary"]["duplicate_row_count"], "Description": f"{data['summary']['duplicate_group_count']}个重复组，共{data['summary']['duplicate_row_count']}条重复来源行。"},
        {"Step": "纳入UAS证据", "Count": decision_counts.get("纳入", 0), "Description": "题名/摘要显示UAS为研究对象、干预、对照、技术或主要临床问题。"},
        {"Step": "排除", "Count": decision_counts.get("排除", 0), "Description": "无UAS主题、仅背景提及、主要研究对象为其他器械/术式或缺少UAS相关结局。"},
        {"Step": "待人工确认", "Count": decision_counts.get("待人工确认", 0), "Description": "UAS相关但主题权重、研究类型或证据用途需人工复核。"},
        {"Step": "PubMed未匹配但潜在UAS题录", "Count": data["summary"].get("potential_uas_unmatched_pubmed_count", 0), "Description": "题录提示UAS相关，但未匹配到本地PDF；单独列出，不混入PDF筛选总表。"},
    ]
    for source_name, count in source_counts.items():
        flow_rows.append({"Step": f"来源：{source_name}", "Count": count, "Description": "去重后筛选总表中的主来源计数。"})

    dataset_counts: dict[str, int] = {}
    for row in dataset_rows:
        dataset_counts[row["Dataset_Assignment"]] = dataset_counts.get(row["Dataset_Assignment"], 0) + 1

    report_summary = {
        "title": "Ureteral Access Sheath (UAS) Literature Screening and Evaluation Report",
        "scope": "Cochrane, Google Scholar, PubMed and secondary search folders; 产品文献 excluded.",
        "screening_basis": "筛选.docx was used as a process/template reference; topic criteria were adapted to UAS rather than Double-J ureteral stents.",
        "main_result": f"{data['summary']['screened_unique_count']} unique PDF records were screened: {decision_counts.get('纳入', 0)} included, {decision_counts.get('排除', 0)} excluded, and {decision_counts.get('待人工确认', 0)} pending manual confirmation.",
        "dataset_counts": dataset_counts,
        "appraisal_counts": data["summary"].get("appraisal_overall_counts", {}),
        "key_message": "The strongest evidence base is concentrated in direct comparative or feasibility studies of suction/flexible/navigable UAS in RIRS/FURS for renal or upper urinary tract stones; systematic reviews/meta-analyses provide SOTA support, while case and non-clinical studies should be down-weighted.",
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
