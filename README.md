# BTC/EUR Paper Scalper

DEMO ONLY. Uses public Kraken API. No exchange credentials, no real orders. Starts with EUR 1,000 virtual funds, EMA9/21 crossover, stop loss, take profit and conservative simulated fees. State in SQLite. For persistence on Railway, attach a volume at `/data` and set `DB_PATH=/data/paper.sqlite3`. Otherwise redeployments may reset the demo balance. Never enable real trading without separate review. The strategy has no guaranteed return.
