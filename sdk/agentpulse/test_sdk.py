from agentpulse import tracker
import time

tracker.init(
    api_key='ap__RN2TdOV4yBuzOMg5hmc3UJVIjHR6pD6',
    project_id='2d80e591-375b-42ec-b802-902dc0bc6276'
)

@tracker.trace(session_id='sdk-test-002')
def my_agent(message: str) -> str:
    time.sleep(0.1)
    return f'Response to: {message}'

result = my_agent('Does the SDK work?')
print('Agent returned:', result)
time.sleep(1)
print('Done')