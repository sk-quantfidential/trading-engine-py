# Trading Engine System

A sophisticated Python-based trading engine that executes systematic trading strategies with pluggable strategy scripts, comprehensive risk controls, and realistic chaos injection through deliberately misbehaving strategy implementations.

## 🎯 Overview

The Trading Engine System serves as the algorithmic brain of the trading ecosystem, executing quantitative trading strategies across multiple venues and asset classes. Unlike traditional trading systems, it includes a comprehensive chaos engineering framework through deliberately faulty strategy scripts that can simulate real-world algorithmic failures, risk breaches, and operational errors.

### Key Features
- **Pluggable Strategy Architecture**: Hot-swappable Python strategy scripts with isolated execution
- **Multi-Venue Execution**: Simultaneous trading across multiple simulated exchanges
- **Comprehensive Risk Management**: Pre-trade and post-trade risk controls with circuit breakers
- **Portfolio Management**: Real-time position tracking and P&L calculation
- **Strategy Chaos Testing**: Deliberately misbehaving strategies for failure scenario testing
- **Performance Analytics**: Real-time strategy performance monitoring and attribution
- **Backtesting Engine**: Historical strategy validation with realistic market conditions

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                Trading Engine System                    │
├─────────────────────────────────────────────────────────┤
│  Strategy Layer                                         │
│  ├─Strategy Loader (Dynamic script loading)            │
│  ├─Strategy Sandbox (Isolated execution environment)   │
│  ├─Strategy Manager (Lifecycle management)             │
│  └─Chaos Strategy Repository (Misbehaving strategies)  │
├─────────────────────────────────────────────────────────┤
│  Execution Engine                                       │
│  ├─Order Manager (Order lifecycle and routing)         │
│  ├─Venue Manager (Multi-exchange connectivity)         │
│  ├─Position Manager (Real-time position tracking)      │
│  └─Portfolio Manager (P&L and risk aggregation)        │
├─────────────────────────────────────────────────────────┤
│  Risk Management                                        │
│  ├─Pre-Trade Risk (Position limits, notional limits)   │
│  ├─Post-Trade Risk (Drawdown monitoring, VAR)          │
│  ├─Circuit Breakers (Emergency position liquidation)   │
│  └─Risk Dashboard (Real-time risk monitoring)          │
├─────────────────────────────────────────────────────────┤
│  Data & Analytics                                       │
│  ├─Market Data Consumer (Real-time price feeds)        │
│  ├─Performance Calculator (Strategy attribution)       │
│  ├─Backtesting Engine (Historical validation)          │
│  └─Metrics Publisher (Strategy and system metrics)     │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Python 3.13+
- Docker and Docker Compose
- Poetry (for dependency management)

### Development Setup
```bash
# Clone the repository
git clone <repo-url>
cd trading-engine

# Install dependencies with Poetry
poetry install

# Activate virtual environment
poetry shell

# Run tests
make test

# Start development server
make run-dev
```

### Docker Deployment
```bash
# Build container
docker build -t trading-engine .

# Run with docker-compose (recommended)
docker-compose up trading-engine

# Verify health
curl http://localhost:8083/health
```

## 📡 API Reference

### gRPC Services

#### Trading Service
```protobuf
service TradingService {
  rpc StartStrategy(StartStrategyRequest) returns (StrategyResponse);
  rpc StopStrategy(StopStrategyRequest) returns (StrategyResponse);
  rpc GetStrategyStatus(StrategyStatusRequest) returns (StrategyStatus);
  rpc ListActiveStrategies(ListStrategiesRequest) returns (ListStrategiesResponse);
  rpc GetPositions(GetPositionsRequest) returns (PositionsResponse);
  rpc GetPortfolio(GetPortfolioRequest) returns (PortfolioResponse);
}
```

#### Risk Service
```protobuf
service RiskService {
  rpc SetRiskLimits(RiskLimitsRequest) returns (RiskLimitsResponse);
  rpc GetRiskStatus(RiskStatusRequest) returns (RiskStatus);
  rpc ForcePositionClose(ForceCloseRequest) returns (ForceCloseResponse);
  rpc EnableCircuitBreaker(CircuitBreakerRequest) returns (CircuitBreakerResponse);
}
```

### REST Endpoints

