from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA_JSON = ROOT / "outputs" / "uas_screening" / "uas_screening_data.json"


def has(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text or "", flags=re.I))


def grade_device(record: dict[str, Any]) -> tuple[str, str]:
    cls = record.get("Inclusion_Class", "")
    title = record.get("Title", "")
    if "core clinical" in cls or "non-clinical" in cls or "case" in cls:
        return "D1", "直接评价UAS/吸引UAS/可弯曲或导航UAS等目标器械或技术"
    if "secondary" in cls and has(title, r"access sheath|UAS|suction sheath|FANS|TFS|FV-UAS"):
        return "D2", "系统综述/Meta或二级证据直接围绕UAS或相似UAS"
    return "D3", "较宽泛URS/RIRS证据，UAS只作为技术组成或背景信息"


def grade_application(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([record.get("Title", ""), record.get("Clinical_Context", ""), record.get("Evidence_Sentence", "")])
    if has(text, r"RIRS|FURS|ureteroscop|ureterorenoscop|renal stone|kidney stone|upper urinary tract calcul|renal calcul"):
        if record.get("Decision") == "纳入":
            return "A1", "用途与UAS在URS/RIRS/肾或上尿路结石治疗中的预期应用一致"
        return "A2", "用途相关，但文献主题较宽或UAS不是主要干预"
    return "A3", "用途与UAS目标应用存在明显偏离"


def grade_patient(record: dict[str, Any]) -> tuple[str, str]:
    text = " ".join([record.get("Title", ""), record.get("Study_Type", ""), record.get("Evidence_Sentence", "")])
    if has(record.get("Study_Type", ""), r"Non-clinical|bench"):
        return "P3", "体外/模型研究，无真实目标患者人群"
    if has(text, r"case report|cystine|children|pediatric|paediatric|pregnan|transplant|UPJ|special|model"):
        return "P2", "特殊或有限患者人群，适用性低于常规目标人群"
    if has(text, r"patient|clinical|renal stone|kidney stone|upper urinary tract calcul|renal calcul|RIRS|FURS|ureteroscop"):
        return "P1", "患者/疾病背景符合UAS目标治疗人群"
    return "P2", "患者人群信息有限"


def grade_report(record: dict[str, Any]) -> tuple[str, str]:
    status = record.get("Text_Status", "")
    score = float(record.get("PubMed_Match_Score") or 0)
    evidence = record.get("Evidence_Sentence", "")
    if status.startswith("read_error") or status in {"no_text", "low_text"}:
        return "R3", "PDF文字不可读或证据信息不足"
    if record.get("Source_Database") == "PubMed" and score >= 0.82 and evidence:
        return "R1", "PubMed题录匹配可信且PDF可读，报告信息较完整"
    if evidence:
        return "R2", "PDF可读并有证据句，但题录/来源信息或匹配完整性存在轻微不足"
    return "R3", "缺少可审计证据句"


def grade_source_type(record: dict[str, Any]) -> tuple[str, str]:
    st = record.get("Study_Type", "")
    if has(st, r"Clinical original|Systematic review|Meta-analysis|Guideline|Recommendation"):
        return "T1", "研究/证据类型可用于UAS安全性或性能评价"
    if has(st, r"Case report|Non-clinical|bench"):
        return "T2", "病例或非临床证据，设计对临床评价贡献有限"
    if record.get("Decision") == "待人工确认":
        return "T2", "主题权重或研究类型需人工确认"
    return "T1", "研究类型基本可接受"


def grade_outcome(record: dict[str, Any]) -> tuple[str, str]:
    outcome = record.get("Outcome_Data", "")
    evidence = record.get("Evidence_Sentence", "")
    if outcome or has(evidence, r"stone-free|SFR|safety|efficacy|complication|pressure|infection|sepsis|clearance|evacuation|hospital stay|bleeding"):
        return "O1", "报告了与UAS性能/安全性相关的结局"
    return "O2", "未自动识别明确UAS性能或安全性结局"


def grade_statistics(record: dict[str, Any]) -> tuple[str, str]:
    st = record.get("Study_Type", "")
    evidence = record.get("Evidence_Sentence", "")
    if has(st, r"Systematic review|Meta-analysis|Clinical original") or has(evidence, r"\bp\s*[<=>]|confidence interval|CI|statistically|randomi[sz]ed"):
        return "S1", "有统计分析或研究类型通常包含统计比较"
    return "S2", "统计分析不明确或证据等级有限"


def grade_clinical_significance(record: dict[str, Any]) -> tuple[str, str]:
    st = record.get("Study_Type", "")
    outcome = " ".join([record.get("Outcome_Data", ""), record.get("Evidence_Sentence", "")])
    if has(st, r"Case report|Non-clinical|bench"):
        return "C2", "临床意义有限或主要为技术/探索性支持"
    if has(outcome, r"stone-free|SFR|safety|efficacy|complication|infection|sepsis|pressure|hospital stay|bleeding|clearance"):
        return "C1", "结局与临床疗效或安全性直接相关"
    return "C2", "临床意义需进一步确认"


def overall_appraisal(grades: dict[str, str], decision: str) -> tuple[str, str]:
    if decision == "待人工确认":
        return "待确认", "题名/摘要提示相关但主题权重或证据用途需人工复核"
    severe = {"A3", "P3", "R3", "O2"}
    limited = {"T2", "S2", "C2", "P2", "R2", "D3", "A2"}
    values = set(grades.values())
    if values & severe:
        return "低/仅支持性", "存在非目标用途、非目标人群、报告不足或缺少结局等限制"
    if values & limited:
        return "中等/可作为支持证据", "与UAS主题相关，但存在研究类型、患者人群、报告质量或统计/临床意义限制"
    return "高/核心证据", "器械、用途、人群、报告和结局均与UAS临床评价高度匹配"


def use_for(record: dict[str, Any], overall: str) -> str:
    cls = record.get("Inclusion_Class", "")
    if overall == "待确认":
        return "待人工确认后决定是否纳入背景或支持证据"
    if overall.startswith("高"):
        return "UAS核心临床安全性/性能证据"
    if "secondary" in cls:
        return "UAS二级证据/SOTA背景支持"
    if "case" in cls:
        return "病例/特殊场景支持，不宜单独作为核心证据"
    if "non-clinical" in cls or "低" in overall:
        return "技术或非临床支持，临床评价中需降权"
    return "UAS支持性临床证据"


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
        "Record_ID": record.get("Record_ID", ""),
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
        {"Item": "D1/D2/D3", "Description": "D1=直接UAS器械或技术证据；D2=相似UAS或UAS二级证据；D3=宽泛URS/RIRS背景中涉及UAS。"},
        {"Item": "A1/A2/A3", "Description": "A1=用途与UAS在URS/RIRS/结石治疗中的预期用途一致；A2=相关但主题较宽或有轻微偏离；A3=明显偏离。"},
        {"Item": "P1/P2/P3", "Description": "P1=目标患者人群；P2=特殊/有限人群；P3=非临床或不同人群。"},
        {"Item": "R1/R2/R3", "Description": "R1=报告完整且题录匹配可信；R2=有轻微不足；R3=信息不足或PDF不可读。"},
        {"Item": "T1/T2", "Description": "T1=临床原始研究、系统综述、Meta或指南等可用证据类型；T2=病例、非临床或主题权重不足。"},
        {"Item": "O1/O2", "Description": "O1=有UAS相关安全性/性能/有效性结局；O2=未见明确相关结局。"},
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
