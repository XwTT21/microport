from __future__ import annotations

import hashlib
import html
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs" / "literature_screening"
DOCX_PATH = ROOT / "筛选.docx"

INCLUDED_TOP_LEVELS = {"Cochrane", "Google Scholar", "PubMed", "文献2次搜索(24-26.6)"}
EXCLUDED_TOP_LEVELS = {"产品文献"}


EXCLUSION_REASONS_CN = {
    "E1": "文献不可获取、非英文、病例报告、protocol、系统综述、meta分析或非原始数据",
    "E2": "受试者基础疾病不是输尿管疾病或输尿管梗阻",
    "E3": "基础机制研究、动物实验或不反映临床价值",
    "E4": "输尿管支架未用于治疗输尿管疾病或梗阻",
    "E5": "器械或预期用途不符，如金属支架、输尿镜/鞘/碎石等不同器械或手术策略研究",
    "E6": "缺少DJ/输尿管支架相关安全性或性能结局，或为经济学/卫生保健研究",
}


INCLUSION_TERMS = [
    "double j",
    "double-j",
    "dj stent",
    "jj stent",
    "double pigtail",
    "double-pigtail",
    "ureteral stent",
    "ureteric stent",
    "ureter stent",
    "ureteral catheter stent",
    "indwelling ureteral stent",
]

WEAK_STENT_TERMS = [
    "stent",
    "stents",
    "stented",
    "stenting",
]

CONDITION_TERMS = [
    "ureteral obstruction",
    "ureteric obstruction",
    "ureter obstruction",
    "obstructive uropathy",
    "obstructive pyelonephritis",
    "hydronephrosis",
    "ureteral disease",
    "ureteric disease",
    "ureteral calcul",
    "ureteric calcul",
    "ureterolithiasis",
    "urolithiasis",
    "urinary stone",
    "urinary calcul",
    "renal calcul",
    "kidney stone",
    "upper urinary tract stone",
    "upjo",
    "ureteropelvic junction obstruction",
    "ureteral stricture",
    "ureteric stricture",
    "ureteral injury",
    "ureteric injury",
    "malignant ureteral obstruction",
    "transplant ureter",
]

OUTCOME_TERMS = [
    "safety",
    "performance",
    "complication",
    "adverse",
    "infection",
    "uti",
    "pain",
    "symptom",
    "quality of life",
    "qol",
    "ussq",
    "encrustation",
    "biofilm",
    "migration",
    "dislodgement",
    "patency",
    "drainage",
    "obstruction",
    "failure",
    "success",
    "hematuria",
    "haematuria",
    "irritative",
    "tolerability",
    "morbidity",
]

NON_ORIGINAL_TERMS = [
    "systematic review",
    "meta-analysis",
    "metaanalysis",
    "narrative review",
    "scoping review",
    "review and meta",
    "bibliometric",
    "guideline",
    "guidelines",
    "consensus",
    "protocol",
    "case report",
    "case reports",
    "letter to",
    "editorial",
    "commentary",
    "abstracts of",
    "congress",
    "conference abstract",
    "current status and future perspective",
    "update and perspective",
    "an update",
]

NON_CLINICAL_TERMS = [
    "in vitro",
    "ex vivo",
    "bench",
    "phantom",
    "simulator",
    "simulation",
    "training model",
    "3d printed",
    "animal",
    "porcine",
    "swine",
    "canine",
    "rat ",
    "mice",
]

DIFFERENT_DEVICE_TERMS = [
    "ureteroscope",
    "ureteroscopes",
    "ureteroscopy",
    "ureterorenoscopy",
    "retrograde intrarenal surgery",
    "rirs",
    "percutaneous nephrolithotomy",
    "pcnl",
    "mini-percutaneous",
    "shock wave lithotripsy",
    "shockwave lithotripsy",
    "swl",
    "eswl",
    "laser lithotripsy",
    "holmium laser",
    "thulium fiber laser",
    "ureteral access sheath",
    "ureteric access sheath",
    "access sheath",
    "suction sheath",
    "basket",
    "fragmentation",
    "dusting",
]

