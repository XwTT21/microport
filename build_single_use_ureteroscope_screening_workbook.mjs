import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const inputPath = path.join(root, "outputs", "single_use_ureteroscope_screening", "single_use_ureteroscope_screening_data.json");
const outputDir = path.join(root, "outputs", "single_use_ureteroscope_screening");
const outputPath = path.join(outputDir, "文献筛选结果_一次性输尿管镜_完整版.xlsx");

const raw = JSON.parse(await fs.readFile(inputPath, "utf8"));
const workbook = Workbook.create();

const columns = [
  "Record_ID",
  "Decision",
  "Inclusion_Class",
  "Exclusion_Code",
  "Exclusion_Reason_CN",
  "Title",
  "Authors",
  "Journal",
  "Year",
  "DOI",
  "PMID",
  "Study_Type",
  "Single_Use_Ureteroscope_Relevance",
  "Single_Use_Ureteroscope_Device_or_Technique",
  "Clinical_Context",
  "Outcome_Data",
  "Source_Database",
  "Search_Batch",
  "Search_Folder",
  "PDF_Path",
  "PubMed_TXT_Source",
  "Duplicate_Group_ID",
  "Screening_Level",
  "Evidence_Sentence",
  "All_Sources",
  "All_PDF_Paths",
  "Text_Status",
  "PubMed_Match_Score",
  "Notes",
];

const duplicateColumns = [
  "Duplicate_Group_ID",
  "Duplicate_Key",
  "Title",
  "DOI",
  "PMID",
  "Source_Database",
  "Search_Batch",
  "Search_Folder",
  "PDF_Path",
  "SHA1",
  "Kept_As_Primary",
];

const unmatchedColumns = [
  "Source_TXT",
  "Search_Batch",
  "Search_Folder",
  "Index",
  "Title",
  "Year",
  "DOI",
  "PMID",
  "Potential_Single_Use_Ureteroscope",
  "Reason",
];

const criteriaColumns = ["Item", "Description"];
const flowColumns = ["Step", "Count", "Description"];

const datasetColumns = [
  "Record_ID",
  "Dataset_Assignment",
  "Assignment_Reason",
  "Overall_Appraisal",
  "Title",
  "Study_Type",
  "Decision",
  "Source_Database",
  "Search_Batch",
  "PDF_Path",
];

const evidenceColumns = [
  "Record_ID",
  "Dataset_Assignment",
  "Title",
  "Study_Design",
  "Sample_Size_N",
  "Single_Use_Ureteroscope_Device_or_Technique",
  "Comparator",
  "Clinical_Context",
  "Performance_Outcomes",
  "Safety_Outcomes",
  "Pressure_or_Irrigation_Outcomes",
  "Efficiency_or_Resource_Outcomes",
  "Extracted_Percentages",
  "Overall_Appraisal",
  "Use_For",
  "Extraction_Note",
  "PDF_Path",
];

const appraisalColumns = [
  "Record_ID",
  "Decision",
  "Inclusion_Class",
  "Title",
  "Study_Type",
  "Source_Database",
  "Search_Batch",
  "Search_Folder",
  "D",
  "D_Reason",
  "A",
  "A_Reason",
  "P",
  "P_Reason",
  "R",
  "R_Reason",
  "T",
  "T_Reason",
  "O",
  "O_Reason",
  "S",
  "S_Reason",
  "C",
  "C_Reason",
  "Overall_Appraisal",
  "Use_For",
  "Appraisal_Rationale",
  "Evidence_Sentence",
  "PDF_Path",
];

function colLetter(index) {
  let n = index + 1;
  let out = "";
  while (n > 0) {
    const rem = (n - 1) % 26;
    out = String.fromCharCode(65 + rem) + out;
    n = Math.floor((n - 1) / 26);
  }
  return out;
}

function matrix(records, cols) {
  return [
    cols,
    ...records.map((r) => cols.map((c) => r?.[c] ?? "")),
  ];
}

function safeTableName(name) {
  return name.replace(/[^A-Za-z0-9_]/g, "").slice(0, 220);
}

function applySheetStyle(sheet, rowCount, colCount, tableName) {
  sheet.showGridLines = false;
  const lastCol = colLetter(colCount - 1);
  const usedRange = sheet.getRange(`A1:${lastCol}${Math.max(rowCount, 1)}`);
  usedRange.format = {
    font: { name: "Arial", size: 9, color: "#1F2937" },
    fill: "#FFFFFF",
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#D9DEE8" },
  };
  const header = sheet.getRange(`A1:${lastCol}1`);
  header.format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF", name: "Arial", size: 9 },
    wrapText: true,
    borders: { preset: "all", style: "thin", color: "#AAB7C4" },
  };
  sheet.getRange(`A1:${lastCol}1`).format.rowHeightPx = 34;
  sheet.freezePanes.freezeRows(1);
  if (rowCount > 1) {
    const table = sheet.tables.add(`A1:${lastCol}${rowCount}`, true, safeTableName(tableName));
    table.style = "TableStyleMedium2";
  }
}

