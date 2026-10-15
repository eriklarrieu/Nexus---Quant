# NEXUS Quant v0.1 — Operaciones virtuales exclusivamente

**ESTE SOFTWARE NO COMPRA, VENDE NI TRANSFIERE CRIPTOMONEDAS REALES.** No acepta ni necesita claves de Binance. Consulta datos de mercado públicos y mantiene una contabilidad virtual de US$20. Las ganancias virtuales **no** son dinero cobrado ni rentabilidad futura.

## Sistema en prueba

- Par observado: BTC/USDT, velas de 1 hora ya cerradas.
- Señal experimental: cruce de medias móviles simples de 12 y 48 velas.
- Capital virtual inicial: US$20; exposición máxima de US$10 por compra virtual.
- Costes supuestos: 0,10% de comisión por lado y 0,03% de deslizamiento por lado; el backtest supone además un spread fijo del 0,05% total. Costes reales pueden ser distintos.
- Bloqueo: cuando el patrimonio virtual estimado llega a US$18 o menos, fuerza una venta simulada y bloquea nuevas compras. No es un límite de pérdida garantizado en mercados reales.
- Sin futuros, deuda ni apalancamiento; sin operaciones de prueba oficiales ni operaciones de dinero real.
- No inventa ganancias. Reporta patrimonio virtual y resultado frente a US$20.

## Pruebas

Requiere Python 3.11 o superior, sin librerías externas.

~~~bash
python -m unittest -v test_quant.py test_backtest.py
python backtest.py --limit 1000
python quant.py
~~~

El backtest utiliza velas históricas de Binance y compara la estrategia con comprar y mantener una exposición similar. **Un backtest no prueba ventaja estadística:** no incluye cotizaciones históricas bid/ask reales, no ha sido validado fuera de muestra ni permite garantizar resultados.

## GitHub Actions: simulación horaria

El flujo [NEXUS Quant - Paper Only](.github/workflows/paper.yml) programa una ejecución por hora y también permite activación manual. Ejecuta pruebas, backtest, lectura de precios y una decisión virtual. Publica los informes como artefactos durante 7 días. Si cambia el estado de la simulación, intenta guardar `state/paper_state.json` mediante un commit automático para conservarlo entre ejecuciones.

Consulta **Actions** y revisa que cada ejecución termine con éxito. Si falla por permisos del bot, revisa *Settings > Actions > General > Workflow permissions*: puede requerir **Read and write permissions**. Si falla la API pública de Binance por red o ubicación, no se realiza ninguna operación virtual nueva. Las tareas cron de GitHub pueden retrasarse o saltarse.

**No usar este workflow para operaciones reales**: GitHub Actions no garantiza tiempos de ejecución, disponibilidad ni control de riesgo aptos para un exchange.

## Criterios antes de considerar fondos reales

1. Recoger suficientes operaciones y días de observación para calcular resultados netos y caídas del capital.
2. Validar con datos fuera de muestra, escenarios adversos, distintos spreads/comisiones y comparación contra comprar y mantener.
3. Comprobar mínimos por orden, restricciones, elegibilidad y método de depósito/retiro desde Chile.
4. Diseñar un ejecutor totalmente separado con límites del lado del exchange, seguridad de secretos y apagado independiente.
5. Obtener autorización específica del titular **después** de revisar pruebas y riesgos.

**Capital real comprometido hoy: US$0. Saldo de US$20 bajo el control del accionista.**

## Comparativa paralela 1h vs 15m (14–15 octubre 2026)

- **1h**: se conserva el flujo original `.github/workflows/paper.yml`, con 12/48 velas (12h/48h de observación) y su cartera virtual `state/paper_state.json`. Sigue ejecutándose una vez por hora.
- **15m**: flujo nuevo `.github/workflows/paper15.yml`, programado aproximadamente a los minutos 09, 24, 39 y 54 de cada hora (UTC); media rápida 48 velas y lenta 192 velas (las mismas ventanas de 12h/48h), cartera virtual separada `state/paper_15m.json` y tope de US$10 por entrada. Las horas de ejecución de GitHub **no son precisas ni garantizadas**.
- **Comparación observacional**: `comparison.py` genera `reports/comparison.json` y `reports/comparison.md` comparando valores marcados a mercado; se ejecuta durante el flujo de 15 minutos. Las dos carteras arrancaron en momentos ligeramente distintos y no representan US$40 de capital real.
- **Historia de referencia**: `compare_history.py` genera `reports/comparison_history.json`; aproxima ventanas retrospectivas de duración equivalente con los mismos supuestos de comisiones, spread y deslizamiento. No es una validación fuera de muestra ni una predicción.
- **Errores observados**: el flujo 15m contabiliza intervalos perdidos como `skipped_intervals`; no inventa ejecuciones retroactivas con cotizaciones imposibles de recuperar. Las órdenes virtuales no equivalen a operaciones reales.
- **Auditoría acordada**: 15 de octubre de 2026, **14:00 America/Santiago**. Comparar ganancias/pérdidas, órdenes, errores y riesgo; si faltan datos, extender la simulación. **Un solo día no prueba rentabilidad ni autoriza operar fondos reales.**

Los tres sistemas consultan precios públicos de Binance, no usan claves API y no envían órdenes a Binance. Antes de operar con fondos reales habría que validar la estrategia durante un período mucho más largo y autorizar específicamente un sistema de ejecución separado.

## Tercera cartera experimental Agile 15m (autorizada 14 de octubre de 2026)

