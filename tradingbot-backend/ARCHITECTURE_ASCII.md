# 🏗️ Genesis Trading Bot - ASCII Arkitekturöversikt

## 📊 Huvudarkitektur

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GENESIS TRADING BOT                                   │
│                              (Backend Core)                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                REST API                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │   /api/v2/      │  │   /api/v2/      │  │   /api/v2/      │                │
│  │   strategy/     │  │   risk/         │  │   orders/       │                │
│  │   regime/       │  │   status/       │  │   place/        │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              CORE SERVICES                                     │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │  SignalService  │  │  RiskManager    │  │  EnhancedAuto   │                │
│  │                 │  │                 │  │  Trader         │                │
│  │  • SignalScore  │  │  • TradingCB    │  │  • Policy-based │                │
│  │  • Confidence   │  │  • RiskGuards   │  │  • SignalScore  │                │
│  │  • Probability  │  │  • PolicyEngine │  │  • Integration  │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │ TradeConstraints│  │ MarketDataFacade│  │ ExchangeClient  │                │
│  │                 │  │                 │  │                 │                │
│  │  • Time/Slots   │  │  • WS-first     │  │  • Signing      │                │
│  │  • TradeCounter │  │  • REST fallback│  │  • Nonce mgmt   │                │
│  │  • TradingWindow│  │  • CandleCache  │  │  • Auth headers │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                          │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │  WebSocket      │  │  REST API       │  │  Indicators     │                │
│  │  Pool           │  │  (Bitfinex)     │  │                 │                │
│  │                 │  │                 │  │  • Regime       │                │
│  │  • Real-time    │  │  • Fallback     │  │  • ADX/EMA      │                │
│  │  • Subscriptions│  │  • Auth         │  │  • RSI/ATR      │                │
│  │  • Reconnect    │  │  • Rate limit   │  │  • Prob Model   │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            INFRASTRUCTURE                                      │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                │
│  │  Rate Limiter   │  │  Circuit        │  │  Metrics        │                │
│  │                 │  │  Breakers       │  │                 │                │
│  │  • Token Bucket │  │                 │  │  • Prometheus   │                │
│  │  • Semaphores   │  │  • TransportCB  │  │  • Latency      │                │
│  │  • Endpoint     │  │  • TradingCB    │  │  • HTTP Errors  │                │
│  │    specific     │  │  • Auto-recovery│  │  • Performance  │                │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🔄 Dataflöde

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Market    │───▶│   Signal    │───▶│   Risk      │───▶│   Trading   │
│   Data      │    │   Service   │    │   Manager   │    │   Execution │
│             │    │             │    │             │    │             │
│ • WS-first  │    │ • SignalScore│    │ • Policy    │    │ • Orders    │
│ • REST      │    │ • Confidence │    │ • Guards    │    │ • Position  │
│ • Cache     │    │ • Probability│    │ • Circuit   │    │ • Sizing    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Indicators │    │  Enhanced   │    │  Trade      │    │  Exchange   │
│             │    │  AutoTrader │    │  Constraints│    │  Client     │
│ • Regime    │    │             │    │             │    │             │
│ • ADX/EMA   │    │ • Policy    │    │ • Time      │    │ • Signing   │
│ • RSI/ATR   │    │ • SignalScore│    │ • Limits    │    │ • Nonce     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 🛡️ Circuit Breaker Arkitektur

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           CIRCUIT BREAKERS                                     │
│                                                                                 │
│  ┌─────────────────────────────────┐  ┌─────────────────────────────────┐      │
│  │     TransportCircuitBreaker     │  │     TradingCircuitBreaker       │      │
│  │                                 │  │                                 │      │
│  │  • Nätverk/HTTP (429/5xx)       │  │  • Handelspaus med orsak/TTL    │      │
│  │  • Per endpoint                  │  │  • Risk-baserad                │      │
│  │  • Auto-recovery                 │  │  • Policy-driven               │      │
│  │  • Rate limiting                 │  │  • Status endpoint             │      │
│  └─────────────────────────────────┘  └─────────────────────────────────┘      │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                        AdvancedRateLimiter                             │    │
│  │                                                                         │    │
│  │  • Token Bucket per endpoint-typ                                       │    │
│  │  • Semaphores för concurrency                                          │    │
│  │  • Context manager + decorators                                        │    │
│  │  • has_capacity() för snabb check                                      │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 📈 Signal Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Market    │───▶│  Indicators │───▶│   Signal    │───▶│  Enhanced   │
│   Data      │    │             │    │   Service   │    │  AutoTrader │
│             │    │             │    │             │    │             │
│ • Ticker    │    │ • Regime    │    │ • SignalScore│    │ • Policy    │
│ • Candles   │    │ • ADX       │    │ • Confidence │    │ • Execution │
│ • Orderbook │    │ • EMA       │    │ • Probability│    │ • Sizing    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Cache     │    │   Prob      │    │   Features  │    │   Risk      │
│             │    │   Model     │    │             │    │   Manager   │
│ • CandleCache│    │             │    │ • ADX value │    │             │
│ • TickerCache│    │ • ML-based  │    │ • EMA value │    │ • Guards    │
│ • Debounce  │    │ • Hybrid    │    │ • Regime    │    │ • Policy    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 🔧 Service Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE DEPENDENCIES                                  │
│                                                                                 │
│  EnhancedAutoTrader                                                             │
│  ├── SignalGeneratorService                                                     │
│  ├── TradingIntegrationService                                                  │
│  ├── RealtimeStrategyService                                                    │
│  └── PerformanceTracker                                                         │
│                                                                                 │
│  SignalGeneratorService                                                         │
│  ├── MarketDataFacade                                                           │
│  ├── SignalService                                                              │
│  └── ProbModel                                                                  │
│                                                                                 │
│  MarketDataFacade                                                               │
│  ├── WSFirstDataService                                                         │
│  ├── BitfinexDataService                                                        │
│  └── CandleCache                                                                │
│                                                                                 │
│  RiskManager                                                                    │
│  ├── RiskPolicyEngine                                                           │
│  ├── TradeConstraintsService                                                    │
│  ├── RiskGuards                                                                 │
│  └── PerformanceTracker                                                         │
│                                                                                 │
│  TradeConstraintsService                                                        │
│  ├── TradeCounterService                                                        │
│  └── TradingWindowService                                                       │
│                                                                                 │
│  ExchangeClient                                                                 │
│  ├── NonceManager                                                               │
│  └── Settings                                                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 📊 Observability Stack

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           OBSERVABILITY                                         │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │    Metrics      │  │    Logging      │  │    Status       │                  │
│  │                 │  │                 │  │                 │                  │
│  │  • Prometheus   │  │  • Structured   │  │  • REST         │                  │
│  │  • Latency      │  │  • JSON         │  │  • Real-time    │                  │
│  │  • HTTP Errors  │  │  • Levels       │  │  • Circuit      │                  │
│  │  • Performance  │  │  • Context      │  │  • Health       │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
│                                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                  │
│  │    Circuit      │  │    Rate         │  │    Market       │                  │
│  │    Breaker      │  │    Limiter      │  │    Data         │                  │
│  │                 │  │                 │  │                 │                  │
│  │  • TransportCB  │  │  • Token Bucket │  │  • WS Stats     │                  │
│  │  • TradingCB    │  │  • Semaphores   │  │  • Cache Hits   │                  │
│  │  • Status       │  │  • Endpoint     │  │  • Fallbacks    │                  │
│  │  • Recovery     │  │  • Concurrency  │  │  • Latency      │                  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## 🎯 Nyckelprinciper

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ARKITEKTURPRINCIPER                                   │
│                                                                                 │
│  ✅ INGEN DUBLETTLOGIK                                                         │ 
│     • Signering/nonce endast i ExchangeClient                                   │
│     • WS-first/fallback endast i MarketDataFacade                               │
│     • Tid/antal/slots endast i TradeConstraintsService                          │
│                                                                                 │
│  ✅ TYDLIG NAMNSEPARATION                                                       │
│     • TransportCircuitBreaker (nät/HTTP)                                       │
│     • TradingCircuitBreaker (handel)                                           │
│                                                                                 │
│  ✅ ENHETLIG DATAFLÖDE                                                          │
│     • SignalScore som enda payload                                             │
│     • Policy-driven beslut                                                     │
│     • Centraliserad konfiguration                                              │
│                                                                                 │
│  ✅ OBSERVABILITY-FIRST                                                        │
│     • Fullständig mätning                                                      │
│     • Transparent status                                                       │
│     • Real-time monitoring                                                     │
│                                                                                 │
│  ✅ FAIL-SAFE DESIGN                                                           │
│     • Circuit breakers                                                          │
│     • Risk guards                                                               │
│     • Graceful degradation                                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

_Skapad: 2025-09-08_
_Syfte: ASCII-översikt av Genesis Trading Bot arkitektur_