function setWidths(sheet, cols) {
  cols.forEach((col, i) => {
    const letter = colLetter(i);
    let width = 120;
    if (["Title", "Authors", "Evidence_Sentence", "Description", "All_PDF_Paths", "Appraisal_Rationale", "Performance_Outcomes", "Safety_Outcomes", "Pressure_or_Irrigation_Outcomes", "Efficiency_or_Resource_Outcomes"].includes(col)) width = 360;
    if (["PDF_Path", "PubMed_TXT_Source", "Source_TXT"].includes(col)) width = 320;
    if (["Exclusion_Reason_CN", "Single_Use_Ureteroscope_Relevance", "Screening_Level", "Notes", "Reason", "Use_For", "Assignment_Reason", "Extraction_Note"].includes(col)) width = 250;
    if (["Dataset_Assignment", "Overall_Appraisal", "Study_Design", "Comparator", "Single_Use_Ureteroscope_Device_or_Technique"].includes(col)) width = 190;
    if (["Record_ID", "Decision", "Year", "DOI", "PMID", "Index", "Potential_Single_Use_Ureteroscope"].includes(col)) width = 105;
    if (["D", "A", "P", "R", "T", "O", "S", "C"].includes(col)) width = 55;
    if (["PubMed_Match_Score", "Sample_Size_N"].includes(col)) width = 95;
    sheet.getRange(`${letter}:${letter}`).format.columnWidthPx = width;
  });
}

function addDataSheet(name, records, cols, tableName) {
  const sheet = workbook.worksheets.add(name);
  const values = matrix(records ?? [], cols);
  sheet.getRangeByIndexes(0, 0, values.length, cols.length).values = values;
  applySheetStyle(sheet, values.length, cols.length, tableName);
  setWidths(sheet, cols);
  return sheet;
}

function addSummarySheet() {
  const sheet = workbook.worksheets.add("统计汇总");
  const s = raw.summary;
  const datasetCounts = raw.report_summary?.dataset_counts ?? {};
  const rows = [
    ["Metric", "Value"],
    ["缓存PDF总数", s.cache_pdf_count ?? s.pdf_count ?? 0],
    ["产品文献排除PDF数", s.product_pdf_excluded_count ?? 0],
    ["实际进入筛选PDF数", s.pdf_count ?? 0],
    ["去重后筛选记录数", s.screened_unique_count ?? 0],
    ["PubMed TXT题录数（不含产品）", s.pubmed_txt_record_count ?? 0],
    ["纳入", s.decision_counts?.["纳入"] ?? 0],
    ["排除", s.decision_counts?.["排除"] ?? 0],
    ["待人工确认", s.decision_counts?.["待人工确认"] ?? 0],
    ["重复组数", s.duplicate_group_count ?? 0],
    ["重复来源行数", s.duplicate_row_count ?? 0],
    ["PubMed未匹配题录数", s.unmatched_pubmed_count ?? 0],
    ["PubMed未匹配但潜在一次性输尿管镜题录数", s.potential_single_use_ureteroscope_unmatched_pubmed_count ?? 0],
    ["适应性评估记录数", s.appraisal_record_count ?? 0],
    ["相似器械临床数据", datasetCounts["Similar device clinical dataset"] ?? 0],
    ["SOTA数据", datasetCounts["SOTA dataset"] ?? 0],
    ["技术支持数据", datasetCounts["Technical supportive data"] ?? 0],
    ["经济/资源证据", datasetCounts["Economic/resource evidence"] ?? 0],
    ["病例支持证据", datasetCounts["Supportive case evidence"] ?? 0],
    ["待确认分层", datasetCounts["Pending confirmation"] ?? 0],
    ["", ""],
    ["Decision counts", ""],
    ...Object.entries(s.decision_counts ?? {}),
    ["", ""],
    ["Included study type counts", ""],
    ...Object.entries(s.study_type_counts_included ?? {}),
    ["", ""],
    ["Appraisal overall counts", ""],
    ...Object.entries(s.appraisal_overall_counts ?? {}),
    ["", ""],
    ["Source counts", ""],
    ...Object.entries(s.source_counts ?? {}),
  ];
  sheet.getRangeByIndexes(0, 0, rows.length, 2).values = rows;
  applySheetStyle(sheet, rows.length, 2, "SummaryTable");
  sheet.getRange("A:A").format.columnWidthPx = 300;
  sheet.getRange("B:B").format.columnWidthPx = 140;
  return sheet;
}

addSummarySheet();
addDataSheet("检索与筛选流程", raw.flow_rows ?? [], flowColumns, "FlowTable");
addDataSheet("SOTA与相似器械分层", raw.dataset_assignment ?? [], datasetColumns, "DatasetAssignmentTable");
addDataSheet("安全性能数据提取", raw.performance_safety_extraction ?? [], evidenceColumns, "EvidenceExtractionTable");
addDataSheet("筛选总表", raw.records ?? [], columns, "AllScreeningTable");
addDataSheet("纳入文献", raw.included ?? [], columns, "IncludedTable");
addDataSheet("排除文献", raw.excluded ?? [], columns, "ExcludedTable");
addDataSheet("待人工确认", raw.pending ?? [], columns, "PendingTable");
addDataSheet("适应性评估", raw.appraisal ?? [], appraisalColumns, "AppraisalTable");
addDataSheet("重复文献", raw.duplicates ?? [], duplicateColumns, "DuplicateTable");
addDataSheet("PubMed未匹配", raw.unmatched_pubmed ?? [], unmatchedColumns, "UnmatchedPubMedTable");
addDataSheet("适应性评级规则", raw.appraisal_rules ?? [], criteriaColumns, "AppraisalRulesTable");
addDataSheet("筛选标准提取记录", raw.criteria ?? [], criteriaColumns, "CriteriaTable");

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "统计汇总",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.mkdir(outputDir, { recursive: true });
await fs.writeFile(path.join(outputDir, "single_use_ureteroscope_summary_preview.png"), new Uint8Array(await preview.arrayBuffer()));

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outputPath);
console.log(outputPath);
