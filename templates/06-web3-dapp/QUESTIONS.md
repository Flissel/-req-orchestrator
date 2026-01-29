# 📋 Web3 DApp - Projekt-Fragebogen
## Template: 06-web3-dapp (Hardhat + Next.js + Solidity)

> **Ziel**: Durch Beantwortung dieser Fragen wird genug Kontext für die automatische Code-Generierung gesammelt.

---

## 🚀 QUICK-START

| Feld | Antwort |
|------|---------|
| **DApp Name** | |
| **Blockchain** | Ethereum, Polygon, Base, Arbitrum |
| **DApp-Typ** | DeFi, NFT, DAO, Gaming |

---

## A. BLOCKCHAIN & NETZWERK

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| A1 | Primäres Netzwerk? | [ ] Ethereum [ ] Polygon [ ] Base [ ] Arbitrum [ ] Optimism | |
| A2 | Testnet? | [ ] Sepolia [ ] Mumbai [ ] Base Sepolia | |
| A3 | Multi-Chain? | [ ] Nein [ ] Ja (welche?) | |
| A4 | L2 Rollup? | [ ] Nein [ ] Optimistic [ ] ZK | |

---

## B. SMART CONTRACTS

| # | Frage | Hinweis | Antwort |
|---|-------|---------|---------|
| B1 | Contract-Typ? | Token, NFT, DAO, Custom | |
| B2 | Token Standard? | ERC-20, ERC-721, ERC-1155 | |
| B3 | Upgradeable? | Proxy Pattern | |
| B4 | Access Control? | Ownable, Roles | |
| B5 | Pausable? | Emergency Stop | |

---

## C. TOKEN ECONOMICS (falls Token)

| # | Frage | Antwort |
|---|-------|---------|
| C1 | Token Name? | |
| C2 | Token Symbol? | |
| C3 | Decimals? | 18 (default) |
| C4 | Max Supply? | |
| C5 | Mintable? | Ja/Nein |
| C6 | Burnable? | Ja/Nein |

---

## D. NFT DETAILS (falls NFT)

| # | Frage | Antwort |
|---|-------|---------|
| D1 | Collection Name? | |
| D2 | Collection Size? | |
| D3 | Mint Price? | |
| D4 | Whitelist? | Ja/Nein |
| D5 | Reveal Mechanik? | Instant, Delayed |
| D6 | Royalties? | % |
| D7 | Metadata Storage? | IPFS, Arweave |

---

## E. TECH-STACK ENTSCHEIDUNGEN

### Smart Contract Development

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E1 | Framework? | [ ] Hardhat (default) [ ] Foundry | |
| E2 | Solidity Version? | [ ] 0.8.20+ (empfohlen) | |
| E3 | OpenZeppelin? | [ ] Ja (empfohlen) [ ] Nein | |
| E4 | Testing? | [ ] Hardhat Tests [ ] Foundry Fuzz | |
| E5 | Gas Optimization? | [ ] Standard [ ] Aggressive | |

### Frontend

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E6 | Framework? | [ ] Next.js 14 (default) [ ] Vite | |
| E7 | Web3 Library? | [ ] wagmi + viem (empfohlen) [ ] ethers.js [ ] web3.js | |
| E8 | Wallet Connect? | [ ] RainbowKit (empfohlen) [ ] ConnectKit [ ] Custom | |
| E9 | State Management? | [ ] React Query [ ] Zustand | |

### Infrastructure

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| E10 | RPC Provider? | [ ] Alchemy [ ] Infura [ ] QuickNode [ ] Public | |
| E11 | IPFS Pinning? | [ ] Pinata [ ] NFT.Storage [ ] Web3.Storage | |
| E12 | Indexing? | [ ] Keins [ ] The Graph [ ] Custom | |

---

## F. WALLET & AUTH

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| F1 | Supported Wallets? | [ ] MetaMask [ ] Coinbase [ ] WalletConnect [ ] Safe | |
| F2 | ENS Resolution? | [ ] Ja [ ] Nein | |
| F3 | Sign-In with Ethereum? | [ ] Ja [ ] Nein | |
| F4 | Guest Mode? | [ ] Ja (read-only) [ ] Nein | |

---

## G. SICHERHEIT

| # | Frage | Antwort |
|---|-------|---------|
| G1 | Audit geplant? | Vor Mainnet Launch |
| G2 | Bug Bounty? | Immunefi, etc. |
| G3 | Multi-Sig Admin? | Gnosis Safe |
| G4 | Timelock? | Governance Delay |
| G5 | Reentrancy Guards? | Ja (OpenZeppelin) |

---

## H. TESTING & DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| H1 | Local Testing? | [ ] Hardhat Node [ ] Anvil | |
| H2 | Forking? | [ ] Mainnet Fork [ ] None | |
| H3 | Verification? | [ ] Etherscan [ ] Sourcify | |
| H4 | Deployment Script? | [ ] Hardhat Ignition [ ] Custom | |

---

## I. FRONTEND DEPLOYMENT

| # | Frage | Optionen | Antwort |
|---|-------|----------|---------|
| I1 | Hosting? | [ ] Vercel [ ] IPFS [ ] Fleek | |
| I2 | Domain? | [ ] ENS [ ] Traditional | |
| I3 | Decentralized? | [ ] Ja (IPFS + ENS) [ ] Nein | |

---

# 📊 GENERIERUNGSOPTIONEN

- [ ] Smart Contract (Solidity)
- [ ] Hardhat Config
- [ ] Deploy Scripts
- [ ] Contract Tests
- [ ] Frontend Integration
- [ ] Wallet Connect
- [ ] Contract ABIs
- [ ] TypeScript Types

---

# 🔧 TECH-STACK ZUSAMMENFASSUNG

```json
{
  "template": "06-web3-dapp",
  "contracts": {
    "framework": "Hardhat",
    "language": "Solidity 0.8.20+",
    "libraries": ["OpenZeppelin"],
    "testing": "Hardhat + Chai"
  },
  "frontend": {
    "framework": "Next.js 14",
    "web3": "wagmi + viem",
    "wallet": "RainbowKit"
  },
  "infrastructure": {
    "rpc": "Alchemy",
    "ipfs": "Pinata",
    "indexing": "The Graph"
  },
  "deployment": {
    "testnet": "Sepolia",
    "mainnet": "Ethereum / Polygon"
  }
}
```
