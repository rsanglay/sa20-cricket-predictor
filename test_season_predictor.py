#!/usr/bin/env python3
"""Test script for season predictor endpoint."""
import requests
import json
import sys
from typing import Dict, Any

API_BASE_URL = "http://localhost:8002/api/v1"

def test_season_predictor(num_simulations: int = 100) -> Dict[str, Any]:
    """Test the season predictor endpoint."""
    url = f"{API_BASE_URL}/predictions/season"
    
    payload = {
        "num_simulations": num_simulations,
        "custom_xis": None
    }
    
    print(f"Testing season predictor with {num_simulations} simulations...")
    print(f"POST {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, timeout=300)  # 5 minute timeout for large simulations
        response.raise_for_status()
        
        result = response.json()
        
        print("✅ Season predictor test PASSED!")
        print()
        print("Response Summary:")
        print(f"  - Number of simulations: {result.get('num_simulations', 'N/A')}")
        print(f"  - Number of teams in standings: {len(result.get('predicted_standings', []))}")
        print()
        
        if result.get('predicted_standings'):
            print("Predicted Standings:")
            for i, standing in enumerate(result['predicted_standings'][:5], 1):
                print(f"  {i}. Team ID {standing['team_id']}: "
                      f"Avg Position: {standing['avg_position']:.2f}, "
                      f"Avg Points: {standing['avg_points']:.2f}, "
                      f"Playoff Probability: {standing['playoff_probability']:.1f}%, "
                      f"Championship Probability: {standing['championship_probability']:.1f}%")
            print()
        
        if result.get('orange_cap'):
            oc = result['orange_cap']
            print(f"Orange Cap (Top Run Scorer):")
            print(f"  - Player: {oc.get('player_name', 'N/A')}")
            print(f"  - Team: {oc.get('team_name', 'N/A')}")
            print(f"  - Avg Runs: {oc.get('avg_runs', 0):.1f}")
            print()
        
        if result.get('purple_cap'):
            pc = result['purple_cap']
            print(f"Purple Cap (Top Wicket Taker):")
            print(f"  - Player: {pc.get('player_name', 'N/A')}")
            print(f"  - Team: {pc.get('team_name', 'N/A')}")
            print(f"  - Avg Wickets: {pc.get('avg_wickets', 0):.1f}")
            print()
        
        if result.get('champion'):
            champ = result['champion']
            print(f"Predicted Champion:")
            print(f"  - Team: {champ.get('team_name', 'N/A')}")
            print(f"  - Win Probability: {champ.get('win_probability', 0):.1f}%")
            print()
        
        if result.get('mvp'):
            mvp = result['mvp']
            print(f"MVP (Most Valuable Player):")
            print(f"  - Player: {mvp.get('player_name', 'N/A')}")
            print(f"  - Team: {mvp.get('team_name', 'N/A')}")
            print(f"  - Avg Runs: {mvp.get('avg_runs', 0):.1f}, Avg Wickets: {mvp.get('avg_wickets', 0):.1f}")
            print()
        
        if result.get('team_of_tournament'):
            print(f"Team of the Tournament ({len(result['team_of_tournament'])} players):")
            for player in result['team_of_tournament'][:5]:
                print(f"  - {player.get('player_name', 'N/A')} ({player.get('role', 'N/A')}) - "
                      f"{player.get('team_name', 'N/A')}")
            print()
        
        return {
            "success": True,
            "result": result
        }
        
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to backend server.")
        print(f"   Make sure the backend is running at {API_BASE_URL}")
        print("   Start it with: cd backend && uvicorn app.main:app --reload")
        return {"success": False, "error": "Connection error"}
    
    except requests.exceptions.Timeout:
        print("❌ ERROR: Request timed out. The simulation may be taking too long.")
        return {"success": False, "error": "Timeout"}
    
    except requests.exceptions.HTTPError as e:
        print(f"❌ ERROR: HTTP {e.response.status_code}")
        try:
            error_detail = e.response.json()
            print(f"   Details: {json.dumps(error_detail, indent=2)}")
        except:
            print(f"   Response: {e.response.text}")
        return {"success": False, "error": f"HTTP {e.response.status_code}"}
    
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    num_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    result = test_season_predictor(num_sims)
    sys.exit(0 if result.get("success") else 1)

