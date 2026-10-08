import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ollama import ResponseError

from userbot.config import DEFAULT_SYSTEM_PROMPT_FILE, PROMPTS_DIR, Config
from userbot.llm import FALLBACK_SYSTEM_PROMPT, LLM, LLMError, load_system_prompt

HISTORY = [{"role": "user", "content": "hej"}]


def make_llm(client, tmp_path=None, prompt="You speak for {name}.", **overrides):
    prompt_file = DEFAULT_SYSTEM_PROMPT_FILE
    if tmp_path is not None:
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(prompt)
    config = Config(api_id=1, api_hash="x", llm_system_prompt_file=prompt_file, **overrides)
    return LLM(config, client=client)


def chat_response(content):
    return SimpleNamespace(message=SimpleNamespace(content=content))


def test_reply_sends_system_prompt_with_owner_name(tmp_path):
    client = SimpleNamespace(chat=AsyncMock(return_value=chat_response("ćao")))
    llm = make_llm(client, tmp_path, llm_model="qwen3.5:9b")

    assert asyncio.run(llm.reply("Aleksa", HISTORY)) == "ćao"

    kwargs = client.chat.await_args.kwargs
    assert kwargs["model"] == "qwen3.5:9b"
    assert kwargs["think"] is False
    assert kwargs["messages"] == [{"role": "system", "content": "You speak for Aleksa."}, *HISTORY]


def test_reply_language_adds_reminder_after_history(tmp_path):
    llm = make_llm(SimpleNamespace(), tmp_path, llm_reply_language="English")

    messages = llm.build_messages("Aleksa", HISTORY)

    assert messages[1:-1] == HISTORY
    assert messages[-1]["role"] == "system"
    assert messages[-1]["content"].startswith("Reply in English only")


def test_no_reply_language_adds_no_reminder(tmp_path):
    messages = make_llm(SimpleNamespace(), tmp_path).build_messages("Aleksa", HISTORY)

    assert messages[1:] == HISTORY


def test_reply_strips_thinking_blocks(tmp_path):
    client = SimpleNamespace(chat=AsyncMock(return_value=chat_response("<think>hmm</think>\nćao")))

    assert asyncio.run(make_llm(client, tmp_path).reply("A", HISTORY)) == "ćao"


def test_empty_reply_raises(tmp_path):
    client = SimpleNamespace(chat=AsyncMock(return_value=chat_response("  ")))

    with pytest.raises(LLMError, match="empty"):
        asyncio.run(make_llm(client, tmp_path).reply("A", HISTORY))


def test_timeout_raises(tmp_path):
    async def slow_chat(**kwargs):
        await asyncio.sleep(1)

    llm = make_llm(SimpleNamespace(chat=slow_chat), tmp_path, llm_timeout=0.01)

    with pytest.raises(LLMError, match="No reply"):
        asyncio.run(llm.reply("A", HISTORY))


@pytest.mark.parametrize("error", [ConnectionError("refused"), ResponseError("model crashed", 500)])
def test_request_failures_raise(tmp_path, error):
    client = SimpleNamespace(chat=AsyncMock(side_effect=error))

    with pytest.raises(LLMError, match="Ollama request failed"):
        asyncio.run(make_llm(client, tmp_path).reply("A", HISTORY))


def test_check_reports_ready(tmp_path):
    client = SimpleNamespace(show=AsyncMock())

    assert asyncio.run(make_llm(client, tmp_path).check()) is None


def test_check_reports_missing_model(tmp_path):
    client = SimpleNamespace(show=AsyncMock(side_effect=ResponseError("not found", 404)))

    problem = asyncio.run(make_llm(client, tmp_path, llm_model="qwen3.5:9b").check())
    assert "ollama pull qwen3.5:9b" in problem


def test_check_reports_unreachable_server(tmp_path):
    client = SimpleNamespace(show=AsyncMock(side_effect=ConnectionError("refused")))

    assert "cannot reach Ollama" in asyncio.run(make_llm(client, tmp_path).check())


def test_missing_prompt_file_uses_built_in_default(tmp_path):
    assert load_system_prompt(tmp_path / "nope.txt") == FALLBACK_SYSTEM_PROMPT


@pytest.mark.parametrize("name", ["chat.txt", "busy.txt"])
def test_shipped_prompts_exist_and_use_owner_placeholder(name):
    assert "{name}" in load_system_prompt(PROMPTS_DIR / name)


def test_default_prompt_is_the_conversation_prompt():
    assert DEFAULT_SYSTEM_PROMPT_FILE == PROMPTS_DIR / "chat.txt"
