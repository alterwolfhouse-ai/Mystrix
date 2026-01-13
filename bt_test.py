import yaml
from engine.bot import RemixBot
cfg = yaml.safe_load(open('config.yaml','r'))
cfg['symbols']=['BTC/USDT','ETH/USDT']
cfg['backtest_start']='21-04-2025'
cfg['backtest_end']='21-10-2025'
cfg['timeframe_hist']='3m'
cfg['use_dxy_filter']=False
bot = RemixBot(cfg)
try:
    metrics = bot.run_backtest()
    print('OK', metrics)
except Exception as e:
    import traceback
    traceback.print_exc()
