from data_engine import MacroEngine
import json

def test_engine():
    print("Testing Advanced Macro Engine...")
    engine = MacroEngine()
    try:
        data = engine.calculate_regime()
        print("\n--- COMPOSITE SCORE ---")
        print(f"Score: {data['composite']:.4f}")
        
        print("\n--- COMPONENTS ---")
        for k, v in data['components'].items():
            print(f"{k}: {v:.4f}")
            
        print("\n--- RAW DATA PREVIEW ---")
        fred = data['raw']['fred']
        print(f"Net Liquidity: ${fred['net_liquidity']:,.0f}")
        print(f"Yield 10Y-3M: {fred['yield_10y3m']:.2f}")
        print(f"Real Yield: {fred['real_yield']:.2f}")
        print(f"Rotation: {data['raw']['market']['rotation']:.4f}")
        
        print("\nVerification Successful.")
    except Exception as e:
        print(f"\nVerification Failed: {e}")

if __name__ == "__main__":
    test_engine()
