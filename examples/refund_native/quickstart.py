from __future__ import annotations

import asyncio

from examples.refund_native.suite import build_suite


async def main() -> None:
    result = await build_suite(idempotent=False).run(store_artifacts=False)
    failure = result.failures[0]
    print(failure.status)
    print(failure.violated_invariants)
    print(len([effect for effect in failure.effects if effect.type == "refund.created"]))


if __name__ == "__main__":
    asyncio.run(main())