OUT_OF_SCOPE_STENT_FOCUS = [
    "stent removal",
    "removal string",
    "stent string",
    "extraction string",
    "sexual",
    "cost-effectiveness",
    "cost effectiveness",
    "economic",
    "healthcare cost",
    "health care cost",
    "hospital encounters",
    "consultations and surgeries",
]

METALLIC_STENT_TERMS = [
    "metallic stent",
    "metal stent",
    "resonance stent",
    "self-expanding",
]


@dataclass
class PubMedRecord:
    record_key: str
    source_txt: str
    source_database: str
    search_batch: str
    search_folder: str
    txt_index: int
    title: str
    authors: str
    journal: str
    year: str
    doi: str
    pmid: str
    citation: str
    abstract: str
    raw_record: str


@dataclass
class PdfRecord:
    source_database: str
    search_batch: str
    search_folder: str
    pdf_path: str
    file_name: str
    file_stem: str
    size_bytes: int
    sha1: str
    pdf_title: str = ""
    pdf_year: str = ""
    pdf_text_excerpt: str = ""
    pdf_text_status: str = ""
    pdf_page_count: int = 0
    matched_pubmed_key: str = ""
    matched_pubmed_score: float = 0.0


@dataclass
class ScreenedRecord:
    record_id: str
    decision: str
    dataset_type: str
    exclusion_code: str
    exclusion_reason_cn: str
    title: str
    authors: str
    journal: str
    year: str
    doi: str
    pmid: str
    source_database: str
    search_batch: str
    search_folder: str
    pdf_path: str
    pubmed_txt_source: str
    duplicate_group_id: str
    screening_level: str
    evidence_sentence: str
    device_relevance: str
    patient_condition: str
    outcome_data: str
    D: str = ""
    A: str = ""
    P: str = ""
    R: str = ""
    T: str = ""
    O: str = ""
    S: str = ""
    C: str = ""
    all_sources: str = ""
    all_pdf_paths: str = ""
    text_status: str = ""
    notes: str = ""


def clean_text(text: str) -> str:
    text = html.unescape(text)
    text = text.replace("\x00", " ")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_title(text: str) -> str:
    text = clean_text(text).lower()
    text = text.replace("≤", " less than or equal ")
    text = text.replace("≥", " greater than or equal ")
    text = re.sub(r"\.pdf$", "", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w not in {"a", "an", "the", "and", "or", "of", "in", "to", "for"}]
    return " ".join(words)


def token_set(text: str) -> set[str]:
    return {w for w in normalize_title(text).split() if len(w) > 2}


def has_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term in lower for term in terms)


def first_hit(text: str, terms: list[str]) -> str:
    lower = text.lower()
    for term in terms:
        if term in lower:
            return term
    return ""


def source_parts(relative_pdf: str) -> tuple[str, str, str]:
    parts = Path(relative_pdf).parts
    if parts[0] == "文献2次搜索(24-26.6)":
        source_database = parts[1] if len(parts) > 1 else ""
        search_batch = "二次搜索(24-26.6)"
        search_folder = parts[2] if len(parts) > 2 else ""
    else:
        source_database = parts[0] if parts else ""
        search_batch = "首次搜索"
        search_folder = parts[1] if len(parts) > 1 else ""
    return source_database, search_batch, search_folder


def open_path(path: Path, mode: str = "rb"):
    abs_path = str(path.resolve())
    if os.name == "nt" and not abs_path.startswith("\\\\?\\"):
        abs_path = "\\\\?\\" + abs_path
    return open(abs_path, mode)


