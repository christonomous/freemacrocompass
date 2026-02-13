import yfinance as yf
import pandas as pd
import numpy as np
import requests
from fredapi import Fred
import os
from dotenv import load_dotenv

load_dotenv()

class MacroEngine:
    def __init__(self):
        self.fred_key = os.getenv("FRED_API_KEY")
        self.av_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.fred = Fred(api_key=self.fred_key) if self.fred_key else None

    def calculate_regime(self):
        """Fetch data and calculate the market regime score."""
        # 1. Macro Indicators (FRED)
        try:
            if self.fred:
                yield_curve = self.fred.get_series('T10Y2Y').iloc[-1]
                cpi = self.fred.get_series('CPIAUCSL')
                inflation = cpi.pct_change(12).iloc[-1] * 100
                fed_funds = self.fred.get_series('FEDFUNDS').iloc[-1]
            else:
                yield_curve, inflation, fed_funds = -0.45, 3.1, 5.33
        except Exception:
            yield_curve, inflation, fed_funds = -0.45, 3.1, 5.33

        # 2. Market Sentiment & Performance (YFinance)
        assets = {'SPY': 'S&P 500', 'GLD': 'Gold', 'USO': 'Oil', '^GDAXI': 'DAX', '^N225': 'Nikkei'}
        try:
            df = yf.download(list(assets.keys()), period='1mo', progress=False)['Close']
            df = df.ffill().bfill()
            momentum = df.pct_change().iloc[-1].to_dict()
            correlation = df.corr().to_dict()
        except Exception:
            momentum = {k: 0.01 for k in assets}
            correlation = {k: {k2: 1.0 if k==k2 else 0.5 for k2 in assets} for k in assets}

        # 3. News Sentiment (Alpha Vantage)
        sentiment = 0.15
        if self.av_key:
            try:
                url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={self.av_key}'
                r = requests.get(url).json()
                scores = [float(i['overall_sentiment_score']) for i in r.get('feed', [])[:50]]
                sentiment = np.mean(scores) if scores else 0.15
            except Exception: pass

        # 4. Normalized Calculations (-1 to +1)
        # Yield Curve: < 0 is risk-off
        s_growth = np.clip(yield_curve / 0.5, -1, 1)
        # Inflation: Target 2%, > 4% is bad
        s_inflation = np.clip((2.0 - inflation) / 2.0, -1, 1)
        # Momentum: 5% month is max bull
        s_momentum = np.clip(momentum.get('SPY', 0) / 0.05, -1, 1)
        # Sentiment: 0.5 is high bullish
        s_sentiment = np.clip(sentiment / 0.5, -1, 1)
        
        composite = (s_growth * 0.3) + (s_inflation * 0.2) + (s_momentum * 0.3) + (s_sentiment * 0.2)

        return {
            'composite': float(np.clip(composite, -1, 1)),
            'components': {
                'Growth': float(s_growth),
                'Inflation': float(s_inflation),
                'Momentum': float(s_momentum),
                'Sentiment': float(s_sentiment)
            },
            'raw': {
                'fred': {'yield_curve': float(yield_curve), 'inflation': float(inflation), 'fed_funds': float(fed_funds)},
                'market': {'momentum': momentum, 'correlation': correlation}
            }
        }