#### Production APIs (Risk Monitor & Management)
```
GET    /api/v1/strategies/active
GET    /api/v1/strategies/{strategy_id}/status
GET    /api/v1/positions/current
GET    /api/v1/portfolio/pnl
GET    /api/v1/risk/status
POST   /api/v1/strategies/start
POST   /api/v1/strategies/stop
POST   /api/v1/risk/circuit-breaker
```

#### Management APIs (Strategy Operations)
```
POST   /api/v1/strategies/upload
GET    /api/v1/strategies/available
GET    /api/v1/strategies/{strategy_id}/performance
GET    /api/v1/backtest/results/{backtest_id}
POST   /api/v1/backtest/start
```

#### State Inspection APIs (Development/Audit)
```
GET    /debug/strategy-sandbox/status
GET    /debug/order-queue
GET    /debug/position-calculator
GET    /debug/risk-engine/limits
GET    /metrics (Prometheus format)
```

## 📈 Strategy Architecture

### Strategy Base Class
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class MarketSignal:
    symbol: str
    timestamp: datetime
    signal_strength: float  # -1.0 to 1.0
    confidence: float      # 0.0 to 1.0
    metadata: Dict[str, Any]

class TradingStrategy(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.positions = {}
        self.performance_metrics = {}
    
    @abstractmethod
    def on_market_data(self, price_update: PriceUpdate) -> List[MarketSignal]:
        """Process market data and generate trading signals"""
        pass
    
    @abstractmethod
    def on_order_fill(self, fill: OrderFill) -> None:
        """Handle order execution callbacks"""
        pass
    
    @abstractmethod
    def on_risk_breach(self, breach: RiskBreach) -> None:
        """Handle risk limit violations"""
        pass
    
    def get_strategy_info(self) -> Dict[str, Any]:
        return {
            "name": self.__class__.__name__,
            "version": getattr(self, "VERSION", "1.0.0"),
            "description": self.__doc__,
            "parameters": self.config
        }
```

### Example: Well-Behaved Arbitrage Strategy
```python
class ArbitrageStrategy(TradingStrategy):
    """Cross-exchange arbitrage strategy with risk controls"""
    
    VERSION = "1.2.0"
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.min_spread_bps = config.get("min_spread_bps", 10)
        self.max_position_size = config.get("max_position_size", 1.0)
        self.venues = config.get("venues", ["exchange-1", "exchange-2"])
    
    def on_market_data(self, price_update: PriceUpdate) -> List[MarketSignal]:
        signals = []
        
        # Calculate cross-venue spread
        if len(self.price_cache) >= 2:
            spread_bps = self.calculate_spread_bps(price_update.symbol)
            
            if spread_bps > self.min_spread_bps:
                # Generate buy signal for cheaper venue, sell for expensive
                signals.extend(self.generate_arbitrage_signals(
                    symbol=price_update.symbol,
                    spread_bps=spread_bps
                ))
        
        return signals
    
    def calculate_spread_bps(self, symbol: str) -> float:
        """Calculate spread between venues in basis points"""
        prices = [venue_price for venue_price in self.price_cache[symbol].values()]
        if len(prices) < 2:
            return 0.0
        
        return ((max(prices) - min(prices)) / min(prices)) * 10000
```

## 🎭 Chaos Engineering via Misbehaving Strategies

### Chaos Strategy Repository
Located in `/strategies/chaos/`, these strategies deliberately misbehave to test system resilience:

#### 1. RunawayStrategy - Massive Order Spam
```python
class RunawayStrategy(TradingStrategy):
    """Deliberately sends massive orders to test risk controls"""
    
    def on_market_data(self, price_update: PriceUpdate) -> List[MarketSignal]:
        # Simulate strategy malfunction - send 100 market buy orders
        signals = []
        for _ in range(100):
            signals.append(MarketSignal(
                symbol=price_update.symbol,
                signal_strength=1.0,  # Full position size
                confidence=1.0,
                metadata={"order_type": "market", "chaos_type": "runaway_buying"}
            ))
        return signals
```

#### 2. RiskIgnorantStrategy - Ignores Risk Limits
```python
class RiskIgnorantStrategy(TradingStrategy):
    """Ignores risk limits and position constraints"""
    
    def on_risk_breach(self, breach: RiskBreach) -> None:
        # Deliberately ignore risk breaches and continue trading
        self.logger.info(f"Ignoring risk breach: {breach.breach_type}")
        
        # Generate more signals in opposite direction
        if breach.breach_type == "position_limit":
            self.generate_contrarian_signals()
    
    def generate_contrarian_signals(self):
        """Generate signals that worsen risk exposure"""
        for symbol in self.active_symbols:
            current_position = self.positions.get(symbol, 0)
            # Double down on existing position
            signal_strength = 1.0 if current_position > 0 else -1.0
            # ... generate more of same position type
```

#### 3. VolatilityAmplifierStrategy - Creates Market Impact
```python
class VolatilityAmplifierStrategy(TradingStrategy):
    """Amplifies market volatility through momentum chasing"""
    
    def on_market_data(self, price_update: PriceUpdate) -> List[MarketSignal]:
        # Chase momentum aggressively, amplifying volatility
        price_change = self.calculate_short_term_momentum(price_update)
        
        if abs(price_change) > 0.01:  # 1% move
            # Chase the move with excessive size
            signal_strength = np.sign(price_change) * 2.0  # 200% of normal size
            
            return [MarketSignal(
                symbol=price_update.symbol,
                signal_strength=signal_strength,
                confidence=1.0,
                metadata={"chaos_type": "volatility_amplification"}
            )]
        return []
```

#### 4. CorrelationBreakerStrategy - Breaks Asset Correlations
```python
class CorrelationBreakerStrategy(TradingStrategy):
    """Trades against normal asset correlations"""
    
    def on_market_data(self, price_update: PriceUpdate) -> List[MarketSignal]:
        signals = []
        
        # When BTC goes up, aggressively sell ETH (break normal correlation)
        if price_update.symbol == "BTC-USD" and price_update.change_pct > 0.02:
            signals.append(MarketSignal(
                symbol="ETH-USD",
                signal_strength=-1.0,  # Full short position
                confidence=1.0,
                metadata={"chaos_type": "correlation_breaking"}
            ))
        
        return signals
```

#### 5. SlowLeakStrategy - Gradual Performance Degradation
```python
class SlowLeakStrategy(TradingStrategy):
    """Gradually degrades performance over time"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.trade_count = 0
        self.degradation_rate = config.get("degradation_rate", 0.001)
    
    def on_market_data(self, price_update: PriceUpdate) -> List[MarketSignal]:
        self.trade_count += 1
        
        # Gradually increase bad decision rate
        error_probability = min(0.5, self.trade_count * self.degradation_rate)
        
        if random.random() < error_probability:
            # Make deliberately bad trading decision
            return self.generate_bad_signal(price_update)
        else:
            return self.generate_good_signal(price_update)
```

### Chaos Strategy Configuration
```yaml
# chaos_strategies.yaml
strategies:
  runaway_buying:
    class: "RunawayStrategy"
    trigger_conditions:
      - market_condition: "low_volatility"
        probability: 0.1
        duration_minutes: 5
    
  risk_ignoring:
    class: "RiskIgnorantStrategy"
    trigger_conditions:
      - risk_breach_count: 3
        escalation_factor: 2.0
    
  volatility_amplifier:
    class: "VolatilityAmplifierStrategy"
    parameters:
      momentum_threshold: 0.02
      amplification_factor: 2.0
      max_duration_minutes: 30
```

## 🛡️ Risk Management System

### Pre-Trade Risk Controls
```python
class PreTradeRisk:
    def __init__(self, config: Dict[str, Any]):
        self.position_limits = config["position_limits"]
        self.notional_limits = config["notional_limits"]
        self.concentration_limits = config["concentration_limits"]
    
    def validate_order(self, order: Order) -> RiskCheckResult:
        checks = [
            self.check_position_limit(order),
            self.check_notional_limit(order),
            self.check_concentration_limit(order),
            self.check_strategy_limit(order),
        ]
        
        failed_checks = [check for check in checks if not check.passed]
        
        return RiskCheckResult(
            passed=len(failed_checks) == 0,
            failed_checks=failed_checks,
            risk_score=self.calculate_risk_score(order)
        )
```

### Risk Limit Configuration
```yaml
risk_limits:
  position_limits:
    BTC-USD:
      max_long: 10.0      # Max 10 BTC long
      max_short: -5.0     # Max 5 BTC short
    ETH-USD:
      max_long: 200.0     # Max 200 ETH long
      max_short: -100.0   # Max 100 ETH short
  
  notional_limits:
    per_strategy: 1000000  # $1M max per strategy
    total_portfolio: 5000000  # $5M total exposure
  
  drawdown_limits:
    daily_loss: -100000    # Max $100k daily loss
    strategy_drawdown: -0.15  # Max 15% strategy drawdown
    portfolio_var: 500000  # Max $500k 1-day VAR
  
  circuit_breakers:
    portfolio_loss_pct: -0.10  # Stop all trading at 10% loss
    single_strategy_loss: -50000  # Stop strategy at $50k loss
    rapid_drawdown_rate: -0.05   # Stop if losing 5%+ in 10 minutes
```

### Post-Trade Risk Monitoring
```python
class PostTradeRisk:
    def __init__(self):
        self.risk_monitors = [
            DrawdownMonitor(),
            ConcentrationMonitor(),
            CorrelationMonitor(),
            VARCalculator()
        ]
    
    def monitor_portfolio(self, portfolio: Portfolio) -> List[RiskAlert]:
        alerts = []
        for monitor in self.risk_monitors:
            monitor_alerts = monitor.check(portfolio)
            alerts.extend(monitor_alerts)
        
        return alerts
    
    def trigger_circuit_breaker(self, alert: RiskAlert) -> bool:
        if alert.severity >= AlertSeverity.CRITICAL:
            self.emergency_liquidation()
            return True
        return False
```

## 📊 Performance Analytics

### Strategy Performance Metrics
```python
@dataclass
class StrategyPerformance:
    strategy_name: str
    total_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    avg_trade_pnl: float
    trades_per_day: float
    risk_adjusted_return: float
    
    # Chaos testing metrics
    chaos_recovery_time: Optional[float]
    risk_breach_count: int
    emergency_stops: int
```

### Real-time Performance Dashboard
```python
class PerformanceDashboard:
    def __init__(self):
        self.metrics_calculator = MetricsCalculator()
        self.dashboard_server = DashboardServer()
    
    def update_strategy_metrics(self, strategy_id: str, trades: List[Trade]):
        performance = self.metrics_calculator.calculate_performance(trades)
        
        # Publish to Prometheus
        self.publish_performance_metrics(strategy_id, performance)
        
        # Update real-time dashboard
        self.dashboard_server.update_strategy_panel(strategy_id, performance)
```

## 🧪 Testing Framework

### Strategy Testing
```python
class StrategyTester:
    def __init__(self, strategy_class: Type[TradingStrategy]):
        self.strategy_class = strategy_class
        self.market_simulator = MarketSimulator()
        self.risk_engine = RiskEngine()
    
    def test_strategy_behavior(self, config: Dict[str, Any]) -> TestResult:
        strategy = self.strategy_class(config)
        
        # Test normal conditions
        normal_result = self.run_normal_conditions_test(strategy)
        
        # Test stress conditions
        stress_result = self.run_stress_test(strategy)
        
        # Test chaos scenarios
        chaos_result = self.run_chaos_test(strategy)
        
        return TestResult(
            normal=normal_result,
            stress=stress_result,
            chaos=chaos_result
        )
```

### Chaos Strategy Testing
```bash
# Run chaos strategy test suite
make test-chaos-strategies

# Test specific chaos scenario
python -m pytest tests/chaos/test_runaway_strategy.py -v

# Test risk system response to chaos
python -m pytest tests/risk/test_chaos_recovery.py -v
```

### Backtesting with Chaos Injection
```python
class ChaosBacktester:
    def run_backtest_with_chaos(self, 
                               strategy: TradingStrategy,
                               chaos_events: List[ChaosEvent],
                               start_date: datetime,
                               end_date: datetime) -> BacktestResult:
        
        for timestamp in self.time_range(start_date, end_date):
            # Normal market data processing
            market_data = self.get_market_data(timestamp)
            signals = strategy.on_market_data(market_data)
            
            # Inject chaos events at specified times
            active_chaos = self.get_active_chaos_events(timestamp, chaos_events)
            if active_chaos:
                signals = self.apply_chaos_to_signals(signals, active_chaos)
            
            # Process signals and calculate performance
            self.process_signals(signals, timestamp)
        
        return self.calculate_backtest_results()
```

## 📊 Monitoring & Observability

### Prometheus Metrics
```
# Strategy performance metrics
trading_strategy_pnl{strategy_name, strategy_version}
trading_strategy_trades_total{strategy_name, side="buy|sell"}
trading_strategy_win_rate{strategy_name}
trading_strategy_sharpe_ratio{strategy_name}

# Risk metrics
trading_risk_position_size{symbol, strategy}
trading_risk_drawdown{strategy}
trading_risk_limit_breaches_total{limit_type, strategy}
trading_risk_circuit_breaker_triggered{reason}

# Chaos testing metrics
trading_chaos_strategy_active{chaos_type, strategy}
trading_chaos_recovery_time_seconds{chaos_type, strategy}
trading_chaos_damage_usd{chaos_type, strategy}

# System performance
trading_engine_orders_per_second
trading_engine_strategy_execution_time{strategy}
trading_engine_risk_check_latency{check_type}
```

### Strategy Execution Tracing
```json
{
  "timestamp": "2025-09-16T14:23:45.123Z",
  "level": "info",
  "service": "trading-engine",
  "correlation_id": "strategy-arb-001",
  "event": "signal_generated",
  "strategy_name": "ArbitrageStrategy",
  "strategy_version": "1.2.0",
  "symbol": "BTC-USD",
  "signal_strength": 0.75,
  "confidence": 0.92,
  "market_conditions": {
    "spread_bps": 15.3,
    "volatility": 0.023,
    "volume": 1250000
  },
  "chaos_active": false
}
```

## ⚙️ Configuration

### Environment Variables
```bash
# Core settings
TRADING_ENGINE_PORT=8083
TRADING_ENGINE_GRPC_PORT=50054
TRADING_ENGINE_LOG_LEVEL=info

# Strategy configuration
STRATEGIES_PATH=/app/strategies
ENABLE_CHAOS_STRATEGIES=true
STRATEGY_ISOLATION=sandbox  # sandbox|container|thread

# Risk management
ENABLE_PRE_TRADE_RISK=true
ENABLE_CIRCUIT_BREAKERS=true
RISK_CHECK_TIMEOUT_MS=100
EMERGENCY_LIQUIDATION_ENABLED=true

# Performance
MAX_CONCURRENT_STRATEGIES=10
ORDER_QUEUE_SIZE=10000
METRICS_PUBLISH_INTERVAL_MS=1000
```

### Strategy Configuration
```yaml
# strategies.yaml
default_strategies:
  - name: "arbitrage"
    class: "ArbitrageStrategy"
    enabled: true
    config:
      min_spread_bps: 10
      max_position_size: 1.0
      venues: ["exchange-1", "exchange-2"]
  
chaos_strategies:
  - name: "runaway"
    class: "RunawayStrategy"
    enabled_in_test: true
    trigger_probability: 0.05  # 5% chance per hour
    max_duration_minutes: 10

risk_limits:
  global:
    max_portfolio_value: 10000000
    max_daily_loss: 500000
    max_drawdown: 0.20
  
  per_strategy:
    max_position_notional: 1000000
    max_daily_trades: 1000
    stop_loss_pct: 0.10
```

## 🐳 Docker Configuration

### Dockerfile
```dockerfile
FROM python:3.11-slim as builder

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry export -f requirements.txt --output requirements.txt

FROM python:3.11-slim
RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN pip install -e .

EXPOSE 8080 50051
CMD ["python", "-m", "trading_engine.main"]
```

### Health Checks
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8083/health').raise_for_status()"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

## 🚀 Performance

### Benchmarks
- **Order Processing**: >1,000 orders/second per strategy
- **Signal Generation**: <50ms latency from market data to signal
- **Risk Checks**: <10ms pre-trade risk validation
- **Strategy Execution**: Support for 10+ concurrent strategies

### Resource Usage
- **Memory**: ~200MB base + ~50MB per active strategy
- **CPU**: <50% single core under normal load
- **Network**: <10MB/hour data consumption
- **Disk**: <100MB logs per day

## 🤝 Contributing

### Adding New Strategies
1. Inherit from `TradingStrategy` base class
2. Implement required abstract methods
3. Add comprehensive unit tests
4. Document strategy logic and parameters
5. Test with various market conditions

### Creating Chaos Strategies
1. Create in `/strategies/chaos/` directory
2. Document specific misbehavior and expected system response
3. Include configuration for failure intensity and duration
4. Test system recovery after chaos injection

## 📚 References

- **Strategy Development Guide**: [Link to strategy development documentation]
- **Risk Management Framework**: [Link to risk system specification]
- **Chaos Engineering Best Practices**: [Link to chaos testing guidelines]
- **API Documentation**: [Link to trading engine API specs]

---

**Status**: 🚧 Development Phase  
**Maintainer**: [Your team]  
**Last Updated**: September 2025
