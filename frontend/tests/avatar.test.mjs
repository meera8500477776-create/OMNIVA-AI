import assert from "node:assert/strict";
import test from "node:test";
import { AvatarAdapterError, AvatarSession } from "../src/features/ai/adapters/avatar.ts";

function fakeStream() {
  const tracks = [{ stopped: false, stop() { this.stopped = true; } }];
  return { tracks, getTracks() { return tracks; } };
}
function fakeRenderer() {
  return {
    attached: [],
    stops: 0,
    attachAudioStream(stream) { this.attached.push(stream); },
    stop() { this.stops += 1; },
  };
}

test("demo is deterministic simulation and does not call TTS or renderer", async () => {
  const renderer = fakeRenderer();
  let ttsCalls = 0;
  const session = new AvatarSession("s1", "demo", renderer, {
    providerName: "must-not-run",
    async synthesize() { ttsCalls += 1; return fakeStream(); },
  });
  assert.equal(session.start().simulation, true);
  const event = await session.speak("Hello");
  assert.equal(event.type, "tts_started");
  assert.equal(event.simulation, true);
  assert.equal(ttsCalls, 0);
  assert.equal(renderer.attached.length, 0);
  assert.match(event.message, /no audio was generated/);
});

test("live mode reports unavailable TTS", async () => {
  const session = new AvatarSession("s2", "live", fakeRenderer());
  session.start();
  await assert.rejects(session.speak("Hi"), error =>
    error instanceof AvatarAdapterError && error.code === "provider_unavailable");
});

test("live TTS stream drives renderer and end stops tracks", async () => {
  const renderer = fakeRenderer();
  const stream = fakeStream();
  const session = new AvatarSession("s3", "live", renderer, {
    providerName: "test-provider",
    async synthesize() { return stream; },
  });
  session.start();
  const event = await session.speak("Welcome");
  assert.equal(event.type, "lip_sync_started");
  assert.equal(event.simulation, false);
  assert.equal(renderer.attached[0], stream);
  assert.equal(session.events[1].type, "tts_started");
  await session.end();
  assert.equal(stream.tracks[0].stopped, true);
  assert.equal(renderer.stops, 1);
});

test("TTS timeout aborts provider and returns typed error", async () => {
  let signal;
  const session = new AvatarSession("s4", "live", fakeRenderer(), {
    providerName: "slow",
    synthesize(_text, abortSignal) {
      signal = abortSignal;
      return new Promise(() => {});
    },
  }, 50);
  session.start();
  await assert.rejects(session.speak("Hi"), error =>
    error instanceof AvatarAdapterError && error.code === "provider_timeout");
  assert.equal(signal.aborted, true);
  assert.equal(session.events.at(-1).type, "error");
});

test("explicit cancellation aborts TTS and does not report provider success", async () => {
  const session = new AvatarSession("s5", "live", fakeRenderer(), {
    providerName: "cancel-aware",
    synthesize(_text, signal) {
      return new Promise((_resolve, reject) =>
        signal.addEventListener("abort", () => reject(new Error("cancelled by caller")), { once: true }));
    },
  }, 1000);
  session.start();
  const speak = session.speak("Hi");
  await new Promise(resolve => setTimeout(resolve, 5));
  await session.cancel();
  await assert.rejects(speak, error =>
    error instanceof AvatarAdapterError && error.code === "cancelled");
  assert.equal(session.events.some(event => event.type === "lip_sync_started"), false);
});

test("provider failures are sanitized and session end is terminal", async () => {
  const session = new AvatarSession("s6", "live", fakeRenderer(), {
    providerName: "broken",
    async synthesize() { throw new Error("secret token value"); },
  });
  session.start();
  await assert.rejects(session.speak("Hi"), error =>
    error instanceof AvatarAdapterError && error.code === "provider_error" && !error.message.includes("secret"));
  assert.ok(!session.events.at(-1).message.includes("secret"));
  await session.end();
  await assert.rejects(session.speak("again"), error =>
    error instanceof AvatarAdapterError && error.code === "session_state_conflict");
});
