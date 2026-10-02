"""Simulador de clientes: ejecuta conversaciones turn-by-turn contra el sistema (SIM, §9.5, §11)."""

import logging
from collections.abc import Iterable

from sofia_agent.runner import Harness, arun_conversation
from sofia_contracts.common import SystemVersion
from sofia_contracts.eval_case import ConversationResult, EvalCase

logger = logging.getLogger("sofia_eval.simulator")


class ClientSimulator:
    def __init__(self, system_version: SystemVersion = "proposed") -> None:
        self.system_version = system_version

    async def run_case(self, case: EvalCase, harness: Harness | None = None) -> ConversationResult:
        logger.info("Iniciando caso %s [%s] level=%d", case.case_id, self.system_version, case.level)
        result = await arun_conversation(case, self.system_version, harness=harness)
        logger.info(
            "Finalizado caso %s route=%s expected=%s latency=%dms",
            case.case_id,
            result.route_final,
            case.expected_route,
            result.latency_ms,
        )
        return result

    async def run_batch(
        self,
        cases: Iterable[EvalCase],
        harness: Harness | None = None,
    ) -> list[ConversationResult]:
        results: list[ConversationResult] = []
        for case in cases:
            results.append(await self.run_case(case, harness=harness))
        return results
