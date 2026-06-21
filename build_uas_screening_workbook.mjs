import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const inputPath = path.join(root, "outputs", "uas_screening", "uas_screening_data.json");
const outputDir = path.join(root, "outputs", "uas_screening");
const outputPath = path.join(outputDir, "文献筛选结果_UAS_完整版.xlsx");
const fallbackOutputPath = path.join(outputDir, "文献筛选结果_UAS_完整版_新.xlsx");

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
  "UAS_Relevance",
  "UAS_Device_or_Technique",
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
  "Potential_UAS",
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
  "UAS_Device_or_Technique",
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

function rowsFor(records, cols) {
  return records.map((record) => cols.map((col) => record[col] ?? ""));
}

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

function applySheetStyle(sheet, rowCount, colCount, tableName) {
  sheet.showGridLines = false;
  const lastCol = colLetter(colCount - 1);
  const usedRange = sheet.getRange(`A1:${lastCol}${Math.max(rowCount, 1)}`);
  usedRange.format = {
    font: { name: "Aptos", size: 10, color: "#111827" },
    wrapText: true,
    verticalAlignment: "top",
    borders: { preset: "all", style: "thin", color: "#E5E7EB" },
  };
  const header = sheet.getRange(`A1:${lastCol}1`);
  header.format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF", name: "Aptos", size: 10 },
    wrapText: true,
    verticalAlignment: "middle",
  };
  header.format.rowHeightPx = 34;
  sheet.freezePanes.freezeRows(1);
  if (rowCount >= 2) {
    sheet.tables.add(`A1:${lastCol}${rowCount}`, true, tableName);
  }
}

function setWidths(sheet, cols) {
  cols.forEach((col, idx) => {
    const letter = colLetter(idx);
    let width = 110;
    if (["Title", "Authors", "Evidence_Sentence", "Description", "All_PDF_Paths", "Appraisal_Rationale", "Performance_Outcomes", "Safety_Outcomes", "Pressure_or_Irrigation_Outcomes", "Efficiency_or_Resource_Outcomes"].includes(col)) width = 360;
    if (["PDF_Path", "PubMed_TXT_Source"].includes(col)) width = 320;
    if (["Exclusion_Reason_CN", "UAS_Relevance", "Screening_Level", "Notes", "Reason", "Use_For", "Assignment_Reason", "Extraction_Note"].includes(col)) width = 240;
    if (["Dataset_Assignment", "Overall_Appraisal", "Study_Design", "Comparator"].includes(col)) width = 180;
    if (/_Reason$/.test(col)) width = 230;
    if (["Record_ID", "Decision", "Year", "DOI", "PMID", "Index", "Potential_UAS"].includes(col)) width = 95;
    if (["D", "A", "P", "R", "T", "O", "S", "C"].includes(col)) width = 55;
    if (["PubMed_Match_Score"].includes(col)) width = 90;
    sheet.getRange(`${letter}:${letter}`).format.columnWidthPx = width;
  });
}

function addDataSheet(name, records, cols, tableName) {
  const sheet = workbook.worksheets.add(name);
  const values = [cols, ...rowsFor(records, cols)];
  sheet.getRangeByIndexes(0, 0, values.length, cols.length).values = values;
  applySheetStyle(sheet, values.length, cols.length, tableName);
  setWidths(sheet, cols);
  return sheet;
}

function addSummarySheet() {
  const sheet = workbook.worksheets.add("统计汇总");
  const s = raw.summary;
  const rows = [
    ["项目", "数值"],
    ["PDF总数", s.pdf_count],
    ["去重后筛选记录数", s.screened_unique_count],
    ["PubMed TXT题录数", s.pubmed_txt_record_count],
    ["纳入", s.decision_counts["纳入"] ?? 0],
    ["排除", s.decision_counts["排除"] ?? 0],
    ["待人工确认", s.decision_counts["待人工确认"] ?? 0],
    ["重复组数", s.duplicate_group_count],
    ["重复记录行数", s.duplicate_row_count],
    ["PubMed未匹配题录数", s.unmatched_pubmed_count],
    ["PubMed未匹配但潜在UAS题录数", s.potential_uas_unmatched_pubmed_count],
    ["适应性评估记录数", s.appraisal_record_count ?? 0],
    ["相似器械临床数据", (raw.report_summary?.dataset_counts ?? {})["Similar device clinical dataset"] ?? 0],
    ["SOTA数据", (raw.report_summary?.dataset_counts ?? {})["SOTA dataset"] ?? 0],
    ["技术支持数据", (raw.report_summary?.dataset_counts ?? {})["Technical supportive data"] ?? 0],
    [],
    ["纳入类别", "数量"],
    ...Object.entries(s.inclusion_class_counts ?? {}),
    [],
    ["纳入研究类型", "数量"],
    ...Object.entries(s.study_type_counts_included ?? {}),
    [],
    ["排除代码", "数量"],
    ...Object.entries(s.exclusion_counts ?? {}),
    [],
    ["来源数据库", "数量"],
    ...Object.entries(s.source_counts ?? {}),
    [],
    ["适应性综合评价", "数量"],
    ...Object.entries(s.appraisal_overall_counts ?? {}),
  ];
  sheet.getRangeByIndexes(0, 0, rows.length, 2).values = rows;
  applySheetStyle(sheet, rows.length, 2, "SummaryTable");
  sheet.getRange("A:A").format.columnWidthPx = 260;
  sheet.getRange("B:B").format.columnWidthPx = 120;
  return sheet;
}

addSummarySheet();
addDataSheet("检索与筛选流程", raw.flow_rows ?? [], flowColumns, "FlowTable");
addDataSheet("SOTA与相似器械分层", raw.dataset_assignment ?? [], datasetColumns, "DatasetAssignmentTable");
addDataSheet("安全性能数据提取", raw.performance_safety_extraction ?? [], evidenceColumns, "EvidenceExtractionTable");
addDataSheet("筛选总表", raw.records, columns, "AllScreeningTable");
addDataSheet("纳入文献", raw.included, columns, "IncludedTable");
addDataSheet("排除文献", raw.excluded, columns, "ExcludedTable");
addDataSheet("待人工确认", raw.pending, columns, "PendingTable");
addDataSheet("适应性评估", raw.appraisal ?? [], appraisalColumns, "AppraisalTable");
addDataSheet("重复文献", raw.duplicates, duplicateColumns, "DuplicateTable");
addDataSheet("PubMed未匹配", raw.unmatched_pubmed, unmatchedColumns, "UnmatchedPubMedTable");
addDataSheet("适应性评级规则", raw.appraisal_rules ?? [], criteriaColumns, "AppraisalRulesTable");
addDataSheet("筛选标准提取记录", raw.criteria, criteriaColumns, "CriteriaTable");

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "final formula error scan",
});
console.log(errors.ndjson);

const preview = await workbook.render({
  sheetName: "统计汇总",
  autoCrop: "all",
  scale: 1,
  format: "png",
});
await fs.writeFile(path.join(outputDir, "uas_summary_preview.png"), new Uint8Array(await preview.arrayBuffer()));

await fs.mkdir(outputDir, { recursive: true });
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
let finalOutputPath = outputPath;
try {
  await xlsx.save(outputPath);
} catch (error) {
  if (error?.code !== "EBUSY") throw error;
  finalOutputPath = fallbackOutputPath;
  await xlsx.save(finalOutputPath);
}
console.log(JSON.stringify({ outputPath: finalOutputPath }, null, 2));
