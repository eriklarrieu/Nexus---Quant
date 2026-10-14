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
- **Auditoría acordada**: 15 de octubre de 2026, **13:00 America/Santiago**. Comparar ganancias/pérdidas, órdenes, errores y riesgo; si faltan datos, extender la simulación. **Un solo día no prueba rentabilidad ni autoriza operar fondos reales.**

Ambos sistemas consultan precios públicos de Binance, no usan claves API, y no envían órdenes a Binance. Antes de operar con fondos reales habría que validar la estrategia durante un período mucho más largo y autorizar específicamente un sistema de ejecución separado.
