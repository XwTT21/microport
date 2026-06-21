from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "outputs" / "single_use_ureteroscope_screening" / "single_use_ureteroscope_screening_data.json"


def has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text or "", flags=re.I))


def grade_device(record: dict[str, Any]) -> tuple[str, str]:
    title = " ".join([record.get("Title", ""), record.get("Single_Use_Ureteroscope_Device_or_Technique", ""), record.get("Evidence_Sentence", "")])
    cls = record.get("Inclusion_Class", "").lower()
    if has(title, r"single[- ]use|disposable|一次性|可抛弃|单次使用"):
        if has(title, r"ureteroscope|ureterorenoscope|f[- ]?URS|输尿管镜"):
            return "D1", "直接评价目标一次性输尿管镜/一次性软镜/一次性电子输尿管镜"
    if "secondary" in cls or "economic" in cls or has(title, r"reusable"):
        return "D2", "评价相似一次性输尿管镜或一次性/可重复使用对照证据"
    return "D3", "宽泛URS/RIRS证据中包含一次性输尿管镜，但不是核心对象"


def grade_application(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([record.get("Title", ""), record.get("Clinical_Context", ""), record.get("Evidence_Sentence", "")])
    if has(text, r"ureteroscopy|ureterorenoscopy|RIRS|FURS|renal stone|kidney stone|ureteral calcul|ureteric calcul|upper urinary tract|urolithiasis|lithotripsy"):
        if record.get("Decision") == "纳入":
            return "A1", "用途与输尿镜/RIRS/FURS诊疗、结石治疗或上尿路操作一致"
        return "A2", "用途相关，但主题权重或证据用途需人工确认"
    return "A3", "用途与目标应用存在明显偏离"


def grade_patient(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([record.get("Title", ""), record.get("Evidence_Sentence", "")])
    if has(text, r"pediatric|children|child|pregnan|transplant|octogenarian|HIV|case report|staghorn|bilateral"):
        return "P2", "特殊或有限人群/特殊场景，外推需降权"
    if has(record.get("Study_Type", ""), r"Non-clinical|bench"):
        return "P3", "非临床研究，不直接对应目标患者人群"
    return "P1", "患者/疾病背景符合一次性输尿管镜目标治疗人群"


def grade_report(record: dict[str, Any]) -> tuple[str, str]:
    if record.get("Text_Status") != "readable":
        return "R3", "PDF文本不可读或读取质量不足"
    if record.get("PubMed_Match_Score", 0) and record.get("PubMed_Match_Score", 0) < 0.82:
        return "R2", "题录匹配置信度有限，需核对PDF题名"
    if not record.get("Evidence_Sentence"):
        return "R2", "自动证据句不足"
    return "R1", "报告完整，PDF/题录可审计"


def grade_source_type(record: dict[str, Any]) -> tuple[str, str]:
    study = record.get("Study_Type", "")
    if has(study, r"Clinical original|Systematic review|Meta-analysis|Guideline|Recommendation|Economic"):
        return "T1", "研究/证据类型可用于一次性输尿管镜安全性、性能或资源评价"
    return "T2", "病例、非临床或证据类型有限，作为支持性证据"


def grade_outcome(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([record.get("Outcome_Data", ""), record.get("Evidence_Sentence", "")])
    if has(text, r"stone[- ]free|SFR|complication|safety|infection|fever|sepsis|SIRS|operative time|procedure time|failure|deflection|irrigation|image quality|cost|repair|sterili[sz]ation|environment|readmission|adverse"):
        return "O1", "报告了与一次性输尿管镜相关的安全性/性能/有效性/资源结局"
    return "O2", "未自动识别明确相关结局"


def grade_statistics(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([record.get("Study_Type", ""), record.get("Evidence_Sentence", "")])
    if has(text, r"random|prospective|retrospective|cohort|systematic review|meta-analysis|comparative|compared|versus|vs\.?|p\s*[<=>]"):
        return "S1", "统计分析明确或研究类型通常包含统计比较"
    return "S2", "统计分析不明确或证据等级有限"


def grade_clinical_significance(record: dict[str, Any]) -> tuple[str, str]:
    if has(record.get("Study_Type", ""), r"Non-clinical|bench"):
        return "C2", "非临床证据，临床意义需结合临床数据确认"
    if has(record.get("Outcome_Data", "") + " " + record.get("Evidence_Sentence", ""), r"stone[- ]free|complication|infection|sepsis|operative time|hospital|readmission|cost|adverse"):
        return "C1", "结局具有直接临床或资源管理意义"
    return "C2", "临床意义有限或需进一步确认"


def overall_appraisal(grades: dict[str, str], decision: str) -> tuple[str, str]:
    if decision == "待人工确认":
        return "待确认", "自动筛选提示相关，但主题权重、报告质量或结局需人工复核"
    values = set(grades.values())
    if {"D1", "A1", "P1", "R1", "T1", "O1", "C1"}.issubset(values) and "S1" in values:
        return "高/核心证据", "器械、用途、人群、报告和结局均与一次性输尿管镜临床评价高度匹配"
    if "D3" in values or "A3" in values or "O2" in values or "R3" in values:
        return "低/仅支持性", "与一次性输尿管镜主题或可审计性存在明显限制"
    return "中等/可作为支持证据", "与一次性输尿管镜主题相关，但存在研究类型、患者人群、报告质量或统计/临床意义限制"


def use_for(record: dict[str, Any], overall: str) -> str:
    cls = record.get("Inclusion_Class", "").lower()
    if overall == "待确认":
        return "待人工复核后决定是否纳入证据包"
    if "economic" in cls:
        return "一次性/可重复使用输尿管镜经济学、资源或环境证据"
    if "secondary" in cls:
        return "一次性输尿管镜SOTA/二级证据背景支持"
    if "technical" in cls:
        return "一次性输尿管镜技术性能支持数据"
    if "case" in cls:
        return "特殊场景或病例支持证据"
    if overall.startswith("高"):
        return "一次性输尿管镜核心临床安全性/性能证据"
    return "一次性输尿管镜支持性临床证据"


def appraise(record: dict[str, Any]) -> dict[str, Any]:
    d, d_reason = grade_device(record)
    a, a_reason = grade_application(record)
    p, p_reason = grade_patient(record)
    r, r_reason = grade_report(record)
    t, t_reason = grade_source_type(record)
    o, o_reason = grade_outcome(record)
    s, s_reason = grade_statistics(record)
    c, c_reason = grade_clinical_significance(record)
    grades = {"D": d, "A": a, "P": p, "R": r, "T": t, "O": o, "S": s, "C": c}
    overall, overall_reason = overall_appraisal(grades, record.get("Decision", ""))
    rationale = "；".join([d_reason, a_reason, p_reason, r_reason, t_reason, o_reason, s_reason, c_reason, overall_reason])
    return {
        "Record_ID": record["Record_ID"],
        "Decision": record.get("Decision", ""),
        "Inclusion_Class": record.get("Inclusion_Class", ""),
        "Title": record.get("Title", ""),
        "Study_Type": record.get("Study_Type", ""),
        "Source_Database": record.get("Source_Database", ""),
        "Search_Batch": record.get("Search_Batch", ""),
        "Search_Folder": record.get("Search_Folder", ""),
        "D": d,
        "D_Reason": d_reason,
        "A": a,
        "A_Reason": a_reason,
        "P": p,
        "P_Reason": p_reason,
        "R": r,
        "R_Reason": r_reason,
        "T": t,
        "T_Reason": t_reason,
        "O": o,
        "O_Reason": o_reason,
        "S": s,
        "S_Reason": s_reason,
        "C": c,
        "C_Reason": c_reason,
        "Overall_Appraisal": overall,
        "Use_For": use_for(record, overall),
        "Appraisal_Rationale": rationale,
        "Evidence_Sentence": record.get("Evidence_Sentence", ""),
        "PDF_Path": record.get("PDF_Path", ""),
    }


def counts(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value or "(blank)"] = out.get(value or "(blank)", 0) + 1
    return dict(sorted(out.items()))


def main() -> int:
    data = json.loads(DATA_JSON.read_text(encoding="utf-8"))
    candidate_records = [r for r in data["records"] if r.get("Decision") in {"纳入", "待人工确认"}]
    appraisal = [appraise(r) for r in candidate_records]
    rules = [
        {"Item": "D1/D2/D3", "Description": "D1=直接评价目标一次性输尿管镜/一次性软镜/一次性电子输尿管镜；D2=相似一次性输尿管镜或一次性/可重复使用对照研究；D3=宽泛URS/RIRS证据中包含一次性输尿管镜但不是核心对象。"},
        {"Item": "A1/A2/A3", "Description": "A1=用途与输尿镜/RIRS/FURS诊疗、结石治疗、上尿路操作一致；A2=相关但主题较宽或轻微偏离；A3=明显不符。"},
        {"Item": "P1/P2/P3", "Description": "P1=目标患者人群适用；P2=儿童、孕妇、移植肾、特殊结石或单病例等有限人群；P3=非临床或不同人群。"},
        {"Item": "R1/R2/R3", "Description": "R1=报告完整、PDF/题录可审计；R2=轻微信息不足；R3=信息不足或PDF不可读。"},
        {"Item": "T1/T2", "Description": "T1=临床原始研究、系统综述/Meta、指南、经济学研究等可用证据类型；T2=病例、非临床或主题权重不足。"},
        {"Item": "O1/O2", "Description": "O1=有一次性输尿管镜相关安全性/性能/有效性/资源结局；O2=未见明确相关结局。"},
        {"Item": "S1/S2", "Description": "S1=统计分析明确或研究类型通常包含统计比较；S2=统计分析不明确或证据等级有限。"},
        {"Item": "C1/C2", "Description": "C1=结局具有直接临床意义；C2=临床意义有限或需进一步确认。"},
    ]
    data["appraisal"] = appraisal
    data["appraisal_rules"] = rules
    data["summary"]["appraisal_record_count"] = len(appraisal)
    data["summary"]["appraisal_overall_counts"] = counts([r["Overall_Appraisal"] for r in appraisal])
    data["summary"]["appraisal_grade_counts"] = {
        grade: counts([r[grade] for r in appraisal]) for grade in ["D", "A", "P", "R", "T", "O", "S", "C"]
    }
    DATA_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "appraisal_record_count": len(appraisal),
        "appraisal_overall_counts": data["summary"]["appraisal_overall_counts"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
