from pydantic import BaseModel


class BasePlayer(BaseModel):
    name: str
    tag: str
    discord_id: int

class LeaderboardPlayer(BasePlayer):
    rank: str
    rr: int
    winrate: float
    games: int
    rank_id: int
    card: str
    avatar: str
    rank_leaderboard: int = 0