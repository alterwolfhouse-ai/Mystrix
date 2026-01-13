import yaml
from datetime import datetime, timedelta
from engine.bot import RemixBot

def main():
    cfg = yaml.safe_load(open('config.yaml','r'))
    cfg['symbols'] = ['ETH/USDT']
    cfg['backtest_end'] = datetime.utcnow().strftime('%Y-%m-%d')
    cfg['backtest_start'] = (datetime.utcnow() - timedelta(days=60)).strftime('%Y-%m-%d')
    cfg['timeframe_hist'] = '3m'
    cfg['use_dxy_filter'] = False
    bot = RemixBot(cfg)
    m = bot.run_backtest()
    print('Metrics:', m)
    if bot.trades:
        print('Last 5 trades:')
        for t in bot.trades[-5:]:
            print(t)

if __name__ == '__main__':
    main()