- **Propósito:** estudiar entradas más frecuentes sin alterar los dos experimentos existentes. El aumento de operaciones **no** constituye evidencia de mayor rentabilidad.
- **Código y horario:** `paper15_agile.py` con `.github/workflows/agile15.yml` (programación 4 veces/hora, ejecución real sujeta a retrasos u omisiones de GitHub).
- **Cartera independiente:** `state/paper_15m_agile.json`, US$20 *virtuales* independientes; máximo US$10 por compra. No hay US$60 depositados, ni capital real comprometido.
- **Señales:** medias SMA de 8 y 21 velas de 15 minutos, cruce alcista o recuperación de retroceso. No fuerza órdenes para mostrar movimiento; puede marcar `HOLD` cuando no existe señal.
- **Salidas simuladas:** caída de 1% desde el precio simulado de entrada, subida de 1,5%, pérdida de tendencia o 16 velas desde la entrada, según la primera regla observada. **Los stops no son órdenes del exchange ni están garantizados**. Las salidas se revisan únicamente cuando se ejecuta el workflow.
- **Seguridad experimental:** máximo 4 compras por día UTC, intervalo mínimo de 2 velas tras una salida, circuito de parada aproximado en US$18 de patrimonio virtual; comisión supuesta del 0,1% y deslizamiento supuesto del 0,03% por lado.
- **Auditoría:** cada decisión de vela evaluada, su razón y ciclos omitidos quedan en `signal_events`, con historial acotado a 500 entradas. Las operaciones simuladas y el P&L realizado están en `trades` y `realized_pnl_usd`.
- **Informes:** `reports/agile_latest.json`, `.md`, `reports/agile_three_way.json`, `.md` y `reports/agile_backtest.json` se suben como artefactos de GitHub Actions. La comparación de tres estrategias tiene inicios de observación distintos.
- **Verificaciones:** `python -m unittest -v test_paper15_agile.py test_agile_backtest.py`; `python agile_backtest.py` realiza backtest aproximado con entrada en la siguiente apertura tras una señal de vela cerrada, spread supuesto y costes. No usa futuros ni información de mercado privada.
- **Limitaciones:** los trabajos programados pueden retrasarse o faltar, y el sistema no reconstruye operaciones hipotéticas de los intervalos no ejecutados; puede perder entradas o stops. Un backtest con pérdidas y pocas operaciones prospectivas no justifica operar con fondos reales.

La evaluación de las tres carteras se realizará el **15 de octubre de 2026 a las 14:00 horas de Chile**, sobre datos que efectivamente puedan verificarse.

## Cuarta estrategia: NEXUS Micro 10s (autorizada 15 octubre 2026)

**Estado real:** codigo de proceso WebSocket continuo listo para ejecutar en una maquina propia; flujo de GitHub Actions para una prueba limitada a 55 segundos. **NO hay servidor 24/7 contratado ni operativo.** No se envian ordenes a Binance Spot/Testnet ni se utilizan claves privadas. Cuarta cartera separada de US$20 exclusivamente VIRTUALES, no US$80 depositados. Las tres estrategias originales permanecen sin cambios.

### Datos y velas

- WebSocket publico de Binance: wss://data-stream.binance.vision:443/stream?streams=btcusdt@kline_1s/btcusdt@bookTicker
- Agrupa **diez velas 1s cerradas y consecutivas** para construir una vela de 10 segundos. Si falta un segundo, descarta la vela y registra la omision, sin inventar precios.
- Usa bid/ask de la misma conexion. No ejecuta senales con cotizacion de mas de 3 segundos o spread de mas de 0,08%.
- El estado se guarda atomicamente en state/micro10_state.json, el ultimo informe en reports/micro10_latest.json. Detecta reconexiones, decisiones, fills simulados y velas incompletas. Despues de caidas no reproduce operaciones hipoteticas del pasado.

### Reglas experimentales (rentabilidad NO demostrada)

- SMA6 y SMA18 sobre velas 10s, cruce alcista con momentum minimo del 0,25% sobre 30 segundos.
- Maximo US$10 por compra virtual, 4 compras por dia UTC, 12 velas de enfriamiento despues de vender.
- Stops **simulados**, no ejecutados en exchange: caida del 0,4%, beneficio objetivo del 0,6%, reversion de tendencia o limite temporal de 60 velas.
- Detiene nuevas compras cuando el valor de cartera virtual llega a US$19 o menos o las perdidas realizadas en el dia alcanzan US$0,35. Limites no garantizados: si se corta el flujo, no puede ejecutar un stop.
- Comision supuesta 0,1% por lado y deslizamiento 0,03% por lado, mas spread observado. Ninguna compra se fuerza para generar actividad.
- Al arrancar desde cero requiere aproximadamente 190 segundos para reunir suficiente historial; hasta entonces genera HOLD.

### Instalacion en servidor o equipo constantemente encendido

Python 3.11+:

    python -m pip install -r requirements-micro10.txt
    python -m unittest -v test_micro10.py
    python micro10_run.py --duration-seconds 0

Duracion cero inicia ejecucion hasta que se interrumpa. Requiere maquina/VM siempre encendida, supervision, reinicios automaticos y conexion de red. Si el equipo se apaga, **el bot deja de observar y simular**; no se reponen operaciones omitidas.

### GitHub Actions solo verifica, no aloja un bot continuo

.github/workflows/micro10.yml ejecuta pruebas y, cuando se publica codigo o se activa manualmente, hace una sesion acotada de 55 segundos con el WebSocket de Binance. Reporta cuantas velas 10s completas recibio, sin movimientos reales. Guarda un artefacto nexus-micro10-10s-public-market-evidence. El flujo NO tiene programacion cada 10 segundos ni cada 5 minutos: es imposible garantizar operativa micro en la infraestructura intermitente de GitHub Actions. Antes de afirmar funcionamiento 24/7, hay que desplegarlo en un host continuo y verificarlo.

**Capital real gastado US$0. No hay cuenta de Binance conectada ni ordenes reales o Testnet.**
