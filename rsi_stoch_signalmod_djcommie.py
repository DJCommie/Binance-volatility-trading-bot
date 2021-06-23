# Available indicators here: https://python-tradingview-ta.readthedocs.io/en/latest/usage.html#retrieving-the-analysis

from tradingview_ta import TA_Handler, Interval, Exchange
# use for environment variables
import os
# use if needed to pass args to external modules
import sys
# used for directory handling
import glob
import time
import threading
import array
import statistics
import numpy as np


from analysis_buffer import AnalysisBuffer

OSC_INDICATORS = ['RSI', 'Stoch.RSI'] # Indicators to use in Oscillator analysis
OSC_THRESHOLD = 2 # Must be less or equal to number of items in OSC_INDICATORS 
MA_INDICATORS = ['EMA10', 'EMA20'] # Indicators to use in Moving averages analysis
MA_THRESHOLD = 2 # Must be less or equal to number of items in MA_INDICATORS 
INTERVAL = Interval.INTERVAL_5_MINUTES #Timeframe for analysis
INTERVAL_IN_MINUTES = 5 # interval in minutes
NUM_CANDLES = 20 # number of candles to be cached in buffer... e.g. the maximum number of candles you want to go back in time for

EXCHANGE = 'BINANCE'
SCREENER = 'CRYPTO'
PAIR_WITH = 'USDT'
TICKERS = 'custsignal.txt' #'signalsample.txt'
TIME_TO_WAIT = 1 # Minutes to wait between analysis
FULL_LOG = False # List analysis result to console

# TODO: check every 1 minute on 5 minute timeframes by keeping a circular buffer array 
global coin_analysis
coin_analysis = {}

def analyze(pairs):
    global last_RSI

    signal_coins = {}
    analysis = {}
    handler = {}
    
    if os.path.exists('signals/custsignalmod.exs'):
        os.remove('signals/custsignalmod.exs')

    for pair in pairs:
        handler[pair] = TA_Handler(
            symbol=pair,
            exchange=EXCHANGE,
            screener=SCREENER,
            interval=INTERVAL,
            timeout= 10)
       
    for pair in pairs:
        try:
            analysis = handler[pair].get_analysis()
        except Exception as e:
            print("Signalsample:")
            print("Exception:")
            print(e)
            print (f'Coin: {pair}')
            print (f'handler: {handler[pair]}')

        oscCheck=0
        maCheck=0
        for indicator in OSC_INDICATORS:
            oscResult = analysis.oscillators ['COMPUTE'][indicator]
            #print(f'Indicator for {indicator} is {oscResult}')
            if analysis.oscillators ['COMPUTE'][indicator] != 'SELL': oscCheck +=1
      	
        for indicator in MA_INDICATORS:
            if analysis.moving_averages ['COMPUTE'][indicator] == 'BUY': maCheck +=1

        if (pair not in coin_analysis):
            print(f'create new analysis buffer for pair {pair}')
            coin_analysis[pair] = AnalysisBuffer(TIME_TO_WAIT, INTERVAL_IN_MINUTES, NUM_CANDLES * 3)

        coin_analysis[pair].put(analysis)
        prev_candle_analysis = coin_analysis[pair].get_prev_candle()
        prev_RSI = -1
        if (prev_candle_analysis is not None):
            prev_RSI = coin_analysis[pair].get_prev_candle().indicators['RSI']

        # Stoch.RSI (25 - 52) & Stoch.RSI.K > Stoch.RSI.D, RSI (49-67), EMA10 > EMA20 > EMA100, Stoch.RSI = BUY, RSI = BUY, EMA10 = EMA20 = BUY
        RSI = float(analysis.indicators['RSI'])
        STOCH_RSI_K = float(analysis.indicators['Stoch.RSI.K'])
        EMA10 = float(analysis.indicators['EMA10'])
        EMA20 = float(analysis.indicators['EMA20'])
        EMA100 = float(analysis.indicators['EMA100'])
        STOCH_K = float(analysis.indicators['Stoch.K'])
        STOCH_D = float(analysis.indicators['Stoch.D'])

        RSI_list = coin_analysis[pair].get_indicator_list('RSI', int(NUM_CANDLES * 3.5))
        action = 'NADA'
        if (RSI_list is not None):
            action = RSI_BB_dispersion(RSI_list[::-1], NUM_CANDLES, RSI)

        if action == 'BUY' and maCheck >= MA_THRESHOLD and EMA10 > EMA20 and (STOCH_K - STOCH_D >= 4.5) and (RSI >= 35 and RSI <= 67):
            signal_coins[pair] = pair
            print(f'\033[92mCustsignalmod: Buy Signal detected on {pair}')
            with open('signals/custsignalmod.exs','a+') as f:
                f.write(pair + '\n')
        
        elif action == 'SELL':
            print(f'buysellcustsignal: Sell Signal detected on {pair}')
            with open('signals/djcommie_rsi_stoch.sell','a+') as f:
                f.write(pair + '\n')


        if FULL_LOG:
            print(f'Custsignalmod:{pair} Oscillators:{oscCheck}/{len(OSC_INDICATORS)} Moving averages:{maCheck}/{len(MA_INDICATORS)}, trading action:{action}')
    
    return signal_coins

def RSI_BB_dispersion(RSI_buffer, for_ma, current_RSI):
    for_rsi = 14
    for_mult = 2
    for_sigma = 0.1

    if RSI_buffer is None:
        return
    #current_RSI = RSI_buffer[for_ma]
    # get the EMA of the 20 RSIs
    basis = calculate_ema(RSI_buffer, for_ma)[-1]
    # get the deviation
    dev = for_mult * statistics.stdev(RSI_buffer[:for_ma])
    upper = basis + dev
    lower = basis - dev
    disp_up = basis + ((upper - lower) * for_sigma)
    disp_down = basis - ((upper - lower) * for_sigma) 
    
    print(f'RSI_BB_dispersion: current_RSI: {current_RSI}, disp_up: {disp_up}, disp_down: {disp_down}')

    if current_RSI >= disp_up:
        print(f'RSI_BB_dispersion: Buy!!')
        return 'BUY'
    elif current_RSI <= disp_down:
        print(f'RSI_BB_dispersion: Sell!')
        return 'SELL'
    else:
        print(f'RSI_BB_dispersion: Do nada') 
        return 'NADA'

def calculate_ema(prices, days, smoothing=2):
    ema = [sum(prices[:days]) / days]
    for price in prices[days:]:
        ema.append((price * (smoothing / (1 + days))) + ema[-1] * (1 - (smoothing / (1 + days))))
    return ema

def do_work():
    signal_coins = {}
    pairs = {}

    pairs=[line.strip() for line in open(TICKERS)]
    for line in open(TICKERS):
        pairs=[line.strip() + PAIR_WITH for line in open(TICKERS)] 
    
    while True:
        if not threading.main_thread().is_alive(): exit()
        print(f'Custsignalmod: Analyzing {len(pairs)} coins')
        signal_coins = analyze(pairs)
        print(f'Custsignalmod: {len(signal_coins)} coins above {OSC_THRESHOLD}/{len(OSC_INDICATORS)} oscillators and {MA_THRESHOLD}/{len(MA_INDICATORS)} moving averages Waiting {TIME_TO_WAIT} minutes for next analysis.')
        time.sleep((TIME_TO_WAIT*60))
