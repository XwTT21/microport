from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CACHE_JSON = ROOT / "outputs" / "literature_screening" / "screening_data.json"
OUTPUT_DIR = ROOT / "outputs" / "single_use_ureteroscope_screening"
OUTPUT_JSON = OUTPUT_DIR / "single_use_ureteroscope_screening_data.json"


EXCLUSION_REASONS_CN = {
    "S1": "未见single-use/disposable ureteroscope或等同一次性输尿管镜作为研究主题",
    "S2": "一次性输尿管镜仅在背景、方法常规步骤或正文中顺带出现，主题权重不足",
    "S3": "主要研究对象为UAS、PCNL、ESWL、激光、取石篮、支架、药物、影像预测模型或其他非一次性输尿管镜主题",
    "S4": "产品文献目录记录，按本轮范围不纳入筛选",
    "S5": "文献不可读、题录缺失或关键信息不足，需人工确认",
    "S6": "主题虽属URS/RIRS/FURS，但缺少一次性输尿管镜相关安全性、性能、有效性或资源结局",
}


CORE_SCOPE_PATTERNS = [
    r"\bsingle[- ]use(?: digital)?(?: flexible)? ureteroscope(?:s)?\b",
    r"\bsingle[- ]use(?: digital)?(?: flexible)? ureterorenoscope(?:s)?\b",
    r"\bsingle[- ]use(?: digital)?(?: flexible)? f[- ]?URS\b",
    r"\bdisposable(?: digital)?(?: flexible)? ureteroscope(?:s)?\b",
    r"\bdisposable(?: digital)?(?: flexible)? ureterorenoscope(?:s)?\b",
    r"\bdisposable(?: digital)?(?: flexible)? f[- ]?URS\b",
    r"\bdigital disposable ureteroscope(?:s)?\b",
    r"\breusable (?:and|vs\.?|versus) single[- ]use ureteroscope(?:s)?\b",
    r"\bsingle[- ]use (?:and|vs\.?|versus) reusable ureteroscope(?:s)?\b",
    r"\breusable (?:and|vs\.?|versus) disposable ureteroscope(?:s)?\b",
    r"\bdisposable (?:and|vs\.?|versus) reusable ureteroscope(?:s)?\b",
    r"\buse of (?:a )?disposable flexible ureteroscope\b",
    r"\btreated with (?:a )?single[- ]use ureteroscope\b",
    r"\btreated with (?:a )?disposable flexible ureteroscope\b",
    r"一次性.{0,8}输尿管镜",
    r"可抛弃.{0,8}输尿管镜",
    r"单次使用.{0,8}输尿管镜",
]

WEAK_SCOPE_PATTERNS = [
    r"\bsingle[- ]use(?: digital)?(?: flexible)? scope(?:s)?\b",
    r"\bdisposable(?: digital)?(?: flexible)? scope(?:s)?\b",
    r"\breusable (?:and|vs\.?|versus) single[- ]use\b",
    r"\bsingle[- ]use (?:and|vs\.?|versus) reusable\b",
]

URO_CONTEXT_PATTERNS = [
    r"ureteroscope",
    r"ureteroscopic",
    r"ureteroscopy",
    r"ureterorenoscope",
    r"ureterorenoscopy",
    r"flexible ureteroscop",
    r"retrograde intrarenal surgery",
    r"\bRIRS\b",
    r"\bFURS\b",
    r"renal stone",
    r"kidney stone",
    r"upper urinary tract calcul",
    r"urolithiasis",
    r"renal calcul",
    r"ureteral calcul",
    r"ureteric calcul",
    r"lithotripsy",
]

OUTCOME_PATTERNS = [
    r"stone[- ]free",
    r"\bSFR\b",
    r"complication",
    r"safety",
    r"efficacy",
    r"effectiveness",
    r"operative time",
    r"procedure time",
    r"surgery duration",
    r"intrarenal pressure",
    r"renal pelvic pressure",
    r"irrigation",
    r"flow rate",
    r"image quality",
    r"deflection",
    r"scope failure",
    r"device failure",
    r"access success",
    r"conversion",
    r"usability",
    r"infection",
    r"sepsis",
    r"\bSIRS\b",
    r"fever",
    r"ureteral injury",
    r"access failure",
    r"success rate",
    r"hospitali[sz]ation",
    r"readmission",
    r"hospital stay",
    r"adverse event",
    r"pain",
    r"repair",
    r"sterili[sz]ation",
    r"contamination",
    r"cross[- ]infection",
    r"cost",
    r"resource",
    r"environment",
    r"carbon footprint",
]

