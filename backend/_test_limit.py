from screener import run_stock_screener

result = run_stock_screener('List top 2 stocks under NIFTY 50 stock list')
print('Query:', result['query'])
print('Total matches:', result['total_matches'])
print('Stocks returned:', len(result['stocks']))
print('Top stocks:')
for i, stock in enumerate(result['stocks'][:5]):
    print(f'{i+1}. {stock["ticker"]} ({stock["name"]}): {stock["currency"]}{stock["price"]}')