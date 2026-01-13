import yaml
from engine.bot import RemixBot

if __name__ == "__main__":
    with open("config.yaml","r") as f:
        cfg = yaml.safe_load(f)
    bot = RemixBot(cfg)
    metrics = bot.run_backtest()
    if metrics:
        for k,v in metrics.items():
            print(f"{k}: {v}")

