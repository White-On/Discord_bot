from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from playwright.async_api import async_playwright
from schemas import LeaderboardPlayer

def render_html(templates_path: Path, render_path: Path, players: list[LeaderboardPlayer], act: str):
    env = Environment(loader=FileSystemLoader(templates_path))
    template = env.get_template("leaderboard.html")

    for i, player in enumerate(players):
        player.rank_leaderboard = i + 1

    first_player = players[0]
    second_player = players[1] if len(players) > 1 else None
    third_player = players[2] if len(players) > 2 else None

    rest_players = players[3:12] if len(players) > 3 else []

    html_content = template.render(
        act=act,
        first_player=first_player,
        second_player=second_player,
        third_player=third_player,
        rest_players=rest_players
    )
    rendered_file_path = render_path / "leaderboard_render.html"

    with open(rendered_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    return rendered_file_path


async def generate_image(rendered_file_path: Path, size: tuple[int, int] = (1000, 1400)) -> Path:
    screenshot_path = rendered_file_path.parent / "leaderboard.png"
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": size[0], "height": size[1]})

        await page.goto(rendered_file_path.absolute().as_uri())

        await page.wait_for_load_state("networkidle")

        await page.screenshot(path=screenshot_path, full_page=True)
        await browser.close()
    
    return screenshot_path
