# Pi Hub transport deadlock — 7 September 2026

## Observed failure

The saved Mario session stopped producing events at 18:23:38 UTC. At 18:39 UTC,
MTPLX answered health/snapshot requests in 10–20 ms with no active generation,
while the launcher still held an active request and its status endpoint timed
out. Native process samples showed the controller blocked in `os_write`, console
reader and status threads waiting on a lock, and the relay blocked in `sendall`.
Pi also failed to respond to SIGTERM. Terminating that specific Pi process
released the controller and relay; its saved JSONL was retained.

The controller wrote PTY input synchronously while holding `AgentConsole.lock`.
A full input buffer therefore prevented the reader from acquiring the lock to
drain Pi output. Pi could in turn block on that output and stop consuming input.
Periodic status checks could enter this cycle without a user sending a message.
This was a launcher I/O deadlock, separate from the earlier repetitive-reasoning
failure. There was no active engine request or memory-pressure failure in this
snapshot.

## Source changes

- `agent_console_transport.py` owns nonblocking PTY I/O. Senders enqueue complete
  commands; the existing reader advances both directions. Readiness waits hold
  neither the console state lock nor the transport lock. Partial writes retain
  byte order, including UTF-8 and JSONL boundaries. The queue is limited to
  256 KiB / 128 messages, rejects overflow explicitly, and coalesces pending
  state probes. Close clears pending input and wakes the reader within its
  50 ms readiness interval. No additional writer thread or unbounded queue.
- `relay_transport.py` owns interruptible HTTP connections. Cancellation shuts
  down both the retained upstream socket and the downstream client socket.
  This also works after `HTTPConnection` has detached a `Connection: close`
  response into a file object. Final close remains with the request handler.
  A client that stops reading cannot block a relay write for more than 30 seconds;
  this does not shorten the engine's 900-second prefill/read allowance.
- The launcher and request scheduler use these small transport modules instead
  of embedding blocking writes and cross-thread close logic in state management.
  Both modules participate in controller source-freshness checks.

## Verification

The real-PTY regression failed on the original code with “A full Pi input buffer
blocked the sender” and passed after the change. Further tests verify intact
120 KB duplex transfers, command ordering, queue bounds, redundant-probe
coalescing, and close while idle. Real socket tests verify blocked downstream
write cancellation, next-request admission, detached upstream response
cancellation, and cancellation before connection establishment.

The controller suite passed 301 tests with 10 optional skips. All seven new
transport tests and four existing steering tests passed. Installed Pi 0.85.1
passed its generated-model integration covering streaming, follow-up order,
abort, limit/disconnection recovery and retained transcript. No user tools ran
in those fixtures.

After restarting the controller and restoring the same saved Qwopus session,
the controller reported current source. Eight concurrent status checks returned
in 7–21 ms during generation. Native telemetry showed a 31,219-token prompt,
479 fresh output tokens and 0.1 seconds since progress; Safari showed live
reasoning, approximately 26 generation tokens/s and 376 prompt tokens/s.
The route retained xhigh thinking, 131,072 context, MTP depth 2, scoped reasoning
history and the verified `iogpu.wired_limit_mb=40960` setting.

These checks do not claim a model decode speedup or prove the Mario task is
complete. Model, thinking, sampling, context and the 40 GiB memory ceiling are
independent of these transport changes.
