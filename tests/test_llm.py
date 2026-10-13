import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ollama import ResponseError

from userbot.config import DEFAULT_PROMPT, Config
from userbot.llm import FALLBACK_SYSTEM_PROMPT, LLM, LLMError, PromptFile, load_system_prompt
from userbot.handoff import HANDOFF_MARKER
from userbot.paths import DEFAULT_PROMPTS_DIR

HISTORY = [{"role": "user", "content": "hej"}]


def make_llm(client, tmp_path=None, prompt="You speak for {name}.", **overrides):
    prompt_file = DEFAULT_PROMPTS_DIR / "chat.txt"
    if tmp_path is not None:
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(prompt)
    overrides.setdefault("llm_system_prompt_file", prompt_file)
    config = Config(api_id=1, api_hash="x", **overrides)
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


def test_shipped_prompt_uses_owner_placeholder_and_handoff_marker():
    prompt = load_system_prompt(DEFAULT_PROMPTS_DIR / "chat.txt")

    assert "{name}" in prompt
    assert HANDOFF_MARKER in prompt


def test_default_prompt_is_the_conversation_prompt():
    assert DEFAULT_PROMPT == "prompts/chat.txt"


def test_prompt_file_is_reloaded_when_it_changes(tmp_path):
    path = tmp_path / "prompt.txt"
    path.write_text("Version one for {name}.")
    llm = make_llm(SimpleNamespace(), llm_system_prompt_file=path)
    assert llm.build_messages("Aleksa", [])[0]["content"] == "Version one for Aleksa."

    path.write_text("Version two, a bit longer, for {name}.")

    assert llm.build_messages("Aleksa", [])[0]["content"] == "Version two, a bit longer, for Aleksa."


def test_prompt_file_that_disappears_falls_back_to_default(tmp_path):
    path = tmp_path / "prompt.txt"
    path.write_text("Mine.")
    prompt = PromptFile(path)
    assert prompt.text == "Mine."

    path.unlink()

    assert prompt.text == FALLBACK_SYSTEM_PROMPT


def test_switching_prompt_file(tmp_path):
    (tmp_path / "busy.txt").write_text("Busy {name}.")
    llm = make_llm(SimpleNamespace(), tmp_path)

    llm.use_prompt_file(tmp_path / "busy.txt")

    assert llm.system_prompt == "Busy {name}."


IMAGE_HISTORY = [{"role": "user", "content": "[sent a photo]", "images": [b"jpeg"]}]


def test_images_are_passed_to_a_vision_model(tmp_path):
    messages = make_llm(SimpleNamespace(), tmp_path).build_messages("A", IMAGE_HISTORY)

    assert messages[1:] == IMAGE_HISTORY


def test_images_are_dropped_when_vision_is_off(tmp_path):
    messages = make_llm(SimpleNamespace(), tmp_path, llm_vision=False).build_messages("A", IMAGE_HISTORY)

    assert messages[1:] == [{"role": "user", "content": "[sent a photo]"}]


def test_check_turns_vision_off_for_text_only_models(tmp_path):
    client = SimpleNamespace(show=AsyncMock(return_value=SimpleNamespace(capabilities=["completion"])))
    llm = make_llm(client, tmp_path)

    assert asyncio.run(llm.check()) is None
    assert llm.vision is False


def test_check_keeps_vision_for_vision_models(tmp_path):
    client = SimpleNamespace(show=AsyncMock(return_value=SimpleNamespace(capabilities=["completion", "vision"])))
    llm = make_llm(client, tmp_path)

    assert asyncio.run(llm.check()) is None
    assert llm.vision is True
