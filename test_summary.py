from data_engine import MacroEngine
import json

def test_summary():
    engine = MacroEngine()
    # Mock data if API keys are missing or network fails, but let's try real first
    try:
        data = engine.calculate_regime()
        print("Successfully calculated regime.")
        
        if 'summaries' in data:
            print("\nSummaries found:")
            print(json.dumps(data['summaries'], indent=2))
        else:
            print("\nERROR: 'summaries' key missing in result.")
            
    except Exception as e:
        print(f"Error running engine: {e}")

if __name__ == "__main__":
    test_summary()
