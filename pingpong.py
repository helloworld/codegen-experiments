import openai
from rich.console import Console
from rich.text import Text
from rich.panel import Panel

console = Console()

conversation = []


def completion_step(model="gpt-3.5-turbo", temperature=0.6):
    messages = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": content}
        for i, content in enumerate(conversation)
    ]

    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an AI language model that is acting as a staff software engineer. Your goal is to write software that is well thought out, testable, and ready to ship into production. If the user asks for code to solve a problem, implement what the user is asking for. If the user provided code, collaborate with the user to give a code review and rewrite code to make it better. Feel free to ask questions to gather requirements.",
            },
            *messages,
        ],
        temperature=temperature,
        stream=True,
    )

    collected_messages = []

    for chunk in response:
        chunk_message = chunk["choices"][0]["delta"]
        message = chunk_message.get("content", "")
        collected_messages.append(message)

        console.print(
            message,
            style="blue" if len(conversation) % 2 == 0 else "green",
            end="",
        )

    full_reply_content = "".join(collected_messages)
    conversation.append(full_reply_content)
    console.print("\n\n")


def conversation_loop(initial_prompt: str, iterations: int = 10):
    initial_prompt = initial_prompt.strip()

    console.print(
        Panel(
            Text(initial_prompt, style="bold"),
            title="Initial Prompt",
        )
    )

    conversation.append(initial_prompt)
    for i in range(iterations):
        console.print(f"\nIteration {i + 1}:\n", style="bold")
        completion_step()


initial_prompt = """
Write me a fizz buzz program in Python
"""

conversation_loop(initial_prompt, iterations=10)