def extract_docx_text() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    media_entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(DOCX_PATH) as zf:
        for info in zf.infolist():
            if info.filename.startswith("word/media/"):
                media_entries.append({"name": info.filename, "size": info.file_size})

        text_parts: list[str] = []
        for name in ["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]:
            try:
                xml = zf.read(name).decode("utf-8", errors="ignore")
            except KeyError:
                continue
            xml = re.sub(r"<w:tab\s*/>", "\t", xml)
            xml = re.sub(r"</w:(?:p|tr)>", "\n", xml)
            xml = re.sub(r"</w:tc>", "\t", xml)
            text = re.sub(r"<[^>]+>", "", xml)
            text_parts.append(html.unescape(text))

    full_text = clean_text("\n".join(text_parts))
    raw_lines = [clean_text(line) for line in re.split(r"[\r\n]+", "\n".join(text_parts))]
    lines = [line for line in raw_lines if line]
    keywords = [
        "Inclusion",
        "Exclusion",
        "Selection criteria",
        "E1",
        "E2",
        "E3",
        "E4",
        "E5",
        "E6",
        "Data screened",
        "Full text",
        "Final inclusion",
        "Duplicate",
        "Appraisal",
        "D1",
        "D2",
        "D3",
        "A1",
        "A2",
        "A3",
        "P1",
        "P2",
        "P3",
        "R1",
        "R2",
        "R3",
        "T1",
        "T2",
        "O1",
        "O2",
        "S1",
        "S2",
        "C1",
        "C2",
    ]
    for idx, line in enumerate(lines, start=1):
        if any(k.lower() in line.lower() for k in keywords):
            entries.append({"line_no": idx, "text": line[:3000]})

    return {
        "docx_path": str(DOCX_PATH),
        "media_entries": media_entries,
        "media_count": len(media_entries),
        "relevant_entries": entries,
        "full_text_excerpt": full_text[:20000],
        "extraction_note": "DOCX package has no word/media entries; screening flow text was extracted from Word XML text/shape content.",
    }


def parse_pubmed_records() -> list[PubMedRecord]:
    records: list[PubMedRecord] = []
    txt_files = [
        p
        for p in ROOT.rglob("*.txt")
        if p.name != "检索词.txt"
        and "产品文献" not in p.parts
        and ("PubMed" in p.parts)
    ]
    for txt_path in sorted(txt_files):
        rel = txt_path.relative_to(ROOT)
        source_database, search_batch, search_folder = source_parts(str(rel))
        text = txt_path.read_text(encoding="utf-8", errors="replace")
        chunks = re.split(r"(?m)(?=^\d+\.\s+)", text)
        for chunk in chunks:
            chunk = chunk.strip()
            if not re.match(r"^\d+\.\s+", chunk):
                continue
            m_idx = re.match(r"^(\d+)\.\s+", chunk)
            txt_index = int(m_idx.group(1)) if m_idx else 0
            blocks = [b.strip() for b in re.split(r"\n\s*\n", chunk) if b.strip()]
            citation = clean_text(blocks[0]) if blocks else ""
            title = clean_text(blocks[1]) if len(blocks) > 1 else ""
            authors = clean_text(blocks[2]) if len(blocks) > 2 else ""
            doi_match = re.search(r"DOI:\s*([^\s\]]+)", chunk, flags=re.I) or re.search(r"\bdoi:\s*([^\s\]]+)", chunk, flags=re.I)
            doi = doi_match.group(1).strip(" .;") if doi_match else ""
            pmid_match = re.search(r"PMID:\s*(\d+)", chunk, flags=re.I)
            pmid = pmid_match.group(1) if pmid_match else ""
            year_match = re.search(r"\b(20\d{2}|19\d{2})\b", citation)
            year = year_match.group(1) if year_match else ""
            journal = citation
            journal = re.sub(r"^\d+\.\s*", "", journal)
            if year:
                journal = journal.split(year)[0]
            journal = journal.strip(" .;")

            abstract = chunk
            if "Author information:" in abstract:
                abstract = abstract.split("Author information:", 1)[-1]
            abstract = re.sub(r"DOI:\s*.*", "", abstract, flags=re.I | re.S)
            abstract = clean_text(abstract)
            record_key = f"{txt_path.relative_to(ROOT)}::{txt_index}"
            records.append(
                PubMedRecord(
                    record_key=record_key,
                    source_txt=str(rel),
                    source_database=source_database,
                    search_batch=search_batch,
                    search_folder=search_folder,
                    txt_index=txt_index,
                    title=title,
                    authors=authors,
                    journal=journal,
                    year=year,
                    doi=doi,
                    pmid=pmid,
                    citation=citation,
                    abstract=abstract[:12000],
                    raw_record=chunk[:20000],
                )
            )
    return records


def list_pdf_paths() -> list[Path]:
    try:
        result = subprocess.run(
            ["rg", "--files", "-g", "*.pdf"],
            cwd=ROOT,
            check=True,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        rels = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        paths = [ROOT / rel for rel in rels]
    except Exception:
        paths = list(ROOT.rglob("*.pdf"))

    filtered = []
    for path in paths:
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue
        parts = rel.parts
        if not parts:
            continue
        if parts[0] in EXCLUDED_TOP_LEVELS:
            continue
        if parts[0] in INCLUDED_TOP_LEVELS:
            filtered.append(path)
    return sorted(filtered, key=lambda p: str(p.relative_to(ROOT)).lower())


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with open_path(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def extract_pdf_text(path: Path) -> tuple[str, str, str, int]:
    try:
        with open_path(path, "rb") as fh:
            reader = PdfReader(fh, strict=False)
            page_count = len(reader.pages)
            metadata_title = ""
            try:
                if reader.metadata and reader.metadata.title:
                    metadata_title = clean_text(str(reader.metadata.title))
            except Exception:
                metadata_title = ""
            parts: list[str] = []
            for page in reader.pages[:12]:
                if sum(len(x) for x in parts) > 70000:
                    break
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                if text:
                    parts.append(text)
            excerpt = clean_text("\n".join(parts))[:70000]
            status = "readable" if len(excerpt) >= 300 else ("low_text" if excerpt else "no_text")
            return excerpt, status, metadata_title, page_count
    except Exception as exc:
        return "", f"read_error: {type(exc).__name__}: {exc}", "", 0


def collect_pdfs() -> list[PdfRecord]:
    records: list[PdfRecord] = []
    for path in list_pdf_paths():
        rel = str(path.relative_to(ROOT))
        source_database, search_batch, search_folder = source_parts(rel)
        try:
            size_bytes = path.stat().st_size
        except OSError:
            size_bytes = 0
        try:
            sha = sha1_file(path)
        except Exception:
            sha = ""
        text, status, pdf_title, page_count = extract_pdf_text(path)
        year_match = re.search(r"\b(20\d{2}|19\d{2})\b", path.stem + " " + text[:4000])
        records.append(
            PdfRecord(
                source_database=source_database,
                search_batch=search_batch,
                search_folder=search_folder,
                pdf_path=rel,
                file_name=path.name,
                file_stem=path.stem,
                size_bytes=size_bytes,
                sha1=sha,
                pdf_title=pdf_title,
                pdf_year=year_match.group(1) if year_match else "",
                pdf_text_excerpt=text,
                pdf_text_status=status,
                pdf_page_count=page_count,
            )
        )
    return records


def title_similarity(a: str, b: str) -> float:
    na = normalize_title(a)
    nb = normalize_title(b)
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta = set(na.split())
    tb = set(nb.split())
    token_score = (2 * len(ta & tb) / (len(ta) + len(tb))) if ta and tb else 0.0
    contain_score = 0.0
    if len(na) > 35 and len(nb) > 35 and (na[:80] in nb or nb[:80] in na):
        contain_score = 0.95
    return max(seq, token_score, contain_score)


def match_pubmed_to_pdfs(pdfs: list[PdfRecord], pubmed: list[PubMedRecord]) -> None:
    by_search = {}
    for rec in pubmed:
        by_search.setdefault((rec.search_batch, rec.search_folder), []).append(rec)

    for pdf in pdfs:
        if pdf.source_database != "PubMed":
            continue
        candidates = by_search.get((pdf.search_batch, pdf.search_folder), pubmed)
        best_key = ""
        best_score = 0.0
        for rec in candidates:
            score = title_similarity(pdf.file_stem, rec.title)
            if score > best_score:
                best_score = score
                best_key = rec.record_key
        if best_score >= 0.56:
            pdf.matched_pubmed_key = best_key
            pdf.matched_pubmed_score = round(best_score, 3)


def find_sentence(text: str, terms: list[str]) -> str:
    if not text:
        return ""
    compact = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    lower_terms = [t.lower() for t in terms]
    for sent in sentences:
        sl = sent.lower()
        if any(t in sl for t in lower_terms):
            return sent[:700]
    return compact[:500]


def classify_record(pdf: PdfRecord, pubmed_rec: PubMedRecord | None) -> dict[str, str]:
    title = pubmed_rec.title if pubmed_rec and pubmed_rec.title else (pdf.pdf_title or pdf.file_stem)
    abstract = pubmed_rec.abstract if pubmed_rec else ""
    source_text = " ".join([title, abstract, pdf.pdf_text_excerpt])
    title_abstract = " ".join([title, abstract])
    title_lower = title.lower()
    lower = source_text.lower()
    ta_lower = title_abstract.lower()
    notes: list[str] = []

    if pdf.pdf_text_status.startswith("read_error") or pdf.pdf_text_status in {"no_text", "low_text"}:
        if not abstract:
            return {
                "decision": "待人工确认",
                "dataset_type": "",
                "exclusion_code": "",
                "screening_level": "PDF全文不可读或文字不足",
                "evidence_sentence": pdf.pdf_text_status,
                "device_relevance": "",
                "patient_condition": "",
                "outcome_data": "",
                "D": "",
                "A": "",
                "P": "",
                "R": "",
                "T": "",
                "O": "",
                "S": "",
                "C": "",
                "notes": "无可用题录摘要，需人工打开PDF确认。",
            }
        notes.append(f"PDF text status: {pdf.pdf_text_status}; judged from PubMed abstract/title.")

    non_original_hit = first_hit(ta_lower, NON_ORIGINAL_TERMS)
    if non_original_hit:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E1",
            "screening_level": "题名/摘要初筛",
            "evidence_sentence": find_sentence(title_abstract, [non_original_hit]),
            "device_relevance": "非原始临床研究",
            "patient_condition": "",
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    non_clinical_hit = first_hit(ta_lower, NON_CLINICAL_TERMS)
    if non_clinical_hit:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E3",
            "screening_level": "题名/摘要初筛",
            "evidence_sentence": find_sentence(title_abstract, [non_clinical_hit]),
            "device_relevance": "非临床研究或基础/体外研究",
            "patient_condition": "",
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    condition_hit = first_hit(lower, CONDITION_TERMS)
    strong_stent_hit = first_hit(lower, INCLUSION_TERMS)
    weak_stent_hit = first_hit(lower, WEAK_STENT_TERMS)
    outcome_hit = first_hit(lower, OUTCOME_TERMS)
    different_device_hit = first_hit(ta_lower, DIFFERENT_DEVICE_TERMS)
    out_scope_hit = first_hit(ta_lower, OUT_OF_SCOPE_STENT_FOCUS)
    metallic_hit = first_hit(lower, METALLIC_STENT_TERMS)

    if not condition_hit:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E2",
            "screening_level": "题名/摘要初筛",
            "evidence_sentence": find_sentence(title_abstract or source_text, ["disease", "stone", "urology"]),
            "device_relevance": "",
            "patient_condition": "未见输尿管疾病/梗阻相关对象",
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if metallic_hit:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E5",
            "screening_level": "题名/摘要/全文关键词",
            "evidence_sentence": find_sentence(source_text, [metallic_hit]),
            "device_relevance": "金属或自膨支架，不属于Double J/DJ相似器械范围",
            "patient_condition": condition_hit,
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if out_scope_hit:
        code = "E6" if "cost" in out_scope_hit or "economic" in out_scope_hit else "E5"
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": code,
            "screening_level": "题名/摘要初筛",
            "evidence_sentence": find_sentence(title_abstract, [out_scope_hit]),
            "device_relevance": "支架相关但聚焦主题不在预期用途/安全性能证据范围",
            "patient_condition": condition_hit,
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if not strong_stent_hit and not weak_stent_hit:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E4",
            "screening_level": "题名/摘要/全文关键词",
            "evidence_sentence": find_sentence(title_abstract or source_text, CONDITION_TERMS),
            "device_relevance": "未见输尿管支架/DJ支架使用",
            "patient_condition": condition_hit,
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    title_has_strong_stent = has_any(title_lower, INCLUSION_TERMS)
    title_has_weak_stent = has_any(title_lower, WEAK_STENT_TERMS)
    title_has_different_device = bool(different_device_hit)
    ta_stent_hits = sum(ta_lower.count(term) for term in INCLUSION_TERMS + WEAK_STENT_TERMS)
    full_stent_hits = sum(lower.count(term) for term in INCLUSION_TERMS + WEAK_STENT_TERMS)
    incidental_stent_only = (not title_has_strong_stent and not title_has_weak_stent and full_stent_hits <= 3)

    if title_has_different_device and not title_has_strong_stent and not title_has_weak_stent:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E5",
            "screening_level": "题名/摘要初筛",
            "evidence_sentence": find_sentence(title_abstract, [different_device_hit]),
            "device_relevance": f"主要器械/技术为{different_device_hit}",
            "patient_condition": condition_hit,
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if incidental_stent_only:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E6",
            "screening_level": "全文关键词核对",
            "evidence_sentence": find_sentence(source_text, [strong_stent_hit or weak_stent_hit]),
            "device_relevance": "仅在全文零星提及支架，题名/摘要未显示支架为研究核心",
            "patient_condition": condition_hit,
            "outcome_data": "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if not title_has_strong_stent and not title_has_weak_stent:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E6",
            "screening_level": "题名/摘要/全文关键词核对",
            "evidence_sentence": find_sentence(source_text, [strong_stent_hit or weak_stent_hit]),
            "device_relevance": "题名未显示DJ/输尿管支架为研究核心，支架仅作为治疗过程或背景出现",
            "patient_condition": condition_hit,
            "outcome_data": outcome_hit or "",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if not outcome_hit:
        return {
            "decision": "排除",
            "dataset_type": "",
            "exclusion_code": "E6",
            "screening_level": "题名/摘要/全文关键词",
            "evidence_sentence": find_sentence(source_text, [strong_stent_hit or weak_stent_hit]),
            "device_relevance": strong_stent_hit or weak_stent_hit,
            "patient_condition": condition_hit,
            "outcome_data": "未见安全性或性能结局关键词",
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "",
        }

    if not (title_has_strong_stent or title_has_weak_stent):
        return {
            "decision": "待人工确认",
            "dataset_type": "",
            "exclusion_code": "",
            "screening_level": "全文关键词命中但题名/摘要证据弱",
            "evidence_sentence": find_sentence(source_text, [strong_stent_hit or weak_stent_hit, outcome_hit]),
            "device_relevance": strong_stent_hit or weak_stent_hit,
            "patient_condition": condition_hit,
            "outcome_data": outcome_hit,
            "D": "",
            "A": "",
            "P": "",
            "R": "",
            "T": "",
            "O": "",
            "S": "",
            "C": "",
            "notes": "支架词多来自全文或弱关键词，需人工确认是否为研究核心。",
        }

    dataset_type = "Similar device" if title_has_strong_stent or "double" in lower or "jj stent" in lower else "SOTA"
    d_value = "D2" if dataset_type == "Similar device" else "D3"
    evidence_terms = [strong_stent_hit or weak_stent_hit, condition_hit, outcome_hit]
    return {
        "decision": "纳入",
        "dataset_type": dataset_type,
        "exclusion_code": "",
        "screening_level": "题名/摘要初筛+全文关键词核对",
        "evidence_sentence": find_sentence(source_text, [t for t in evidence_terms if t]),
        "device_relevance": strong_stent_hit or weak_stent_hit,
        "patient_condition": condition_hit,
        "outcome_data": outcome_hit,
        "D": d_value,
        "A": "A1",
        "P": "P1" if condition_hit in {"ureteral obstruction", "ureteric obstruction", "ureter obstruction", "obstructive uropathy", "malignant ureteral obstruction"} else "P2",
        "R": "R2",
        "T": "T1",
        "O": "O1",
        "S": "S1",
        "C": "C1" if any(term in lower for term in ["randomized", "prospective", "registry", "multicenter", "cohort"]) else "C2",
        "notes": "; ".join(notes),
    }


def make_duplicate_key(pdf: PdfRecord, pubmed_rec: PubMedRecord | None) -> str:
    if pubmed_rec:
        if pubmed_rec.doi:
            return "doi:" + pubmed_rec.doi.lower()
        if pubmed_rec.pmid:
            return "pmid:" + pubmed_rec.pmid
        if pubmed_rec.title:
            return "title:" + normalize_title(pubmed_rec.title)[:120]
    stem_norm = normalize_title(pdf.file_stem)[:120]
    if stem_norm:
        return "title:" + stem_norm
    return "sha1:" + pdf.sha1


def build_screened_records(pdfs: list[PdfRecord], pubmed: list[PubMedRecord]) -> tuple[list[ScreenedRecord], list[dict[str, Any]], list[dict[str, Any]]]:
    pubmed_by_key = {rec.record_key: rec for rec in pubmed}
    groups: dict[str, list[tuple[PdfRecord, PubMedRecord | None]]] = {}
    for pdf in pdfs:
        pubmed_rec = pubmed_by_key.get(pdf.matched_pubmed_key)
        key = make_duplicate_key(pdf, pubmed_rec)
        groups.setdefault(key, []).append((pdf, pubmed_rec))

    screened: list[ScreenedRecord] = []
    duplicates: list[dict[str, Any]] = []
    for group_num, (key, items) in enumerate(sorted(groups.items()), start=1):
        duplicate_group_id = f"DUP-{group_num:04d}" if len(items) > 1 else ""
        # Prefer records with PubMed metadata, then readable PDF text, then earliest search batch.
        items_sorted = sorted(
            items,
            key=lambda x: (
                0 if x[1] else 1,
                0 if x[0].pdf_text_status == "readable" else 1,
                0 if x[0].search_batch == "首次搜索" else 1,
                x[0].pdf_path.lower(),
            ),
        )
        primary_pdf, primary_pubmed = items_sorted[0]
        classification = classify_record(primary_pdf, primary_pubmed)
        all_sources = sorted({f"{p.source_database}/{p.search_batch}/{p.search_folder}" for p, _ in items})
        all_paths = sorted({p.pdf_path for p, _ in items})
        if len(items) > 1:
            for p, rec in items:
                duplicates.append(
                    {
                        "Duplicate_Group_ID": duplicate_group_id,
                        "Duplicate_Key": key,
                        "Title": rec.title if rec else (p.pdf_title or p.file_stem),
                        "DOI": rec.doi if rec else "",
                        "PMID": rec.pmid if rec else "",
                        "Source_Database": p.source_database,
                        "Search_Batch": p.search_batch,
                        "Search_Folder": p.search_folder,
                        "PDF_Path": p.pdf_path,
                        "SHA1": p.sha1,
                        "Kept_As_Primary": "Yes" if p.pdf_path == primary_pdf.pdf_path else "No",
                    }
                )

        record_id = f"R{len(screened) + 1:04d}"
        title = primary_pubmed.title if primary_pubmed and primary_pubmed.title else (primary_pdf.pdf_title or primary_pdf.file_stem)
        screened.append(
            ScreenedRecord(
                record_id=record_id,
                decision=classification["decision"],
                dataset_type=classification["dataset_type"],
                exclusion_code=classification["exclusion_code"],
                exclusion_reason_cn=EXCLUSION_REASONS_CN.get(classification["exclusion_code"], ""),
                title=title,
                authors=primary_pubmed.authors if primary_pubmed else "",
                journal=primary_pubmed.journal if primary_pubmed else "",
                year=primary_pubmed.year if primary_pubmed and primary_pubmed.year else primary_pdf.pdf_year,
                doi=primary_pubmed.doi if primary_pubmed else "",
                pmid=primary_pubmed.pmid if primary_pubmed else "",
                source_database=primary_pdf.source_database,
                search_batch=primary_pdf.search_batch,
                search_folder=primary_pdf.search_folder,
                pdf_path=primary_pdf.pdf_path,
                pubmed_txt_source=primary_pubmed.source_txt if primary_pubmed else "",
                duplicate_group_id=duplicate_group_id,
                screening_level=classification["screening_level"],
                evidence_sentence=classification["evidence_sentence"],
                device_relevance=classification["device_relevance"],
                patient_condition=classification["patient_condition"],
                outcome_data=classification["outcome_data"],
                D=classification["D"],
                A=classification["A"],
                P=classification["P"],
                R=classification["R"],
                T=classification["T"],
                O=classification["O"],
                S=classification["S"],
                C=classification["C"],
                all_sources=" | ".join(all_sources),
                all_pdf_paths=" | ".join(all_paths),
                text_status=primary_pdf.pdf_text_status,
                notes=classification["notes"],
            )
        )

    matched_keys = {pdf.matched_pubmed_key for pdf in pdfs if pdf.matched_pubmed_key}
    unmatched_pubmed = [
        {
            "Source_TXT": rec.source_txt,
            "Search_Batch": rec.search_batch,
            "Search_Folder": rec.search_folder,
            "Index": rec.txt_index,
            "Title": rec.title,
            "Year": rec.year,
            "DOI": rec.doi,
            "PMID": rec.pmid,
            "Reason": "PubMed题录未匹配到本地PDF，未纳入本次PDF筛选总表",
        }
        for rec in pubmed
        if rec.record_key not in matched_keys
    ]
    return screened, duplicates, unmatched_pubmed


def summarize(records: list[ScreenedRecord], pdfs: list[PdfRecord], pubmed: list[PubMedRecord], duplicates: list[dict[str, Any]], unmatched_pubmed: list[dict[str, Any]]) -> dict[str, Any]:
    def count_by(values: list[str]) -> dict[str, int]:
        out: dict[str, int] = {}
        for value in values:
            out[value or "(blank)"] = out.get(value or "(blank)", 0) + 1
        return dict(sorted(out.items()))

    return {
        "pdf_count": len(pdfs),
        "pubmed_txt_record_count": len(pubmed),
        "screened_unique_count": len(records),
        "decision_counts": count_by([r.decision for r in records]),
        "exclusion_counts": count_by([r.exclusion_code for r in records if r.exclusion_code]),
        "source_counts": count_by([r.source_database for r in records]),
        "text_status_counts": count_by([p.pdf_text_status.split(":")[0] for p in pdfs]),
        "duplicate_group_count": len({d["Duplicate_Group_ID"] for d in duplicates}),
        "duplicate_row_count": len(duplicates),
        "unmatched_pubmed_count": len(unmatched_pubmed),
    }


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    docx = extract_docx_text()
    pubmed = parse_pubmed_records()
    pdfs = collect_pdfs()
    match_pubmed_to_pdfs(pdfs, pubmed)
    screened, duplicates, unmatched_pubmed = build_screened_records(pdfs, pubmed)
    data = {
        "summary": summarize(screened, pdfs, pubmed, duplicates, unmatched_pubmed),
        "exclusion_reasons_cn": EXCLUSION_REASONS_CN,
        "docx": docx,
        "records": [asdict(r) for r in screened],
        "duplicates": duplicates,
        "unmatched_pubmed": unmatched_pubmed,
        "pdf_manifest": [asdict(p) for p in pdfs],
        "pubmed_records": [asdict(r) for r in pubmed],
    }
    output_path = OUTPUT_DIR / "screening_data.json"
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
