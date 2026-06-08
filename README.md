# # 🍷 Wine Market Intelligence Agent

An automated market intelligence and pricing tool designed to streamline the wine procurement and selection process. 

This agent automates data gathering from multiple sources to provide a comprehensive buyer's brief, including global pricing benchmarks, consumer sentiment, and localized landed cost calculations for the BC market.

## ✨ Core Features

* **Global Pricing Benchmark:** Scrapes Wine-Searcher for global average prices and converts them to CAD.
* **Consumer Sentiment Analysis:** Retrieves Vivino ratings, review counts, and common flavor profiles to gauge market acceptance.
* **Automated Landed Cost Calculator:** Calculates the final landed cost for the British Columbia market (incorporating CETA 0% duty for EU wines, LDB markups, GST, and container deposit).
* **Winery Tech Sheet Parsing:** Utilizes LLM (Claude) to extract grape blend proportions, aging potential, and terroir details directly from winery websites.
* **Report Generation:** Outputs structured, easy-to-read buyer's briefs in the terminal and exports them to the `reports_output` directory.

## 🚀 Quick Start

### 1. Prerequisites
Ensure you have Python 3.8+ installed on your system.

### 2. Installation
Clone or download this repository, then install the required dependencies:

```bash
pip install -r requirements.txt
