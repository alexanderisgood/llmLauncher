# oMLX summary reasoning override

On September 11, a Pi session hit oMLX's prefill admission ceiling at
118,813 prompt tokens. The engine remained alive. Both recovery summaries
then reached 4,096 output tokens with `finish_reason=length`, so Pi correctly
refused to save an incomplete checkpoint.

The relay already sent `chat_template_kwargs.enable_thinking=false` for Pi's
exact native summarization system prompt. However, the generated oMLX model
settings listed `enable_thinking` and `reasoning_effort` in `forced_ct_kwargs`.
oMLX's `merge_chat_template_request_kwargs` ignores request overrides for
those keys. The summary therefore inherited xhigh thinking and its 16,384-token
budget despite having only 4,096 tokens for the entire response.

Normal launcher sessions now keep the selected reasoning settings as engine
defaults without forcing those template keys. The authenticated session relay
still removes client reasoning overrides before forwarding ordinary requests;
only its existing native Pi summary policy supplies the override. Ordinary
coding retains the selected reasoning level and budget. Direct engine
measurements keep forced settings because they do not use that relay.

The running session can receive the same change through oMLX's authenticated
model-settings API by setting `forced_ct_kwargs` to an empty list. This does
not require unloading the model. Context, KV precision, response allowance,
memory admission guards, and the summary's existing length/failure validation
remain unchanged. A truncated summary must never be relabelled as complete.

Live recovery on September 11 completed both native split-turn summaries with
`finish_reason=stop`: 14,411 input / 1,495 output tokens, then 79,405 input /
1,705 output tokens. Pi persisted the checkpoint at 08:26:48 UTC with
`tokensBefore=118795`. The second pass reclaimed allocator buffers under
memory pressure without aborting. The launcher was then restarted on the
updated source and reopened the same saved session with its paused follow-up
intact, xhigh / 16,384-token thinking budget, Q8 KV and 158,240 context.
Validation used the real failed conversation and a syntax check; no benchmark
or synthetic model task was run.
