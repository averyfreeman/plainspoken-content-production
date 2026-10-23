"""Plainspoken: English editing and a portable voice research skill.

The checker is offline. Automatic edits use only Hermes's configured model.
Corpus research and interviews belong to the skill, outside the reply hook.
"""
from pathlib import Path
from . import schemas, tools
from .hook import Guard


def register(ctx):
    guard = Guard(ctx)
    ctx.register_tool(name="writing_check", toolset="writing", schema=schemas.WRITING_CHECK,
                      handler=tools.writing_check, emoji="🖋")
    ctx.register_hook("transform_llm_output", guard.on_output)
    ctx.register_hook("post_tool_call", guard.on_tool_result)
    ctx.register_command("writing-check", tools.make_command(guard),
                         description="Check English writing (no arguments: last local answer's report)",
                         args_hint="[surface] <text>")
    ctx.register_skill("natural-writing", Path(__file__).parent / "skills" / "natural-writing" / "SKILL.md")
