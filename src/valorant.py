import requests
import os
import dotenv
import time

dotenv.load_dotenv()

class RiotAPIClient:
    BASE_URL = "https://api.henrikdev.xyz"

    def __init__(self):
        self.headers = {"Authorization": os.getenv("RIOT_API_KEY")}
        self.session = requests.Session()
    
    def _retry_request(self, url: str, retry: int = 3) -> dict:
        for attempt in range(retry):
            try:
                response = self.session.get(url, headers=self.headers)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt == retry - 1:
                    raise
                else:
                    # 1 minute, 2 minutes, 3 minutes...
                    time.sleep((attempt + 1) * 60)
    
    def get_match_list(self, player_name: str, region: str, tag: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v3/matches/{region}/{player_name}/{tag}"
        response = self._retry_request(url)
        return response

    def get_player_info(self, player_name: str, tag: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v1/account/{player_name}/{tag}"
        response = self._retry_request(url)
        return response.get("data", {})

    def get_mmr_history(self, player_name: str, region: str, tag: str, platform: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v2/mmr-history/{region}/{platform}/{player_name}/{tag}"
        response = self._retry_request(url)
        return response

    def get_rank_carrier(self, player_name: str, region: str, tag: str, platform: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v3/mmr/{region}/{platform}/{player_name}/{tag}"
        response = self._retry_request(url)
        return response

    def get_match_details(self, region: str, match_id: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v4/match/{region}/{match_id}"
        response = self._retry_request(url)
        return response

    def get_stored_matches(self, player_name: str, region: str, tag: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v1/stored-matches/{region}/{player_name}/{tag}"
        response = self._retry_request(url)
        return response

    def get_stored_mmr_history(self, player_name: str, region: str, tag: str, platform: str) -> dict:
        url = f"{self.BASE_URL}/valorant/v2/stored-mmr-history/{region}/{platform}/{player_name}/{tag}"
        response = self._retry_request(url)
        return response