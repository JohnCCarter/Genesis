from config.settings import Settings

settings = Settings()

print(f"API_KEY status: {'SET' if settings.BITFINEX_API_KEY else 'MISSING'}")
print(f"API_SECRET status: {'SET' if settings.BITFINEX_API_SECRET else 'MISSING'}")
