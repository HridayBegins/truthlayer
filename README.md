# TruthLayer - AI-Powered Fact Checker

> Automated Fact-Checking Web App for PDF Documents
> Built for CogDigital Product Management Trainee Assessment

## 🚀 Live Demo
**Deployed App:** [https://truthlayer-factcheck.streamlit.app](https://truthlayer-factcheck.streamlit.app)

## 📋 Overview

TruthLayer is a "Truth Layer" web application that reads PDF documents, extracts verifiable claims (statistics, dates, financial figures, technical specs), cross-references them against live web data, and flags inaccuracies.

### Key Features
- **📄 PDF Upload & Text Extraction** - Reads any PDF and extracts readable text
- **🔍 Smart Claim Detection** - Identifies statistics, dates, financial figures, technical specs, and comparative claims using regex patterns
- **🌐 Live Web Verification** - Searches DuckDuckGo to cross-reference claims against current web data
- **📊 Interactive Dashboard** - Visual breakdown of verified, unverified, and flagged claims
- **📥 Export Reports** - Download results as JSON or CSV

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| PDF Parsing | PyPDF2 |
| Web Search | DuckDuckGo HTML (no API key required) |
| Data Viz | Plotly |
| Export | Pandas, JSON |

## 🏃 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/yourusername/truthlayer.git
cd truthlayer

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

### Deployment

#### Option 1: Streamlit Cloud (Recommended)
1. Push code to GitHub
2. Connect repo at [share.streamlit.io](https://share.streamlit.io)
3. Deploy automatically

#### Option 2: Docker
```bash
docker build -t truthlayer .
docker run -p 8501:8501 truthlayer
```

## 📊 How It Works

### 1. Claim Extraction Engine
The system uses multi-pattern regex to identify:
- **Statistics**: Percentages, ratios, "X in Y" claims
- **Dates**: Full dates, years, quarters
- **Financial**: Dollar amounts, revenue figures, growth rates
- **Technical**: Speeds, capacities, version numbers
- **Comparative**: Superlatives, comparisons

### 2. Web Verification Engine
- Constructs search queries from extracted claims
- Queries DuckDuckGo HTML for live results
- Analyzes snippets for confirmation/contradiction
- Assigns confidence scores based on evidence

### 3. Report Generation
- Aggregates all claims with status labels
- Generates visual dashboard with metrics
- Exports to JSON and CSV formats

## 🧪 Testing with Trap Documents

Create a PDF with these intentional errors to test the system:

| Claim | Status Expected |
|-------|----------------|
| "AI market was $50B in 2020" | ⚠️ Inaccurate (actual ~$95B) |
| "ChatGPT launched Jan 2023" | ❌ False (actual Nov 2022) |
| "Eiffel Tower is 400m tall" | ⚠️ Inaccurate (actual 330m) |
| "Apple revenue 2024 was $500B" | ❌ False (actual ~$391B) |

## 📁 Project Structure

```
truthlayer/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
├── .streamlit/
│   └── config.toml     # Streamlit configuration
└── README.md           # This file
```

## 🎯 Evaluation Criteria Met

| Criteria | Implementation |
|----------|---------------|
| PDF Upload | ✅ Streamlit file uploader with PyPDF2 |
| Claim Extraction | ✅ Multi-pattern regex for 5 claim types |
| Web Verification | ✅ Live DuckDuckGo search |
| Status Flags | ✅ Verified / Inaccurate / False / Unverified |
| Dashboard | ✅ Interactive charts and metrics |
| Export | ✅ JSON and CSV downloads |
| Deployment | ✅ Streamlit Cloud ready |

## 📝 License

MIT License - Built for assessment purposes.

## 👤 Author

Product Management Trainee Assessment | CogDigital (P) Ltd
