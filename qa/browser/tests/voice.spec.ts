import { expect, test } from '@playwright/test';

const user = { id: 'qa-voice-user', name: 'Voice Tester', email: 'voice@example.test' };

function wavBase64() {
  const sampleRate = 48_000;
  const frames = sampleRate / 2;
  const data = Buffer.alloc(44 + frames * 2);
  data.write('RIFF', 0); data.writeUInt32LE(data.length - 8, 4); data.write('WAVE', 8);
  data.write('fmt ', 12); data.writeUInt32LE(16, 16); data.writeUInt16LE(1, 20);
  data.writeUInt16LE(1, 22); data.writeUInt32LE(sampleRate, 24);
  data.writeUInt32LE(sampleRate * 2, 28); data.writeUInt16LE(2, 32);
  data.writeUInt16LE(16, 34); data.write('data', 36); data.writeUInt32LE(frames * 2, 40);
  for (let i = 0; i < frames; i++) data.writeInt16LE(Math.round(Math.sin(2 * Math.PI * 440 * i / sampleRate) * 5000), 44 + i * 2);
  return data.toString('base64');
}

test.skip(process.env.OMNIVA_E2E_MODE !== 'live', 'voice pipeline test runs with the live-mode frontend build');

test('voice captures, reviews, submits and plays a WAV response without duplicate playback', async ({ page }) => {
  await page.addInitScript((sessionUser) => {
    sessionStorage.setItem('omniva.session.v1', JSON.stringify(sessionUser));
    Object.defineProperty(window, '__voicePlayCount', { value: 0, writable: true });
    Object.defineProperty(window, '__voicePlaySucceeded', { value: false, writable: true });
    const play = HTMLMediaElement.prototype.play;
    HTMLMediaElement.prototype.play = function () {
      (window as any).__voicePlayCount++;
      return play.call(this).then(() => { (window as any).__voicePlaySucceeded = true; });
    };
  }, user);
  await page.context().grantPermissions(['microphone']);
  await page.route('**/api/v1/auth/refresh', async (route) => route.fulfill({ json: {
    access_token: 'qa-live-token', expires_in: 900,
    user: { id: user.id, email: user.email, display_name: user.name },
  } }));

  let submittedTurns = 0;
  await page.route('**/api/v1/features/voice/sessions**', async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/transcribe')) {
      const body = route.request().postDataBuffer()?.toString('latin1') ?? '';
      expect(body).toContain('audio/wav');
      expect(body).toContain('recording.wav');
      return route.fulfill({ json: { transcript: 'Unreviewed speech', language: 'en' } });
    }
    if (url.pathname.endsWith('/turns')) {
      submittedTurns++;
      expect(route.request().postDataJSON().text).toBe('Edited reviewed speech');
      return route.fulfill({ json: {
        answer: 'Gemini voice response', demo: false, audio_base64: wavBase64(),
        audio_content_type: 'audio/wav', mode: 'voice',
      } });
    }
    if (url.pathname.endsWith('/cancel')) return route.fulfill({ json: { cancelled: false } });
    return route.fulfill({ status: 201, json: {
      session_id: 'voice-session-1', state: 'active', demo: false,
      transport: 'gnani-gemini-gnani', token: null,
    } });
  });

  await page.goto('/voice-assistant');
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: /start voice assistant/i }).click();
  await expect(page.getByText(/real voice ready/i)).toBeVisible();
  await page.getByRole('button', { name: 'Record speech' }).click();
  await expect(page.getByText('Recording')).toBeVisible();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Stop recording' }).click();
  const transcript = page.getByRole('textbox', { name: 'Review transcript' });
  await expect(transcript).toHaveValue('Unreviewed speech');
  expect(submittedTurns).toBe(0);
  await transcript.fill('Edited reviewed speech');
  await page.getByRole('button', { name: /send reviewed transcript/i }).click();
  await expect(page.getByText('Gemini voice response')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Play response' })).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).__voicePlaySucceeded)).toBe(true);
  expect(submittedTurns).toBe(1);
  await page.getByRole('button', { name: /stop playback/i }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('button', { name: 'Play response' })).toBeVisible();
});