ECONOMIC_PATTERNS = [
    r"cost",
    r"economic",
    r"cost[- ]effectiveness",
    r"repair",
    r"maintenance",
    r"sterili[sz]ation",
    r"workflow",
    r"resource",
    r"environment",
    r"carbon footprint",
    r"life cycle",
]

NON_CLINICAL_PATTERNS = [
    r"in vitro",
    r"ex vivo",
    r"bench",
    r"phantom",
    r"simulator",
    r"training",
    r"3d[- ]printed",
    r"simulation model",
    r"porcine",
    r"animal",
    r"mechanical",
    r"optical",
    r"deflection",
    r"irrigation flow",
]

OTHER_DEVICE_PATTERNS = [
    r"ureteral access sheath",
    r"ureteric access sheath",
    r"\bUAS\b",
    r"suction(?:ing)? ureteral access sheath",
    r"mini[- ]percutaneous nephrolithotomy",
    r"percutaneous nephrolithotomy",
    r"\bPCNL\b",
    r"shock wave lithotripsy",
    r"\bESWL\b",
    r"holmium laser",
    r"thulium fiber laser",
    r"basket",
    r"stone cone",
    r"ureteral stent",
    r"ureteric stent",
    r"double[- ]?j",
    r"cystoscope",
    r"cystoscopy",
    r"prediction model",
    r"machine learning",
]


def clean_text(text: str) -> str:
    text = text or ""
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def is_product_path(text: str) -> bool:
    return "产品" in (text or "")


def normalize_title(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"\.pdf$", "", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w not in {"a", "an", "the", "and", "or", "of", "in", "to", "for", "with"}]
    return " ".join(words)


def title_similarity(a: str, b: str) -> float:
    na = normalize_title(a)
    nb = normalize_title(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta = set(na.split())
    tb = set(nb.split())
    token_score = (2 * len(ta & tb) / (len(ta) + len(tb))) if ta and tb else 0.0
    return max(seq, token_score)


def select_pubmed_record(pdf: dict[str, Any], pubmed_records: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    candidates = [
        r
        for r in pubmed_records
        if r.get("search_batch") == pdf.get("search_batch") and r.get("search_folder") == pdf.get("search_folder")
    ]
    if not candidates:
        candidates = pubmed_records

    pdf_title = clean_text(" ".join([pdf.get("file_stem", ""), pdf.get("pdf_title", "")]))
    pdf_norm = normalize_title(pdf_title)
    best: dict[str, Any] | None = None
    best_score = 0.0
    best_overlap = 0.0
    pdf_tokens = set(pdf_norm.split())
    for rec in candidates:
        title = rec.get("title", "")
        score = title_similarity(pdf_title, title)
        rec_tokens = set(normalize_title(title).split())
        overlap = (len(pdf_tokens & rec_tokens) / max(1, min(len(pdf_tokens), len(rec_tokens)))) if pdf_tokens and rec_tokens else 0.0
        combined = max(score, overlap * 0.95)
        if combined > best_score:
            best = rec
            best_score = combined
            best_overlap = overlap

    if not best:
        return None, 0.0
    if best_score >= 0.82 and best_overlap >= 0.55:
        return best, round(best_score, 3)
    if best_score >= 0.92 and len(pdf_tokens & set(normalize_title(best.get("title", "")).split())) >= 5:
        return best, round(best_score, 3)
    return None, round(best_score, 3)


def any_re(patterns: list[str], text: str) -> bool:
    return any(re.search(p, text, flags=re.I) for p in patterns)


def first_re(patterns: list[str], text: str) -> str:
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return m.group(0)
    return ""


def count_re(patterns: list[str], text: str) -> int:
    total = 0
    for p in patterns:
        total += len(re.findall(p, text, flags=re.I))
    return total


def sentence_with(text: str, patterns: list[str]) -> str:
    text = clean_text(text)
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?。；;])\s+", text)
    for sent in sentences:
        if any_re(patterns, sent):
            return sent[:700]
    return text[:500]


