import yfinance as yf
import pandas as pd
import numpy as np
import requests
import json
import re
from datetime import datetime, timedelta
from fredapi import Fred
import os
from dotenv import load_dotenv

load_dotenv()

class MacroEngine:
    def __init__(self):
        self.fred_key = os.getenv("FRED_API_KEY")
        self.av_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.fred = Fred(api_key=self.fred_key) if self.fred_key else None
        self._cache = None
        self._last_calc = None
        self._cache_ttl = 300 # 5 minutes

    def get_net_liquidity(self):
        """Calculate Net Liquidity: WALCL (Balance Sheet) - WTGANN (TGA) - RRPONTSYD (RRP)"""
        if not self.fred:
            return 6.5e12  # Placeholder ~6.5T
        try:
            walcl = self.fred.get_series('WALCL').iloc[-1] * 1e6 # Millions to Dollars
            tga = self.fred.get_series('WTGANN').iloc[-1] * 1e9 # Billions to Dollars
            rrp = self.fred.get_series('RRPONTSYD').iloc[-1] * 1e9 # Billions to Dollars
            return walcl - tga - rrp
        except Exception:
            return 6.5e12

    def calculate_regime(self):
        """Fetch data and calculate the advanced institutional regime score. Includes 5-min caching."""
        now = datetime.now()
        if self._cache and self._last_calc and (now - self._last_calc).total_seconds() < self._cache_ttl:
            return self._cache

        # 1. Advanced Macro (FRED)
        try:
            if self.fred:
                yield_10y3m = self.fred.get_series('T10Y3M').iloc[-1]
                # Real Yield (10Y Nominal - 10Y Breakeven)
                nom_10y = self.fred.get_series('DGS10').iloc[-1]
                be_10y = self.fred.get_series('T10YIE').iloc[-1]
                real_yield = nom_10y - be_10y
                
                # Credit Stress (HY Spread) & Financial Conditions (NFCI)
                hy_spread = self.fred.get_series('BAMLH0A0HYM2').iloc[-1]
                nfci = self.fred.get_series('NFCI').iloc[-1]
                stress_index = self.fred.get_series('STLFSI4').iloc[-1] # St. Louis Fed Stress Index
                
                cpi = self.fred.get_series('CPIAUCSL')
                inflation = cpi.pct_change(12).iloc[-1] * 100
                fed_funds = self.fred.get_series('FEDFUNDS').iloc[-1]
                liquidity = self.get_net_liquidity()
            else:
                yield_10y3m, real_yield, hy_spread, nfci, stress_index, inflation, fed_funds, liquidity = -0.6, 2.1, 4.5, -0.5, 0.2, 3.1, 5.33, 6.5e12
        except Exception:
            yield_10y3m, real_yield, hy_spread, nfci, stress_index, inflation, fed_funds, liquidity = -0.6, 2.1, 4.5, -0.5, 0.2, 3.1, 5.33, 6.5e12

        # 2. Market Dynamics (YFinance)
        assets = {
            'SPY': 'S&P 500', 
            'GLD': 'Gold', 
            'HG=F': 'Copper',
            'DX-Y.NYB': 'Dollar Index',
            'TLT': 'Long Bonds',
            'XLK': 'Technology', 
            'XLP': 'Staples'
        }
        try:
            df = yf.download(list(assets.keys()), period='6mo', progress=False)['Close']
            df = df.ffill().bfill()
            # 21-day rolling momentum for history
            momentum_df = df.pct_change(21).dropna()
            momentum_history = {
                'dates': momentum_df.index.strftime('%Y-%m-%d').tolist(),
                'series': {k: (momentum_df[k] * 100).tolist() for k in assets}
            }
            momentum = df.pct_change(21).iloc[-1].to_dict() # 21-day momentum
            
            # Growth Proxy: Copper / Gold ratio (Industrial vs Safe Haven)
            ratio_series = (df['HG=F'] / df['GLD']).ffill().bfill()
            cg_ratio = ratio_series.iloc[-1]
            cg_momentum = ratio_series.pct_change(21).iloc[-1]
            
            # Risk Proxy: TLT Volatility (MOVE proxy)
            tlt_vol = df['TLT'].pct_change().std() * np.sqrt(252) * 100
            
            # Sector Rotation: Tech vs Staples
            rotation_series = (df['XLK'] / df['XLP']).ffill().bfill()
            rotation_raw = rotation_series.pct_change(21).iloc[-1]
            correlation = df.corr().to_dict()
        except Exception:
            momentum = {k: 0.01 for k in assets}
            momentum_history = {'dates': [], 'series': {k: [] for k in assets}}
            cg_ratio, cg_momentum, rotation_raw, tlt_vol = 0.0125, -0.11, -0.10, 15.0
            correlation = {k: {k2: 1.0 if k==k2 else 0.5 for k2 in assets} for k in assets}

        # 3. Sentiment (Alpha Vantage)
        sentiment = 0.15
        if self.av_key:
            try:
                url = f'https://www.alphavantage.co/query?function=NEWS_SENTIMENT&apikey={self.av_key}'
                r = requests.get(url).json()
                scores = [float(i['overall_sentiment_score']) for i in r.get('feed', [])[:50]]
                sentiment = np.mean(scores) if scores else 0.15
            except Exception: pass

        # 4. Professional Normalization
        s_liquidity = np.clip((liquidity - 6e12) / 2e12, -1, 1) # Net Liquidity (Divisor to 2T)
        s_credit = np.clip((4.5 - hy_spread) / 2.5, -1, 1) # Credit Spreads
        s_conditions = np.clip(-nfci / 0.8, -1, 1) # Financial Conditions
        s_growth = np.clip(cg_momentum / 0.15, -1, 1) # Copper/Gold Momentum (Loosened to 15%)
        s_rotation = np.clip(rotation_raw / 0.15, -1, 1) # Risk appetite (Loosened to 15%)
        s_sentiment = np.clip(sentiment / 0.5, -1, 1)

        # Institutional Weighting
        composite = (s_liquidity * 0.25) + (s_credit * 0.20) + (s_conditions * 0.15) + \
                    (s_growth * 0.15) + (s_rotation * 0.15) + (s_sentiment * 0.10)

        result = {
            'composite': float(np.clip(composite, -1, 1)),
            'components': {
                'Liquidity': float(s_liquidity),
                'Credit': float(s_credit),
                'Monetary': float(s_conditions),
                'Growth': float(s_growth),
                'Appetite': float(s_rotation),
                'Sentiment': float(s_sentiment)
            },
            'raw': {
                'fred': {
                    'yield_10y3m': float(yield_10y3m),
                    'real_yield': float(real_yield),
                    'hy_spread': float(hy_spread),
                    'nfci': float(nfci),
                    'stress_index': float(stress_index),
                    'inflation': float(inflation),
                    'fed_funds': float(fed_funds),
                    'net_liquidity': float(liquidity)
                },
                'market': {
                    'momentum': momentum,
                    'momentum_history': momentum_history,
                    'cg_ratio': float(cg_ratio),
                    'cg_momentum': float(cg_momentum) if not np.isnan(cg_momentum) else 0.0,
                    'rotation_raw': float(rotation_raw),
                    'tlt_vol': float(tlt_vol),
                    'correlation': correlation
                }
            }
        }
        self._cache = result
        self._last_calc = now
        return result
