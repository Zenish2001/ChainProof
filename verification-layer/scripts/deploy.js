const hre = require("hardhat");
const { ethers } = hre;

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with account:", deployer.address);
  console.log(
    "Account balance:",
    ethers.formatEther(await ethers.provider.getBalance(deployer.address)),
    "ETH"
  );

  const ChainProofRegistry = await ethers.getContractFactory("ChainProofRegistry");
  const registry = await ChainProofRegistry.deploy();
  await registry.waitForDeployment();

  const address = await registry.getAddress();

  console.log("\n===== DEPLOYMENT SUMMARY =====");
  console.log("Network:            ", hre.network.name);
  console.log("ChainProofRegistry: ", address);
  console.log("===============================\n");
  console.log("Save this address -- the submission script needs it next.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
