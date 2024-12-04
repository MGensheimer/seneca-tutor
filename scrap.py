import anthropic
anthropic_client = anthropic.Anthropic()

MODEL_NAME = 'claude-3-5-sonnet-latest'
messages = [{"role": "user", "content": 'test1'}, {"role": "user", "content": 'test2'}]
response = anthropic_client.messages.create(
            model=MODEL_NAME,
            max_tokens=8192,
            messages=messages
        )