def study_type(title_abstract: str, full_text: str) -> str:
    ta = title_abstract.lower()
    full = full_text.lower()
    if re.search(r"systematic review|meta-analysis|meta analysis", ta):
        return "Systematic review / Meta-analysis"
    if re.search(r"guideline|recommendation|consensus", ta):
        return "Guideline / Recommendation"
    if re.search(r"narrative review|comprehensive review|current evidence|update and perspective|review of", ta):
        return "Narrative review"
    if re.search(r"case report", ta):
        return "Case report"
    if any_re(NON_CLINICAL_PATTERNS, ta):
        return "Non-clinical / bench"
    if re.search(r"randomi[sz]ed|randomised|randomized|prospective", full):
        return "Clinical original - prospective/RCT"
    if re.search(r"retrospective|cohort|case-control|case control|observational|cross-sectional", full):
        return "Clinical original - retrospective/observational"
    if any_re(ECONOMIC_PATTERNS, ta):
        return "Economic/resource study"
    if re.search(r"review", ta):
        return "Narrative review"
    return "Clinical/technical study - unspecified"


def source_key(pdf: dict[str, Any], pubmed: dict[str, Any] | None) -> str:
    if pubmed:
        if pubmed.get("doi"):
            return "doi:" + pubmed["doi"].lower()
        if pubmed.get("pmid"):
            return "pmid:" + pubmed["pmid"]
        if pubmed.get("title"):
            return "title:" + normalize_title(pubmed["title"])[:140]
    title = pdf.get("pdf_title") or pdf.get("file_stem") or pdf.get("file_name")
    return "title:" + normalize_title(title)[:140]


