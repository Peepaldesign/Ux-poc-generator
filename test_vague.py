import asyncio
from backend.main import run_workflow, jobs_store
async def test():
    brief = 'A cool app for people to do things online'
    await run_workflow('vague-job', brief)
    state = jobs_store['vague-job']
    print('Orchestrator:', state.orchestrator.status)
    if state.orchestrator.error_message:
        print('Orchestrator Error:', state.orchestrator.error_message)
    print('Frame:', state.frame.status)
    if state.frame.error_message:
        print('Frame Error:', state.frame.error_message)

asyncio.run(test())
