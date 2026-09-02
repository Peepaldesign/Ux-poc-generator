import asyncio
from backend.main import run_workflow, jobs_store
async def test():
    brief = 'A mobile app for manufacturing shop-floor maintenance. Allows technicians to see assets, work orders, log downtime, and track MTTR.'
    await run_workflow('test-job', brief)
    state = jobs_store['test-job']
    print('Orchestrator:', state.orchestrator.status, state.orchestrator.error_message)
    print('Frame:', state.frame.status, state.frame.error_message)
    print('Research:', state.research.status, state.research.error_message)

asyncio.run(test())
