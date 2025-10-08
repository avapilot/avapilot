from langchain_core.tools import tool
import requests
import json

# We will use the public Snowtrace (Avalanche block explorer) API
SNOWTRACE_API_URL = "https://api.snowtrace.io/api"
# Free tier allows up to 2 requests per second and 10,000 calls per day
# Use "placeholder" as the API key for free tier access
SNOWTRACE_API_KEY = "placeholder" 

@tool
def get_dapp_schema(contract_address: str) -> str:
    """
    Fetches the ABI (Application Binary Interface) for a given smart 
    contract address on the Avalanche C-Chain. The ABI defines the
    contract's functions and is its technical schema.
    
    This uses the free tier of Snowtrace API which allows 2 requests/second
    and 10,000 calls per day without requiring a real API key.
    """
    print(f"---TOOL CALLED: get_dapp_schema for address: {contract_address}---")

    params = {
        "module": "contract",
        "action": "getabi",
        "address": contract_address,
        "apikey": SNOWTRACE_API_KEY
    }

    try:
        response = requests.get(SNOWTRACE_API_URL, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()

        if data["status"] == "1":
            # The ABI is returned as a JSON string, so we return that directly
            return data["result"]
        else:
            return f"Error fetching ABI: {data['message']} - {data['result']}"
    except requests.exceptions.RequestException as e:
        return f"Error: Network request failed: {e}"
    except json.JSONDecodeError:
        return "Error: Failed to parse response from block explorer."