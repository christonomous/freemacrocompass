# 🧭 Global Macro Terminal

A high-density, institutional-grade market intelligence engine designed for quantitative alpha selection and systemic risk monitoring.

![Status](https://img.shields.io/badge/Status-v2.5--Institutional-cyan)
![Tech](https://img.shields.io/badge/Architecture-API--First-blue)
![Caching](https://img.shields.io/badge/Cache-5--Min%20TTL-brightgreen)

## 📡 The Engine
The **Global Macro Terminal** aggregates critical systemic pulses—**Liquidity, Credit, Growth, and Volatility**—into a professional "Single-Pane-Of-Glass" dashboard. It calculates a real-time **Market Regime Score** based on weighted institutional proxies to identify **Risk-On** vs **Risk-Off** regimes.

### Institutional Features:
- **Systemic Plumbing Matrix**: High-density 6-point matrix tracking **Bond Volatility (MOVE)**, **St. Louis Fed Stress Index**, **Credit Spreads (HY)**, **NFCI**, **Yield Curve (10Y-3M)**, and **Real Yields**.
- **Growth & Momentum Pulse**: Leading economic signals via **Copper/Gold Ratio**, **XLK/XLP Rotation**, and **Beta (SPY) Momentum**.
- **API-First Architecture**: Decoupled backend exposing data via `/api/macro` JSON endpoint with **5-minute TTL caching** for multi-client scalability.
- **Premium Terminal UI**: v4.5 "Glassmorphism" interface with **JetBrains Mono** typography and real-time **ApexCharts** visualizations.
- **Data Hardening**: Robust momentum engine with automated `.fillna()` logic to ensure continuous live streams during market stress.

---

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   python3 -m pip install --user -r requirements.txt
   ```

2. **Run the Server**:
   ```bash
   python3 app.py
   ```

3. **View the Pulse**:
   Open your browser to `http://localhost:3000`.

---

## 💎 Proprietary Alpha & Consulting

This project is a **Freemium** demonstration of our quantitative capabilities. If you are looking to build a **Proprietary Alpha Engine**, bespoke data pipelines, or automated trading systems, let's connect.

- **📅 Book a Strategy Session**: [Calendly](https://calendly.com/chrisberlin/session)
- **🔗 Connect with me**: [LinkedIn](https://www.linkedin.com/in/christonomous/)
- **🏠 Personal Homepage**: [chris.zillions.app](https://chris.zillions.app/)
- **💼 Consulting & Solutions**: [Revoro Consulting](https://revoro.consulting/)
- **🤖 Onchain SMC Trading Bot**: [Zillions.app](https://zillions.app/)

---

### "Turning Data into an Edge."
Built by [**Christonomous**](https://github.com/christonomous) @ Revoro Consulting.
