const fs = require("fs");
const path = require("path");
const hre = require("hardhat");
const { ethers } = hre;

// ============================================================
// PASTE YOUR DEPLOYED CONTRACT ADDRESS HERE
// (from the "ChainProofRegistry:" line in your deploy output)
// ============================================================
const CONTRACT_ADDRESS = "0x57AfFe0184Bb5A9EfcaEe523b77D17880948A955";

const COMMITMENTS_CSV = path.join(__dirname, "..", "..", "data", "chainproof_commitments.csv");
const OUTPUT_CSV = path.join(__dirname, "..", "..", "data", "chainproof_onchain_log.csv");

function parseCsv(filePath) {
  const raw = fs.readFileSync(filePath, "utf8").trim();
  const lines = raw.split("\n");
  const headers = lines[0].split(",");
  return lines.slice(1).map((line) => {
    const values = line.split(",");
    const row = {};
    headers.forEach((h, i) => (row[h] = values[i]));
    return row;
  });
}

function withPrefix(hex) {
  return hex.startsWith("0x") ? hex : "0x" + hex;
}

function toUnixTimestamp(pandasTimestampStr) {
  return Math.floor(new Date(pandasTimestampStr).getTime() / 1000);
}

async function main() {
  if (CONTRACT_ADDRESS === "PASTE_YOUR_CONTRACT_ADDRESS_HERE") {
    console.error("Set CONTRACT_ADDRESS at the top of this script before running.");
    process.exit(1);
  }

  console.log("=".repeat(70));
  console.log("CHAINPROOF -- SUBMITTING COMMITMENTS ON-CHAIN");
  console.log("=".repeat(70));

  const [signer] = await ethers.getSigners();
  console.log("Submitting with account:", signer.address);
  console.log(
    "Account balance:",
    ethers.formatEther(await ethers.provider.getBalance(signer.address)),
    "ETH"
  );

  const registry = await ethers.getContractAt("ChainProofRegistry", CONTRACT_ADDRESS);

  const rows = parseCsv(COMMITMENTS_CSV);
  console.log(`\nLoaded ${rows.length} commitments from ${COMMITMENTS_CSV}`);

  const results = [];

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const commitmentHash = withPrefix(row.commitment_hash);
    const signature = withPrefix(row.signature);
    const timestamp = toUnixTimestamp(row.timestamp);

    process.stdout.write(
      `[${i + 1}/${rows.length}] ${row.action.padEnd(10)} @ $${row.price}  ... `
    );

    try {
      const tx = await registry.submitCommitment(
        commitmentHash,
        row.action,
        timestamp,
        row.signer_address,
        signature
      );
      const receipt = await tx.wait();

      console.log(`OK (block ${receipt.blockNumber}, tx ${tx.hash.slice(0, 10)}...)`);

      results.push({
        ...row,
        tx_hash: tx.hash,
        block_number: receipt.blockNumber,
        onchain_index: results.length,
      });
    } catch (err) {
      console.log(`FAILED: ${err.message.slice(0, 100)}`);
      results.push({ ...row, tx_hash: "FAILED", block_number: "", onchain_index: "" });
    }
  }

  const outHeaders = Object.keys(results[0]);
  const outLines = [
    outHeaders.join(","),
    ...results.map((r) => outHeaders.map((h) => r[h]).join(",")),
  ];
  fs.writeFileSync(OUTPUT_CSV, outLines.join("\n"));

  const succeeded = results.filter((r) => r.tx_hash !== "FAILED").length;

  console.log("\n" + "=".repeat(70));
  console.log(`SUBMITTED: ${succeeded}/${rows.length} commitments succeeded`);
  console.log(`Saved on-chain log to: ${OUTPUT_CSV}`);
  console.log(`\nView the contract on Sepolia Etherscan:`);
  console.log(`https://sepolia.etherscan.io/address/${CONTRACT_ADDRESS}`);
  console.log("=".repeat(70));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
