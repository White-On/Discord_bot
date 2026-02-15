from pydantic import BaseModel


class BasePlayer(BaseModel):
    name: str
    tag: str
    discord_id: str

class LeaderboardPlayer(BasePlayer):
    rank: int
    region: str
    name: str
    rank_name: str
    rr: int
    winrate: float
    games: int
    rank_id: int
    card: str
    avatar: str
    rank_leaderboard: int = 0