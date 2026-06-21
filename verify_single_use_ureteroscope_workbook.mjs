import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "outputs", "single_use_ureteroscope_screening");
const workbookPath = path.join(outputDir, "文献筛选结果_一次性输尿管镜_完整版.xlsx");

const input = await FileBlob.load(workbookPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const expectedSheets = [
  "统计汇总",
  "检索与筛选流程",
  "SOTA与相似器械分层",
  "安全性能数据提取",
  "筛选总表",
  "纳入文献",
  "排除文献",
  "待人工确认",
  "适应性评估",
  "重复文献",
  "PubMed未匹配",
  "适应性评级规则",
  "筛选标准提取记录",
];

const sheetInspect = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
});
console.log(sheetInspect.ndjson);

const summary = await workbook.inspect({
  kind: "table",
  sheetId: "统计汇总",
  range: "A1:B40",
  include: "values",
  tableMaxRows: 45,
  tableMaxCols: 2,
  tableMaxCellChars: 120,
});
console.log(summary.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 300 },
  summary: "verification formula error scan",
});
console.log(errors.ndjson);

for (const sheetName of expectedSheets) {
  const preview = await workbook.render({
    sheetName,
    autoCrop: "all",
    scale: 1,
    format: "png",
  });
  const safeName = sheetName.replace(/[\\/:*?"<>|]/g, "_");
  await fs.writeFile(path.join(outputDir, `preview_${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const actualSheetNames = sheetInspect.ndjson
  .split("\n")
  .filter(Boolean)
  .map((line) => JSON.parse(line).name)
  .filter(Boolean);
const missing = expectedSheets.filter((name) => !actualSheetNames.includes(name));
if (missing.length) {
  throw new Error(`Missing expected sheets: ${missing.join(", ")}`);
}

console.log(JSON.stringify({ workbookPath, renderedSheets: expectedSheets.length, missingSheets: missing }, null, 2));
