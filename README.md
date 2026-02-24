# 📈 Quantara
### Predicting tariff risk and its impact on global markets

> Built at **Hacklytics 2026: Golden Byte** by Risheet Jajoo, Vikram Ren, Shashank Shaga, and Sai Rajan.

[![Devpost](https://img.shields.io/badge/Devpost-Quantara-blue?logo=devpost)](https://devpost.com/software/triumph-s6k4zr)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?logo=typescript&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-339933?logo=node.js&logoColor=white)
![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?logo=snowflake&logoColor=white)

---

## 🌍 Inspiration

Over the past year, escalating tariff announcements have triggered immediate and often severe volatility across global equity markets. Traditional financial models assume smooth price evolution, while geopolitical policy moves create sudden structural shocks. Prediction markets often reflect sentiment shifts *before* institutions fully price them in — yet no existing tool quantifies how tariff data affects market trends across countries and sectors.

**Our core question:** What if we could quantify tariff uncertainty *before* it hits and simulate its ripple effects across global markets in real time?

Quantara was built to transform policy uncertainty into measurable, forward-looking financial insight.

---

## 🚀 What It Does

Quantara is a full-stack predictive analytics platform that stress-tests global markets against shifting tariff landscapes. By bridging prediction market sentiment with stochastic financial modeling, it provides a real-time macroeconomic impact simulator.

**Key capabilities:**
- Calculates a **"Surprise Gap"** between market expectations and tariff probability
- Visualizes geopolitical risk via an **interactive global choropleth map**
- Simulates **90-day price trajectories** for major indices and sectors
- Models discontinuous policy shocks using **jump-diffusion mathematics**
- Translates complex quantitative outputs into plain-English via an **AI analyst**

Instead of reacting after the market moves, Quantara enables proactive macro risk assessment.

---

## 🏗️ Architecture

Quantara operates through a dual-engine architecture supported by an intelligence layer.

### 1. 🧮 Probability Engine — Sentiment Analysis
We ingest data from **Kalshi prediction markets** to compute a **Surprise Gap** — the delta between implied probability and expected tariff outcomes. This gap acts as a forward-looking policy stress indicator, surfaced through an interactive global choropleth map that lets users instantly identify geopolitical hotspots.

### 2. 📊 Impact Engine — Stochastic Forecasting
We convert the Surprise Gap into projected financial impact using a **Merton Jump-Diffusion model**. Unlike traditional geometric Brownian motion models, this framework captures:

- **Jump Component:** The instantaneous market shock following a tariff announcement
- **Diffusion Component:** The longer-term cost absorption and repricing process

We run **Monte Carlo simulations** to generate 90-day probabilistic trajectories for:
- Major indices (S&P 500, Nasdaq, Dow)
- Sector-specific exposure
- Country-sensitive industries (e.g., automotive, semiconductors)

### 3. 🤖 Intelligence Layer — RAG Chatbot
A **Retrieval-Augmented Generation (RAG) chatbot** powered by **Snowflake Cortex** interprets complex outputs in plain English. The AI analyst:
- Interprets jagged simulation graphs
- Correlates projections with policy documents
- Connects outcomes to supply chain metadata
- Explains sector-specific valuation cliffs clearly

---

## 🛠️ Tech Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | TypeScript, HTML, CSS, JavaScript |
| Backend | Node.js, Python |
| ML / Modeling | Python, yfinance, Monte Carlo / Merton Jump-Diffusion |
| Data Sources | Kalshi prediction markets, yfinance |
| AI / RAG | Snowflake Cortex |

---

## 📁 Repository Structure

```
Hacklytics-2026/
├── Triumph/            # Frontend application
├── backend/            # API and data pipeline
├── chatbot/            # RAG chatbot integration (Snowflake Cortex)
├── ml/                 # Stochastic modeling and Monte Carlo engine
├── Trained_models/     # Saved model outputs
└── train_1.py          # Model training entrypoint
```

---

## ⚙️ Getting Started

### Prerequisites
- Node.js 18+
- Python 3.9+
- Snowflake account (for RAG chatbot)
- Kalshi API key

### Installation

```bash
# Clone the repository
git clone https://github.com/rjajoo18/Hacklytics-2026.git
cd Hacklytics-2026

# Install frontend/backend dependencies
npm install

# Install Python dependencies
pip install -r ml/requirements.txt   # (or install yfinance, numpy, scipy, etc.)

# Set up environment variables
cp .env.local.example .env.local
# Fill in your API keys (Kalshi, Snowflake, etc.)
```

### Running the App

```bash
# Start the backend
cd backend && npm run dev

# Start the frontend (in a separate terminal)
cd Triumph && npm run dev

# Run the ML simulation engine
python ml/simulate.py
```

---

## 🧠 Challenges

- Translating qualitative geopolitical uncertainty into a measurable numerical shock variable
- Calibrating jump intensity and diffusion parameters without overfitting
- Aligning prediction market probabilities with financial volatility data
- Maintaining interpretability while preserving quantitative rigor
- Integrating real-time data pipelines within a hackathon timeline

---

## 🏆 Accomplishments

- Successfully integrated prediction market sentiment into stochastic financial modeling
- Implemented a working Merton Jump-Diffusion simulation engine
- Built an interactive geopolitical risk visualization interface
- Deployed a RAG-powered AI analyst for contextual interpretation
- Delivered a cohesive full-stack macro stress-testing platform within a hackathon timeframe

---

## 🔭 What's Next

- Expand beyond tariffs into sanctions and monetary policy shocks
- Integrate additional macroeconomic and prediction data sources
- Add portfolio-level stress testing tools
- Deploy live APIs for institutional use
- Enable customizable scenario simulations for advanced users

**Long-term goal:** Make macroeconomic shock modeling proactive, interpretable, and accessible — not reactive.

---

## 👥 Team

| Name | GitHub |
|------|--------|
| Risheet Jajoo | [@rjajoo18](https://github.com/rjajoo18) |
| Vikram Ren | [@viren108](https://github.com/viren108) |
| Shashank Shaga | [@shashankshaga](https://github.com/shashankshaga) |
| Sai Rajan | [@sair9991](https://github.com/sair9991) |

---

## 📄 License

This project was built for Hacklytics 2026. Feel free to explore and build on it!