def classify(pdf: dict[str, Any], pubmed: dict[str, Any] | None) -> dict[str, str]:
    title = clean_text((pubmed or {}).get("title") or pdf.get("pdf_title") or pdf.get("file_stem") or "")
    if title.lower() in {"untitled", ""}:
        title = clean_text(pdf.get("file_stem") or title)
    abstract = clean_text((pubmed or {}).get("abstract", ""))
    file_title = clean_text(" ".join([pdf.get("file_stem", ""), pdf.get("pdf_title", "")]))
    front_text = clean_text(" ".join([title, file_title, abstract, pdf.get("pdf_text_excerpt", "")[:12000]]))
    title_text = clean_text(" ".join([title, file_title]))
    title_abstract = clean_text(" ".join([title, file_title, abstract]))
    full_text = clean_text(" ".join([front_text, pdf.get("pdf_text_excerpt", "")]))

    core_in_title = any_re(CORE_SCOPE_PATTERNS, title_text)
    weak_in_title = any_re(WEAK_SCOPE_PATTERNS, title_text) and any_re(URO_CONTEXT_PATTERNS, title_text + " " + title_abstract)
    core_in_abstract = any_re(CORE_SCOPE_PATTERNS, title_abstract)
    weak_in_abstract = any_re(WEAK_SCOPE_PATTERNS, title_abstract) and any_re(URO_CONTEXT_PATTERNS, title_abstract)
    core_anywhere = any_re(CORE_SCOPE_PATTERNS, full_text)
    weak_anywhere = any_re(WEAK_SCOPE_PATTERNS, full_text) and any_re(URO_CONTEXT_PATTERNS, full_text)
    scope_hits_front = count_re(CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS, title_abstract)
    scope_hits_full = count_re(CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS, full_text)
    outcome_hit = first_re(OUTCOME_PATTERNS, title_abstract + " " + pdf.get("pdf_text_excerpt", "")[:20000])
    scope_hit = first_re(CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS, title_abstract + " " + full_text[:20000])
    context_hit = first_re(URO_CONTEXT_PATTERNS, title_abstract + " " + full_text[:20000])
    other = first_re(OTHER_DEVICE_PATTERNS, title_abstract)
    type_label = study_type(title_abstract, full_text)
    text_status = pdf.get("pdf_text_status", "")

    if text_status.startswith("read_error") or text_status in {"no_text", "low_text"}:
        if not title_abstract:
            return {
                "Decision": "待人工确认",
                "Inclusion_Class": "",
                "Exclusion_Code": "S5",
                "Exclusion_Reason_CN": EXCLUSION_REASONS_CN["S5"],
                "Study_Type": type_label,
                "Single_Use_Ureteroscope_Relevance": "PDF不可读且缺少可用题录",
                "Single_Use_Ureteroscope_Device_or_Technique": "",
                "Clinical_Context": "",
                "Outcome_Data": "",
                "Screening_Level": "PDF读取质量控制",
                "Evidence_Sentence": text_status,
                "Notes": "需人工打开PDF确认。",
            }

    if not (core_anywhere or weak_anywhere):
        return {
            "Decision": "排除",
            "Inclusion_Class": "",
            "Exclusion_Code": "S3" if other else "S1",
            "Exclusion_Reason_CN": EXCLUSION_REASONS_CN["S3" if other else "S1"],
            "Study_Type": type_label,
            "Single_Use_Ureteroscope_Relevance": "未见一次性/可抛弃输尿管镜主题词",
            "Single_Use_Ureteroscope_Device_or_Technique": other,
            "Clinical_Context": context_hit,
            "Outcome_Data": "",
            "Screening_Level": "题名/摘要/全文关键词初筛",
            "Evidence_Sentence": sentence_with(title_abstract or full_text, OTHER_DEVICE_PATTERNS + URO_CONTEXT_PATTERNS),
            "Notes": "",
        }

    direct_title_topic = core_in_title or weak_in_title
    broader_abstract_topic = core_in_abstract or weak_in_abstract

    if not (direct_title_topic or broader_abstract_topic):
        if scope_hits_full >= 2 and outcome_hit:
            return {
                "Decision": "待人工确认",
                "Inclusion_Class": "Single-use ureteroscope incidental mention - verify",
                "Exclusion_Code": "",
                "Exclusion_Reason_CN": "",
                "Study_Type": type_label,
                "Single_Use_Ureteroscope_Relevance": "全文中出现一次性输尿管镜，但题名/摘要未显示为研究核心",
                "Single_Use_Ureteroscope_Device_or_Technique": scope_hit,
                "Clinical_Context": context_hit,
                "Outcome_Data": outcome_hit,
                "Screening_Level": "全文关键词提示相关，需人工确认主题权重",
                "Evidence_Sentence": sentence_with(full_text, CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS + OUTCOME_PATTERNS),
                "Notes": "可能仅为方法中使用的器械，需核对是否为研究问题。",
            }
        return {
            "Decision": "排除",
            "Inclusion_Class": "",
            "Exclusion_Code": "S2",
            "Exclusion_Reason_CN": EXCLUSION_REASONS_CN["S2"],
            "Study_Type": type_label,
            "Single_Use_Ureteroscope_Relevance": "一次性输尿管镜仅在全文中出现，题名/摘要未显示为研究核心",
            "Single_Use_Ureteroscope_Device_or_Technique": scope_hit,
            "Clinical_Context": context_hit,
            "Outcome_Data": outcome_hit,
            "Screening_Level": "全文关键词核对",
            "Evidence_Sentence": sentence_with(full_text, CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS),
            "Notes": "",
        }

    if not direct_title_topic and scope_hits_front < 2:
        return {
            "Decision": "待人工确认",
            "Inclusion_Class": "Single-use ureteroscope broad topic - verify",
            "Exclusion_Code": "",
            "Exclusion_Reason_CN": "",
            "Study_Type": type_label,
            "Single_Use_Ureteroscope_Relevance": "摘要提示一次性输尿管镜相关，但题名主题较宽",
            "Single_Use_Ureteroscope_Device_or_Technique": scope_hit,
            "Clinical_Context": context_hit,
            "Outcome_Data": outcome_hit,
            "Screening_Level": "题名主题较宽，需人工确认是否保留",
            "Evidence_Sentence": sentence_with(title_abstract + " " + full_text[:12000], CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS),
            "Notes": "",
        }

    if any_re(NON_CLINICAL_PATTERNS, title_abstract) and not re.search(r"clinical|patient|retrospective|prospective", title_abstract, flags=re.I):
        return {
            "Decision": "纳入",
            "Inclusion_Class": "Single-use ureteroscope technical evidence",
            "Exclusion_Code": "",
            "Exclusion_Reason_CN": "",
            "Study_Type": type_label,
            "Single_Use_Ureteroscope_Relevance": "一次性输尿管镜为核心主题，研究类型偏体外/工程/性能测试",
            "Single_Use_Ureteroscope_Device_or_Technique": scope_hit,
            "Clinical_Context": context_hit,
            "Outcome_Data": outcome_hit,
            "Screening_Level": "题名/摘要初筛",
            "Evidence_Sentence": sentence_with(title_abstract, CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS + NON_CLINICAL_PATTERNS),
            "Notes": "非临床证据，作为技术支持数据分层。",
        }

    if not outcome_hit:
        return {
            "Decision": "待人工确认",
            "Inclusion_Class": "Single-use ureteroscope topic - outcome unclear",
            "Exclusion_Code": "",
            "Exclusion_Reason_CN": "",
            "Study_Type": type_label,
            "Single_Use_Ureteroscope_Relevance": "一次性输尿管镜为主题，但自动抽取未见明确安全/性能/有效性/资源结局词",
            "Single_Use_Ureteroscope_Device_or_Technique": scope_hit,
            "Clinical_Context": context_hit,
            "Outcome_Data": "",
            "Screening_Level": "题名/摘要初筛",
            "Evidence_Sentence": sentence_with(title_abstract, CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS),
            "Notes": "需人工确认全文结局指标。",
        }

    inclusion_class = "Single-use ureteroscope core clinical evidence"
    if any_re(ECONOMIC_PATTERNS, title_abstract):
        inclusion_class = "Single-use ureteroscope economic/resource evidence"
    elif "review" in type_label.lower() or "guideline" in type_label.lower() or "recommendation" in type_label.lower():
        inclusion_class = "Single-use ureteroscope secondary evidence"
    elif "case report" in type_label.lower():
        inclusion_class = "Single-use ureteroscope case evidence"

    return {
        "Decision": "纳入",
        "Inclusion_Class": inclusion_class,
        "Exclusion_Code": "",
        "Exclusion_Reason_CN": "",
        "Study_Type": type_label,
        "Single_Use_Ureteroscope_Relevance": "一次性/可抛弃输尿管镜为题名/摘要核心主题",
        "Single_Use_Ureteroscope_Device_or_Technique": scope_hit,
        "Clinical_Context": context_hit,
        "Outcome_Data": outcome_hit,
        "Screening_Level": "题名/摘要初筛+全文关键词核对",
        "Evidence_Sentence": sentence_with(title_abstract + " " + full_text[:20000], CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS + OUTCOME_PATTERNS),
        "Notes": "",
    }


