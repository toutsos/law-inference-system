import httpx

from greek_law.config import Settings


def probe_ollama() -> None:
    settings = Settings()
    base_url = settings.ollama_base_url
    model = settings.ollama_model
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant.",
        },
        {
            "role": "user",
            "content": "Hello, Ollama!",
        },
    ]
    response = httpx.post(
        f"{base_url}/api/chat",
        json={
            "model": model,
            "stream": False,
            "messages": messages,
        },
        timeout=settings.request_timeout,
    )
    # Check if the request was successful otherwise raise an exception
    response.raise_for_status()

    data = response.json()
    print(f"Response: {data['message']['content']}")
    duration_seconds = data["total_duration"] / 1_000_000_000
    print(f"Total Duration: {duration_seconds:.2f} seconds")
    print(f"Done Reason: {data['done_reason']}")
    print(f"Prompt Eval Count: {data['prompt_eval_count']}")
    print(f"Eval Count: {data['eval_count']}")
    eval_duration_seconds = data["eval_duration"] / 1_000_000_000
    print(f"Eval Duration: {eval_duration_seconds:.2f} seconds")
    print(f"Eval Rate: {data['eval_count'] / data['eval_duration'] * 1e9}")


if __name__ == "__main__":
    probe_ollama()
