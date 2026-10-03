# Guion del video pitch (DEL-04)

**Límite duro: 3:00. Objetivo: 2:50** (10 s de margen para la edición). Narración en español, con un tramo en
portugués dentro de la demo. Ritmo de lectura de referencia: ~150 palabras/min.

- **Demo:** https://frontend-i6dmh3qssa-uc.a.run.app · cliente demo `MX-DEMO-001` · el OTP simulado aparece en
  pantalla (se muestra a propósito: es una sesión de prueba, REQ-11).
- **Quién graba qué (§14, mitigación de DS sobrecargado):** **AG** graba todas las tomas de pantalla de la demo
  (chat, caja de cristal, consola, Langfuse). **DS** graba la voz en off y las tomas de slides, y edita.
  **OPS** revisa el guion y deja una instancia caliente antes de grabar (`MIN_INSTANCES=1`).
- **Cifras:** solo placeholders `{{...}}`, que se reemplazan con los JSON versionados antes de grabar la voz. Si una
  cifra no existe, la frase se dice sin la cifra.

## Guion

| Tiempo | Pantalla / toma | Narración | Graba |
|---|---|---|---|
| 0:00–0:12 | Slide 1 (título S.O.F.I.A.) sobre un cargo "no reconocido" en un estado de cuenta | "Un cliente ve un cargo que no reconoce. Hoy eso es una llamada, una espera y, muchas veces, una disputa que rompe el SLA. Les presentamos a Sofía." | DS |
| 0:12–0:27 | Slide 4: barras por categoría de contacto | "Elegimos un solo workflow con datos: la recepción de disputas. Es `{{results/workflow_justification.json:dispute_share_pct}}` por ciento de las quejas del dataset, y la acción es segura: registrar la disputa, nunca mover dinero." | DS |
| 0:27–0:40 | Demo: pantalla de ingreso, `MX-DEMO-001`, OTP visible, se ingresa | "Primero, autenticación de verdad: un número de cliente solo no basta. Sofía pide un código de un solo uso y liga la sesión a ese cliente." | AG |
| 0:40–1:05 | Demo ES (camino feliz): "Me cobraron algo que no reconozco en [comercio] la semana pasada" → Sofía muestra la transacción → pide confirmación → cliente confirma → número de caso. Caja de cristal abierta a la derecha, las capas se encienden | "Camino normal, en español. Sofía encuentra la transacción en los registros del cliente, la política dice que es elegible y, antes de actuar, pide confirmación explícita. Registra la disputa y la vuelve a leer: solo confirma el número de caso cuando verificó que existe. A la derecha, la caja de cristal: registros de ejecución, no razonamiento del modelo." | AG |
| 1:05–1:22 | Demo PT (camino feliz): selector de idioma en PT, "Quero contestar uma compra que não reconheço" → confirmação → número do caso | (voz, en portugués, 2 frases) "Agora em português: mesma política, mesmas regras, resposta no idioma do cliente." (DS sigue en español) "Las métricas las reportamos por idioma, por separado." | AG |
| 1:22–1:47 | Demo handoff: cargo de monto alto → Sofía explica que lo revisa una persona → corte a la consola del agente humano con la ficha (hechos verificados, acciones, preguntas abiertas, riesgo) | "Ahora un monto alto. Acá Sofía sabe que no debe actuar: la regla de política manda el caso a una persona. El agente humano no recibe un transcript; recibe una ficha con hechos verificados y su fuente, lo que ya se hizo y lo que falta preguntar." | AG |
| 1:47–2:02 | Demo Langfuse: la traza de esa conversación, árbol de spans por capa, tool calls, latencia y costo | "Cada conversación es una traza en Langfuse: un span por capa y por llamada a herramienta, con latencia y costo reales. De ahí salen nuestras métricas de latencia y costo." | AG |
| 2:02–2:22 | Slide 5: diagrama de 7 capas con la frontera de confianza | "La decisión clave: el LLM entiende y redacta, pero no decide. Permisos y elegibilidad viven en la API, fuera del prompt; una inyección no tiene nada que convencer. Y auditamos los datos: el dataset no trae intenciones válidas, así que no fingimos un modelo sobre ellas." | DS |
| 2:22–2:42 | Slide 6: dot plot con intervalos, baseline vs Sofía, ES y PT | "Contra un baseline con las mismas herramientas pero sin capas, Sofía pasa de `{{eval/outputs/ds_stats.json:baseline.all.met01}}` a `{{eval/outputs/ds_stats.json:proposed.all.met01}}` en resolución automática segura, con `{{eval/outputs/ds_stats.json:proposed.all.met04_count}}` resultados inseguros. Somos honestos: el portugués es traducido por nosotros y una muestra chica no prueba riesgo cero." | DS |
| 2:42–2:50 | Slide de cierre: repo + link a la demo | "Sofía funciona, lo medimos, y sabe cuándo no actuar. Todo está en el repo." | DS |

## Verificación de duración

Conteo de palabras de la narración, sin acotaciones entre paréntesis; cada placeholder cuenta como 2 palabras
habladas (una cifra con su unidad):

| Tramo | Duración | Palabras | Tiempo a 150 ppm |
|---|---|---|---|
| 0:00–0:12 | 12 s | 28 | 11.2 s |
| 0:12–0:27 | 15 s | 31 | 12.4 s |
| 0:27–0:40 | 13 s | 26 | 10.4 s |
| 0:40–1:05 | 25 s | 58 | 23.2 s |
| 1:05–1:22 | 17 s | 20 | 8.0 s (+ pausa para leer la confirmación) |
| 1:22–1:47 | 25 s | 47 | 18.8 s |
| 1:47–2:02 | 15 s | 30 | 12.0 s |
| 2:02–2:22 | 20 s | 46 | 18.4 s |
| 2:22–2:42 | 20 s | 43 | 17.2 s |
| 2:42–2:50 | 8 s | 14 | 5.6 s |
| **Total** | **2:50** | **343** | **2:17.2** de voz; el resto son pausas sobre la demo |

Ninguna fila excede su ventana a 150 ppm. Si al grabar alguna toma de demo se alarga (arranque en frío de Cloud
Run, respuesta lenta de Gemini), se corta la espera en edición; **no** se acelera la voz.

## Notas de grabación (AG)

- Grabar con la instancia caliente; resolución 1920×1080, zoom del navegador 110–125 % para que el texto se lea.
- Ensayar el caso de monto alto con una transacción de `MX-DEMO-001` que supere U, para que el handoff salga por
  POL-6 y no por otra regla.
- Tener abierta de antemano la traza de Langfuse de la conversación del handoff (se graba en una toma aparte).
- Si el selector PT exige otra sesión, repetir el ingreso fuera de cámara; no mostrarlo dos veces.
- Grabar cada tramo por separado (10 clips) para editar sin regrabar todo.
