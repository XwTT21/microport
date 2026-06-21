import fs from "node:fs/promises";
import path from "node:path";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const root = process.cwd();
const outputDir = path.join(root, "outputs", "uas_screening");
const preferredPath = path.join(outputDir, "文献筛选结果_UAS_含适应性评估.xlsx");
const originalPath = path.join(outputDir, "文献筛选结果_UAS.xlsx");
const xlsxPath = await fs
  .access(preferredPath)
  .then(() => preferredPath)
  .catch(() => originalPath);
const input = await FileBlob.load(xlsxPath);
const workbook = await SpreadsheetFile.importXlsx(input);

const sheetInspect = await workbook.inspect({
  kind: "sheet",
  include: "id,name",
  maxChars: 4000,
});
console.log(sheetInspect.ndjson);

const overview = await workbook.inspect({
  kind: "table",
  range: "统计汇总!A1:B25",
  include: "values",
  tableMaxRows: 25,
  tableMaxCols: 2,
  maxChars: 6000,
});
console.log(overview.ndjson);

const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "verification formula error scan",
});
console.log(errors.ndjson);

const appraisal = await workbook.inspect({
  kind: "table",
  range: "适应性评估!A1:AC30",
  include: "values",
  tableMaxRows: 30,
  tableMaxCols: 29,
  maxChars: 9000,
});
console.log(appraisal.ndjson);

const sheetNames = ["统计汇总", "筛选总表", "纳入文献", "排除文献", "待人工确认", "适应性评估", "适应性评级规则", "重复文献", "PubMed未匹配", "筛选标准提取记录"];
for (const sheetName of sheetNames) {
  const preview = await workbook.render({
    sheetName,
    range: "A1:H20",
    scale: 1,
    format: "png",
  });
  const safeName = sheetName.replace(/[\\/:*?"<>|]/g, "_");
  await fs.writeFile(path.join(outputDir, `preview_${safeName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

console.log(JSON.stringify({ verified: true, xlsxPath }, null, 2));