@dataclass
class OutputRecord:
    Record_ID: str
    Decision: str
    Inclusion_Class: str
    Exclusion_Code: str
    Exclusion_Reason_CN: str
    Title: str
    Authors: str
    Journal: str
    Year: str
    DOI: str
    PMID: str
    Study_Type: str
    Single_Use_Ureteroscope_Relevance: str
    Single_Use_Ureteroscope_Device_or_Technique: str
    Clinical_Context: str
    Outcome_Data: str
    Source_Database: str
    Search_Batch: str
    Search_Folder: str
    PDF_Path: str
    PubMed_TXT_Source: str
    Duplicate_Group_ID: str
    Screening_Level: str
    Evidence_Sentence: str
    All_Sources: str
    All_PDF_Paths: str
    Text_Status: str
    PubMed_Match_Score: float
    Notes: str


def counts(values: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value or "(blank)"] = out.get(value or "(blank)", 0) + 1
    return dict(sorted(out.items()))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
    all_pdfs = data["pdf_manifest"]
    all_pubmed_records = data["pubmed_records"]
    pdfs = [p for p in all_pdfs if not is_product_path(p.get("pdf_path", "")) and not is_product_path(p.get("search_folder", ""))]
    pubmed_records = [
        r
        for r in all_pubmed_records
        if not is_product_path(r.get("source_txt", "")) and not is_product_path(r.get("search_folder", ""))
    ]

    groups: dict[str, list[tuple[dict[str, Any], dict[str, Any] | None]]] = {}
    for pdf in pdfs:
        pub, match_score = select_pubmed_record(pdf, pubmed_records)
        pdf["single_use_pubmed_match_score"] = match_score
        key = source_key(pdf, pub)
        groups.setdefault(key, []).append((pdf, pub))

    records: list[OutputRecord] = []
    duplicates: list[dict[str, Any]] = []
    for group_no, (key, items) in enumerate(sorted(groups.items()), start=1):
        dup_id = f"DUP-SUU-{group_no:04d}" if len(items) > 1 else ""
        items_sorted = sorted(
            items,
            key=lambda x: (
                0 if x[1] else 1,
                0 if x[0].get("pdf_text_status") == "readable" else 1,
                0 if x[0].get("search_batch") == "二次搜索(24-26.6)" else 1,
                x[0].get("pdf_path", "").lower(),
            ),
        )
        primary_pdf, primary_pub = items_sorted[0]
        cls = classify(primary_pdf, primary_pub)
        title = clean_text((primary_pub or {}).get("title") or primary_pdf.get("pdf_title") or primary_pdf.get("file_stem") or "")
        if title.lower() in {"untitled", ""}:
            title = clean_text(primary_pdf.get("file_stem", ""))
        all_sources = sorted({f"{p.get('source_database','')}/{p.get('search_batch','')}/{p.get('search_folder','')}" for p, _ in items})
        all_paths = sorted({p.get("pdf_path", "") for p, _ in items})
        if len(items) > 1:
            for p, pub in items:
                duplicates.append(
                    {
                        "Duplicate_Group_ID": dup_id,
                        "Duplicate_Key": key,
                        "Title": clean_text((pub or {}).get("title") or p.get("pdf_title") or p.get("file_stem") or ""),
                        "DOI": (pub or {}).get("doi", ""),
                        "PMID": (pub or {}).get("pmid", ""),
                        "Source_Database": p.get("source_database", ""),
                        "Search_Batch": p.get("search_batch", ""),
                        "Search_Folder": p.get("search_folder", ""),
                        "PDF_Path": p.get("pdf_path", ""),
                        "SHA1": p.get("sha1", ""),
                        "Kept_As_Primary": "Yes" if p.get("pdf_path") == primary_pdf.get("pdf_path") else "No",
                    }
                )
        records.append(
            OutputRecord(
                Record_ID=f"SUU{len(records)+1:04d}",
                Decision=cls["Decision"],
                Inclusion_Class=cls["Inclusion_Class"],
                Exclusion_Code=cls["Exclusion_Code"],
                Exclusion_Reason_CN=cls["Exclusion_Reason_CN"],
                Title=title,
                Authors=clean_text((primary_pub or {}).get("authors", "")),
                Journal=clean_text((primary_pub or {}).get("journal", "")),
                Year=(primary_pub or {}).get("year", "") or primary_pdf.get("pdf_year", ""),
                DOI=(primary_pub or {}).get("doi", ""),
                PMID=(primary_pub or {}).get("pmid", ""),
                Study_Type=cls["Study_Type"],
                Single_Use_Ureteroscope_Relevance=cls["Single_Use_Ureteroscope_Relevance"],
                Single_Use_Ureteroscope_Device_or_Technique=cls["Single_Use_Ureteroscope_Device_or_Technique"],
                Clinical_Context=cls["Clinical_Context"],
                Outcome_Data=cls["Outcome_Data"],
                Source_Database=primary_pdf.get("source_database", ""),
                Search_Batch=primary_pdf.get("search_batch", ""),
                Search_Folder=primary_pdf.get("search_folder", ""),
                PDF_Path=primary_pdf.get("pdf_path", ""),
                PubMed_TXT_Source=clean_text((primary_pub or {}).get("source_txt", "")),
                Duplicate_Group_ID=dup_id,
                Screening_Level=cls["Screening_Level"],
                Evidence_Sentence=cls["Evidence_Sentence"],
                All_Sources=" | ".join(all_sources),
                All_PDF_Paths=" | ".join(all_paths),
                Text_Status=primary_pdf.get("pdf_text_status", ""),
                PubMed_Match_Score=primary_pdf.get("single_use_pubmed_match_score", 0.0),
                Notes=cls["Notes"],
            )
        )

    matched_pubmed = {pub["record_key"] for _, items in groups.items() for _, pub in items if pub}
    unmatched_pubmed = []
    for rec in pubmed_records:
        if rec["record_key"] not in matched_pubmed:
            text = rec["title"] + " " + rec["abstract"]
            unmatched_pubmed.append(
                {
                    "Source_TXT": rec["source_txt"],
                    "Search_Batch": rec["search_batch"],
                    "Search_Folder": rec["search_folder"],
                    "Index": rec["txt_index"],
                    "Title": rec["title"],
                    "Year": rec["year"],
                    "DOI": rec["doi"],
                    "PMID": rec["pmid"],
                    "Potential_Single_Use_Ureteroscope": "Yes"
                    if any_re(CORE_SCOPE_PATTERNS + WEAK_SCOPE_PATTERNS, text) and any_re(URO_CONTEXT_PATTERNS, text)
                    else "No",
                    "Reason": "PubMed题录未匹配到本地PDF，未进入PDF筛选总表",
                }
            )

    decision_counts = counts([r.Decision for r in records])
    summary = {
        "cache_pdf_count": len(all_pdfs),
        "pdf_count": len(pdfs),
        "product_pdf_excluded_count": len(all_pdfs) - len(pdfs),
        "screened_unique_count": len(records),
        "pubmed_txt_record_count": len(pubmed_records),
        "product_pubmed_excluded_count": len(all_pubmed_records) - len(pubmed_records),
        "decision_counts": decision_counts,
        "inclusion_class_counts": counts([r.Inclusion_Class for r in records if r.Decision == "纳入"]),
        "study_type_counts_included": counts([r.Study_Type for r in records if r.Decision == "纳入"]),
        "exclusion_counts": counts([r.Exclusion_Code for r in records if r.Decision == "排除"]),
        "pending_count": sum(1 for r in records if r.Decision == "待人工确认"),
        "duplicate_group_count": len({d["Duplicate_Group_ID"] for d in duplicates}),
        "duplicate_row_count": len(duplicates),
        "unmatched_pubmed_count": len(unmatched_pubmed),
        "potential_single_use_ureteroscope_unmatched_pubmed_count": sum(
            1 for r in unmatched_pubmed if r["Potential_Single_Use_Ureteroscope"] == "Yes"
        ),
        "source_counts": counts([r.Source_Database for r in records]),
    }

    criteria_entries = [
        {"Item": "筛选主题", "Description": "以single-use/disposable ureteroscope、single-use/disposable flexible ureteroscope、single-use/disposable ureterorenoscope、reusable vs single-use ureteroscope、digital disposable ureteroscope及中文同义词为核心主题。"},
        {"Item": "产品文献处理", "Description": "任何路径或检索文件夹含“产品”的PDF和PubMed题录均在输入阶段排除，不纳入筛选总表。"},
        {"Item": "DOCX用途", "Description": "筛选.docx仅作为筛选流程和表格结构参考，不沿用Double-J支架主题纳排标准。"},
        {"Item": "纳入逻辑", "Description": "题名或摘要显示一次性/可抛弃/单次使用输尿管镜为研究对象、干预、对照、器械、技术平台或主要临床问题，并报告安全性、性能、有效性、资源或经济学相关结局。"},
        {"Item": "排除逻辑", "Description": "UAS-only、激光、PCNL、ESWL、取石篮、支架、药物、影像预测模型等主题，且一次性输尿管镜不是核心问题者排除。"},
        {"Item": "待确认逻辑", "Description": "PDF/题录质量不足、题名主题较宽、仅全文提示相关或结局指标自动抽取不充分者进入待人工确认。"},
    ]
    for code, reason in EXCLUSION_REASONS_CN.items():
        criteria_entries.append({"Item": code, "Description": reason})
    criteria_entries.extend(
        [
            {"Item": f"DOCX reference {i+1}", "Description": e.get("text", "")}
            for i, e in enumerate(data.get("docx", {}).get("relevant_entries", [])[:60])
        ]
    )

    output = {
        "summary": summary,
        "records": [asdict(r) for r in records],
        "included": [asdict(r) for r in records if r.Decision == "纳入"],
        "excluded": [asdict(r) for r in records if r.Decision == "排除"],
        "pending": [asdict(r) for r in records if r.Decision == "待人工确认"],
        "duplicates": duplicates,
        "unmatched_pubmed": unmatched_pubmed,
        "criteria": criteria_entries,
        "source_cache": str(CACHE_JSON),
    }
    OUTPUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
