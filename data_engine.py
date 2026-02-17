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

        # Generate Summaries
        summaries = {
            'radar': self._get_radar_summary(
                {'Liquidity': s_liquidity, 'Credit': s_credit, 'Monetary': s_conditions, 
                 'Growth': s_growth, 'Appetite': s_rotation, 'Sentiment': s_sentiment}
            ),
            'plumbing': self._get_plumbing_summary(
                {'hy_spread': hy_spread, 'stress_index': stress_index, 'yield_10y3m': yield_10y3m, 'nfci': nfci},
                {'tlt_vol': tlt_vol}
            ),
            'growth': self._get_growth_summary(cg_momentum, rotation_raw),
            'momentum': self._get_momentum_summary(momentum),
            'correlation': self._get_correlation_summary(correlation)
        }

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
            'summaries': summaries,
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

    def _get_radar_summary(self, components):
        sorted_comps = sorted(components.items(), key=lambda x: x[1], reverse=True)
        dominant = sorted_comps[0]
        weakest = sorted_comps[-1]
        
        conclusion = ""
        dom_name = dominant[0]
        
        if dom_name in ['Liquidity', 'Monetary']:
            conclusion = "Market is heavily liquidity-driven. Systemic plumbing and central bank posture are the primary anchors of the current regime, overriding fundamental growth concerns."
        elif dom_name in ['Appetite', 'Sentiment']:
             conclusion = "Animal spirits are in control. Risk appetite and speculative sentiment are the main engines of price action, reflecting high institutional confidence."
        elif dom_name == 'Growth':
            conclusion = "Fundamentals are leading the charge. Strong economic growth signals are the primary driver, suggesting a healthy expansionary phase."
        elif dom_name == 'Credit':
            conclusion = "Credit markets are providing the tailwind. Tightening spreads and robust financial conditions are supporting broad market stability."

        if weakest[1] < -0.3:
            conclusion += f" However, {weakest[0]} represents a significant point of friction that could challenge the current trend."
            
        return {
            'driver': dom_name.upper(),
            'conclusion': conclusion
        }

    def _get_plumbing_summary(self, fred, market):
        stress_score = (
            (fred['hy_spread'] / 5) * 0.4 +
            ((fred['stress_index'] + 1) / 3) * 0.3 +
            (market['tlt_vol'] / 20) * 0.3
        )
        
        if stress_score > 0.7:
            return {
                'conclusion': "Systemic plumbing is showing critical stress. Elevated credit spreads and high bond volatility suggest institutional liquidity is tightening, creating a high-risk environment for leveraged positions.",
                'status': "CRITICAL",
                'color': "text-terminal-bearish"
            }
        elif stress_score > 0.4:
            return {
                'conclusion': "Systemic tension is rising. Credit markets are pricing in increased risk, and volatility in the rates market is exerting pressure on overall financial stability.",
                'status': "CAUTION",
                'color': "text-yellow-500"
            }
        elif fred['yield_10y3m'] < -0.1:
            return {
                'conclusion': "Monetary structure remains restrictive. The yield curve inversion highlights persistent recessionary signals despite relatively calm credit markets.",
                'status': "RESTRICTIVE",
                'color': "text-terminal-accent"
            }
        elif stress_score < 0.25 and fred['nfci'] < -0.5:
             return {
                'conclusion': "Systemic plumbing is highly accommodative. Low stress markers and loose financial conditions provide a supportive backdrop for risk-asset expansion.",
                'status': "ACCOMMODATIVE",
                'color': "text-terminal-bullish"
            }
        else:
             return {
                'conclusion': "Systemic pulse is currently neutral. Financial conditions are in equilibrium, without immediate signs of liquidity distress or extreme accommodation.",
                'status': "STABLE",
                'color': "text-terminal-accent"
            }

    def _get_growth_summary(self, cg_mom, rotation):
        # Convert to percentage points for logic comparison to match JS (which multiplied by 100)
        # JS Logic: cgMomRaw > 1 (which refers to 1%)
        cg_pct = cg_mom * 100
        rot_pct = rotation * 100
        
        if cg_pct > 1 and rot_pct > 1:
            return {
                'conclusion': "Strong economic acceleration signaling. Expansionary leadership in industrial commodities and high-beta tech sectors suggests a robust cyclical uptrend.",
                'status': "EXPANSION",
                'color': "text-terminal-bullish"
            }
        elif cg_pct < -1 and rot_pct < -1:
            return {
                'conclusion': "Signs of economic cooling or contraction. Defensive rotation and safe-haven demand (Gold) indicate institutional positioning for a growth slowdown or recessionary risk.",
                'status': "CONTRACTION",
                'color': "text-terminal-bearish"
            }
        elif cg_pct > 1 and rot_pct < -1:
             return {
                'conclusion': "Divergent growth signals. While industrial demand (Copper) remains firm, equity markets are rotating defensively. This typically precedes a broader structural transition.",
                'status': "DIVERGING",
                'color': "text-terminal-accent"
            }
        elif cg_pct < -1 and rot_pct > 1:
            return {
                'conclusion': "Liquidity-driven expansion. Weak industrial momentum but strong speculative tech rotation suggests market growth is being fueled more by liquidity than fundamental expansion.",
                'status': "LIQUIDITY-DRIVEN",
                'color': "text-terminal-accent"
            }
        else:
             return {
                'conclusion': "Equilibrium regime. Growth signals are currently balanced without extreme directional bias in leading economic indicators.",
                'status': "NEUTRAL",
                'color': "text-terminal-accent"
            }

    def _get_momentum_summary(self, momentum):
        asset_names = {
            'SPY': 'S&P 500', 'GLD': 'Gold', 'HG=F': 'Copper',
            'DX-Y.NYB': 'US Dollar', 'TLT': 'Long-Term Bonds',
            'XLK': 'Technology', 'XLP': 'Consumer Staples'
        }
        
        sorted_mom = sorted(momentum.items(), key=lambda x: x[1], reverse=True)
        leader = sorted_mom[0]
        laggard = sorted_mom[-1]
        
        positive_count = sum(1 for v in momentum.values() if v > 0)
        breadth = (positive_count / len(momentum)) * 100
        
        leader_key = leader[0]
        leader_name = asset_names.get(leader_key, leader_key)
        laggard_name = asset_names.get(laggard[0], laggard[0])
        
        if leader_key == 'XLK' or (leader_key == 'SPY' and momentum.get('XLK', 0) > 0):
             return {
                'conclusion': "Market exhibiting strong Risk-On expansion. Technology leads the momentum sequence, suggesting high institutional risk appetite and growth-oriented capital allocation.",
                'color': "text-terminal-bullish",
                'breadth': breadth, 'leader': {'name': leader_name, 'val': leader[1]}, 'laggard': {'name': laggard_name, 'val': laggard[1]},
                'leader_color': 'bg-terminal-bullish' if leader[1] > 0 else 'bg-terminal-bearish'
            }
        elif leader_key == 'GLD' or (leader_key == 'TLT' and momentum.get('GLD', 0) > 0):
            return {
                'conclusion': "Defensive rotation detected. Leadership in Gold and Bonds indicates a 'Flight to Quality' regime, often preceding volatility or reflecting macro-uncertainty.",
                'color': "text-terminal-bearish",
                'breadth': breadth, 'leader': {'name': leader_name, 'val': leader[1]}, 'laggard': {'name': laggard_name, 'val': laggard[1]},
                'leader_color': 'bg-terminal-bullish' if leader[1] > 0 else 'bg-terminal-bearish'
            }
        elif leader_key == 'DX-Y.NYB':
             return {
                'conclusion': "Dollar strength is dominating the cross-asset landscape. This typically exerts downward pressure on global liquidity and suggests a 'Cash is King' defensive posture.",
                'color': "text-terminal-bearish",
                'breadth': breadth, 'leader': {'name': leader_name, 'val': leader[1]}, 'laggard': {'name': laggard_name, 'val': laggard[1]},
                'leader_color': 'bg-terminal-bullish' if leader[1] > 0 else 'bg-terminal-bearish'
            }
        elif leader_key == 'HG=F':
             return {
                'conclusion': "Industrial momentum is leading. Strong Copper performance relative to Gold suggests professional expectations of a cyclical economic recovery and industrial expansion.",
                'color': "text-terminal-bullish",
                'breadth': breadth, 'leader': {'name': leader_name, 'val': leader[1]}, 'laggard': {'name': laggard_name, 'val': laggard[1]},
                'leader_color': 'bg-terminal-bullish' if leader[1] > 0 else 'bg-terminal-bearish'
            }
        elif momentum.get('XLP', 0) > momentum.get('XLK', 0) and momentum.get('XLP', 0) > 0:
             return {
                'conclusion': "Late-cycle defensive positioning. Consumer Staples are outperforming Tech, signaling an institutional shift toward stable yield and recession-resistant sectors.",
                'color': "text-terminal-accent",
                'breadth': breadth, 'leader': {'name': leader_name, 'val': leader[1]}, 'laggard': {'name': laggard_name, 'val': laggard[1]},
                'leader_color': 'bg-terminal-bullish' if leader[1] > 0 else 'bg-terminal-bearish'
            }
        else:
             return {
                'conclusion': "Market is in an undecisive structural transition. Momentum is fragmented across asset classes without a clear directional theme or sector leadership.",
                'color': "text-terminal-accent",
                'breadth': breadth, 'leader': {'name': leader_name, 'val': leader[1]}, 'laggard': {'name': laggard_name, 'val': laggard[1]},
                'leader_color': 'bg-terminal-bullish' if leader[1] > 0 else 'bg-terminal-bearish'
            }

    def _get_correlation_summary(self, correlation):
        assets = list(correlation.keys())
        if not assets or 'SPY' not in correlation:
            return {'conclusion': "Insufficient data for correlation analysis."}
            
        pairs = []
        for i, r in enumerate(assets):
            for j, c in enumerate(assets):
                if i < j:
                    pairs.append({'p': [r, c], 'v': correlation[r].get(c, 0)})
        
        if not pairs:
             return {'conclusion': "Insufficient data for correlation analysis."}

        sorted_pairs = sorted(pairs, key=lambda x: x['v'], reverse=True)
        strongest = sorted_pairs[0]
        weakest = sorted_pairs[-1]
        avg_abs_corr = sum(abs(p['v']) for p in pairs) / len(pairs)
        
        if avg_abs_corr > 0.6:
            conclusion = "Strong Systemic Tie-In. High correlation across all asset classes indicates a macro-dominated environment where 'Everything is one trade' (likely Liquidity or Dollar driven)."
        elif avg_abs_corr < 0.3:
            conclusion = "High Market Dispersion. Assets are moving independently, suggesting a stock-picker's market with idiosyncratic sector rotations and low systemic stress."
        else:
            conclusion = "Balanced Structural Alignment. Standard correlation levels suggest normal market functioning without extreme systemic synchronization."
            
        spy_gld = correlation['SPY'].get('GLD', 0)
        if spy_gld < -0.4:
            conclusion += " Notable active hedge between Equities and Gold."
            
        return {
            'conclusion': conclusion,
            'strongest': {'pair': '/'.join(strongest['p']), 'val': strongest['v']},
            'weakest': {'pair': '/'.join(weakest['p']), 'val': weakest['v']},
            'tension': avg_abs_corr * 10
        }
