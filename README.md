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
