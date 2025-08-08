from config.settings import Settings

settings = Settings()

print(f"✅ API_KEY: {settings.BITFINEX_API_KEY}")
print(f"✅ API_SECRET: {settings.BITFINEX_API_SECRET}")
